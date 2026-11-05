"""Semantic similarity retrieval and hybrid source ranking service."""
from dataclasses import dataclass
import re
import time
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    AppException,
    EntityNotFoundError,
    OwnershipViolationError,
    VectorStoreUnavailableError,
)
from app.core.logging import logger
from app.models.course import ChunkMetadata, Course, Document
from app.retrieval.embeddings import STOPWORDS, EmbeddingService, _stem_token, get_embedding_service
from app.retrieval.vector_store import (
    PersistentChromaStore,
    VectorSearchMatch,
    cosine_similarity,
    get_vector_store,
)


@dataclass
class RetrievedPassage:
    """A ranked passage retrieved for a student's question with full source metadata."""

    chroma_vector_id: str
    document_id: uuid.UUID
    course_id: uuid.UUID
    filename: str
    chunk_index: int
    page_start: int
    page_end: int
    section_title: str | None
    chunk_text: str
    semantic_similarity: float
    lexical_overlap: float
    relevance_score: float


@dataclass
class RetrievalOutcome:
    """Result of executing semantic retrieval and source ranking for a course question."""

    passages: list[RetrievedPassage]
    top_k_requested: int
    total_candidates_indexed: int
    retrieval_latency_ms: float
    embedding_model: str
    max_relevance_score: float


def _compute_lexical_overlap(query: str, passage_text: str, section_title: str | None) -> float:
    """Compute normalized query keyword stem coverage in the candidate passage."""
    q_words = [
        _stem_token(w)
        for w in re.sub(r"[^a-z0-9\s]", " ", query.lower()).split()
        if len(w) > 1 and w not in STOPWORDS
    ]
    if not q_words:
        return 0.0

    p_words = {
        _stem_token(w)
        for w in re.sub(r"[^a-z0-9\s]", " ", passage_text.lower()).split()
        if len(w) > 1
    }
    matched = sum(1 for qw in q_words if qw in p_words)
    base_coverage = matched / len(q_words)

    if section_title:
        title_words = {
            _stem_token(w)
            for w in re.sub(r"[^a-z0-9\s]", " ", section_title.lower()).split()
            if len(w) > 1
        }
        if any(qw in title_words for qw in q_words):
            base_coverage = min(1.0, base_coverage + 0.15)

    return round(base_coverage, 4)


class RetrievalService:
    """Manages indexing of course chunks into ChromaDB and semantic retrieval with source ranking."""

    def __init__(
        self,
        db: Session,
        embedding_service: EmbeddingService | None = None,
        vector_store: PersistentChromaStore | None = None,
    ) -> None:
        self.db = db
        self.embedding_service = embedding_service or get_embedding_service()
        self.vector_store = vector_store or get_vector_store()

    def _verify_course_ownership(
        self, course_id: uuid.UUID, requesting_user_id: uuid.UUID | None = None
    ) -> Course:
        course = self.db.get(Course, course_id)
        if course is None:
            raise EntityNotFoundError("Course", course_id)
        if requesting_user_id is not None and course.user_id != requesting_user_id:
            raise OwnershipViolationError(
                "You do not have permission to access or query this course."
            )
        return course

    def index_document_chunks(
        self,
        document: Document,
        chunks: list[ChunkMetadata],
        *,
        force_reindex: bool = False,
    ) -> int:
        """Generate embeddings and upsert document chunks into ChromaDB.

        Skips chunks that are already present in the vector store unless force_reindex=True.
        """
        if not chunks:
            return 0

        if force_reindex:
            self.vector_store.delete_by_document(document.id)
            chunks_to_index = chunks
        else:
            chunks_to_index = [
                c
                for c in chunks
                if not self.vector_store.has_vector_id(c.chroma_vector_id)
            ]

        if not chunks_to_index:
            return 0

        texts = [c.chunk_text for c in chunks_to_index]
        embeddings = self.embedding_service.embed_batch(texts)

        ids = [c.chroma_vector_id for c in chunks_to_index]
        metadatas = [
            {
                "course_id": str(document.course_id),
                "document_id": str(document.id),
                "user_id": str(document.user_id),
                "filename": document.filename,
                "chunk_index": int(c.chunk_index),
                "page_start": int(c.page_start or c.page_number or 1),
                "page_end": int(c.page_end or c.page_start or c.page_number or 1),
                "section_title": c.section_title or "",
            }
            for c in chunks_to_index
        ]

        self.vector_store.upsert_chunks(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )
        return len(chunks_to_index)

    def reindex_course(
        self, course_id: uuid.UUID, requesting_user_id: uuid.UUID | None = None
    ) -> int:
        """Clear and rebuild all ChromaDB chunk vectors for a course from persisted ChunkMetadata."""
        course = self._verify_course_ownership(course_id, requesting_user_id)
        try:
            self.vector_store.delete_by_course(course.id)
        except AppException:
            raise
        except Exception as exc:
            raise VectorStoreUnavailableError(
                f"ChromaDB vector store unavailable during reindex: {exc}"
            ) from exc

        docs_stmt = select(Document).where(
            Document.course_id == course.id, Document.status == "READY"
        )
        ready_docs = list(self.db.scalars(docs_stmt).all())
        total_indexed = 0
        for doc in ready_docs:
            chunks_stmt = (
                select(ChunkMetadata)
                .where(ChunkMetadata.document_id == doc.id)
                .order_by(ChunkMetadata.chunk_index.asc())
            )
            chunks = list(self.db.scalars(chunks_stmt).all())
            try:
                total_indexed += self.index_document_chunks(
                    doc, chunks, force_reindex=False
                )
            except AppException:
                raise
            except Exception as exc:
                raise VectorStoreUnavailableError(
                    f"ChromaDB vector store unavailable during indexing: {exc}"
                ) from exc
        return total_indexed

    def _fallback_relational_matches(
        self,
        course: Course,
        query_embedding: list[float],
        top_k: int,
    ) -> tuple[int, list[VectorSearchMatch]]:
        """Fallback to relational ChunkMetadata when ChromaDB is degraded or unavailable."""
        stmt = (
            select(ChunkMetadata, Document)
            .join(Document, ChunkMetadata.document_id == Document.id)
            .where(
                ChunkMetadata.course_id == course.id,
                Document.status == "READY",
            )
            .order_by(ChunkMetadata.chunk_index.asc())
        )
        rows = list(self.db.execute(stmt).all())
        if not rows:
            return 0, []
        texts = [c.chunk_text for c, _ in rows]
        embeddings = self.embedding_service.embed_batch(texts)
        matches: list[VectorSearchMatch] = []
        for (chunk, doc), emb in zip(rows, embeddings):
            sim = max(0.0, round(cosine_similarity(query_embedding, emb), 4))
            matches.append(
                VectorSearchMatch(
                    chroma_vector_id=chunk.chroma_vector_id,
                    chunk_text=chunk.chunk_text,
                    similarity_score=sim,
                    metadata={
                        "course_id": str(course.id),
                        "document_id": str(doc.id),
                        "user_id": str(course.user_id),
                        "filename": doc.filename,
                        "chunk_index": int(chunk.chunk_index),
                        "page_start": int(chunk.page_start or chunk.page_number or 1),
                        "page_end": int(chunk.page_end or chunk.page_start or chunk.page_number or 1),
                        "section_title": chunk.section_title or "",
                    },
                )
            )
        matches.sort(key=lambda m: m.similarity_score, reverse=True)
        return len(rows), matches[:top_k]

    def retrieve(
        self,
        *,
        course_id: uuid.UUID,
        question: str,
        requesting_user_id: uuid.UUID | None = None,
        top_k: int | None = None,
        min_score: float | None = None,
    ) -> RetrievalOutcome:
        """Retrieve and rank top-k relevant passages strictly scoped to the target course and user."""
        start_time = time.perf_counter()
        course = self._verify_course_ownership(course_id, requesting_user_id)

        resolved_top_k = top_k if top_k is not None else settings.RETRIEVAL_TOP_K
        resolved_min_score = (
            min_score if min_score is not None else settings.RETRIEVAL_MIN_SCORE
        )

        query_embedding = self.embedding_service.embed_text(question)

        try:
            course_vector_count = self.vector_store.count(
                where={"course_id": str(course.id)}
            )
            if course_vector_count == 0:
                course_vector_count = self.reindex_course(course.id, course.user_id)

            if course_vector_count == 0:
                latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
                return RetrievalOutcome(
                    passages=[],
                    top_k_requested=resolved_top_k,
                    total_candidates_indexed=0,
                    retrieval_latency_ms=latency_ms,
                    embedding_model=self.embedding_service.model_name,
                    max_relevance_score=0.0,
                )

            candidate_pool_size = min(max(resolved_top_k * 3, 10), course_vector_count)
            raw_matches = self.vector_store.query_similar(
                query_embedding=query_embedding,
                course_id=course.id,
                user_id=course.user_id,
                top_k=candidate_pool_size,
            )
        except VectorStoreUnavailableError as exc:
            logger.warning(f"ChromaDB unavailable for course '{course.id}', attempting DB fallback: {exc.detail}")
            course_vector_count, raw_matches = self._fallback_relational_matches(
                course, query_embedding, max(resolved_top_k * 3, 10)
            )
            if course_vector_count == 0:
                raise
        except Exception as exc:
            logger.warning(f"ChromaDB query error for course '{course.id}', falling back to relational chunks: {exc}")
            course_vector_count, raw_matches = self._fallback_relational_matches(
                course, query_embedding, max(resolved_top_k * 3, 10)
            )
            if course_vector_count == 0:
                raise VectorStoreUnavailableError(
                    f"ChromaDB vector store is unavailable: {exc}"
                ) from exc

        ranked_passages: list[RetrievedPassage] = []
        for match in raw_matches:
            meta = match.metadata
            section_title = str(meta.get("section_title") or "").strip() or None
            lex_score = _compute_lexical_overlap(
                question, match.chunk_text, section_title
            )
            sem_score = match.similarity_score
            # Combined relevance ranking: 65% semantic cosine + 35% lexical term coverage
            combined_score = round(0.65 * sem_score + 0.35 * lex_score, 4)

            if combined_score < resolved_min_score:
                continue

            ranked_passages.append(
                RetrievedPassage(
                    chroma_vector_id=match.chroma_vector_id,
                    document_id=uuid.UUID(str(meta["document_id"])),
                    course_id=uuid.UUID(str(meta["course_id"])),
                    filename=str(meta.get("filename") or "Course_Document.pdf"),
                    chunk_index=int(meta.get("chunk_index", 0)),
                    page_start=int(meta.get("page_start", 1)),
                    page_end=int(meta.get("page_end", 1)),
                    section_title=section_title,
                    chunk_text=match.chunk_text,
                    semantic_similarity=sem_score,
                    lexical_overlap=lex_score,
                    relevance_score=combined_score,
                )
            )

        ranked_passages.sort(
            key=lambda p: (p.relevance_score, p.semantic_similarity),
            reverse=True,
        )
        top_passages = ranked_passages[:resolved_top_k]
        max_score = top_passages[0].relevance_score if top_passages else 0.0
        latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        return RetrievalOutcome(
            passages=top_passages,
            top_k_requested=resolved_top_k,
            total_candidates_indexed=course_vector_count,
            retrieval_latency_ms=latency_ms,
            embedding_model=self.embedding_service.model_name,
            max_relevance_score=max_score,
        )
