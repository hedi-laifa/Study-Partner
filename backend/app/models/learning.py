"""LearningEvidence, ConceptProgress, and RevisionTask SQLAlchemy ORM models."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
import uuid

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import JSONVariant, TimestampMixin, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.models.course import Concept, Course
    from app.models.session import Evaluation
    from app.models.user import User


class LearningEvidence(UUIDPrimaryKeyMixin, Base):
    """Granular evidence record linking student assessment performance to a Concept."""

    __tablename__ = "learning_evidences"
    __table_args__ = (
        Index("ix_learning_evidences_user_id", "user_id"),
        Index("ix_learning_evidences_concept_id", "concept_id"),
        Index("ix_learning_evidences_evaluation_id", "evaluation_id"),
        Index("ix_learning_evidences_user_concept", "user_id", "concept_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
    )
    evaluation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evaluations.id", ondelete="SET NULL"),
        nullable=True,
    )
    evidence_type: Mapped[str] = mapped_column(String(40), nullable=False)
    score_delta: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    observed_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONVariant, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="learning_evidences")
    concept: Mapped[Concept] = relationship(
        "Concept", back_populates="learning_evidences"
    )
    evaluation: Mapped[Evaluation | None] = relationship(
        "Evaluation", back_populates="learning_evidences"
    )


class ConceptProgress(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tracks per-user mastery score, status, and practice history for a Concept."""

    __tablename__ = "concept_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "concept_id", name="uq_concept_progress_user_concept"),
        Index("ix_concept_progress_user_id", "user_id"),
        Index("ix_concept_progress_course_id", "course_id"),
        Index("ix_concept_progress_concept_id", "concept_id"),
        Index("ix_concept_progress_mastery_status", "mastery_status"),
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
    concept_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
    )
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    mastery_status: Mapped[str] = mapped_column(
        String(30), default="NOT_STARTED", nullable=False
    )
    attempts_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_attempts_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    last_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_practiced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_review_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="concept_progress_records")
    course: Mapped[Course] = relationship(
        "Course", back_populates="concept_progress_records"
    )
    concept: Mapped[Concept] = relationship(
        "Concept", back_populates="progress_records"
    )


class RevisionTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Scheduled remediation or spaced-repetition revision task for a User and Concept."""

    __tablename__ = "revision_tasks"
    __table_args__ = (
        Index("ix_revision_tasks_user_id", "user_id"),
        Index("ix_revision_tasks_course_id", "course_id"),
        Index("ix_revision_tasks_concept_id", "concept_id"),
        Index("ix_revision_tasks_status", "status"),
        Index("ix_revision_tasks_priority", "priority"),
        Index("ix_revision_tasks_due_at", "due_at"),
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
    concept_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_evaluation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("evaluations.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(
        String(20), default="MEDIUM", nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30), default="PENDING", nullable=False
    )
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="revision_tasks")
    course: Mapped[Course] = relationship("Course", back_populates="revision_tasks")
    concept: Mapped[Concept] = relationship("Concept", back_populates="revision_tasks")
    source_evaluation: Mapped[Evaluation | None] = relationship(
        "Evaluation", back_populates="revision_tasks"
    )
