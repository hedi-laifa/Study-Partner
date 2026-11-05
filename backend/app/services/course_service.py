"""CRUD service for Course, Document, ChunkMetadata, and Concept entities."""
from pathlib import Path
import shutil
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import EntityNotFoundError, OwnershipViolationError
from app.core.logging import logger
from app.models.course import ChunkMetadata, Concept, Course, Document
from app.models.user import User
from app.retrieval.vector_store import get_vector_store
from app.schemas.course import (
    ChunkMetadataCreate,
    ConceptCreate,
    CourseCreate,
    CourseUpdate,
    DocumentCreate,
    DocumentUpdate,
)


class CourseService:
    """Encapsulates Course, Document, ChunkMetadata, and Concept persistence with ownership enforcement."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def _verify_user_exists(self, user_id: uuid.UUID) -> User:
        user = self.db.get(User, user_id)
        if user is None:
            raise EntityNotFoundError("User", user_id)
        return user

    def create_course(self, payload: CourseCreate) -> Course:
        """Create a course owned by the specified user."""
        self._verify_user_exists(payload.user_id)
        course = Course(
            user_id=payload.user_id,
            title=payload.title.strip(),
            code=payload.code.strip() if payload.code else None,
            description=payload.description.strip() if payload.description else None,
        )
        self.db.add(course)
        self.db.commit()
        self.db.refresh(course)
        return course

    def get_course(
        self, course_id: uuid.UUID, requesting_user_id: uuid.UUID | None = None
    ) -> Course:
        """Fetch a course by ID and optionally enforce user ownership."""
        course = self.db.get(Course, course_id)
        if course is None:
            raise EntityNotFoundError("Course", course_id)
        if requesting_user_id is not None and course.user_id != requesting_user_id:
            raise OwnershipViolationError("Course belongs to a different user.")
        return course

    def list_courses_for_user(self, user_id: uuid.UUID) -> list[Course]:
        """List all courses owned by a user ordered by creation timestamp."""
        stmt = (
            select(Course)
            .where(Course.user_id == user_id)
            .order_by(Course.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def update_course(
        self,
        course_id: uuid.UUID,
        payload: CourseUpdate,
        requesting_user_id: uuid.UUID | None = None,
    ) -> Course:
        """Update a course after verifying ownership."""
        course = self.get_course(course_id, requesting_user_id=requesting_user_id)
        if payload.title is not None:
            course.title = payload.title.strip()
        if payload.code is not None:
            course.code = payload.code.strip()
        if payload.description is not None:
            course.description = payload.description
        self.db.commit()
        self.db.refresh(course)
        return course

    def delete_course(
        self, course_id: uuid.UUID, requesting_user_id: uuid.UUID | None = None
    ) -> None:
        """Delete a course, its ChromaDB vectors, its uploaded PDF files on disk, and all child DB records."""
        course = self.get_course(course_id, requesting_user_id=requesting_user_id)
        doc_paths = [Path(doc.file_path) for doc in (course.documents or []) if doc.file_path]

        try:
            get_vector_store().delete_by_course(course.id)
        except Exception as exc:
            logger.warning(f"Failed to delete ChromaDB vectors for course '{course.id}': {exc}")

        self.db.delete(course)
        self.db.commit()

        # Remove stored PDF files and course upload directory
        for file_path in doc_paths:
            try:
                if file_path.is_file():
                    file_path.unlink()
            except OSError as exc:
                logger.warning(f"Failed to remove PDF file '{file_path}' during course deletion: {exc}")

        course_upload_dir = Path(settings.UPLOAD_STORAGE_DIR) / str(course_id)
        try:
            if course_upload_dir.is_dir():
                shutil.rmtree(course_upload_dir, ignore_errors=True)
        except OSError:
            pass

    def create_document(self, payload: DocumentCreate) -> Document:
        """Create a document within a course after verifying ownership."""
        course = self.get_course(payload.course_id, requesting_user_id=payload.user_id)
        document = Document(
            user_id=course.user_id,
            course_id=course.id,
            filename=payload.filename,
            file_path=payload.file_path,
            file_size_bytes=payload.file_size_bytes,
            mime_type=payload.mime_type,
            page_count=payload.page_count,
            status="UPLOADED",
            extraction_warnings=[],
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def get_document(
        self, document_id: uuid.UUID, requesting_user_id: uuid.UUID | None = None
    ) -> Document:
        """Fetch a document by ID and optionally enforce user ownership."""
        document = self.db.get(Document, document_id)
        if document is None:
            raise EntityNotFoundError("Document", document_id)
        if requesting_user_id is not None and document.user_id != requesting_user_id:
            raise OwnershipViolationError("Document belongs to a different user.")
        return document

    def update_document(
        self,
        document_id: uuid.UUID,
        payload: DocumentUpdate,
        requesting_user_id: uuid.UUID | None = None,
    ) -> Document:
        """Update document ingestion status and metadata."""
        document = self.get_document(document_id, requesting_user_id=requesting_user_id)
        if payload.page_count is not None:
            document.page_count = payload.page_count
        if payload.chunk_count is not None:
            document.chunk_count = payload.chunk_count
        if payload.status is not None:
            document.status = payload.status
        if payload.error_message is not None:
            document.error_message = payload.error_message
        if payload.extraction_warnings is not None:
            document.extraction_warnings = payload.extraction_warnings
        self.db.commit()
        self.db.refresh(document)
        return document

    def create_chunk_metadata(self, payload: ChunkMetadataCreate) -> ChunkMetadata:
        """Persist relational metadata for a ChromaDB chunk."""
        document = self.get_document(payload.document_id)
        if document.course_id != payload.course_id:
            raise OwnershipViolationError(
                "Document does not belong to the specified course."
            )
        chunk = ChunkMetadata(
            document_id=payload.document_id,
            course_id=payload.course_id,
            chroma_vector_id=payload.chroma_vector_id
            or f"{payload.document_id}_chunk_{payload.chunk_index}",
            chunk_index=payload.chunk_index,
            page_start=payload.page_start,
            page_end=payload.page_end,
            page_number=payload.page_number,
            section_title=payload.section_title,
            chunk_text=payload.chunk_text or payload.text_content or "",
            char_count=payload.char_count or len(payload.chunk_text or ""),
            metadata_json=payload.metadata_json,
        )
        self.db.add(chunk)
        self.db.commit()
        self.db.refresh(chunk)
        return chunk

    def create_concept(self, payload: ConceptCreate) -> Concept:
        """Create an extracted academic Concept within a Course."""
        self.get_course(payload.course_id)
        concept = Concept(
            course_id=payload.course_id,
            source_document_id=payload.source_document_id,
            title=payload.title.strip(),
            summary=payload.summary,
            difficulty=payload.difficulty,
            display_order=payload.display_order,
            source_pages=payload.source_pages,
        )
        self.db.add(concept)
        self.db.commit()
        self.db.refresh(concept)
        return concept

    def list_concepts_for_course(self, course_id: uuid.UUID) -> list[Concept]:
        """List all concepts for a course ordered by display_order."""
        stmt = (
            select(Concept)
            .where(Concept.course_id == course_id)
            .order_by(Concept.display_order.asc(), Concept.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())
