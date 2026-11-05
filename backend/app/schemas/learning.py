"""Pydantic schemas for LearningEvidence, ConceptProgress, RevisionTask, and Phase 7 Adaptive Learning Coach."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field

MasteryStatus = Literal["NOT_STARTED", "NEEDS_REVIEW", "LEARNING", "MASTERED"]
RevisionPriority = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
RevisionStatus = Literal["PENDING", "IN_PROGRESS", "COMPLETED", "DISMISSED"]

CoachActivityType = Literal[
    "EXPLANATION",
    "DIAGNOSTIC_QUESTION",
    "EASIER_PRACTICE",
    "TARGETED_PRACTICE",
    "HINT_AND_RETRY",
    "HARDER_PRACTICE",
    "TRANSFER_QUESTION",
    "REVIEW",
]

EvidenceStatus = Literal[
    "NO_EVIDENCE",
    "UNCERTAIN_EVIDENCE",
    "NEEDS_REMEDIATION",
    "EMERGING_EVIDENCE",
    "DEVELOPING_EVIDENCE",
    "ASSISTED_PROFICIENCY",
    "STRONG_INDEPENDENT_EVIDENCE",
    "DUE_FOR_REVIEW",
]


class LearningEvidenceCreate(BaseModel):
    """Payload to record LearningEvidence for a User and Concept."""

    user_id: uuid.UUID
    concept_id: uuid.UUID
    evaluation_id: uuid.UUID | None = None
    evidence_type: str = Field(min_length=1, max_length=40)
    score_delta: float = 0.0
    observed_score: float | None = Field(default=None, ge=0.0, le=100.0)
    summary: str = Field(min_length=1)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class LearningEvidenceRead(BaseModel):
    """Serialized LearningEvidence response schema."""

    id: uuid.UUID
    user_id: uuid.UUID
    concept_id: uuid.UUID
    evaluation_id: uuid.UUID | None
    evidence_type: str
    score_delta: float
    observed_score: float | None
    summary: str
    metadata_json: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConceptProgressCreate(BaseModel):
    """Payload to initialize ConceptProgress for a User and Concept."""

    user_id: uuid.UUID
    course_id: uuid.UUID
    concept_id: uuid.UUID
    mastery_score: float = Field(default=0.0, ge=0.0, le=100.0)
    mastery_status: MasteryStatus = "NOT_STARTED"


class ConceptProgressUpdate(BaseModel):
    """Payload to update ConceptProgress after an assessment."""

    mastery_score: float | None = Field(default=None, ge=0.0, le=100.0)
    mastery_status: MasteryStatus | None = None
    attempts_count: int | None = Field(default=None, ge=0)
    correct_attempts_count: int | None = Field(default=None, ge=0)
    last_score: float | None = Field(default=None, ge=0.0, le=100.0)
    last_practiced_at: datetime | None = None
    next_review_at: datetime | None = None


class ConceptProgressRead(BaseModel):
    """Serialized ConceptProgress response schema."""

    id: uuid.UUID
    user_id: uuid.UUID
    course_id: uuid.UUID
    concept_id: uuid.UUID
    mastery_score: float
    mastery_status: str
    attempts_count: int
    correct_attempts_count: int
    last_score: float | None
    last_practiced_at: datetime | None
    next_review_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RevisionTaskCreate(BaseModel):
    """Payload to schedule a RevisionTask for a User and Concept."""

    user_id: uuid.UUID
    course_id: uuid.UUID
    concept_id: uuid.UUID
    source_evaluation_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    reason: str = Field(min_length=1)
    priority: RevisionPriority = "MEDIUM"
    status: RevisionStatus = "PENDING"
    due_at: datetime | None = None


class RevisionTaskUpdate(BaseModel):
    """Payload to update RevisionTask status or priority."""

    priority: RevisionPriority | None = None
    status: RevisionStatus | None = None
    due_at: datetime | None = None
    completed_at: datetime | None = None


class RevisionTaskRead(BaseModel):
    """Serialized RevisionTask response schema."""

    id: uuid.UUID
    user_id: uuid.UUID
    course_id: uuid.UUID
    concept_id: uuid.UUID
    source_evaluation_id: uuid.UUID | None
    title: str
    reason: str
    priority: str
    status: str
    due_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Phase 7: Adaptive Learning, Concept Map, Learning Coach & Profile Schemas
# ---------------------------------------------------------------------------


class AlternativeActivityOption(BaseModel):
    """Selectable activity option allowing students to override the default coach recommendation."""

    activity_type: CoachActivityType
    label: str
    difficulty: str
    description: str


class CoachRecommendation(BaseModel):
    """Structured recommendation produced by the Phase 7 Learning Coach."""

    recommended_activity: CoachActivityType
    target_concept_id: uuid.UUID
    target_concept_title: str
    difficulty: str
    reason: str
    policy_rule_applied: str
    requires_student_confirmation: bool
    evidence_status: EvidenceStatus
    uncertainty_score: float = Field(ge=0.0, le=1.0)
    independent_success_count: int = 0
    assisted_success_count: int = 0
    alternative_activities: list[AlternativeActivityOption] = Field(default_factory=list)


class ConceptMapNode(BaseModel):
    """Node in the course Concept Map linking prerequisites, sequence order, and mastery state."""

    concept_id: uuid.UUID
    title: str
    summary: str
    display_order: int
    source_pages: list[int] = Field(default_factory=list)
    prerequisite_concept_ids: list[uuid.UUID] = Field(default_factory=list)
    dependent_concept_ids: list[uuid.UUID] = Field(default_factory=list)
    mastery_score: float = 0.0
    mastery_status: MasteryStatus = "NOT_STARTED"
    evidence_status: EvidenceStatus = "NO_EVIDENCE"


class ConceptLearningProfileItem(BaseModel):
    """Comprehensive per-concept learning profile entry."""

    concept_id: uuid.UUID
    course_id: uuid.UUID
    title: str
    summary: str
    display_order: int
    source_pages: list[int] = Field(default_factory=list)
    prerequisite_concept_ids: list[uuid.UUID] = Field(default_factory=list)
    mastery_score: float = 0.0
    mastery_status: MasteryStatus = "NOT_STARTED"
    evidence_status: EvidenceStatus = "NO_EVIDENCE"
    uncertainty_score: float = Field(default=1.0, ge=0.0, le=1.0)
    attempts_count: int = 0
    correct_attempts_count: int = 0
    independent_success_count: int = 0
    assisted_success_count: int = 0
    last_score: float | None = None
    last_practiced_at: datetime | None = None
    next_review_at: datetime | None = None
    observed_strengths: list[str] = Field(default_factory=list)
    areas_needing_practice: list[str] = Field(default_factory=list)
    recent_evidence: list[LearningEvidenceRead] = Field(default_factory=list)
    recommended_next_action: CoachRecommendation


class RecentLearningActivityItem(BaseModel):
    """Recent learning evidence / activity item across the course."""

    evidence_id: uuid.UUID
    concept_id: uuid.UUID
    concept_title: str
    evidence_type: str
    observed_score: float | None = None
    score_delta: float = 0.0
    verdict: str | None = None
    hints_used: int = 0
    difficulty: str = "INTERMEDIATE"
    summary: str
    created_at: datetime


class RevisionRecommendationItem(BaseModel):
    """Enriched revision recommendation linking a RevisionTask to its concept and suggested activity."""

    id: uuid.UUID
    course_id: uuid.UUID
    concept_id: uuid.UUID
    concept_title: str
    title: str
    reason: str
    priority: str
    status: str
    recommended_activity: CoachActivityType = "REVIEW"
    due_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class CourseLearningProfile(BaseModel):
    """Complete Phase 7 Learning Profile for a student in a course."""

    user_id: uuid.UUID
    course_id: uuid.UUID
    course_title: str
    total_concepts: int
    mastered_concepts_count: int
    learning_concepts_count: int
    needs_review_concepts_count: int
    not_started_concepts_count: int
    overall_mastery_score: float = 0.0
    overall_uncertainty_score: float = 1.0
    concepts: list[ConceptLearningProfileItem] = Field(default_factory=list)
    concept_map: list[ConceptMapNode] = Field(default_factory=list)
    recent_activity: list[RecentLearningActivityItem] = Field(default_factory=list)
    observed_strengths: list[str] = Field(default_factory=list)
    areas_needing_practice: list[str] = Field(default_factory=list)
    revision_recommendations: list[RevisionRecommendationItem] = Field(default_factory=list)
