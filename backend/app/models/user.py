"""User SQLAlchemy ORM model."""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.course import Course, Document
    from app.models.learning import ConceptProgress, LearningEvidence, RevisionTask
    from app.models.session import Attempt, StudySession


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Represents a student user owning courses, documents, sessions, and learning records."""

    __tablename__ = "users"
    __table_args__ = (Index("ix_users_email", "email", unique=True),)

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    courses: Mapped[list[Course]] = relationship(
        "Course",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    documents: Mapped[list[Document]] = relationship(
        "Document",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    study_sessions: Mapped[list[StudySession]] = relationship(
        "StudySession",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    attempts: Mapped[list[Attempt]] = relationship(
        "Attempt",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    learning_evidences: Mapped[list[LearningEvidence]] = relationship(
        "LearningEvidence",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    concept_progress_records: Mapped[list[ConceptProgress]] = relationship(
        "ConceptProgress",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    revision_tasks: Mapped[list[RevisionTask]] = relationship(
        "RevisionTask",
        back_populates="user",
        cascade="all, delete-orphan",
    )
