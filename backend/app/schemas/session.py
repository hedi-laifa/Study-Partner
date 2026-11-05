"""Pydantic schemas for StudySession, Activity, Attempt, Evaluation, and Interactive Study Sessions."""

from datetime import datetime
from typing import Any, Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.learning import (
    CoachActivityType,
    CoachRecommendation,
    ConceptProgressRead,
    LearningEvidenceRead,
)

SessionState = Literal[
    "IDLE",
    "DIAGNOSTIC",
    "TEACHING",
    "QUESTIONING",
    "EVALUATING",
    "FEEDBACK_READY",
    "COACHING",
    "COMPLETED",
]
ActivityType = Literal[
    "DIAGNOSTIC_QUESTION",
    "EXPLANATION",
    "EASIER_PRACTICE",
    "TARGETED_PRACTICE",
    "HINT_AND_RETRY",
    "HARDER_PRACTICE",
    "TRANSFER_QUESTION",
    "REVIEW",
    "CONCEPTUAL_QUESTION",
    "APPLICATION_QUESTION",
    "REMEDIATION",
]
ActivityStatus = Literal["ACTIVE", "COMPLETED", "SKIPPED"]
CoachAction = Literal["ADVANCE", "PRACTICE_AGAIN", "RETEACH"]


class StudySessionCreate(BaseModel):
    """Payload to start a new StudySession."""

    user_id: uuid.UUID
    course_id: uuid.UUID
    current_concept_id: uuid.UUID | None = None
    state: SessionState = "IDLE"
    context_data: dict[str, Any] = Field(default_factory=dict)


class StudySessionUpdate(BaseModel):
    """Payload to transition a StudySession state."""

    current_concept_id: uuid.UUID | None = None
    state: SessionState | None = None
    context_data: dict[str, Any] | None = None
    completed_at: datetime | None = None


class StudySessionRead(BaseModel):
    """Serialized StudySession response schema."""

    id: uuid.UUID
    user_id: uuid.UUID
    course_id: uuid.UUID
    current_concept_id: uuid.UUID | None
    state: str
    context_data: dict[str, Any]
    started_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class ActivityCreate(BaseModel):
    """Payload to create a learning or assessment Activity within a StudySession."""

    session_id: uuid.UUID
    concept_id: uuid.UUID
    activity_type: ActivityType
    difficulty: str = "INTERMEDIATE"
    prompt_text: str = Field(min_length=1)
    rubric_json: list[dict[str, Any]] = Field(default_factory=list)
    ideal_answer_summary: str | None = None
    source_chunk_ids: list[str] = Field(default_factory=list)
    status: ActivityStatus = "ACTIVE"
    order_index: int = Field(default=0, ge=0)


class ActivityRead(BaseModel):
    """Serialized Activity response schema."""

    id: uuid.UUID
    session_id: uuid.UUID
    concept_id: uuid.UUID
    activity_type: str
    difficulty: str
    prompt_text: str
    rubric_json: list[dict[str, Any]]
    ideal_answer_summary: str | None
    source_chunk_ids: list[str]
    status: str
    order_index: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AttemptCreate(BaseModel):
    """Payload to record a student Attempt on an Activity."""

    activity_id: uuid.UUID
    user_id: uuid.UUID
    attempt_number: int = Field(default=1, ge=1)
    response_text: str = Field(min_length=1)
    time_spent_seconds: int | None = Field(default=None, ge=0)


class AttemptRead(BaseModel):
    """Serialized Attempt response schema."""

    id: uuid.UUID
    activity_id: uuid.UUID
    user_id: uuid.UUID
    attempt_number: int
    response_text: str
    time_spent_seconds: int | None
    submitted_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvaluationCreate(BaseModel):
    """Payload to record a rubric Evaluation for an Attempt."""

    attempt_id: uuid.UUID
    concept_id: uuid.UUID | None = None
    verdict: str = "INCORRECT"
    total_score: float = Field(ge=0.0, le=100.0)
    max_score: float = Field(default=100.0, gt=0.0)
    passed: bool = False
    criteria_scores_json: list[dict[str, Any]] = Field(default_factory=list)
    strengths_json: list[str] = Field(default_factory=list)
    gaps_json: list[str] = Field(default_factory=list)
    misconception: str | None = None
    evidence_json: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    next_activity: str | None = None
    error_classification: str = "NONE"
    uncertain_evaluation: bool = False
    prompt_version: str | None = None
    overall_feedback: str = Field(min_length=1)
    evaluator_model: str | None = None
    coach_action: CoachAction | None = None


class EvaluationRead(BaseModel):
    """Serialized Evaluation response schema (includes Phase 6 Assessment Agent fields)."""

    id: uuid.UUID
    attempt_id: uuid.UUID
    concept_id: uuid.UUID | None = None
    verdict: str = "INCORRECT"
    rubric_score: float = 0.0
    total_score: float
    max_score: float
    passed: bool
    criteria_scores_json: list[dict[str, Any]]
    strengths_json: list[str]
    strengths: list[str] = Field(default_factory=list)
    gaps_json: list[str]
    gaps: list[str] = Field(default_factory=list)
    misconception: str | None = None
    evidence_json: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.85
    next_activity: str | None = None
    error_classification: str = "NONE"
    uncertain_evaluation: bool = False
    prompt_version: str | None = None
    overall_feedback: str
    evaluator_model: str | None
    coach_action: str | None
    evaluated_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Phase 5: Interactive Study Session Request & Response Contracts
# ---------------------------------------------------------------------------


class InteractiveSessionStartRequest(BaseModel):
    """Request payload to start an interactive study session on a course and concept/goal."""

    user_id: uuid.UUID | None = None
    course_id: uuid.UUID
    concept_id: uuid.UUID | None = None
    learning_goal: str | None = Field(default=None, max_length=500)


class AnswerSubmissionRequest(BaseModel):
    """Request payload to submit a student answer to the current session activity."""

    user_id: uuid.UUID | None = None
    activity_id: uuid.UUID | None = None
    response_text: str = Field(min_length=1, max_length=8000)
    time_spent_seconds: int | None = Field(default=None, ge=0)
    idempotency_key: str | None = Field(default=None, max_length=128)


class HintRequest(BaseModel):
    """Request payload to get the next graduated hint for the active question."""

    user_id: uuid.UUID | None = None
    activity_id: uuid.UUID | None = None


class HintResponse(BaseModel):
    """Graduated hint response for the active study session question."""

    session_id: uuid.UUID
    activity_id: uuid.UUID
    hint_level: int
    max_hints: int
    hint_text: str
    relevant_pages: list[int] = Field(default_factory=list)


class ExplanationRequest(BaseModel):
    """Request payload to get a concise grounded explanation during a study session."""

    user_id: uuid.UUID | None = None
    activity_id: uuid.UUID | None = None
    focus_question: str | None = Field(default=None, max_length=1000)


class ExplanationResponse(BaseModel):
    """Concise course-grounded explanation response."""

    session_id: uuid.UUID
    activity_id: uuid.UUID | None = None
    explanation: str
    key_takeaways: list[str] = Field(default_factory=list)
    relevant_pages: list[int] = Field(default_factory=list)


class NextActivityRequest(BaseModel):
    """Request payload to advance to the next study session activity (with optional student override)."""

    user_id: uuid.UUID | None = None
    requested_activity_type: CoachActivityType | None = None
    target_concept_id: uuid.UUID | None = None
    student_confirmed: bool = True


class EndSessionRequest(BaseModel):
    """Request payload to complete a study session and generate a learning summary."""

    user_id: uuid.UUID | None = None


class ActivityAttemptDetail(BaseModel):
    """Combined view of a student Attempt and its rubric Evaluation."""

    attempt: AttemptRead
    evaluation: EvaluationRead | None = None


class ActivityHistoryItem(BaseModel):
    """Enriched view of an Activity within a StudySession including attempts, hints, and citations."""

    id: uuid.UUID
    session_id: uuid.UUID
    concept_id: uuid.UUID
    activity_type: str
    difficulty: str
    prompt_text: str
    status: str
    order_index: int
    relevant_pages: list[int] = Field(default_factory=list)
    source_excerpts: list[dict[str, Any]] = Field(default_factory=list)
    hints_used: list[str] = Field(default_factory=list)
    total_hints_available: int = 3
    explanation_requested: str | None = None
    attempts: list[ActivityAttemptDetail] = Field(default_factory=list)
    created_at: datetime


class SessionProgressInfo(BaseModel):
    """Live progress metrics for an interactive study session."""

    total_activities_generated: int
    completed_activities_count: int
    current_activity_index: int
    total_attempts_submitted: int
    hints_used_count: int
    explanations_requested_count: int
    current_difficulty: str
    average_score: float | None = None


class SessionSummaryData(BaseModel):
    """Learning summary produced when a student finishes an interactive study session."""

    total_activities: int
    completed_activities: int
    total_attempts: int
    hints_used_count: int
    explanations_requested_count: int
    average_score: float
    concept_title: str
    learning_goal: str
    pages_reviewed: list[int] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    areas_for_improvement: list[str] = Field(default_factory=list)
    key_takeaways: list[str] = Field(default_factory=list)
    recommended_next_steps: str


class InteractiveSessionDetail(BaseModel):
    """Complete state and history of an interactive StudySession."""

    id: uuid.UUID
    user_id: uuid.UUID
    course_id: uuid.UUID
    course_title: str
    current_concept_id: uuid.UUID | None
    concept_title: str
    concept_summary: str
    learning_goal: str
    state: str
    started_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    current_activity: ActivityHistoryItem | None = None
    activity_history: list[ActivityHistoryItem] = Field(default_factory=list)
    progress: SessionProgressInfo
    coach_recommendation: CoachRecommendation | None = None
    concept_progress: ConceptProgressRead | None = None
    summary: SessionSummaryData | None = None


class AnswerSubmissionResponse(BaseModel):
    """Response returned when submitting an answer in an interactive study session."""

    session: InteractiveSessionDetail
    attempt: AttemptRead
    evaluation: EvaluationRead
    coach_recommendation: CoachRecommendation | None = None
    concept_progress: ConceptProgressRead | None = None
    learning_evidence: LearningEvidenceRead | None = None
    duplicate_prevented: bool = False
