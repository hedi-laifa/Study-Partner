"""Service orchestrating PDF validation, secure storage, extraction, chunking, ChromaDB indexing, and deletion."""
from pathlib import Path
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import EntityNotFoundError, OwnershipViolationError
from app.core.logging import logger
from app.ingestion.chunker import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    build_overlapping_chunks,
)
from app.ingestion.extractor import PDFExtractionError, extract_pdf_content
from app.ingestion.validator import validate_pdf_upload
from app.models.course import ChunkMetadata, Course, Document
from app.retrieval.embeddings import EmbeddingService
from app.retrieval.retriever import RetrievalService
from app.retrieval.vector_store import PersistentChromaStore, get_vector_store


class IngestionService:
    """Handles the complete course PDF ingestion lifecycle, vector indexing, and document management."""

    def __init__(
        self,
        db: Session,
        storage_root: Path | None = None,
        embedding_service: EmbeddingService | None = None,
        vector_store: PersistentChromaStore | None = None,
    ) -> None:
        self.db = db
        self.storage_root = storage_root or Path(settings.UPLOAD_STORAGE_DIR)
        self.embedding_service = embedding_service
        self.vector_store = vector_store

    def _get_owned_course(self, course_id: uuid.UUID, user_id: uuid.UUID) -> Course:
        course = self.db.get(Course, course_id)
        if course is None:
            raise EntityNotFoundError("Course", course_id)
        if course.user_id != user_id:
            raise OwnershipViolationError(
                "You do not have permission to access or upload documents to this course."
            )
        return course

    def get_document(
        self, document_id: uuid.UUID, requesting_user_id: uuid.UUID | None = None
    ) -> Document:
        """Fetch a Document by ID and enforce user ownership when requesting_user_id is provided."""
        document = self.db.get(Document, document_id)
        if document is None:
            raise EntityNotFoundError("Document", document_id)
        if requesting_user_id is not None and document.user_id != requesting_user_id:
            raise OwnershipViolationError(
                "You do not have permission to access this document."
            )
        return document

    def list_course_documents(
        self, course_id: uuid.UUID, requesting_user_id: uuid.UUID | None = None
    ) -> list[Document]:
        """List all documents uploaded to a course, enforcing ownership when user_id is given."""
        course = self.db.get(Course, course_id)
        if course is None:
            raise EntityNotFoundError("Course", course_id)
        if requesting_user_id is not None and course.user_id != requesting_user_id:
            raise OwnershipViolationError(
                "You do not have permission to view documents for this course."
            )
        stmt = (
            select(Document)
            .where(Document.course_id == course_id)
            .order_by(Document.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def list_document_chunks(
        self, document_id: uuid.UUID, requesting_user_id: uuid.UUID | None = None
    ) -> list[ChunkMetadata]:
        """Return all persisted ChunkMetadata records for a document ordered by chunk_index."""
        self.get_document(document_id, requesting_user_id=requesting_user_id)
        stmt = (
            select(ChunkMetadata)
            .where(ChunkMetadata.document_id == document_id)
            .order_by(ChunkMetadata.chunk_index.asc())
        )
        return list(self.db.scalars(stmt).all())

    def ingest_pdf(
        self,
        *,
        course_id: uuid.UUID,
        user_id: uuid.UUID,
        filename: str | None,
        content_type: str | None,
        file_bytes: bytes,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> Document:
        """Execute end-to-end PDF ingestion and ChromaDB indexing pipeline.

        Pipeline steps:
        1. Verify course ownership
        2. Validate PDF file type, size, and magic header
        3. Save PDF to secure local storage
        4. Create Document record with status='PROCESSING'
        5. Extract page-aware text, detect empty/low-text pages, normalize paragraphs
        6. Build overlapping chunks and persist ChunkMetadata rows
        7. Generate chunk embeddings and store vectors + metadata in ChromaDB
        8. Update Document status to 'READY' (or 'FAILED' with error_message on extraction failure)
        """
        course = self._get_owned_course(course_id, user_id)

        safe_filename = validate_pdf_upload(
            filename=filename,
            content_type=content_type,
            file_bytes=file_bytes,
            max_size_mb=settings.MAX_UPLOAD_SIZE_MB,
        )

        doc_id = uuid.uuid4()
        course_dir = self.storage_root / str(course.id)
        course_dir.mkdir(parents=True, exist_ok=True)
        stored_path = course_dir / f"{doc_id}_{safe_filename}"
        stored_path.write_bytes(file_bytes)

        document = Document(
            id=doc_id,
            user_id=user_id,
            course_id=course.id,
            filename=safe_filename,
            file_path=str(stored_path),
            file_size_bytes=len(file_bytes),
            mime_type="application/pdf",
            status="PROCESSING",
            extraction_warnings=[],
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)

        try:
            extraction = extract_pdf_content(file_bytes)
            chunk_drafts = build_overlapping_chunks(
                extraction.pages,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )

            created_chunks: list[ChunkMetadata] = []
            for draft in chunk_drafts:
                chunk_row = ChunkMetadata(
                    document_id=document.id,
                    course_id=course.id,
                    chroma_vector_id=f"{document.id}_chunk_{draft.chunk_index}",
                    chunk_index=draft.chunk_index,
                    page_start=draft.page_start,
                    page_end=draft.page_end,
                    page_number=draft.page_start,
                    section_title=draft.section_title,
                    chunk_text=draft.chunk_text,
                    char_count=draft.char_count,
                    metadata_json={
                        "page_start": draft.page_start,
                        "page_end": draft.page_end,
                        "section_title": draft.section_title,
                    },
                )
                self.db.add(chunk_row)
                created_chunks.append(chunk_row)

            document.page_count = extraction.page_count
            document.chunk_count = len(created_chunks)
            document.status = "READY"
            document.extraction_warnings = extraction.warnings
            document.error_message = None
            self.db.commit()
            self.db.refresh(document)

            # Index chunks into ChromaDB
            retrieval_service = RetrievalService(
                self.db,
                embedding_service=self.embedding_service,
                vector_store=self.vector_store,
            )
            retrieval_service.index_document_chunks(
                document, created_chunks, force_reindex=False
            )

            logger.info(
                f"Ingested and indexed document '{document.filename}' ({document.page_count} pages, {document.chunk_count} chunks)"
            )
            return document

        except PDFExtractionError as exc:
            self.db.rollback()
            failed_doc = self.db.get(Document, doc_id)
            if failed_doc is not None:
                failed_doc.status = "FAILED"
                failed_doc.error_message = exc.detail
                self.db.commit()
                self.db.refresh(failed_doc)
            logger.warning(f"PDF extraction failed for '{safe_filename}': {exc.detail}")
            raise exc
        except Exception as exc:
            self.db.rollback()
            failed_doc = self.db.get(Document, doc_id)
            if failed_doc is not None:
                failed_doc.status = "FAILED"
                failed_doc.error_message = f"Unexpected ingestion error: {exc}"
                self.db.commit()
            logger.error(f"Unexpected ingestion failure for '{safe_filename}': {exc}")
            raise PDFExtractionError(
                f"Document processing failed: {exc}",
                error_code="INGESTION_PROCESSING_ERROR",
            ) from exc

    def reindex_document(
        self, document_id: uuid.UUID, requesting_user_id: uuid.UUID | None = None
    ) -> int:
        """Re-generate embeddings and re-index a single document's chunks in ChromaDB."""
        document = self.get_document(document_id, requesting_user_id=requesting_user_id)
        chunks = self.list_document_chunks(
            document_id, requesting_user_id=requesting_user_id
        )
        retrieval_service = RetrievalService(
            self.db,
            embedding_service=self.embedding_service,
            vector_store=self.vector_store,
        )
        return retrieval_service.index_document_chunks(
            document, chunks, force_reindex=True
        )

    def delete_document(
        self, document_id: uuid.UUID, requesting_user_id: uuid.UUID | None = None
    ) -> None:
        """Delete a document, its ChromaDB vectors, its ChunkMetadata rows, and its stored PDF file."""
        document = self.get_document(document_id, requesting_user_id=requesting_user_id)
        file_path = Path(document.file_path)

        # Delete vectors from ChromaDB first
        (self.vector_store or get_vector_store()).delete_by_document(document.id)

        self.db.delete(document)
        self.db.commit()

        try:
            if file_path.is_file():
                file_path.unlink()
        except OSError as exc:
            logger.warning(f"Failed to remove PDF file '{file_path}' from disk: {exc}")
