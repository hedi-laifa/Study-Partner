"""API routes for Phase 7 Adaptive Learning, Concept Progress, and Learning Profile."""

from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.exceptions import EntityNotFoundError, OwnershipViolationError
from app.db.session import get_db
from app.learning.coach_service import LearningCoachService
from app.models.course import Concept, Course
from app.schemas.learning import (
    ConceptLearningProfileItem,
    ConceptMapNode,
    CourseLearningProfile,
    RevisionRecommendationItem,
    RevisionTaskRead,
    RevisionTaskUpdate,
)
from app.services.user_service import UserService

router = APIRouter(tags=["Adaptive Learning & Progress"])


def _resolve_user_id(db: Session, user_id: uuid.UUID | None) -> uuid.UUID:
    if user_id is not None:
        return user_id
    return UserService(db).get_or_create_default_user().id


@router.get(
    "/courses/{course_id}/learning-profile",
    response_model=CourseLearningProfile,
    summary="Retrieve the complete Phase 7 Learning Profile for a course",
)
def get_course_learning_profile(
    course_id: uuid.UUID,
    user_id: uuid.UUID | None = Query(
        default=None, description="Optional owner user UUID"
    ),
    db: Session = Depends(get_db),
) -> CourseLearningProfile:
    """Return concept progress, evidence status, uncertainty, recent activity, strengths, gaps, and revision tasks."""
    effective_user_id = _resolve_user_id(db, user_id)
    coach = LearningCoachService(db)
    return coach.progress_service.build_course_learning_profile(
        course_id=course_id,
        user_id=effective_user_id,
    )


@router.get(
    "/courses/{course_id}/concepts/{concept_id}/progress",
    response_model=ConceptLearningProfileItem,
    summary="Retrieve concept progress, evidence history, and Learning Coach recommendation for a single concept",
)
def get_concept_learning_progress(
    course_id: uuid.UUID,
    concept_id: uuid.UUID,
    user_id: uuid.UUID | None = Query(
        default=None, description="Optional owner user UUID"
    ),
    db: Session = Depends(get_db),
) -> ConceptLearningProfileItem:
    """Return detailed ConceptLearningProfileItem including recent evidence and CoachRecommendation."""
    effective_user_id = _resolve_user_id(db, user_id)
    course = db.get(Course, course_id)
    if course is None:
        raise EntityNotFoundError("Course", course_id)
    if course.user_id != effective_user_id:
        raise OwnershipViolationError("Course belongs to a different user.")

    concept = db.get(Concept, concept_id)
    if concept is None or concept.course_id != course_id:
        raise EntityNotFoundError("Concept", concept_id)

    coach = LearningCoachService(db)
    return coach.progress_service.build_concept_learning_profile_item(
        user_id=effective_user_id,
        concept=concept,
    )


@router.get(
    "/courses/{course_id}/concept-map",
    response_model=list[ConceptMapNode],
    summary="Retrieve the prerequisite/dependent concept graph with mastery and evidence statuses",
)
def get_course_concept_map(
    course_id: uuid.UUID,
    user_id: uuid.UUID | None = Query(
        default=None, description="Optional owner user UUID"
    ),
    db: Session = Depends(get_db),
) -> list[ConceptMapNode]:
    """Return the course concept map enriched with student mastery and evidence status."""
    effective_user_id = _resolve_user_id(db, user_id)
    coach = LearningCoachService(db)
    profile = coach.progress_service.build_course_learning_profile(
        course_id=course_id,
        user_id=effective_user_id,
    )
    return profile.concept_map


@router.get(
    "/courses/{course_id}/revision-recommendations",
    response_model=list[RevisionRecommendationItem],
    summary="Retrieve revision recommendations and spaced-review tasks for a course",
)
def list_course_revision_recommendations(
    course_id: uuid.UUID,
    user_id: uuid.UUID | None = Query(
        default=None, description="Optional owner user UUID"
    ),
    db: Session = Depends(get_db),
) -> list[RevisionRecommendationItem]:
    """Return prioritized revision and spaced-review recommendations for the student."""
    effective_user_id = _resolve_user_id(db, user_id)
    coach = LearningCoachService(db)
    profile = coach.progress_service.build_course_learning_profile(
        course_id=course_id,
        user_id=effective_user_id,
    )
    return profile.revision_recommendations


@router.patch(
    "/revision-tasks/{task_id}",
    response_model=RevisionTaskRead,
    summary="Update a revision recommendation task status (e.g. COMPLETED or DISMISSED)",
)
def update_revision_task(
    task_id: uuid.UUID,
    payload: RevisionTaskUpdate,
    user_id: uuid.UUID | None = Query(
        default=None, description="Optional owner user UUID"
    ),
    db: Session = Depends(get_db),
) -> RevisionTaskRead:
    """Update a RevisionTask's status or priority."""
    effective_user_id = _resolve_user_id(db, user_id)
    coach = LearningCoachService(db)
    updated = coach.progress_service.update_revision_task_status(
        task_id=task_id,
        payload=payload,
        requesting_user_id=effective_user_id,
    )
    return RevisionTaskRead.model_validate(updated)
