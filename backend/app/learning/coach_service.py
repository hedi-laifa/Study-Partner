"""Phase 7 Learning Coach Service orchestrating evidence tracking, mastery updates, and adaptive routing."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy.orm import Session

from app.learning.concept_map_service import ConceptMapService
from app.learning.evidence_service import LearningEvidenceService
from app.learning.mastery_heuristic import (
    MasteryUpdateOutcome,
    compute_transparent_mastery_update,
)
from app.learning.progress_service import ConceptProgressService
from app.learning.routing_policy import select_next_adaptive_activity
from app.models.course import Concept
from app.models.learning import ConceptProgress, LearningEvidence
from app.models.session import Evaluation
from app.schemas.learning import (
    CoachRecommendation,
    ConceptProgressRead,
    LearningEvidenceRead,
)


class LearningCoachService:
    """Deterministic Learning Coach tracking concept-level evidence and selecting the next activity."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.concept_map_service = ConceptMapService(db)
        self.evidence_service = LearningEvidenceService(db)
        self.progress_service = ConceptProgressService(db)

    def record_evaluation_and_recommend(
        self,
        *,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        concept: Concept,
        session_goal: str,
        evaluation: Evaluation,
        hints_used: int,
        difficulty: str,
        previous_activity_types: list[str] | None = None,
        now: datetime | None = None,
    ) -> tuple[
        LearningEvidence,
        ConceptProgress,
        CoachRecommendation,
        MasteryUpdateOutcome,
    ]:
        """Deterministically update LearningEvidence, ConceptProgress, RevisionTask, and return CoachRecommendation."""
        ts = now or datetime.now(timezone.utc)
        progress = self.progress_service.get_or_create_progress(
            user_id=user_id,
            course_id=course_id,
            concept_id=concept.id,
        )
        prior_evidences = self.evidence_service.list_evidence_for_concept(
            user_id=user_id,
            concept_id=concept.id,
        )
        ev_summary = self.evidence_service.summarize_evidence_history(prior_evidences)
        recency_hours = self.evidence_service.compute_evidence_recency_hours(
            prior_evidences, now=ts
        )

        outcome = compute_transparent_mastery_update(
            previous_mastery_score=progress.mastery_score,
            previous_attempts_count=progress.attempts_count,
            previous_correct_count=progress.correct_attempts_count,
            previous_independent_success_count=ev_summary["independent_success_count"],
            previous_assisted_success_count=ev_summary["assisted_success_count"],
            previous_consecutive_independent=ev_summary["consecutive_independent_successes"],
            verdict=evaluation.verdict,
            rubric_score=evaluation.rubric_score,
            hints_used=hints_used,
            difficulty=difficulty,
            confidence=evaluation.confidence,
            uncertain_evaluation=evaluation.uncertain_evaluation,
            has_misconception=bool(evaluation.misconception),
            now=ts,
        )

        evidence = self.evidence_service.record_evidence(
            user_id=user_id,
            concept_id=concept.id,
            evaluation_id=evaluation.id,
            evidence_type=outcome.evidence_type,
            score_delta=outcome.score_delta,
            observed_score=evaluation.rubric_score,
            summary=outcome.explanation,
            metadata_json={
                "verdict": evaluation.verdict,
                "rubric_score": evaluation.rubric_score,
                "hints_used": hints_used,
                "difficulty": difficulty,
                "confidence": evaluation.confidence,
                "uncertain_evaluation": evaluation.uncertain_evaluation,
                "error_classification": evaluation.error_classification,
                "evidence_status": outcome.evidence_status,
                "uncertainty_score": outcome.uncertainty_score,
                "strengths": list(evaluation.strengths_json or []),
                "gaps": list(evaluation.gaps_json or []),
                "misconception": evaluation.misconception,
            },
        )

        updated_progress = self.progress_service.apply_mastery_outcome(
            progress=progress,
            outcome=outcome,
            observed_score=evaluation.rubric_score,
            practiced_at=ts,
        )

        self.progress_service.sync_revision_recommendations(
            user_id=user_id,
            course_id=course_id,
            concept=concept,
            evaluation_id=evaluation.id,
            verdict=evaluation.verdict,
            hints_used=hints_used,
            outcome=outcome,
            gaps=list(evaluation.gaps_json or []),
            misconception=evaluation.misconception,
            now=ts,
        )

        recommendation = select_next_adaptive_activity(
            concept_id=concept.id,
            concept_title=concept.title,
            session_goal=session_goal,
            attempts_count=outcome.attempts_count,
            latest_verdict=evaluation.verdict,
            latest_score=evaluation.rubric_score,
            hints_used_on_latest=hints_used,
            current_difficulty=difficulty,
            independent_success_count=outcome.independent_success_count,
            assisted_success_count=outcome.assisted_success_count,
            consecutive_independent_successes=outcome.consecutive_independent_successes,
            evidence_status=outcome.evidence_status,
            uncertainty_score=outcome.uncertainty_score,
            evidence_recency_hours=recency_hours,
            is_due_for_review=False,
            previous_activity_types=previous_activity_types,
            latest_gaps=list(evaluation.gaps_json or []),
            latest_misconception=evaluation.misconception,
        )

        return evidence, updated_progress, recommendation, outcome

    def get_current_recommendation_for_concept(
        self,
        *,
        user_id: uuid.UUID,
        concept: Concept,
        session_goal: str,
        current_difficulty: str = "INTERMEDIATE",
        previous_activity_types: list[str] | None = None,
    ) -> CoachRecommendation:
        """Compute a CoachRecommendation for a concept based on existing evidence (e.g. at session start)."""
        item = self.progress_service.build_concept_learning_profile_item(
            user_id=user_id,
            concept=concept,
        )
        if previous_activity_types:
            evidences = self.evidence_service.list_evidence_for_concept(
                user_id=user_id,
                concept_id=concept.id,
            )
            last_meta = dict(evidences[-1].metadata_json or {}) if evidences else {}
            return select_next_adaptive_activity(
                concept_id=concept.id,
                concept_title=concept.title,
                session_goal=session_goal,
                attempts_count=item.attempts_count,
                latest_verdict=last_meta.get("verdict"),
                latest_score=item.last_score,
                hints_used_on_latest=int(last_meta.get("hints_used") or 0),
                current_difficulty=current_difficulty,
                independent_success_count=item.independent_success_count,
                assisted_success_count=item.assisted_success_count,
                consecutive_independent_successes=0,
                evidence_status=item.evidence_status,
                uncertainty_score=item.uncertainty_score,
                previous_activity_types=previous_activity_types,
                latest_gaps=item.areas_needing_practice,
                latest_misconception=last_meta.get("misconception"),
            )
        return item.recommended_next_action


__all__ = [
    "CoachRecommendation",
    "ConceptProgressRead",
    "LearningCoachService",
    "LearningEvidenceRead",
]
