"""Validated Pydantic schemas for Phase 6: Assessment Agent and Explicit Rubrics."""

from __future__ import annotations

from typing import Any, Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

AssessmentVerdict = Literal[
    "CORRECT",
    "PARTIALLY_CORRECT",
    "INCORRECT",
    "OFF_TOPIC",
    "INSUFFICIENT_EVIDENCE",
]

ErrorClassification = Literal[
    "NONE",
    "INCOMPLETE_REASONING",
    "FACTUAL_MISTAKE",
    "CALCULATION_ERROR",
    "AMBIGUOUS_OR_VAGUE",
    "OFF_TOPIC",
]

NextActivityRecommendation = Literal[
    "ADVANCE_DIFFICULTY",
    "PRACTICE_SAME_CONCEPT",
    "REMEDIATION_EXPLANATION",
    "CLARIFY_AMBIGUOUS_ANSWER",
    "REFOCUS_ON_COURSE_CONCEPT",
]


def normalize_verdict(raw: str) -> AssessmentVerdict:
    """Normalize a string verdict into one of the 5 canonical AssessmentVerdict values."""
    cleaned = raw.strip().upper().replace("-", "_").replace(" ", "_")
    mapping: dict[str, AssessmentVerdict] = {
        "CORRECT": "CORRECT",
        "FULLY_CORRECT": "CORRECT",
        "MASTERED": "CORRECT",
        "PARTIALLY_CORRECT": "PARTIALLY_CORRECT",
        "PARTIAL": "PARTIALLY_CORRECT",
        "DEVELOPING": "PARTIALLY_CORRECT",
        "INCOMPLETE": "PARTIALLY_CORRECT",
        "INCORRECT": "INCORRECT",
        "WRONG": "INCORRECT",
        "FALSE": "INCORRECT",
        "OFF_TOPIC": "OFF_TOPIC",
        "IRRELEVANT": "OFF_TOPIC",
        "UNRELATED": "OFF_TOPIC",
        "INSUFFICIENT_EVIDENCE": "INSUFFICIENT_EVIDENCE",
        "INSUFFICIENT": "INSUFFICIENT_EVIDENCE",
        "AMBIGUOUS": "INSUFFICIENT_EVIDENCE",
        "VAGUE": "INSUFFICIENT_EVIDENCE",
        "UNCERTAIN": "INSUFFICIENT_EVIDENCE",
    }
    if cleaned in mapping:
        return mapping[cleaned]
    raise ValueError(
        f"Invalid assessment verdict '{raw}'. Must be one of: "
        "CORRECT, PARTIALLY_CORRECT, INCORRECT, OFF_TOPIC, INSUFFICIENT_EVIDENCE."
    )


class MisconceptionPattern(BaseModel):
    """Explicit misconception definition requiring textual evidence in the student's answer."""

    pattern_id: str = Field(min_length=1, max_length=80)
    misconception_label: str = Field(
        min_length=3,
        description="Clear description of the specific factual misconception.",
    )
    trigger_phrases: list[str] = Field(
        default_factory=list,
        description="Phrases or claims that provide direct textual evidence of this misconception.",
    )
    correction_explanation: str = Field(
        default="",
        description="Grounded explanation correcting the misconception.",
    )


class NumericalCheckSpec(BaseModel):
    """Deterministic numerical calculation specification for quantitative questions."""

    expected_value: float
    tolerance: float = Field(default=0.01, ge=0.0)
    unit: str | None = None
    formula_description: str | None = None


class NumericVerificationResult(BaseModel):
    """Result of deterministic numerical verification on a student's answer."""

    applied: bool = False
    expected_value: float | None = None
    extracted_student_values: list[float] = Field(default_factory=list)
    matched_value: float | None = None
    is_correct: bool | None = None
    tolerance: float | None = None
    unit: str | None = None
    detail: str | None = None


class RubricCriterionModel(BaseModel):
    """Explicit grading criterion within an ActivityRubric."""

    criterion_id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1)
    max_points: float = Field(gt=0.0, le=100.0)
    required_ideas: list[str] = Field(
        default_factory=list,
        description="Key concepts or ideas required to earn full credit on this criterion.",
    )
    misconception_patterns: list[MisconceptionPattern] = Field(default_factory=list)
    numerical_check: NumericalCheckSpec | None = None


class ActivityRubric(BaseModel):
    """Complete explicit rubric for an assessment activity."""

    rubric_version: str = "1.0"
    concept_id: uuid.UUID | None = None
    concept_title: str
    required_ideas: list[str] = Field(default_factory=list)
    criteria: list[RubricCriterionModel] = Field(default_factory=list)
    misconception_patterns: list[MisconceptionPattern] = Field(default_factory=list)
    numerical_check: NumericalCheckSpec | None = None


class CriterionEvaluationItem(BaseModel):
    """Per-criterion score and diagnostic feedback."""

    criterion_id: str
    name: str
    awarded_points: float = Field(ge=0.0)
    max_points: float = Field(gt=0.0)
    matched_ideas: list[str] = Field(default_factory=list)
    missing_ideas: list[str] = Field(default_factory=list)
    feedback: str


class AssessmentLLMOutput(BaseModel):
    """Raw structured JSON output requested from the LLM during assessment evaluation."""

    verdict: str
    rubric_score: float = Field(ge=0.0, le=100.0)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    misconception: str | None = None
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    next_activity: str = "PRACTICE_SAME_CONCEPT"
    error_classification: str = "NONE"
    feedback_explanation: str
    criteria_scores: list[dict[str, Any]] = Field(default_factory=list)


class AssessmentSchema(BaseModel):
    """Validated Pydantic schema produced by the Phase 6 Assessment Agent.

    Enforces:
    - Required fields: concept_id, verdict, rubric_score, strengths, gaps,
      misconception, evidence, confidence, next_activity
    - No inferred misconceptions without supporting evidence
    - Uncertain evaluation support & capped confidence on ambiguous/vague answers
    - Explicit distinction between factual mistakes and incomplete reasoning
    - No direct mastery assignment (extra="forbid" prevents mastery_score injection)
    """

    model_config = ConfigDict(extra="forbid")

    concept_id: uuid.UUID
    verdict: AssessmentVerdict
    rubric_score: float = Field(ge=0.0, le=100.0)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    misconception: str | None = None
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    next_activity: str = Field(min_length=1, max_length=80)

    # Diagnostic & pedagogical metadata
    feedback_explanation: str = Field(min_length=1)
    error_classification: ErrorClassification = "NONE"
    uncertain_evaluation: bool = False
    criteria_scores: list[dict[str, Any]] = Field(default_factory=list)
    numeric_verification: NumericVerificationResult | None = None
    prompt_version: str = "assessment-v1.0.0"

    @field_validator("verdict", mode="before")
    @classmethod
    def _validate_verdict(cls, value: Any) -> AssessmentVerdict:
        if isinstance(value, str):
            return normalize_verdict(value)
        raise ValueError("verdict must be a valid string.")

    @field_validator("misconception", mode="before")
    @classmethod
    def _clean_placeholder_misconception(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        low = text.lower().rstrip(".")
        if low in {
            "none",
            "n/a",
            "null",
            "no misconception",
            "no misconceptions",
            "no supported misconception",
            "none detected",
            "none identified",
            "not applicable",
        }:
            return None
        return text

    @model_validator(mode="after")
    def _enforce_assessment_rules(self) -> AssessmentSchema:
        # Rule 1: Do not infer misconceptions without evidence.
        # Also, an incomplete answer (INCOMPLETE_REASONING) or vague/off-topic answer
        # without explicit evidence of a false claim must not carry an unsupported misconception.
        cleaned_evidence = [e.strip() for e in self.evidence if e and e.strip()]
        self.evidence = cleaned_evidence

        if self.misconception is not None:
            has_quote_or_claim_evidence = any(
                "student" in ev.lower()
                or "stated" in ev.lower()
                or "claimed" in ev.lower()
                or "wrote" in ev.lower()
                or "calculated" in ev.lower()
                or '"' in ev
                or "'" in ev
                for ev in self.evidence
            )
            if not self.evidence or not has_quote_or_claim_evidence:
                raise ValueError(
                    "Rule violation: Do not infer misconceptions without explicit evidence "
                    "referencing the student's answer."
                )

        # Rule 2: Do not claim certainty when an answer is ambiguous or lacks sufficient evidence.
        if (
            self.verdict == "INSUFFICIENT_EVIDENCE"
            or self.error_classification == "AMBIGUOUS_OR_VAGUE"
        ):
            if self.confidence > 0.65:
                self.confidence = round(min(self.confidence, 0.55), 2)
            self.uncertain_evaluation = True
        elif self.confidence < 0.65:
            self.uncertain_evaluation = True

        # Rule 3: Distinguish factual mistakes from incomplete reasoning.
        if self.verdict == "CORRECT":
            self.error_classification = "NONE"
        elif self.verdict == "OFF_TOPIC":
            self.error_classification = "OFF_TOPIC"
        elif (
            self.verdict == "PARTIALLY_CORRECT"
            and self.error_classification == "NONE"
        ):
            self.error_classification = (
                "FACTUAL_MISTAKE"
                if self.misconception is not None
                else "INCOMPLETE_REASONING"
            )

        self.rubric_score = round(self.rubric_score, 1)
        self.confidence = round(self.confidence, 2)
        return self

    @property
    def overall_feedback(self) -> str:
        """Alias for feedback_explanation for seamless integration with session evaluations."""
        return self.feedback_explanation

    @property
    def passed(self) -> bool:
        """Whether the student attempt satisfied the activity threshold."""
        return self.verdict == "CORRECT" or (
            self.verdict == "PARTIALLY_CORRECT" and self.rubric_score >= 70.0
        )

    @property
    def coach_action(self) -> Literal["ADVANCE", "PRACTICE_AGAIN", "RETEACH"]:
        """Map next_activity recommendation to the 3-way session state machine coach action."""
        if self.next_activity == "ADVANCE_DIFFICULTY" or self.verdict == "CORRECT":
            return "ADVANCE"
        if self.next_activity == "PRACTICE_SAME_CONCEPT" or (
            self.verdict == "PARTIALLY_CORRECT" and self.rubric_score >= 45.0
        ):
            return "PRACTICE_AGAIN"
        return "RETEACH"
