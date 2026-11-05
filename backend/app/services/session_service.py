"""CRUD service for StudySession, Activity, Attempt, Evaluation, LearningEvidence, ConceptProgress, and RevisionTask."""
from datetime import datetime, timezone
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import EntityNotFoundError, OwnershipViolationError
from app.models.course import Concept, Course
from app.models.learning import ConceptProgress, LearningEvidence, RevisionTask
from app.models.session import Activity, Attempt, Evaluation, StudySession
from app.schemas.learning import (
    ConceptProgressCreate,
    ConceptProgressUpdate,
    LearningEvidenceCreate,
    RevisionTaskCreate,
    RevisionTaskUpdate,
)
from app.schemas.session import (
    ActivityCreate,
    AttemptCreate,
    EvaluationCreate,
    StudySessionCreate,
    StudySessionUpdate,
)


class LearningSessionService:
    """Manages persistence of study sessions, activities, immutable student attempts, evaluations, and progress."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_study_session(self, payload: StudySessionCreate) -> StudySession:
        """Start a new StudySession after verifying course ownership."""
        course = self.db.get(Course, payload.course_id)
        if course is None:
            raise EntityNotFoundError("Course", payload.course_id)
        if course.user_id != payload.user_id:
            raise OwnershipViolationError("Cannot start a session on another user's course.")

        session = StudySession(
            user_id=payload.user_id,
            course_id=payload.course_id,
            current_concept_id=payload.current_concept_id,
            state=payload.state,
            context_data=payload.context_data,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_study_session(
        self, session_id: uuid.UUID, requesting_user_id: uuid.UUID | None = None
    ) -> StudySession:
        """Retrieve a StudySession and optionally enforce ownership."""
        session = self.db.get(StudySession, session_id)
        if session is None:
            raise EntityNotFoundError("StudySession", session_id)
        if requesting_user_id is not None and session.user_id != requesting_user_id:
            raise OwnershipViolationError("StudySession belongs to a different user.")
        return session

    def update_study_session(
        self,
        session_id: uuid.UUID,
        payload: StudySessionUpdate,
        requesting_user_id: uuid.UUID | None = None,
    ) -> StudySession:
        """Update StudySession state and context."""
        session = self.get_study_session(session_id, requesting_user_id=requesting_user_id)
        if payload.current_concept_id is not None:
            session.current_concept_id = payload.current_concept_id
        if payload.state is not None:
            session.state = payload.state
        if payload.context_data is not None:
            session.context_data = payload.context_data
        if payload.completed_at is not None:
            session.completed_at = payload.completed_at
        self.db.commit()
        self.db.refresh(session)
        return session

    def create_activity(self, payload: ActivityCreate) -> Activity:
        """Create a learning or assessment Activity within a StudySession."""
        self.get_study_session(payload.session_id)
        concept = self.db.get(Concept, payload.concept_id)
        if concept is None:
            raise EntityNotFoundError("Concept", payload.concept_id)

        activity = Activity(
            session_id=payload.session_id,
            concept_id=payload.concept_id,
            activity_type=payload.activity_type,
            difficulty=payload.difficulty,
            prompt_text=payload.prompt_text,
            rubric_json=payload.rubric_json,
            ideal_answer_summary=payload.ideal_answer_summary,
            source_chunk_ids=payload.source_chunk_ids,
            status=payload.status,
            order_index=payload.order_index,
        )
        self.db.add(activity)
        self.db.commit()
        self.db.refresh(activity)
        return activity

    def record_attempt(self, payload: AttemptCreate) -> Attempt:
        """Record an immutable student Attempt, preserving all prior attempts on the Activity."""
        activity = self.db.get(Activity, payload.activity_id)
        if activity is None:
            raise EntityNotFoundError("Activity", payload.activity_id)

        session = self.get_study_session(activity.session_id)
        if session.user_id != payload.user_id:
            raise OwnershipViolationError("Cannot submit an attempt for another user's session.")

        existing_count_stmt = select(func.count(Attempt.id)).where(
            Attempt.activity_id == payload.activity_id
        )
        existing_count = self.db.scalar(existing_count_stmt) or 0
        next_attempt_number = max(payload.attempt_number, existing_count + 1)

        attempt = Attempt(
            activity_id=payload.activity_id,
            user_id=payload.user_id,
            attempt_number=next_attempt_number,
            response_text=payload.response_text,
            time_spent_seconds=payload.time_spent_seconds,
        )
        self.db.add(attempt)
        self.db.commit()
        self.db.refresh(attempt)
        return attempt

    def list_attempts_for_activity(self, activity_id: uuid.UUID) -> list[Attempt]:
        """Return all historical attempts for an activity ordered by attempt_number."""
        stmt = (
            select(Attempt)
            .where(Attempt.activity_id == activity_id)
            .order_by(Attempt.attempt_number.asc(), Attempt.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def record_evaluation(self, payload: EvaluationCreate) -> Evaluation:
        """Append a rubric Evaluation record for an Attempt (preserving evaluation history)."""
        attempt = self.db.get(Attempt, payload.attempt_id)
        if attempt is None:
            raise EntityNotFoundError("Attempt", payload.attempt_id)

        evaluation = Evaluation(
            attempt_id=payload.attempt_id,
            concept_id=payload.concept_id,
            verdict=payload.verdict,
            total_score=payload.total_score,
            max_score=payload.max_score,
            passed=payload.passed,
            criteria_scores_json=payload.criteria_scores_json,
            strengths_json=payload.strengths_json,
            gaps_json=payload.gaps_json,
            misconception=payload.misconception,
            evidence_json=payload.evidence_json,
            confidence=payload.confidence,
            next_activity=payload.next_activity,
            error_classification=payload.error_classification,
            uncertain_evaluation=payload.uncertain_evaluation,
            prompt_version=payload.prompt_version,
            overall_feedback=payload.overall_feedback,
            evaluator_model=payload.evaluator_model,
            coach_action=payload.coach_action,
        )
        self.db.add(evaluation)
        self.db.commit()
        self.db.refresh(evaluation)
        return evaluation

    def list_evaluations_for_attempt(self, attempt_id: uuid.UUID) -> list[Evaluation]:
        """Return all evaluation records for an attempt chronologically."""
        stmt = (
            select(Evaluation)
            .where(Evaluation.attempt_id == attempt_id)
            .order_by(Evaluation.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def record_learning_evidence(
        self, payload: LearningEvidenceCreate
    ) -> LearningEvidence:
        """Record a piece of learning evidence linking user performance to a concept."""
        evidence = LearningEvidence(
            user_id=payload.user_id,
            concept_id=payload.concept_id,
            evaluation_id=payload.evaluation_id,
            evidence_type=payload.evidence_type,
            score_delta=payload.score_delta,
            observed_score=payload.observed_score,
            summary=payload.summary,
            metadata_json=payload.metadata_json,
        )
        self.db.add(evidence)
        self.db.commit()
        self.db.refresh(evidence)
        return evidence

    def create_or_get_concept_progress(
        self, payload: ConceptProgressCreate
    ) -> ConceptProgress:
        """Get existing ConceptProgress for (user_id, concept_id) or create a new record."""
        stmt = select(ConceptProgress).where(
            ConceptProgress.user_id == payload.user_id,
            ConceptProgress.concept_id == payload.concept_id,
        )
        existing = self.db.scalars(stmt).first()
        if existing is not None:
            return existing

        progress = ConceptProgress(
            user_id=payload.user_id,
            course_id=payload.course_id,
            concept_id=payload.concept_id,
            mastery_score=payload.mastery_score,
            mastery_status=payload.mastery_status,
        )
        self.db.add(progress)
        self.db.commit()
        self.db.refresh(progress)
        return progress

    def update_concept_progress(
        self, progress_id: uuid.UUID, payload: ConceptProgressUpdate
    ) -> ConceptProgress:
        """Update a ConceptProgress record."""
        progress = self.db.get(ConceptProgress, progress_id)
        if progress is None:
            raise EntityNotFoundError("ConceptProgress", progress_id)

        if payload.mastery_score is not None:
            progress.mastery_score = payload.mastery_score
        if payload.mastery_status is not None:
            progress.mastery_status = payload.mastery_status
        if payload.attempts_count is not None:
            progress.attempts_count = payload.attempts_count
        if payload.correct_attempts_count is not None:
            progress.correct_attempts_count = payload.correct_attempts_count
        if payload.last_score is not None:
            progress.last_score = payload.last_score
        if payload.last_practiced_at is not None:
            progress.last_practiced_at = payload.last_practiced_at
        if payload.next_review_at is not None:
            progress.next_review_at = payload.next_review_at

        self.db.commit()
        self.db.refresh(progress)
        return progress

    def create_revision_task(self, payload: RevisionTaskCreate) -> RevisionTask:
        """Create a scheduled RevisionTask for a User and Concept."""
        task = RevisionTask(
            user_id=payload.user_id,
            course_id=payload.course_id,
            concept_id=payload.concept_id,
            source_evaluation_id=payload.source_evaluation_id,
            title=payload.title,
            reason=payload.reason,
            priority=payload.priority,
            status=payload.status,
            due_at=payload.due_at,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def update_revision_task(
        self, task_id: uuid.UUID, payload: RevisionTaskUpdate
    ) -> RevisionTask:
        """Update status or completion timestamp of a RevisionTask."""
        task = self.db.get(RevisionTask, task_id)
        if task is None:
            raise EntityNotFoundError("RevisionTask", task_id)

        if payload.priority is not None:
            task.priority = payload.priority
        if payload.status is not None:
            task.status = payload.status
            if payload.status == "COMPLETED" and payload.completed_at is None:
                task.completed_at = datetime.now(timezone.utc)
        if payload.due_at is not None:
            task.due_at = payload.due_at
        if payload.completed_at is not None:
            task.completed_at = payload.completed_at

        self.db.commit()
        self.db.refresh(task)
        return task
