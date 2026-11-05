"""Repository layer for StudySession, Activity, Attempt, Evaluation, and Concept persistence."""

from __future__ import annotations

import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course import ChunkMetadata, Concept, Course, Document
from app.models.session import Activity, Attempt, Evaluation, StudySession


class SessionRepository:
    """Data access repository isolating SQLAlchemy queries for interactive study sessions."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Course & Concept queries
    # ------------------------------------------------------------------
    def get_course(self, course_id: uuid.UUID) -> Course | None:
        """Fetch a Course by primary key."""
        return self.db.get(Course, course_id)

    def get_concept(self, concept_id: uuid.UUID) -> Concept | None:
        """Fetch a Concept by primary key."""
        return self.db.get(Concept, concept_id)

    def list_concepts_for_course(self, course_id: uuid.UUID) -> list[Concept]:
        """List all concepts belonging to a course ordered by display_order."""
        stmt = (
            select(Concept)
            .where(Concept.course_id == course_id)
            .order_by(Concept.display_order.asc(), Concept.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def create_concept(
        self,
        *,
        course_id: uuid.UUID,
        title: str,
        summary: str,
        difficulty: str = "INTERMEDIATE",
        display_order: int = 0,
        source_document_id: uuid.UUID | None = None,
        source_pages: list[int] | None = None,
    ) -> Concept:
        """Create and persist a Concept entity."""
        concept = Concept(
            course_id=course_id,
            source_document_id=source_document_id,
            title=title.strip(),
            summary=summary.strip(),
            difficulty=difficulty,
            display_order=display_order,
            source_pages=source_pages or [],
        )
        self.db.add(concept)
        self.db.commit()
        self.db.refresh(concept)
        return concept

    def ensure_course_concepts_from_chunks(self, course_id: uuid.UUID) -> list[Concept]:
        """Ensure a course with ingested chunks has selectable Concepts derived from document sections."""
        existing = self.list_concepts_for_course(course_id)
        if existing:
            return existing

        stmt = (
            select(ChunkMetadata)
            .join(Document, ChunkMetadata.document_id == Document.id)
            .where(
                ChunkMetadata.course_id == course_id,
                Document.status == "READY",
            )
            .order_by(Document.created_at.asc(), ChunkMetadata.chunk_index.asc())
        )
        chunks = list(self.db.scalars(stmt).all())
        if not chunks:
            return []

        created: list[Concept] = []
        seen_titles: set[str] = set()
        for idx, chunk in enumerate(chunks):
            raw_title = (chunk.section_title or "").strip()
            if not raw_title:
                first_line = chunk.chunk_text.strip().splitlines()[0].strip()
                raw_title = first_line[:80] if first_line else f"Core Topic {idx + 1}"
            norm_title = raw_title.lower()
            if norm_title in seen_titles:
                continue
            seen_titles.add(norm_title)

            pages: list[int] = []
            if chunk.page_start is not None:
                end_p = chunk.page_end or chunk.page_start
                pages = list(range(chunk.page_start, end_p + 1))

            summary_snippet = chunk.chunk_text.strip().replace("\n", " ")
            if len(summary_snippet) > 220:
                summary_snippet = summary_snippet[:217].rstrip() + "..."

            concept = Concept(
                course_id=course_id,
                source_document_id=chunk.document_id,
                title=raw_title[:255],
                summary=summary_snippet,
                difficulty="INTERMEDIATE",
                display_order=len(created),
                source_pages=pages,
            )
            self.db.add(concept)
            created.append(concept)
            if len(created) >= 8:
                break

        if created:
            self.db.commit()
            for c in created:
                self.db.refresh(c)
        return created

    # ------------------------------------------------------------------
    # StudySession queries
    # ------------------------------------------------------------------
    def create_session(
        self,
        *,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        current_concept_id: uuid.UUID | None,
        state: str,
        context_data: dict,
    ) -> StudySession:
        """Persist a new StudySession."""
        session = StudySession(
            user_id=user_id,
            course_id=course_id,
            current_concept_id=current_concept_id,
            state=state,
            context_data=context_data,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_session(self, session_id: uuid.UUID) -> StudySession | None:
        """Fetch a StudySession by primary key."""
        return self.db.get(StudySession, session_id)

    def save_session(self, session: StudySession) -> StudySession:
        """Commit updates to a StudySession instance."""
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def list_sessions_for_course(
        self, course_id: uuid.UUID, user_id: uuid.UUID | None = None
    ) -> list[StudySession]:
        """List all study sessions for a course ordered by most recently updated."""
        stmt = select(StudySession).where(StudySession.course_id == course_id)
        if user_id is not None:
            stmt = stmt.where(StudySession.user_id == user_id)
        stmt = stmt.order_by(StudySession.updated_at.desc(), StudySession.started_at.desc())
        return list(self.db.scalars(stmt).all())

    # ------------------------------------------------------------------
    # Activity queries
    # ------------------------------------------------------------------
    def create_activity(
        self,
        *,
        session_id: uuid.UUID,
        concept_id: uuid.UUID,
        activity_type: str,
        difficulty: str,
        prompt_text: str,
        rubric_json: list[dict],
        ideal_answer_summary: str | None,
        source_chunk_ids: list[str],
        status: str,
        order_index: int,
    ) -> Activity:
        """Persist a new Activity record."""
        activity = Activity(
            session_id=session_id,
            concept_id=concept_id,
            activity_type=activity_type,
            difficulty=difficulty,
            prompt_text=prompt_text,
            rubric_json=rubric_json,
            ideal_answer_summary=ideal_answer_summary,
            source_chunk_ids=source_chunk_ids,
            status=status,
            order_index=order_index,
        )
        self.db.add(activity)
        self.db.commit()
        self.db.refresh(activity)
        return activity

    def get_activity(self, activity_id: uuid.UUID) -> Activity | None:
        """Fetch an Activity by primary key."""
        return self.db.get(Activity, activity_id)

    def save_activity(self, activity: Activity) -> Activity:
        """Commit updates to an Activity instance."""
        self.db.add(activity)
        self.db.commit()
        self.db.refresh(activity)
        return activity

    def list_activities_for_session(self, session_id: uuid.UUID) -> list[Activity]:
        """List all activities in a StudySession ordered by order_index."""
        stmt = (
            select(Activity)
            .where(Activity.session_id == session_id)
            .order_by(Activity.order_index.asc(), Activity.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def get_active_activity(self, session_id: uuid.UUID) -> Activity | None:
        """Return the currently ACTIVE activity for a session, or the latest activity if in FEEDBACK_READY."""
        stmt = (
            select(Activity)
            .where(Activity.session_id == session_id, Activity.status == "ACTIVE")
            .order_by(Activity.order_index.desc())
        )
        return self.db.scalars(stmt).first()

    # ------------------------------------------------------------------
    # Attempt & Evaluation queries
    # ------------------------------------------------------------------
    def list_attempts_for_activity(self, activity_id: uuid.UUID) -> list[Attempt]:
        """Return all historical attempts for an activity ordered chronologically."""
        stmt = (
            select(Attempt)
            .where(Attempt.activity_id == activity_id)
            .order_by(Attempt.attempt_number.asc(), Attempt.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def create_attempt(
        self,
        *,
        activity_id: uuid.UUID,
        user_id: uuid.UUID,
        attempt_number: int,
        response_text: str,
        time_spent_seconds: int | None = None,
    ) -> Attempt:
        """Persist an immutable student Attempt."""
        attempt = Attempt(
            activity_id=activity_id,
            user_id=user_id,
            attempt_number=attempt_number,
            response_text=response_text,
            time_spent_seconds=time_spent_seconds,
        )
        self.db.add(attempt)
        self.db.commit()
        self.db.refresh(attempt)
        return attempt

    def list_evaluations_for_attempt(self, attempt_id: uuid.UUID) -> list[Evaluation]:
        """Return all evaluations for an attempt ordered chronologically."""
        stmt = (
            select(Evaluation)
            .where(Evaluation.attempt_id == attempt_id)
            .order_by(Evaluation.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def create_evaluation(
        self,
        *,
        attempt_id: uuid.UUID,
        concept_id: uuid.UUID | None = None,
        verdict: str = "INCORRECT",
        total_score: float,
        max_score: float,
        passed: bool,
        criteria_scores_json: list[dict],
        strengths_json: list[str],
        gaps_json: list[str],
        misconception: str | None = None,
        evidence_json: list[str] | None = None,
        confidence: float = 0.85,
        next_activity: str | None = None,
        error_classification: str = "NONE",
        uncertain_evaluation: bool = False,
        prompt_version: str | None = None,
        overall_feedback: str,
        evaluator_model: str | None,
        coach_action: str | None,
    ) -> Evaluation:
        """Persist an Evaluation record for an Attempt."""
        evaluation = Evaluation(
            attempt_id=attempt_id,
            concept_id=concept_id,
            verdict=verdict,
            total_score=total_score,
            max_score=max_score,
            passed=passed,
            criteria_scores_json=criteria_scores_json,
            strengths_json=strengths_json,
            gaps_json=gaps_json,
            misconception=misconception,
            evidence_json=evidence_json or [],
            confidence=confidence,
            next_activity=next_activity,
            error_classification=error_classification,
            uncertain_evaluation=uncertain_evaluation,
            prompt_version=prompt_version,
            overall_feedback=overall_feedback,
            evaluator_model=evaluator_model,
            coach_action=coach_action,
        )
        self.db.add(evaluation)
        self.db.commit()
        self.db.refresh(evaluation)
        return evaluation
