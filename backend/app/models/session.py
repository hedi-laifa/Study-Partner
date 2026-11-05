"""StudySession, Activity, Attempt, and Evaluation SQLAlchemy ORM models."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
import uuid

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.base import JSONVariant, TimestampMixin, UUIDPrimaryKeyMixin, utc_now

if TYPE_CHECKING:
    from app.models.course import Concept, Course
    from app.models.learning import LearningEvidence, RevisionTask
    from app.models.user import User


class StudySession(UUIDPrimaryKeyMixin, Base):
    """Represents a state-machine-driven interactive study session for a User."""

    __tablename__ = "study_sessions"
    __table_args__ = (
        Index("ix_study_sessions_user_id", "user_id"),
        Index("ix_study_sessions_course_id", "course_id"),
        Index("ix_study_sessions_current_concept_id", "current_concept_id"),
        Index("ix_study_sessions_state", "state"),
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
    current_concept_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("concepts.id", ondelete="SET NULL"),
        nullable=True,
    )
    state: Mapped[str] = mapped_column(String(30), default="IDLE", nullable=False)
    context_data: Mapped[dict[str, Any]] = mapped_column(
        JSONVariant, default=dict, nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="study_sessions")
    course: Mapped[Course] = relationship("Course", back_populates="study_sessions")
    current_concept: Mapped[Concept | None] = relationship(
        "Concept", back_populates="study_sessions"
    )
    activities: Mapped[list[Activity]] = relationship(
        "Activity",
        back_populates="session",
        cascade="all, delete-orphan",
    )


class Activity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Represents a learning or assessment activity within a StudySession."""

    __tablename__ = "activities"
    __table_args__ = (
        Index("ix_activities_session_id", "session_id"),
        Index("ix_activities_concept_id", "concept_id"),
        Index("ix_activities_activity_type", "activity_type"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("study_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("concepts.id", ondelete="CASCADE"),
        nullable=False,
    )
    activity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    difficulty: Mapped[str] = mapped_column(
        String(30), default="INTERMEDIATE", nullable=False
    )
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    rubric_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONVariant, default=list, nullable=False
    )
    ideal_answer_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_chunk_ids: Mapped[list[str]] = mapped_column(
        JSONVariant, default=list, nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    session: Mapped[StudySession] = relationship(
        "StudySession", back_populates="activities"
    )
    concept: Mapped[Concept] = relationship("Concept", back_populates="activities")
    attempts: Mapped[list[Attempt]] = relationship(
        "Attempt",
        back_populates="activity",
        cascade="all, delete-orphan",
    )


class Attempt(UUIDPrimaryKeyMixin, Base):
    """Immutable record of a student's submitted response to an Activity.

    Preserves all historical student attempts chronologically.
    """

    __tablename__ = "attempts"
    __table_args__ = (
        Index("ix_attempts_activity_id", "activity_id"),
        Index("ix_attempts_user_id", "user_id"),
        Index("ix_attempts_activity_attempt_num", "activity_id", "attempt_number"),
    )

    activity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    time_spent_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    activity: Mapped[Activity] = relationship("Activity", back_populates="attempts")
    user: Mapped[User] = relationship("User", back_populates="attempts")
    evaluations: Mapped[list[Evaluation]] = relationship(
        "Evaluation",
        back_populates="attempt",
        cascade="all, delete-orphan",
    )


class Evaluation(UUIDPrimaryKeyMixin, Base):
    """Rubric-based evaluation record for a student Attempt.

    Preserves full evaluation history even if an attempt is re-evaluated.
    """

    __tablename__ = "evaluations"
    __table_args__ = (
        Index("ix_evaluations_attempt_id", "attempt_id"),
        Index("ix_evaluations_concept_id", "concept_id"),
        Index("ix_evaluations_verdict", "verdict"),
        Index("ix_evaluations_coach_action", "coach_action"),
    )

    attempt_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("attempts.id", ondelete="CASCADE"),
        nullable=False,
    )
    concept_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("concepts.id", ondelete="SET NULL"),
        nullable=True,
    )
    verdict: Mapped[str] = mapped_column(
        String(40), default="INCORRECT", nullable=False
    )
    total_score: Mapped[float] = mapped_column(Float, nullable=False)
    max_score: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    criteria_scores_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONVariant, default=list, nullable=False
    )
    strengths_json: Mapped[list[str]] = mapped_column(
        JSONVariant, default=list, nullable=False
    )
    gaps_json: Mapped[list[str]] = mapped_column(
        JSONVariant, default=list, nullable=False
    )
    misconception: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_json: Mapped[list[str]] = mapped_column(
        JSONVariant, default=list, nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.85, nullable=False)
    next_activity: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_classification: Mapped[str] = mapped_column(
        String(40), default="NONE", nullable=False
    )
    uncertain_evaluation: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    prompt_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    overall_feedback: Mapped[str] = mapped_column(Text, nullable=False)
    evaluator_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    coach_action: Mapped[str | None] = mapped_column(String(30), nullable=True)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    @property
    def rubric_score(self) -> float:
        """Return rubric_score matching the Phase 6 AssessmentSchema contract."""
        return float(self.total_score)

    @property
    def strengths(self) -> list[str]:
        """Return strengths list matching the Phase 6 AssessmentSchema contract."""
        return list(self.strengths_json or [])

    @property
    def gaps(self) -> list[str]:
        """Return gaps list matching the Phase 6 AssessmentSchema contract."""
        return list(self.gaps_json or [])

    @property
    def evidence(self) -> list[str]:
        """Return evidence list matching the Phase 6 AssessmentSchema contract."""
        return list(self.evidence_json or [])

    # Relationships
    attempt: Mapped[Attempt] = relationship("Attempt", back_populates="evaluations")
    learning_evidences: Mapped[list[LearningEvidence]] = relationship(
        "LearningEvidence",
        back_populates="evaluation",
    )
    revision_tasks: Mapped[list[RevisionTask]] = relationship(
        "RevisionTask",
        back_populates="source_evaluation",
    )
