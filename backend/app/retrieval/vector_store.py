"""Persistent ChromaDB vector store manager supporting course/document metadata filtering and re-indexing."""
from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any
import uuid

from app.core.config import settings
from app.core.logging import logger


@dataclass
class VectorRecord:
    """Stored vector record inside a persistent ChromaDB collection."""

    id: str
    embedding: list[float]
    document: str
    metadata: dict[str, Any]


@dataclass
class VectorSearchMatch:
    """A matched chunk returned from vector similarity search."""

    chroma_vector_id: str
    chunk_text: str
    similarity_score: float
    metadata: dict[str, Any]


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity in [-1.0, 1.0] between two vectors."""
    if len(vec_a) != len(vec_b) or not vec_a:
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a <= 1e-12 or norm_b <= 1e-12:
        return 0.0
    return max(-1.0, min(1.0, dot / (norm_a * norm_b)))


def _matches_where_filter(metadata: dict[str, Any], where: dict[str, Any] | None) -> bool:
    """Evaluate ChromaDB-style metadata filter dictionary against record metadata."""
    if not where:
        return True
    if "$and" in where:
        return all(_matches_where_filter(metadata, clause) for clause in where["$and"])
    for key, expected in where.items():
        actual = metadata.get(key)
        if isinstance(expected, dict) and "$eq" in expected:
            if str(actual) != str(expected["$eq"]):
                return False
        else:
            if str(actual) != str(expected):
                return False
    return True


class PersistentChromaStore:
    """Persistent ChromaDB vector store with automatic native ChromaDB client or JSON-backed Chroma persistence.

    Stores chunk embeddings, chunk text, and ownership metadata (course_id, document_id, user_id,
    page_start, page_end, section_title, chunk_index).
    """

    def __init__(
        self,
        persist_dir: Path | str | None = None,
        collection_name: str | None = None,
    ) -> None:
        self.persist_dir = Path(persist_dir or settings.CHROMA_PERSIST_DIR)
        self.collection_name = collection_name or settings.CHROMA_COLLECTION_NAME
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._storage_file = self.persist_dir / f"{self.collection_name}.chroma.json"
        self._native_collection: Any = None
        self._records: dict[str, VectorRecord] = {}
        self._init_backend()

    def _init_backend(self) -> None:
        """Initialize native chromadb.PersistentClient if installed, else load persistent disk store."""
        try:
            import chromadb  # type: ignore[import-not-found]

            client = chromadb.PersistentClient(path=str(self.persist_dir))
            self._native_collection = client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(
                f"Initialized native ChromaDB collection '{self.collection_name}' at '{self.persist_dir}'"
            )
        except Exception:
            self._native_collection = None
            self._load_from_disk()

    def _load_from_disk(self) -> None:
        if not self._storage_file.is_file():
            self._records = {}
            return
        try:
            raw_data = json.loads(self._storage_file.read_text(encoding="utf-8"))
            loaded: dict[str, VectorRecord] = {}
            for item_id, payload in raw_data.items():
                loaded[item_id] = VectorRecord(
                    id=item_id,
                    embedding=list(payload["embedding"]),
                    document=str(payload["document"]),
                    metadata=dict(payload["metadata"]),
                )
            self._records = loaded
        except Exception as exc:
            logger.warning(f"Failed to load Chroma store file '{self._storage_file}': {exc}")
            self._records = {}

    def _save_to_disk(self) -> None:
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        serializable = {
            rec_id: {
                "embedding": rec.embedding,
                "document": rec.document,
                "metadata": rec.metadata,
            }
            for rec_id, rec in self._records.items()
        }
        tmp_file = self._storage_file.with_suffix(".tmp")
        tmp_file.write_text(json.dumps(serializable), encoding="utf-8")
        tmp_file.replace(self._storage_file)

    def has_vector_id(self, chroma_vector_id: str) -> bool:
        """Return True if a vector with the given ID already exists in the collection."""
        if self._native_collection is not None:
            res = self._native_collection.get(ids=[chroma_vector_id])
            return bool(res and res.get("ids"))
        return chroma_vector_id in self._records

    def count(self, where: dict[str, Any] | None = None) -> int:
        """Count stored vectors matching the optional metadata filter."""
        if self._native_collection is not None:
            if not where:
                return int(self._native_collection.count())
            res = self._native_collection.get(where=where)
            return len(res.get("ids", []))
        if not where:
            return len(self._records)
        return sum(
            1 for rec in self._records.values() if _matches_where_filter(rec.metadata, where)
        )

    def upsert_chunks(
        self,
        *,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        """Upsert a batch of chunk embeddings, texts, and metadata into ChromaDB."""
        if not ids:
            return

        sanitized_metadatas: list[dict[str, Any]] = []
        for meta in metadatas:
            clean_meta: dict[str, Any] = {}
            for k, v in meta.items():
                if v is None:
                    clean_meta[k] = ""
                elif isinstance(v, (str, int, float, bool)):
                    clean_meta[k] = v
                else:
                    clean_meta[k] = str(v)
            sanitized_metadatas.append(clean_meta)

        if self._native_collection is not None:
            self._native_collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=sanitized_metadatas,
            )
            return

        for rec_id, emb, doc_text, meta in zip(
            ids, embeddings, documents, sanitized_metadatas
        ):
            self._records[rec_id] = VectorRecord(
                id=rec_id,
                embedding=emb,
                document=doc_text,
                metadata=meta,
            )
        self._save_to_disk()

    def query_similar(
        self,
        *,
        query_embedding: list[float],
        course_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
        document_id: uuid.UUID | None = None,
        top_k: int = 5,
    ) -> list[VectorSearchMatch]:
        """Query top-k similar chunks strictly scoped to `course_id` (and optional `user_id` / `document_id`)."""
        clauses: list[dict[str, Any]] = [{"course_id": str(course_id)}]
        if user_id is not None:
            clauses.append({"user_id": str(user_id)})
        if document_id is not None:
            clauses.append({"document_id": str(document_id)})

        where_filter: dict[str, Any] = (
            clauses[0] if len(clauses) == 1 else {"$and": clauses}
        )

        if self._native_collection is not None:
            matching_count = self.count(where=where_filter)
            if matching_count == 0:
                return []
            n_results = min(top_k, matching_count)
            res = self._native_collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )
            ids_list = (res.get("ids") or [[]])[0]
            docs_list = (res.get("documents") or [[]])[0]
            metas_list = (res.get("metadatas") or [[]])[0]
            dists_list = (res.get("distances") or [[]])[0]

            matches: list[VectorSearchMatch] = []
            for vid, doc_text, meta, dist in zip(
                ids_list, docs_list, metas_list, dists_list
            ):
                # Chroma cosine distance = 1 - cosine_similarity
                sim = max(0.0, min(1.0, 1.0 - float(dist)))
                matches.append(
                    VectorSearchMatch(
                        chroma_vector_id=str(vid),
                        chunk_text=str(doc_text),
                        similarity_score=round(sim, 4),
                        metadata=dict(meta or {}),
                    )
                )
            matches.sort(key=lambda m: m.similarity_score, reverse=True)
            return matches

        # Built-in persistent Chroma store query
        scored: list[VectorSearchMatch] = []
        for rec in self._records.values():
            if not _matches_where_filter(rec.metadata, where_filter):
                continue
            sim = max(0.0, cosine_similarity(query_embedding, rec.embedding))
            scored.append(
                VectorSearchMatch(
                    chroma_vector_id=rec.id,
                    chunk_text=rec.document,
                    similarity_score=round(sim, 4),
                    metadata=dict(rec.metadata),
                )
            )

        scored.sort(key=lambda m: m.similarity_score, reverse=True)
        return scored[:top_k]

    def delete_by_document(self, document_id: uuid.UUID) -> int:
        """Delete all chunk vectors associated with a document_id."""
        doc_str = str(document_id)
        if self._native_collection is not None:
            existing = self._native_collection.get(where={"document_id": doc_str})
            ids = existing.get("ids", [])
            if ids:
                self._native_collection.delete(ids=ids)
            return len(ids)

        to_delete = [
            rec_id
            for rec_id, rec in self._records.items()
            if str(rec.metadata.get("document_id")) == doc_str
        ]
        for rec_id in to_delete:
            del self._records[rec_id]
        if to_delete:
            self._save_to_disk()
        return len(to_delete)

    def delete_by_course(self, course_id: uuid.UUID) -> int:
        """Delete all chunk vectors associated with a course_id."""
        course_str = str(course_id)
        if self._native_collection is not None:
            existing = self._native_collection.get(where={"course_id": course_str})
            ids = existing.get("ids", [])
            if ids:
                self._native_collection.delete(ids=ids)
            return len(ids)

        to_delete = [
            rec_id
            for rec_id, rec in self._records.items()
            if str(rec.metadata.get("course_id")) == course_str
        ]
        for rec_id in to_delete:
            del self._records[rec_id]
        if to_delete:
            self._save_to_disk()
        return len(to_delete)


_default_vector_store: PersistentChromaStore | None = None


def get_vector_store() -> PersistentChromaStore:
    """Return the active PersistentChromaStore instance."""
    global _default_vector_store
    if _default_vector_store is None or (
        str(_default_vector_store.persist_dir) != str(Path(settings.CHROMA_PERSIST_DIR))
        or _default_vector_store.collection_name != settings.CHROMA_COLLECTION_NAME
    ):
        _default_vector_store = PersistentChromaStore(
            persist_dir=settings.CHROMA_PERSIST_DIR,
            collection_name=settings.CHROMA_COLLECTION_NAME,
        )
    return _default_vector_store
