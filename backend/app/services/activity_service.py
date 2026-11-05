"""ActivityService managing study session activities, attempt persistence, idempotency, and hints."""

from __future__ import annotations

import hashlib
import re
from typing import Any
import uuid

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.assessment.rubric import parse_activity_rubric
from app.assessment.service import AssessmentAgentService
from app.core.config import settings
from app.models.session import Activity, Attempt, Evaluation, StudySession
from app.orchestration.session_state_machine import (
    InvalidSessionStateError,
    SessionStateMachine,
)
from app.repositories.session_repository import SessionRepository
from app.retrieval.retriever import RetrievedPassage
from app.schemas.assessment import AssessmentSchema
from app.schemas.session import (
    ActivityAttemptDetail,
    ActivityHistoryItem,
    AttemptRead,
    EvaluationRead,
)
from app.tutor.session_ai_engine import GeneratedActivitySpec, SessionAIEngine


def _normalize_text_hash(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text.strip().lower())
    return hashlib.sha256(collapsed.encode("utf-8")).hexdigest()


class ActivityService:
    """Encapsulates activity creation, duplicate-safe attempt persistence, and graduated hints."""

    def __init__(
        self,
        db: Session,
        repository: SessionRepository | None = None,
        ai_engine: SessionAIEngine | None = None,
        assessment_agent: AssessmentAgentService | None = None,
    ) -> None:
        self.db = db
        self.repo = repository or SessionRepository(db)
        self.ai_engine = ai_engine or SessionAIEngine()
        self.assessment_agent = assessment_agent or AssessmentAgentService()

    def _get_activity_meta_map(self, session: StudySession) -> dict[str, dict[str, Any]]:
        ctx = dict(session.context_data or {})
        meta_map = dict(ctx.get("activity_meta") or {})
        return meta_map

    def _save_activity_meta(
        self,
        session: StudySession,
        activity_id: uuid.UUID,
        meta: dict[str, Any],
    ) -> None:
        ctx = dict(session.context_data or {})
        meta_map = dict(ctx.get("activity_meta") or {})
        meta_map[str(activity_id)] = meta
        ctx["activity_meta"] = meta_map
        session.context_data = ctx
        flag_modified(session, "context_data")
        self.repo.save_session(session)

    def generate_and_persist_activity(
        self,
        *,
        session: StudySession,
        concept_id: uuid.UUID,
        concept_title: str,
        concept_summary: str,
        learning_goal: str,
        difficulty: str,
        is_diagnostic: bool,
        passages: list[RetrievedPassage],
        requested_activity_type: str | None = None,
    ) -> Activity:
        """Generate a new grounded question activity via SessionAIEngine and persist it."""
        existing_activities = self.repo.list_activities_for_session(session.id)
        prior_prompts = [a.prompt_text for a in existing_activities]
        order_index = len(existing_activities)

        spec: GeneratedActivitySpec = self.ai_engine.generate_question_activity(
            concept_title=concept_title,
            concept_summary=concept_summary,
            learning_goal=learning_goal,
            difficulty=difficulty,
            is_diagnostic=is_diagnostic,
            passages=passages,
            prior_prompts=prior_prompts,
            order_index=order_index,
            requested_activity_type=requested_activity_type,
        )

        activity = self.repo.create_activity(
            session_id=session.id,
            concept_id=concept_id,
            activity_type=spec.activity_type,
            difficulty=spec.difficulty,
            prompt_text=spec.prompt_text,
            rubric_json=spec.rubric_json,
            ideal_answer_summary=spec.ideal_answer_summary,
            source_chunk_ids=spec.source_chunk_ids,
            status="ACTIVE",
            order_index=order_index,
        )

        initial_hints_revealed = 1 if spec.activity_type == "HINT_AND_RETRY" else 0
        initial_explanation = (
            spec.ideal_answer_summary if spec.activity_type == "EXPLANATION" else None
        )

        self._save_activity_meta(
            session,
            activity.id,
            {
                "graduated_hints": spec.graduated_hints,
                "hints_revealed": initial_hints_revealed,
                "relevant_pages": spec.relevant_pages,
                "source_excerpts": spec.source_excerpts,
                "explanation_requested": initial_explanation,
                "submission_fingerprints": {},
            },
        )
        return activity

    def submit_attempt_and_evaluate(
        self,
        *,
        session: StudySession,
        concept_title: str,
        user_id: uuid.UUID,
        response_text: str,
        activity_id: uuid.UUID | None = None,
        time_spent_seconds: int | None = None,
        idempotency_key: str | None = None,
    ) -> tuple[Attempt, Evaluation, bool]:
        """Submit a student answer with idempotency protection, evaluate it, and transition state.

        Returns `(attempt, evaluation, duplicate_prevented)`.
        """
        SessionStateMachine.validate_session_not_completed(session, "submit an answer")

        activities = self.repo.list_activities_for_session(session.id)
        if not activities:
            raise InvalidSessionStateError("Session has no activities to answer.")

        target_activity: Activity | None = None
        if activity_id is not None:
            target_activity = self.repo.get_activity(activity_id)
            if target_activity is None or target_activity.session_id != session.id:
                raise InvalidSessionStateError(
                    f"Activity '{activity_id}' does not belong to session '{session.id}'."
                )
        else:
            target_activity = self.repo.get_active_activity(session.id) or activities[-1]

        meta_map = self._get_activity_meta_map(session)
        act_meta = dict(meta_map.get(str(target_activity.id)) or {})
        fingerprints: dict[str, dict[str, str]] = dict(
            act_meta.get("submission_fingerprints") or {}
        )

        text_hash = _normalize_text_hash(response_text)
        dedup_keys = [f"hash:{text_hash}"]
        if idempotency_key and idempotency_key.strip():
            dedup_keys.insert(0, f"key:{idempotency_key.strip()}")

        # 1. Duplicate request detection (idempotent return of existing Attempt + Evaluation)
        for dkey in dedup_keys:
            if dkey in fingerprints:
                recorded_ids = fingerprints[dkey]
                existing_attempts = self.repo.list_attempts_for_activity(target_activity.id)
                matched_attempt = next(
                    (a for a in existing_attempts if str(a.id) == recorded_ids.get("attempt_id")),
                    existing_attempts[-1] if existing_attempts else None,
                )
                if matched_attempt is not None:
                    evals = self.repo.list_evaluations_for_attempt(matched_attempt.id)
                    if evals:
                        return matched_attempt, evals[-1], True

        # 2. Enforce that the target activity is currently ACTIVE
        active_activity = SessionStateMachine.validate_can_submit_answer(
            session,
            target_activity if target_activity.status == "ACTIVE" else None,
        )

        existing_attempts = self.repo.list_attempts_for_activity(active_activity.id)
        attempt_number = len(existing_attempts) + 1

        attempt = self.repo.create_attempt(
            activity_id=active_activity.id,
            user_id=user_id,
            attempt_number=attempt_number,
            response_text=response_text.strip(),
            time_spent_seconds=time_spent_seconds,
        )

        # 3. Retrieve explicit ActivityRubric and invoke Phase 6 Assessment Agent
        relevant_pages: list[int] = list(act_meta.get("relevant_pages") or [])
        explicit_rubric = parse_activity_rubric(
            rubric_json=active_activity.rubric_json,
            concept_id=active_activity.concept_id,
            concept_title=concept_title,
            ideal_answer_summary=active_activity.ideal_answer_summary or concept_title,
            question_text=active_activity.prompt_text,
        )
        assessment_result: AssessmentSchema = self.assessment_agent.evaluate_answer(
            concept_id=active_activity.concept_id,
            concept_title=concept_title,
            question_text=active_activity.prompt_text,
            rubric_json=explicit_rubric,
            ideal_answer_summary=active_activity.ideal_answer_summary or concept_title,
            student_answer=attempt.response_text,
            relevant_pages=relevant_pages,
        )

        evaluation = self.repo.create_evaluation(
            attempt_id=attempt.id,
            concept_id=assessment_result.concept_id,
            verdict=assessment_result.verdict,
            total_score=assessment_result.rubric_score,
            max_score=100.0,
            passed=assessment_result.passed,
            criteria_scores_json=assessment_result.criteria_scores,
            strengths_json=assessment_result.strengths,
            gaps_json=assessment_result.gaps,
            misconception=assessment_result.misconception,
            evidence_json=assessment_result.evidence,
            confidence=assessment_result.confidence,
            next_activity=assessment_result.next_activity,
            error_classification=assessment_result.error_classification,
            uncertain_evaluation=assessment_result.uncertain_evaluation,
            prompt_version=assessment_result.prompt_version,
            overall_feedback=assessment_result.feedback_explanation,
            evaluator_model=settings.OLLAMA_MODEL,
            coach_action=assessment_result.coach_action,
        )

        # Mark activity COMPLETED and record idempotency fingerprints
        active_activity.status = "COMPLETED"
        self.repo.save_activity(active_activity)

        pair_record = {
            "attempt_id": str(attempt.id),
            "evaluation_id": str(evaluation.id),
        }
        for dkey in dedup_keys:
            fingerprints[dkey] = pair_record
        act_meta["submission_fingerprints"] = fingerprints
        self._save_activity_meta(session, active_activity.id, act_meta)

        return attempt, evaluation, False

    def request_graduated_hint(
        self,
        *,
        session: StudySession,
        activity_id: uuid.UUID | None = None,
    ) -> tuple[Activity, int, int, str, list[int]]:
        """Reveal the next graduated hint (1..3) for the active question."""
        active_activity = self.repo.get_active_activity(session.id)
        if activity_id is not None:
            requested = self.repo.get_activity(activity_id)
            if requested is None or requested.session_id != session.id:
                raise InvalidSessionStateError(
                    f"Activity '{activity_id}' does not belong to session '{session.id}'."
                )
            active_activity = requested

        checked_activity = SessionStateMachine.validate_can_request_hint(
            session, active_activity
        )

        meta_map = self._get_activity_meta_map(session)
        act_meta = dict(meta_map.get(str(checked_activity.id)) or {})
        all_hints: list[str] = list(act_meta.get("graduated_hints") or [])
        if not all_hints:
            all_hints = [
                "Hint 1: Review the section heading and key terms in your course PDF.",
                "Hint 2: Break the question into cause and effect based on the lecture notes.",
                "Hint 3: State the core definition first, then explain how the mechanism responds.",
            ]

        current_revealed = int(act_meta.get("hints_revealed") or 0)
        next_level = min(len(all_hints), current_revealed + 1)
        act_meta["hints_revealed"] = next_level
        self._save_activity_meta(session, checked_activity.id, act_meta)

        ctx = dict(session.context_data or {})
        ctx["total_hints_used"] = int(ctx.get("total_hints_used") or 0) + (
            1 if current_revealed < len(all_hints) else 0
        )
        session.context_data = ctx
        flag_modified(session, "context_data")
        self.repo.save_session(session)

        hint_text = all_hints[next_level - 1]
        relevant_pages = list(act_meta.get("relevant_pages") or [])
        return checked_activity, next_level, len(all_hints), hint_text, relevant_pages

    def record_explanation_for_activity(
        self,
        *,
        session: StudySession,
        activity: Activity | None,
        explanation_text: str,
    ) -> None:
        """Persist the requested explanation in the activity metadata and increment session counter."""
        if activity is not None:
            meta_map = self._get_activity_meta_map(session)
            act_meta = dict(meta_map.get(str(activity.id)) or {})
            act_meta["explanation_requested"] = explanation_text
            self._save_activity_meta(session, activity.id, act_meta)

        ctx = dict(session.context_data or {})
        ctx["explanations_requested_count"] = int(ctx.get("explanations_requested_count") or 0) + 1
        session.context_data = ctx
        flag_modified(session, "context_data")
        self.repo.save_session(session)

    def build_activity_history_item(
        self,
        session: StudySession,
        activity: Activity,
    ) -> ActivityHistoryItem:
        """Serialize an Activity with its attempts, evaluations, revealed hints, and page citations."""
        meta_map = self._get_activity_meta_map(session)
        act_meta = dict(meta_map.get(str(activity.id)) or {})
        all_hints: list[str] = list(act_meta.get("graduated_hints") or [])
        hints_revealed = int(act_meta.get("hints_revealed") or 0)
        revealed_hints = all_hints[:hints_revealed]
        relevant_pages = list(act_meta.get("relevant_pages") or [])
        source_excerpts = list(act_meta.get("source_excerpts") or [])
        explanation_requested = act_meta.get("explanation_requested")

        attempts = self.repo.list_attempts_for_activity(activity.id)
        attempt_details: list[ActivityAttemptDetail] = []
        for att in attempts:
            evals = self.repo.list_evaluations_for_attempt(att.id)
            latest_eval = evals[-1] if evals else None
            attempt_details.append(
                ActivityAttemptDetail(
                    attempt=AttemptRead.model_validate(att),
                    evaluation=(
                        EvaluationRead.model_validate(latest_eval)
                        if latest_eval is not None
                        else None
                    ),
                )
            )

        return ActivityHistoryItem(
            id=activity.id,
            session_id=activity.session_id,
            concept_id=activity.concept_id,
            activity_type=activity.activity_type,
            difficulty=activity.difficulty,
            prompt_text=activity.prompt_text,
            status=activity.status,
            order_index=activity.order_index,
            relevant_pages=relevant_pages,
            source_excerpts=source_excerpts,
            hints_used=revealed_hints,
            total_hints_available=max(3, len(all_hints)),
            explanation_requested=explanation_requested,
            attempts=attempt_details,
            created_at=activity.created_at,
        )
