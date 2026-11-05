"""Course, Document, ChunkMetadata, and Concept SQLAlchemy ORM models."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
import uuid

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.db.session import Base
from app.models.base import JSONVariant, TimestampMixin, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.models.learning import ConceptProgress, LearningEvidence, RevisionTask
    from app.models.session import Activity, StudySession
    from app.models.user import User


class Course(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Represents a university course workspace owned by a student User."""

    __tablename__ = "courses"
    __table_args__ = (
        Index("ix_courses_user_id", "user_id"),
        Index("ix_courses_user_title", "user_id", "title"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    owner: Mapped[User] = relationship("User", back_populates="courses")
    documents: Mapped[list[Document]] = relationship(
        "Document",
        back_populates="course",
        cascade="all, delete-orphan",
    )
    chunks: Mapped[list[ChunkMetadata]] = relationship(
        "ChunkMetadata",
        back_populates="course",
        cascade="all, delete-orphan",
    )
    concepts: Mapped[list[Concept]] = relationship(
        "Concept",
        back_populates="course",
        cascade="all, delete-orphan",
    )
    study_sessions: Mapped[list[StudySession]] = relationship(
        "StudySession",
        back_populates="course",
        cascade="all, delete-orphan",
    )
    concept_progress_records: Mapped[list[ConceptProgress]] = relationship(
        "ConceptProgress",
        back_populates="course",
        cascade="all, delete-orphan",
    )
    revision_tasks: Mapped[list[RevisionTask]] = relationship(
        "RevisionTask",
        back_populates="course",
        cascade="all, delete-orphan",
    )


class Document(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Represents an uploaded course PDF document and its ingestion lifecycle."""

    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_user_id", "user_id"),
        Index("ix_documents_course_id", "course_id"),
        Index("ix_documents_status", "status"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(
        String(100), default="application/pdf", nullable=False
    )
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default="UPLOADED", nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_warnings: Mapped[list[str]] = mapped_column(
        JSONVariant, default=list, nullable=False
    )

    # Relationships
    owner: Mapped[User] = relationship("User", back_populates="documents")
    course: Mapped[Course] = relationship("Course", back_populates="documents")
    chunks: Mapped[list[ChunkMetadata]] = relationship(
        "ChunkMetadata",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="ChunkMetadata.chunk_index",
    )
    concepts: Mapped[list[Concept]] = relationship(
        "Concept",
        back_populates="source_document",
    )


class ChunkMetadata(UUIDPrimaryKeyMixin, Base):
    """Relational metadata for a document text chunk.

    Stores page boundaries (page_start, page_end), optional section_title,
    chunk_text, and chunk_index. Dense vector embeddings are stored in ChromaDB
    (referenced via chroma_vector_id) and omitted from PostgreSQL.
    """

    __tablename__ = "chunk_metadata"
    __table_args__ = (
        Index("ix_chunk_metadata_document_id", "document_id"),
        Index("ix_chunk_metadata_course_id", "course_id"),
        Index("ix_chunk_metadata_chroma_vector_id", "chroma_vector_id", unique=True),
        Index("ix_chunk_metadata_doc_page", "document_id", "page_start"),
        Index("ix_chunk_metadata_doc_index", "document_id", "chunk_index"),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    chroma_vector_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    text_content: Mapped[str] = synonym("chunk_text")
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONVariant, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    document: Mapped[Document] = relationship("Document", back_populates="chunks")
    course: Mapped[Course] = relationship("Course", back_populates="chunks")


class Concept(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Represents a core academic concept extracted from course documents."""

    __tablename__ = "concepts"
    __table_args__ = (
        Index("ix_concepts_course_id", "course_id"),
        Index("ix_concepts_source_document_id", "source_document_id"),
        Index("ix_concepts_course_order", "course_id", "display_order"),
    )

    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[str] = mapped_column(
        String(30), default="INTERMEDIATE", nullable=False
    )
    display_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_pages: Mapped[list[int]] = mapped_column(
        JSONVariant, default=list, nullable=False
    )

    # Relationships
    course: Mapped[Course] = relationship("Course", back_populates="concepts")
    source_document: Mapped[Document | None] = relationship(
        "Document", back_populates="concepts"
    )
    study_sessions: Mapped[list[StudySession]] = relationship(
        "StudySession", back_populates="current_concept"
    )
    activities: Mapped[list[Activity]] = relationship(
        "Activity",
        back_populates="concept",
        cascade="all, delete-orphan",
    )
    learning_evidences: Mapped[list[LearningEvidence]] = relationship(
        "LearningEvidence",
        back_populates="concept",
        cascade="all, delete-orphan",
    )
    progress_records: Mapped[list[ConceptProgress]] = relationship(
        "ConceptProgress",
        back_populates="concept",
        cascade="all, delete-orphan",
    )
    revision_tasks: Mapped[list[RevisionTask]] = relationship(
        "RevisionTask",
        back_populates="concept",
        cascade="all, delete-orphan",
    )
