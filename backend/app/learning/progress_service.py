"""Concept Progress Service & Revision Recommendation Manager for Phase 7 Adaptive Learning."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import EntityNotFoundError, OwnershipViolationError
from app.learning.concept_map_service import ConceptMapService
from app.learning.evidence_service import LearningEvidenceService
from app.learning.mastery_heuristic import (
    MasteryUpdateOutcome,
    compute_evidence_uncertainty,
)
from app.learning.routing_policy import select_next_adaptive_activity
from app.models.course import Concept, Course
from app.models.learning import ConceptProgress, RevisionTask
from app.schemas.learning import (
    CoachActivityType,
    ConceptLearningProfileItem,
    CourseLearningProfile,
    EvidenceStatus,
    LearningEvidenceRead,
    MasteryStatus,
    RecentLearningActivityItem,
    RevisionRecommendationItem,
    RevisionTaskUpdate,
)


class ConceptProgressService:
    """Manages ConceptProgress persistence, RevisionTask scheduling, and CourseLearningProfile synthesis."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.concept_map_service = ConceptMapService(db)
        self.evidence_service = LearningEvidenceService(db)

    def get_progress(
        self,
        *,
        user_id: uuid.UUID,
        concept_id: uuid.UUID,
    ) -> ConceptProgress | None:
        """Fetch existing ConceptProgress for (user_id, concept_id) without creating one."""
        stmt = select(ConceptProgress).where(
            ConceptProgress.user_id == user_id,
            ConceptProgress.concept_id == concept_id,
        )
        return self.db.scalars(stmt).first()

    def get_or_create_progress(
        self,
        *,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        concept_id: uuid.UUID,
    ) -> ConceptProgress:
        """Fetch existing ConceptProgress for (user_id, concept_id) or initialize a NOT_STARTED record."""
        stmt = select(ConceptProgress).where(
            ConceptProgress.user_id == user_id,
            ConceptProgress.concept_id == concept_id,
        )
        existing = self.db.scalars(stmt).first()
        if existing is not None:
            return existing

        progress = ConceptProgress(
            user_id=user_id,
            course_id=course_id,
            concept_id=concept_id,
            mastery_score=0.0,
            mastery_status="NOT_STARTED",
            attempts_count=0,
            correct_attempts_count=0,
        )
        self.db.add(progress)
        self.db.commit()
        self.db.refresh(progress)
        return progress

    def apply_mastery_outcome(
        self,
        *,
        progress: ConceptProgress,
        outcome: MasteryUpdateOutcome,
        observed_score: float,
        practiced_at: datetime | None = None,
    ) -> ConceptProgress:
        """Apply a deterministic MasteryUpdateOutcome to ConceptProgress."""
        ts = practiced_at or datetime.now(timezone.utc)
        progress.mastery_score = outcome.new_mastery_score
        progress.mastery_status = outcome.mastery_status
        progress.attempts_count = outcome.attempts_count
        progress.correct_attempts_count = outcome.correct_attempts_count
        progress.last_score = observed_score
        progress.last_practiced_at = ts
        progress.next_review_at = outcome.next_review_at
        self.db.add(progress)
        self.db.commit()
        self.db.refresh(progress)
        return progress

    def sync_revision_recommendations(
        self,
        *,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        concept: Concept,
        evaluation_id: uuid.UUID | None,
        verdict: str,
        hints_used: int,
        outcome: MasteryUpdateOutcome,
        gaps: list[str],
        misconception: str | None,
        now: datetime | None = None,
    ) -> RevisionTask | None:
        """Create or update RevisionTask records based on the student's evaluation pattern."""
        ts = now or datetime.now(timezone.utc)
        norm_verdict = (verdict or "INCORRECT").upper()

        stmt = (
            select(RevisionTask)
            .where(
                RevisionTask.user_id == user_id,
                RevisionTask.concept_id == concept.id,
                RevisionTask.status == "PENDING",
            )
            .order_by(RevisionTask.created_at.desc())
        )
        pending_tasks = list(self.db.scalars(stmt).all())

        # Case 1: Repeated independent success -> complete remediation tasks and schedule a future REVIEW task
        if norm_verdict == "CORRECT" and hints_used == 0 and outcome.independent_success_count >= 2:
            for t in pending_tasks:
                if "Spaced Review" not in t.title:
                    t.status = "COMPLETED"
                    t.completed_at = ts
                    self.db.add(t)

            existing_review = next(
                (t for t in pending_tasks if "Spaced Review" in t.title), None
            )
            due_date = outcome.next_review_at or (ts + timedelta(days=3))
            if existing_review is not None:
                existing_review.due_at = due_date
                existing_review.source_evaluation_id = evaluation_id
                existing_review.reason = (
                    f"Strong independent mastery ({outcome.new_mastery_score}/100). "
                    f"Scheduled spaced review to maintain long-term retention."
                )
                self.db.add(existing_review)
                self.db.commit()
                self.db.refresh(existing_review)
                return existing_review

            review_task = RevisionTask(
                user_id=user_id,
                course_id=course_id,
                concept_id=concept.id,
                source_evaluation_id=evaluation_id,
                title=f"Spaced Review: {concept.title}",
                reason=(
                    f"Strong independent mastery ({outcome.new_mastery_score}/100 across "
                    f"{outcome.independent_success_count} unassisted successes). Review in 3 days."
                ),
                priority="LOW",
                status="PENDING",
                due_at=due_date,
            )
            self.db.add(review_task)
            self.db.commit()
            self.db.refresh(review_task)
            return review_task

        # Case 2: Incorrect or Misconception -> HIGH/CRITICAL Remediation task
        if norm_verdict in {"INCORRECT", "OFF_TOPIC"} or misconception:
            priority = "CRITICAL" if misconception else "HIGH"
            title = (
                f"Resolve Misconception: {concept.title}"
                if misconception
                else f"Remediation & Easier Practice: {concept.title}"
            )
            reason = (
                f"Supported misconception detected: {misconception}"
                if misconception
                else (
                    gaps[0]
                    if gaps
                    else f"Review explanation and complete easier practice on {concept.title}."
                )
            )
            due_date = ts + timedelta(hours=4)
        # Case 3: Partial or Uncertain -> MEDIUM Targeted Hint & Retry task
        elif norm_verdict in {"PARTIALLY_CORRECT", "INSUFFICIENT_EVIDENCE"}:
            priority = "MEDIUM"
            title = f"Targeted Practice & Retry: {concept.title}"
            reason = (
                gaps[0]
                if gaps
                else f"Complete targeted hint and retry on {concept.title} to close reasoning gaps."
            )
            due_date = ts + timedelta(hours=12)
        # Case 4: Success after hints -> MEDIUM Unassisted Verification task
        elif norm_verdict == "CORRECT" and hints_used > 0:
            priority = "MEDIUM"
            title = f"Unassisted Verification: {concept.title}"
            reason = (
                f"Succeeded with {hints_used} hint(s). Complete one unassisted practice question "
                f"to confirm independent understanding."
            )
            due_date = ts + timedelta(hours=12)
        else:
            # First independent success -> LOW priority harder practice continuation
            priority = "LOW"
            title = f"Confirm Mastery (Harder Practice): {concept.title}"
            reason = (
                f"First independent success recorded ({outcome.new_mastery_score}/100). "
                f"Complete one harder practice question to confirm mastery."
            )
            due_date = ts + timedelta(days=1)

        if pending_tasks:
            active_task = pending_tasks[0]
            active_task.title = title[:255]
            active_task.reason = reason
            active_task.priority = priority
            active_task.source_evaluation_id = evaluation_id
            active_task.due_at = due_date
            self.db.add(active_task)
            self.db.commit()
            self.db.refresh(active_task)
            return active_task

        new_task = RevisionTask(
            user_id=user_id,
            course_id=course_id,
            concept_id=concept.id,
            source_evaluation_id=evaluation_id,
            title=title[:255],
            reason=reason,
            priority=priority,
            status="PENDING",
            due_at=due_date,
        )
        self.db.add(new_task)
        self.db.commit()
        self.db.refresh(new_task)
        return new_task

    def update_revision_task_status(
        self,
        *,
        task_id: uuid.UUID,
        payload: RevisionTaskUpdate,
        requesting_user_id: uuid.UUID | None = None,
    ) -> RevisionTask:
        """Update a RevisionTask's status or priority."""
        task = self.db.get(RevisionTask, task_id)
        if task is None:
            raise EntityNotFoundError("RevisionTask", task_id)
        if requesting_user_id is not None and task.user_id != requesting_user_id:
            raise OwnershipViolationError("RevisionTask belongs to a different user.")

        if payload.priority is not None:
            task.priority = payload.priority
        if payload.status is not None:
            task.status = payload.status
            if payload.status == "COMPLETED" and task.completed_at is None:
                task.completed_at = datetime.now(timezone.utc)
        if payload.due_at is not None:
            task.due_at = payload.due_at
        if payload.completed_at is not None:
            task.completed_at = payload.completed_at

        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def build_concept_learning_profile_item(
        self,
        *,
        user_id: uuid.UUID,
        concept: Concept,
        prerequisite_ids: list[uuid.UUID] | None = None,
        persist_if_missing: bool = False,
    ) -> ConceptLearningProfileItem:
        """Build a detailed ConceptLearningProfileItem with evidence history and CoachRecommendation."""
        if persist_if_missing:
            prog = self.get_or_create_progress(
                user_id=user_id,
                course_id=concept.course_id,
                concept_id=concept.id,
            )
        else:
            prog = self.get_progress(user_id=user_id, concept_id=concept.id)

        mastery_score = prog.mastery_score if prog is not None else 0.0
        mastery_status_raw = prog.mastery_status if prog is not None else "NOT_STARTED"
        attempts_count = prog.attempts_count if prog is not None else 0
        correct_attempts_count = prog.correct_attempts_count if prog is not None else 0
        last_score = prog.last_score if prog is not None else None
        last_practiced_at = prog.last_practiced_at if prog is not None else None
        next_review_at = prog.next_review_at if prog is not None else None

        evidences = self.evidence_service.list_evidence_for_concept(
            user_id=user_id,
            concept_id=concept.id,
        )
        ev_summary = self.evidence_service.summarize_evidence_history(evidences)
        recency_hours = self.evidence_service.compute_evidence_recency_hours(evidences)

        now = datetime.now(timezone.utc)
        is_due = False
        if next_review_at is not None:
            nr = (
                next_review_at
                if next_review_at.tzinfo is not None
                else next_review_at.replace(tzinfo=timezone.utc)
            )
            is_due = nr <= now and attempts_count > 0

        if not evidences:
            ev_status: EvidenceStatus = "NO_EVIDENCE"
            uncertainty = 1.0
            latest_verdict: str | None = None
            latest_hints = 0
            latest_diff = concept.difficulty or "INTERMEDIATE"
            latest_misc: str | None = None
        else:
            last_meta = dict(evidences[-1].metadata_json or {})
            ev_status = last_meta.get("evidence_status") or "EMERGING_EVIDENCE"  # type: ignore[assignment]
            if is_due and ev_status == "STRONG_INDEPENDENT_EVIDENCE":
                ev_status = "DUE_FOR_REVIEW"
            latest_conf = float(last_meta.get("confidence") or 0.85)
            latest_uncert = bool(last_meta.get("uncertain_evaluation") or False)
            uncertainty = compute_evidence_uncertainty(
                attempts_count=attempts_count,
                independent_success_count=ev_summary["independent_success_count"],
                latest_confidence=latest_conf,
                uncertain_evaluation=latest_uncert,
            )
            latest_verdict = str(last_meta.get("verdict") or "")
            latest_hints = int(last_meta.get("hints_used") or 0)
            latest_diff = str(last_meta.get("difficulty") or concept.difficulty or "INTERMEDIATE")
            latest_misc = last_meta.get("misconception")

        recommendation = select_next_adaptive_activity(
            concept_id=concept.id,
            concept_title=concept.title,
            session_goal=f"Master {concept.title}",
            attempts_count=attempts_count,
            latest_verdict=latest_verdict,
            latest_score=last_score,
            hints_used_on_latest=latest_hints,
            current_difficulty=latest_diff,
            independent_success_count=ev_summary["independent_success_count"],
            assisted_success_count=ev_summary["assisted_success_count"],
            consecutive_independent_successes=ev_summary["consecutive_independent_successes"],
            evidence_status=ev_status,
            uncertainty_score=uncertainty,
            evidence_recency_hours=recency_hours,
            is_due_for_review=is_due,
            latest_gaps=ev_summary["areas_needing_practice"],
            latest_misconception=latest_misc,
        )

        m_status: MasteryStatus = (
            mastery_status_raw  # type: ignore[assignment]
            if mastery_status_raw in {"NOT_STARTED", "NEEDS_REVIEW", "LEARNING", "MASTERED"}
            else "NOT_STARTED"
        )

        return ConceptLearningProfileItem(
            concept_id=concept.id,
            course_id=concept.course_id,
            title=concept.title,
            summary=concept.summary,
            display_order=concept.display_order,
            source_pages=list(concept.source_pages or []),
            prerequisite_concept_ids=prerequisite_ids or [],
            mastery_score=round(mastery_score, 1),
            mastery_status=m_status,
            evidence_status=ev_status,
            uncertainty_score=uncertainty,
            attempts_count=attempts_count,
            correct_attempts_count=correct_attempts_count,
            independent_success_count=ev_summary["independent_success_count"],
            assisted_success_count=ev_summary["assisted_success_count"],
            last_score=last_score,
            last_practiced_at=last_practiced_at,
            next_review_at=next_review_at,
            observed_strengths=ev_summary["observed_strengths"],
            areas_needing_practice=ev_summary["areas_needing_practice"],
            recent_evidence=[
                LearningEvidenceRead.model_validate(ev) for ev in evidences[-5:]
            ],
            recommended_next_action=recommendation,
        )

    def build_course_learning_profile(
        self,
        *,
        course_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> CourseLearningProfile:
        """Build the complete Phase 7 CourseLearningProfile for a student in a course."""
        course = self.db.get(Course, course_id)
        if course is None:
            raise EntityNotFoundError("Course", course_id)
        if course.user_id != user_id:
            raise OwnershipViolationError("Course belongs to a different user.")

        concepts = self.concept_map_service.ensure_and_list_concepts(course_id)
        concept_by_id = {c.id: c for c in concepts}

        profile_items: list[ConceptLearningProfileItem] = []
        ev_status_map: dict[uuid.UUID, EvidenceStatus] = {}
        all_strengths: list[str] = []
        all_gaps: list[str] = []

        for idx, concept in enumerate(concepts):
            prereq_ids = [concepts[idx - 1].id] if idx > 0 else []
            item = self.build_concept_learning_profile_item(
                user_id=user_id,
                concept=concept,
                prerequisite_ids=prereq_ids,
            )
            profile_items.append(item)
            ev_status_map[concept.id] = item.evidence_status
            for s in item.observed_strengths:
                if s not in all_strengths:
                    all_strengths.append(s)
            for g in item.areas_needing_practice:
                if g not in all_gaps:
                    all_gaps.append(g)

        concept_map = self.concept_map_service.build_course_concept_map(
            course_id=course_id,
            user_id=user_id,
            evidence_status_map=ev_status_map,
        )

        # Recent activity across course
        recent_rows = self.evidence_service.list_recent_evidence_for_course(
            user_id=user_id,
            course_id=course_id,
            limit=12,
        )
        recent_activity: list[RecentLearningActivityItem] = []
        for ev, conc in recent_rows:
            meta = dict(ev.metadata_json or {})
            recent_activity.append(
                RecentLearningActivityItem(
                    evidence_id=ev.id,
                    concept_id=conc.id,
                    concept_title=conc.title,
                    evidence_type=ev.evidence_type,
                    observed_score=ev.observed_score,
                    score_delta=ev.score_delta,
                    verdict=meta.get("verdict"),
                    hints_used=int(meta.get("hints_used") or 0),
                    difficulty=str(meta.get("difficulty") or "INTERMEDIATE"),
                    summary=ev.summary,
                    created_at=ev.created_at,
                )
            )

        # Revision recommendations
        rev_stmt = (
            select(RevisionTask)
            .where(
                RevisionTask.course_id == course_id,
                RevisionTask.user_id == user_id,
            )
            .order_by(RevisionTask.status.desc(), RevisionTask.created_at.desc())
        )
        rev_tasks = list(self.db.scalars(rev_stmt).all())
        revision_items: list[RevisionRecommendationItem] = []
        for task in rev_tasks:
            conc = concept_by_id.get(task.concept_id)
            c_title = conc.title if conc else "Course Concept"
            if "Misconception" in task.title or "Remediation" in task.title:
                rec_act: CoachActivityType = "EXPLANATION"
            elif "Targeted" in task.title:
                rec_act = "HINT_AND_RETRY"
            elif "Unassisted" in task.title:
                rec_act = "TARGETED_PRACTICE"
            elif "Harder" in task.title:
                rec_act = "HARDER_PRACTICE"
            else:
                rec_act = "REVIEW"

            revision_items.append(
                RevisionRecommendationItem(
                    id=task.id,
                    course_id=task.course_id,
                    concept_id=task.concept_id,
                    concept_title=c_title,
                    title=task.title,
                    reason=task.reason,
                    priority=task.priority,
                    status=task.status,
                    recommended_activity=rec_act,
                    due_at=task.due_at,
                    completed_at=task.completed_at,
                    created_at=task.created_at,
                )
            )

        total_c = len(profile_items)
        mastered_c = sum(1 for i in profile_items if i.mastery_status == "MASTERED")
        learning_c = sum(1 for i in profile_items if i.mastery_status == "LEARNING")
        review_c = sum(1 for i in profile_items if i.mastery_status == "NEEDS_REVIEW")
        not_started_c = sum(1 for i in profile_items if i.mastery_status == "NOT_STARTED")
        overall_mastery = (
            round(sum(i.mastery_score for i in profile_items) / total_c, 1)
            if total_c > 0
            else 0.0
        )
        overall_uncertainty = (
            round(sum(i.uncertainty_score for i in profile_items) / total_c, 2)
            if total_c > 0
            else 1.0
        )

        return CourseLearningProfile(
            user_id=user_id,
            course_id=course_id,
            course_title=course.title,
            total_concepts=total_c,
            mastered_concepts_count=mastered_c,
            learning_concepts_count=learning_c,
            needs_review_concepts_count=review_c,
            not_started_concepts_count=not_started_c,
            overall_mastery_score=overall_mastery,
            overall_uncertainty_score=overall_uncertainty,
            concepts=profile_items,
            concept_map=concept_map,
            recent_activity=recent_activity,
            observed_strengths=all_strengths[:6],
            areas_needing_practice=all_gaps[:6],
            revision_recommendations=revision_items,
        )
