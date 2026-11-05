"""StudySessionService orchestrating Phase 5 Interactive Study Sessions."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.assessment.rubric import parse_activity_rubric
from app.core.exceptions import EntityNotFoundError, OwnershipViolationError
from app.learning.coach_service import LearningCoachService
from app.models.course import Concept, Course
from app.models.session import StudySession
from app.orchestration.session_state_machine import (
    InvalidSessionStateError,
    SessionStateMachine,
)
from app.repositories.session_repository import SessionRepository
from app.retrieval.retriever import RetrievalService
from app.schemas.assessment import ActivityRubric
from app.schemas.learning import (
    CoachRecommendation,
    ConceptProgressRead,
    LearningEvidenceRead,
)
from app.schemas.session import (
    ActivityHistoryItem,
    AnswerSubmissionRequest,
    AnswerSubmissionResponse,
    AttemptRead,
    EndSessionRequest,
    EvaluationRead,
    ExplanationRequest,
    ExplanationResponse,
    HintRequest,
    HintResponse,
    InteractiveSessionDetail,
    InteractiveSessionStartRequest,
    NextActivityRequest,
    SessionProgressInfo,
    SessionSummaryData,
)
from app.services.activity_service import ActivityService
from app.services.user_service import UserService
from app.tutor.session_ai_engine import SessionAIEngine


class StudySessionService:
    """High-level service managing the lifecycle of interactive guided study sessions."""

    def __init__(
        self,
        db: Session,
        repository: SessionRepository | None = None,
        retrieval_service: RetrievalService | None = None,
        ai_engine: SessionAIEngine | None = None,
        activity_service: ActivityService | None = None,
        coach_service: LearningCoachService | None = None,
    ) -> None:
        self.db = db
        self.repo = repository or SessionRepository(db)
        self.retrieval_service = retrieval_service or RetrievalService(db)
        self.ai_engine = ai_engine or SessionAIEngine()
        self.activity_service = activity_service or ActivityService(
            db, repository=self.repo, ai_engine=self.ai_engine
        )
        self.coach_service = coach_service or LearningCoachService(db)

    def _resolve_user_id(self, candidate_user_id: uuid.UUID | None) -> uuid.UUID:
        if candidate_user_id is not None:
            return candidate_user_id
        default_user = UserService(self.db).get_or_create_default_user()
        return default_user.id

    def _get_owned_course(
        self, course_id: uuid.UUID, requesting_user_id: uuid.UUID | None = None
    ) -> Course:
        course = self.repo.get_course(course_id)
        if course is None:
            raise EntityNotFoundError("Course", course_id)
        if requesting_user_id is not None and course.user_id != requesting_user_id:
            raise OwnershipViolationError("Course belongs to a different user.")
        return course

    def _get_owned_session(
        self, session_id: uuid.UUID, requesting_user_id: uuid.UUID | None = None
    ) -> StudySession:
        session = self.repo.get_session(session_id)
        if session is None:
            raise EntityNotFoundError("StudySession", session_id)
        if requesting_user_id is not None and session.user_id != requesting_user_id:
            raise OwnershipViolationError("StudySession belongs to a different user.")
        return session

    def list_or_extract_course_concepts(
        self, course_id: uuid.UUID, requesting_user_id: uuid.UUID | None = None
    ) -> list[Concept]:
        """Return course concepts, auto-extracting them from ingested PDF sections if needed."""
        self._get_owned_course(course_id, requesting_user_id=requesting_user_id)
        return self.repo.ensure_course_concepts_from_chunks(course_id)

    def _resolve_session_concept(
        self,
        *,
        course: Course,
        concept_id: uuid.UUID | None,
        learning_goal: str | None,
    ) -> tuple[Concept, str]:
        """Resolve an existing Concept or create one from the student's learning goal."""
        concepts = self.repo.ensure_course_concepts_from_chunks(course.id)

        if concept_id is not None:
            concept = self.repo.get_concept(concept_id)
            if concept is None or concept.course_id != course.id:
                raise EntityNotFoundError("Concept", concept_id)
            goal = (
                learning_goal.strip()
                if learning_goal and learning_goal.strip()
                else f"Master {concept.title} and apply its mechanisms accurately."
            )
            return concept, goal

        if learning_goal and learning_goal.strip():
            clean_goal = learning_goal.strip()
            for existing in concepts:
                if existing.title.lower() == clean_goal.lower():
                    return existing, clean_goal
            created = self.repo.create_concept(
                course_id=course.id,
                title=clean_goal[:120],
                summary=f"Guided study focus: {clean_goal}",
                difficulty="INTERMEDIATE",
                display_order=len(concepts),
            )
            return created, clean_goal

        if concepts:
            first_concept = concepts[0]
            return (
                first_concept,
                f"Master {first_concept.title} and apply its mechanisms accurately.",
            )

        fallback_concept = self.repo.create_concept(
            course_id=course.id,
            title=f"{course.title} Core Foundations",
            summary=course.description or f"Foundational principles of {course.title}.",
            difficulty="INTERMEDIATE",
            display_order=0,
        )
        return (
            fallback_concept,
            f"Master the foundational concepts of {course.title}.",
        )

    def _retrieve_session_passages(
        self,
        *,
        course_id: uuid.UUID,
        user_id: uuid.UUID,
        concept: Concept,
        learning_goal: str,
    ) -> list:
        query = f"{concept.title}. {learning_goal}. {concept.summary}"
        outcome = self.retrieval_service.retrieve(
            course_id=course_id,
            question=query,
            requesting_user_id=user_id,
            top_k=5,
        )
        return outcome.passages

    def start_interactive_session(
        self,
        payload: InteractiveSessionStartRequest,
        requesting_user_id: uuid.UUID | None = None,
    ) -> InteractiveSessionDetail:
        """Create a new StudySession and generate its initial diagnostic question activity."""
        effective_user_id = self._resolve_user_id(requesting_user_id or payload.user_id)
        course = self._get_owned_course(
            payload.course_id, requesting_user_id=effective_user_id
        )
        concept, resolved_goal = self._resolve_session_concept(
            course=course,
            concept_id=payload.concept_id,
            learning_goal=payload.learning_goal,
        )

        initial_rec = self.coach_service.get_current_recommendation_for_concept(
            user_id=effective_user_id,
            concept=concept,
            session_goal=resolved_goal,
            current_difficulty=concept.difficulty or "INTERMEDIATE",
        )

        context_data = {
            "learning_goal": resolved_goal,
            "concept_title": concept.title,
            "concept_summary": concept.summary,
            "current_difficulty": initial_rec.difficulty or concept.difficulty or "INTERMEDIATE",
            "total_hints_used": 0,
            "explanations_requested_count": 0,
            "activity_meta": {},
            "coach_recommendation": initial_rec.model_dump(mode="json"),
            "summary": None,
        }

        session = self.repo.create_session(
            user_id=effective_user_id,
            course_id=course.id,
            current_concept_id=concept.id,
            state="DIAGNOSTIC",
            context_data=context_data,
        )

        passages = self._retrieve_session_passages(
            course_id=course.id,
            user_id=effective_user_id,
            concept=concept,
            learning_goal=resolved_goal,
        )

        self.activity_service.generate_and_persist_activity(
            session=session,
            concept_id=concept.id,
            concept_title=concept.title,
            concept_summary=concept.summary,
            learning_goal=resolved_goal,
            difficulty=context_data["current_difficulty"],
            is_diagnostic=(initial_rec.recommended_activity == "DIAGNOSTIC_QUESTION"),
            passages=passages,
            requested_activity_type=initial_rec.recommended_activity,
        )

        return self.get_interactive_session(
            session.id, requesting_user_id=effective_user_id, auto_resume=False
        )

    def get_interactive_session(
        self,
        session_id: uuid.UUID,
        requesting_user_id: uuid.UUID | None = None,
        *,
        auto_resume: bool = True,
    ) -> InteractiveSessionDetail:
        """Retrieve full interactive study session state, handling interrupted sessions gracefully."""
        session = self._get_owned_session(session_id, requesting_user_id=requesting_user_id)
        course = self.repo.get_course(session.course_id)
        course_title = course.title if course else "Course Workspace"

        concept = (
            self.repo.get_concept(session.current_concept_id)
            if session.current_concept_id
            else None
        )
        ctx = dict(session.context_data or {})
        concept_title = (
            concept.title
            if concept is not None
            else str(ctx.get("concept_title") or course_title)
        )
        concept_summary = (
            concept.summary
            if concept is not None
            else str(ctx.get("concept_summary") or "")
        )
        learning_goal = str(
            ctx.get("learning_goal") or f"Master {concept_title}."
        )

        activities = self.repo.list_activities_for_session(session.id)

        # Handle interrupted sessions created in IDLE state with no activities yet
        if auto_resume and session.state != "COMPLETED" and not activities and course is not None:
            resolved_concept, resolved_goal = self._resolve_session_concept(
                course=course,
                concept_id=session.current_concept_id,
                learning_goal=learning_goal,
            )
            session.current_concept_id = resolved_concept.id
            session.state = "DIAGNOSTIC"
            ctx["learning_goal"] = resolved_goal
            ctx["concept_title"] = resolved_concept.title
            ctx["concept_summary"] = resolved_concept.summary
            ctx.setdefault("current_difficulty", resolved_concept.difficulty or "INTERMEDIATE")
            session.context_data = ctx
            flag_modified(session, "context_data")
            self.repo.save_session(session)

            passages = self._retrieve_session_passages(
                course_id=course.id,
                user_id=session.user_id,
                concept=resolved_concept,
                learning_goal=resolved_goal,
            )
            self.activity_service.generate_and_persist_activity(
                session=session,
                concept_id=resolved_concept.id,
                concept_title=resolved_concept.title,
                concept_summary=resolved_concept.summary,
                learning_goal=resolved_goal,
                difficulty=str(ctx.get("current_difficulty") or "INTERMEDIATE"),
                is_diagnostic=True,
                passages=passages,
            )
            activities = self.repo.list_activities_for_session(session.id)
            concept_title = resolved_concept.title
            concept_summary = resolved_concept.summary
            learning_goal = resolved_goal

        history_items: list[ActivityHistoryItem] = [
            self.activity_service.build_activity_history_item(session, act)
            for act in activities
        ]

        current_activity: ActivityHistoryItem | None = None
        if session.state != "COMPLETED" and history_items:
            active_candidates = [h for h in history_items if h.status == "ACTIVE"]
            current_activity = (
                active_candidates[-1] if active_candidates else history_items[-1]
            )

        completed_count = sum(1 for h in history_items if h.status == "COMPLETED")
        total_attempts = sum(len(h.attempts) for h in history_items)
        all_scores = [
            att.evaluation.total_score
            for h in history_items
            for att in h.attempts
            if att.evaluation is not None
        ]
        avg_score = (
            round(sum(all_scores) / len(all_scores), 1) if all_scores else None
        )

        ctx = dict(session.context_data or {})
        current_difficulty = str(
            ctx.get("current_difficulty")
            or (current_activity.difficulty if current_activity else "INTERMEDIATE")
        )
        hints_used_count = int(ctx.get("total_hints_used") or 0)
        explanations_count = int(ctx.get("explanations_requested_count") or 0)

        progress = SessionProgressInfo(
            total_activities_generated=len(history_items),
            completed_activities_count=completed_count,
            current_activity_index=(
                current_activity.order_index + 1
                if current_activity is not None
                else len(history_items)
            ),
            total_attempts_submitted=total_attempts,
            hints_used_count=hints_used_count,
            explanations_requested_count=explanations_count,
            current_difficulty=current_difficulty,
            average_score=avg_score,
        )

        raw_summary = ctx.get("summary")
        summary_model = (
            SessionSummaryData.model_validate(raw_summary)
            if isinstance(raw_summary, dict)
            else None
        )

        raw_coach = ctx.get("coach_recommendation")
        coach_rec: CoachRecommendation | None = None
        if isinstance(raw_coach, dict):
            try:
                coach_rec = CoachRecommendation.model_validate(raw_coach)
            except Exception:
                coach_rec = None
        elif concept is not None:
            coach_rec = self.coach_service.get_current_recommendation_for_concept(
                user_id=session.user_id,
                concept=concept,
                session_goal=learning_goal,
                current_difficulty=current_difficulty,
                previous_activity_types=[h.activity_type for h in history_items],
            )

        concept_progress_read: ConceptProgressRead | None = None
        if session.current_concept_id is not None:
            prog_row = self.coach_service.progress_service.get_progress(
                user_id=session.user_id,
                concept_id=session.current_concept_id,
            )
            if prog_row is not None:
                concept_progress_read = ConceptProgressRead.model_validate(prog_row)

        return InteractiveSessionDetail(
            id=session.id,
            user_id=session.user_id,
            course_id=session.course_id,
            course_title=course_title,
            current_concept_id=session.current_concept_id,
            concept_title=concept_title,
            concept_summary=concept_summary,
            learning_goal=learning_goal,
            state=session.state,
            started_at=session.started_at,
            updated_at=session.updated_at,
            completed_at=session.completed_at,
            current_activity=current_activity,
            activity_history=history_items,
            progress=progress,
            coach_recommendation=coach_rec,
            concept_progress=concept_progress_read,
            summary=summary_model,
        )

    def list_course_sessions(
        self, course_id: uuid.UUID, requesting_user_id: uuid.UUID | None = None
    ) -> list[InteractiveSessionDetail]:
        """List all study sessions for a course ordered by most recent update."""
        self._get_owned_course(course_id, requesting_user_id=requesting_user_id)
        sessions = self.repo.list_sessions_for_course(
            course_id, user_id=requesting_user_id
        )
        return [
            self.get_interactive_session(
                s.id, requesting_user_id=requesting_user_id, auto_resume=False
            )
            for s in sessions
        ]

    def get_activity_rubric(
        self,
        session_id: uuid.UUID,
        activity_id: uuid.UUID,
        requesting_user_id: uuid.UUID | None = None,
    ) -> ActivityRubric:
        """Retrieve the explicit grading rubric for an activity within a study session."""
        session = self._get_owned_session(session_id, requesting_user_id=requesting_user_id)
        activity = self.repo.get_activity(activity_id)
        if activity is None or activity.session_id != session.id:
            raise EntityNotFoundError("Activity", activity_id)

        ctx = dict(session.context_data or {})
        concept_title = str(ctx.get("concept_title") or "Course Concept")
        return parse_activity_rubric(
            rubric_json=activity.rubric_json,
            concept_id=activity.concept_id,
            concept_title=concept_title,
            ideal_answer_summary=activity.ideal_answer_summary or concept_title,
            question_text=activity.prompt_text,
        )

    def submit_answer(
        self,
        session_id: uuid.UUID,
        payload: AnswerSubmissionRequest,
        requesting_user_id: uuid.UUID | None = None,
    ) -> AnswerSubmissionResponse:
        """Submit and evaluate a student answer, adapting difficulty and preventing duplicates."""
        effective_user_id = requesting_user_id or payload.user_id
        session = self._get_owned_session(session_id, requesting_user_id=effective_user_id)
        user_id = session.user_id

        ctx = dict(session.context_data or {})
        concept_title = str(ctx.get("concept_title") or "Course Concept")

        attempt, evaluation, duplicate_prevented = (
            self.activity_service.submit_attempt_and_evaluate(
                session=session,
                concept_title=concept_title,
                user_id=user_id,
                response_text=payload.response_text,
                activity_id=payload.activity_id,
                time_spent_seconds=payload.time_spent_seconds,
                idempotency_key=payload.idempotency_key,
            )
        )

        coach_rec: CoachRecommendation | None = None
        concept_progress_read: ConceptProgressRead | None = None
        learning_evidence_read: LearningEvidenceRead | None = None

        if not duplicate_prevented:
            ctx = dict(session.context_data or {})
            prev_diff = str(ctx.get("current_difficulty") or "INTERMEDIATE")
            learning_goal = str(ctx.get("learning_goal") or f"Master {concept_title}")
            meta_map = dict(ctx.get("activity_meta") or {})
            act_meta = dict(meta_map.get(str(attempt.activity_id)) or {})
            hints_used_on_activity = int(act_meta.get("hints_revealed") or 0)

            target_activity = self.repo.get_activity(attempt.activity_id)
            activity_difficulty = (
                target_activity.difficulty if target_activity is not None else prev_diff
            )

            concept = (
                self.repo.get_concept(session.current_concept_id)
                if session.current_concept_id
                else None
            )
            if concept is None:
                course = self.repo.get_course(session.course_id)
                if course is not None:
                    concept, _ = self._resolve_session_concept(
                        course=course,
                        concept_id=None,
                        learning_goal=learning_goal,
                    )

            prior_activities = [
                a.activity_type for a in self.repo.list_activities_for_session(session.id)
            ]

            if concept is not None:
                evidence_row, progress_row, coach_rec, _ = (
                    self.coach_service.record_evaluation_and_recommend(
                        user_id=user_id,
                        course_id=session.course_id,
                        concept=concept,
                        session_goal=learning_goal,
                        evaluation=evaluation,
                        hints_used=hints_used_on_activity,
                        difficulty=activity_difficulty,
                        previous_activity_types=prior_activities,
                    )
                )
                ctx["current_difficulty"] = coach_rec.difficulty
                ctx["coach_recommendation"] = coach_rec.model_dump(mode="json")
                concept_progress_read = ConceptProgressRead.model_validate(progress_row)
                learning_evidence_read = LearningEvidenceRead.model_validate(evidence_row)
            else:
                next_diff = SessionStateMachine.compute_next_difficulty(
                    prev_diff, evaluation.total_score
                )
                ctx["current_difficulty"] = next_diff

            session.context_data = ctx
            session.state = "FEEDBACK_READY"
            flag_modified(session, "context_data")
            self.repo.save_session(session)

        detail = self.get_interactive_session(
            session.id, requesting_user_id=user_id, auto_resume=False
        )
        return AnswerSubmissionResponse(
            session=detail,
            attempt=AttemptRead.model_validate(attempt),
            evaluation=EvaluationRead.model_validate(evaluation),
            coach_recommendation=coach_rec or detail.coach_recommendation,
            concept_progress=concept_progress_read or detail.concept_progress,
            learning_evidence=learning_evidence_read,
            duplicate_prevented=duplicate_prevented,
        )

    def request_hint(
        self,
        session_id: uuid.UUID,
        payload: HintRequest,
        requesting_user_id: uuid.UUID | None = None,
    ) -> HintResponse:
        """Provide the next graduated hint (1..3) for the active session question."""
        effective_user_id = requesting_user_id or payload.user_id
        session = self._get_owned_session(session_id, requesting_user_id=effective_user_id)
        activity, hint_level, max_hints, hint_text, relevant_pages = (
            self.activity_service.request_graduated_hint(
                session=session,
                activity_id=payload.activity_id,
            )
        )
        return HintResponse(
            session_id=session.id,
            activity_id=activity.id,
            hint_level=hint_level,
            max_hints=max_hints,
            hint_text=hint_text,
            relevant_pages=relevant_pages,
        )

    def request_explanation(
        self,
        session_id: uuid.UUID,
        payload: ExplanationRequest,
        requesting_user_id: uuid.UUID | None = None,
    ) -> ExplanationResponse:
        """Generate a concise, grounded concept explanation during the study session."""
        effective_user_id = requesting_user_id or payload.user_id
        session = self._get_owned_session(session_id, requesting_user_id=effective_user_id)
        SessionStateMachine.validate_can_request_explanation(session)

        activities = self.repo.list_activities_for_session(session.id)
        target_activity = None
        if payload.activity_id is not None:
            target_activity = self.repo.get_activity(payload.activity_id)
            if target_activity is None or target_activity.session_id != session.id:
                raise InvalidSessionStateError(
                    f"Activity '{payload.activity_id}' does not belong to session '{session.id}'."
                )
        elif activities:
            target_activity = self.repo.get_active_activity(session.id) or activities[-1]

        ctx = dict(session.context_data or {})
        concept_title = str(ctx.get("concept_title") or "Course Concept")
        learning_goal = str(ctx.get("learning_goal") or concept_title)
        question_text = (
            target_activity.prompt_text if target_activity is not None else concept_title
        )

        concept = (
            self.repo.get_concept(session.current_concept_id)
            if session.current_concept_id
            else None
        )
        if concept is None:
            course = self.repo.get_course(session.course_id)
            if course is not None:
                concept, _ = self._resolve_session_concept(
                    course=course,
                    concept_id=None,
                    learning_goal=learning_goal,
                )

        passages = (
            self._retrieve_session_passages(
                course_id=session.course_id,
                user_id=session.user_id,
                concept=concept,
                learning_goal=learning_goal,
            )
            if concept is not None
            else []
        )

        explanation, takeaways, relevant_pages = (
            self.ai_engine.generate_concise_explanation(
                concept_title=concept_title,
                question_text=question_text,
                passages=passages,
                focus_question=payload.focus_question,
            )
        )

        self.activity_service.record_explanation_for_activity(
            session=session,
            activity=target_activity,
            explanation_text=explanation,
        )

        return ExplanationResponse(
            session_id=session.id,
            activity_id=target_activity.id if target_activity else None,
            explanation=explanation,
            key_takeaways=takeaways,
            relevant_pages=relevant_pages,
        )

    def generate_next_activity(
        self,
        session_id: uuid.UUID,
        payload: NextActivityRequest,
        requesting_user_id: uuid.UUID | None = None,
    ) -> InteractiveSessionDetail:
        """Validate completion of the current question and generate the next adapted activity."""
        effective_user_id = requesting_user_id or payload.user_id
        session = self._get_owned_session(session_id, requesting_user_id=effective_user_id)

        active_activity = self.repo.get_active_activity(session.id)
        active_attempts_count = (
            len(self.repo.list_attempts_for_activity(active_activity.id))
            if active_activity is not None
            else 0
        )
        SessionStateMachine.validate_can_advance_activity(
            session, active_activity, active_attempts_count
        )

        course = self._get_owned_course(session.course_id, requesting_user_id=session.user_id)
        ctx = dict(session.context_data or {})
        learning_goal = str(ctx.get("learning_goal") or f"Master {course.title}")
        target_difficulty = str(ctx.get("current_difficulty") or "INTERMEDIATE")

        effective_concept_id = payload.target_concept_id or session.current_concept_id
        concept, resolved_goal = self._resolve_session_concept(
            course=course,
            concept_id=effective_concept_id,
            learning_goal=learning_goal,
        )
        if payload.target_concept_id is not None and session.current_concept_id != concept.id:
            session.current_concept_id = concept.id
            ctx["concept_title"] = concept.title
            ctx["concept_summary"] = concept.summary

        raw_coach = ctx.get("coach_recommendation")
        coach_rec: CoachRecommendation | None = None
        if isinstance(raw_coach, dict):
            try:
                coach_rec = CoachRecommendation.model_validate(raw_coach)
            except Exception:
                coach_rec = None

        requested_activity_type: str | None = payload.requested_activity_type
        if requested_activity_type is not None:
            if requested_activity_type == "EASIER_PRACTICE":
                target_difficulty = "BASIC"
            elif requested_activity_type in {"HARDER_PRACTICE", "TRANSFER_QUESTION"}:
                target_difficulty = "ADVANCED"
            elif coach_rec is not None:
                for alt in coach_rec.alternative_activities:
                    if alt.activity_type == requested_activity_type:
                        target_difficulty = alt.difficulty
                        break
        elif coach_rec is not None:
            requested_activity_type = coach_rec.recommended_activity
            target_difficulty = coach_rec.difficulty or target_difficulty

        ctx["current_difficulty"] = target_difficulty
        session.context_data = ctx
        flag_modified(session, "context_data")

        passages = self._retrieve_session_passages(
            course_id=course.id,
            user_id=session.user_id,
            concept=concept,
            learning_goal=resolved_goal,
        )

        self.activity_service.generate_and_persist_activity(
            session=session,
            concept_id=concept.id,
            concept_title=concept.title,
            concept_summary=concept.summary,
            learning_goal=resolved_goal,
            difficulty=target_difficulty,
            is_diagnostic=(requested_activity_type == "DIAGNOSTIC_QUESTION"),
            passages=passages,
            requested_activity_type=requested_activity_type,
        )

        session.state = "QUESTIONING"
        self.repo.save_session(session)

        return self.get_interactive_session(
            session.id, requesting_user_id=session.user_id, auto_resume=False
        )

    def end_session(
        self,
        session_id: uuid.UUID,
        payload: EndSessionRequest,
        requesting_user_id: uuid.UUID | None = None,
    ) -> InteractiveSessionDetail:
        """Complete the study session and generate a structured learning summary."""
        effective_user_id = requesting_user_id or payload.user_id
        session = self._get_owned_session(session_id, requesting_user_id=effective_user_id)
        SessionStateMachine.validate_can_end_session(session)

        activities = self.repo.list_activities_for_session(session.id)
        for act in activities:
            if act.status == "ACTIVE":
                attempts = self.repo.list_attempts_for_activity(act.id)
                act.status = "COMPLETED" if attempts else "SKIPPED"
                self.repo.save_activity(act)

        history_items = [
            self.activity_service.build_activity_history_item(session, act)
            for act in activities
        ]

        completed_items = [h for h in history_items if h.status == "COMPLETED"]
        total_attempts = sum(len(h.attempts) for h in history_items)
        scores = [
            att.evaluation.total_score
            for h in history_items
            for att in h.attempts
            if att.evaluation is not None
        ]
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0

        pages_reviewed = sorted(
            {p for h in history_items for p in h.relevant_pages}
        )

        strengths: list[str] = []
        gaps: list[str] = []
        for h in history_items:
            for att in h.attempts:
                if att.evaluation is not None:
                    for s in att.evaluation.strengths_json:
                        if s not in strengths:
                            strengths.append(s)
                    for g in att.evaluation.gaps_json:
                        if g not in gaps:
                            gaps.append(g)

        ctx = dict(session.context_data or {})
        concept_title = str(ctx.get("concept_title") or "Course Concept")
        learning_goal = str(ctx.get("learning_goal") or f"Master {concept_title}")
        hints_used_count = int(ctx.get("total_hints_used") or 0)
        explanations_count = int(ctx.get("explanations_requested_count") or 0)

        if not strengths:
            strengths = [
                f"Initiated guided study on {concept_title}."
            ]
        if not gaps:
            gaps = (
                ["Complete at least one practice question to identify specific knowledge gaps."]
                if not completed_items
                else ["Continue practicing advanced scenario questions to solidify retention."]
            )

        key_takeaways = [
            f"Completed {len(completed_items)} of {len(history_items)} activity prompt(s) on '{concept_title}' with an average score of {avg_score}/100.",
            (
                f"Grounded study across course PDF page(s): {', '.join(map(str, pages_reviewed))}."
                if pages_reviewed
                else f"Focused on learning goal: {learning_goal}."
            ),
        ]

        if avg_score >= 80.0:
            next_steps = (
                f"Excellent command of {concept_title} ({avg_score}/100)! "
                f"Start a new session on the next course concept or challenge yourself with ADVANCED application questions."
            )
        elif avg_score >= 50.0:
            next_steps = (
                f"Solid foundation in {concept_title} ({avg_score}/100). "
                f"Review pages {pages_reviewed or [1]} focusing on: {gaps[0]}"
            )
        else:
            next_steps = (
                f"Re-read the course notes for {concept_title} (pages {pages_reviewed or [1]}) "
                f"and start another diagnostic session to practice step-by-step causal reasoning."
            )

        summary = SessionSummaryData(
            total_activities=len(history_items),
            completed_activities=len(completed_items),
            total_attempts=total_attempts,
            hints_used_count=hints_used_count,
            explanations_requested_count=explanations_count,
            average_score=avg_score,
            concept_title=concept_title,
            learning_goal=learning_goal,
            pages_reviewed=pages_reviewed,
            strengths=strengths[:4],
            areas_for_improvement=gaps[:4],
            key_takeaways=key_takeaways,
            recommended_next_steps=next_steps,
        )

        ctx["summary"] = summary.model_dump(mode="json")
        session.context_data = ctx
        session.state = "COMPLETED"
        session.completed_at = datetime.now(timezone.utc)
        flag_modified(session, "context_data")
        self.repo.save_session(session)

        return self.get_interactive_session(
            session.id, requesting_user_id=session.user_id, auto_resume=False
        )
