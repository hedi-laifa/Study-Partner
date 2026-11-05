"""API routes for Phase 5 Interactive Study Sessions."""

from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.assessment import ActivityRubric
from app.schemas.session import (
    AnswerSubmissionRequest,
    AnswerSubmissionResponse,
    EndSessionRequest,
    ExplanationRequest,
    ExplanationResponse,
    HintRequest,
    HintResponse,
    InteractiveSessionDetail,
    InteractiveSessionStartRequest,
    NextActivityRequest,
)
from app.services.study_session_service import StudySessionService

router = APIRouter(prefix="/sessions", tags=["Study Sessions"])


@router.post(
    "",
    response_model=InteractiveSessionDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new interactive study session",
)
def start_study_session(
    payload: InteractiveSessionStartRequest,
    user_id: uuid.UUID | None = Query(
        default=None, description="Optional owner user UUID"
    ),
    db: Session = Depends(get_db),
) -> InteractiveSessionDetail:
    """Create a StudySession for a course and concept/goal and generate the diagnostic question."""
    service = StudySessionService(db)
    return service.start_interactive_session(
        payload=payload,
        requesting_user_id=user_id or payload.user_id,
    )


@router.get(
    "/{session_id}",
    response_model=InteractiveSessionDetail,
    summary="Retrieve an interactive study session",
)
def get_study_session(
    session_id: uuid.UUID,
    user_id: uuid.UUID | None = Query(
        default=None, description="Optional owner user UUID"
    ),
    db: Session = Depends(get_db),
) -> InteractiveSessionDetail:
    """Retrieve full session state, current question, activity history, progress, and summary."""
    service = StudySessionService(db)
    return service.get_interactive_session(
        session_id=session_id,
        requesting_user_id=user_id,
        auto_resume=True,
    )


@router.post(
    "/{session_id}/resume",
    response_model=InteractiveSessionDetail,
    summary="Resume an interrupted interactive study session",
)
def resume_study_session(
    session_id: uuid.UUID,
    user_id: uuid.UUID | None = Query(
        default=None, description="Optional owner user UUID"
    ),
    db: Session = Depends(get_db),
) -> InteractiveSessionDetail:
    """Resume an interrupted session, restoring or initializing its active question state."""
    service = StudySessionService(db)
    return service.get_interactive_session(
        session_id=session_id,
        requesting_user_id=user_id,
        auto_resume=True,
    )


@router.post(
    "/{session_id}/submit-answer",
    response_model=AnswerSubmissionResponse,
    summary="Submit a student answer to the current study session question",
)
def submit_session_answer(
    session_id: uuid.UUID,
    payload: AnswerSubmissionRequest,
    user_id: uuid.UUID | None = Query(
        default=None, description="Optional owner user UUID"
    ),
    db: Session = Depends(get_db),
) -> AnswerSubmissionResponse:
    """Persist student attempt (with duplicate request protection), evaluate reasoning, and return feedback."""
    service = StudySessionService(db)
    return service.submit_answer(
        session_id=session_id,
        payload=payload,
        requesting_user_id=user_id or payload.user_id,
    )


@router.post(
    "/{session_id}/hint",
    response_model=HintResponse,
    summary="Request the next graduated hint for the current question",
)
def request_session_hint(
    session_id: uuid.UUID,
    payload: HintRequest | None = None,
    user_id: uuid.UUID | None = Query(
        default=None, description="Optional owner user UUID"
    ),
    db: Session = Depends(get_db),
) -> HintResponse:
    """Reveal the next graduated hint (Level 1, 2, or 3) for the active question."""
    req_payload = payload or HintRequest()
    service = StudySessionService(db)
    return service.request_hint(
        session_id=session_id,
        payload=req_payload,
        requesting_user_id=user_id or req_payload.user_id,
    )


@router.post(
    "/{session_id}/explain",
    response_model=ExplanationResponse,
    summary="Request a concise grounded concept explanation",
)
def request_session_explanation(
    session_id: uuid.UUID,
    payload: ExplanationRequest | None = None,
    user_id: uuid.UUID | None = Query(
        default=None, description="Optional owner user UUID"
    ),
    db: Session = Depends(get_db),
) -> ExplanationResponse:
    """Generate a concise course-grounded explanation with page citations."""
    req_payload = payload or ExplanationRequest()
    service = StudySessionService(db)
    return service.request_explanation(
        session_id=session_id,
        payload=req_payload,
        requesting_user_id=user_id or req_payload.user_id,
    )


@router.post(
    "/{session_id}/next-activity",
    response_model=InteractiveSessionDetail,
    summary="Advance to the next adapted activity in the study session",
)
def next_session_activity(
    session_id: uuid.UUID,
    payload: NextActivityRequest | None = None,
    user_id: uuid.UUID | None = Query(
        default=None, description="Optional owner user UUID"
    ),
    db: Session = Depends(get_db),
) -> InteractiveSessionDetail:
    """Validate completion of the current question and generate the next difficulty-adapted question."""
    req_payload = payload or NextActivityRequest()
    service = StudySessionService(db)
    return service.generate_next_activity(
        session_id=session_id,
        payload=req_payload,
        requesting_user_id=user_id or req_payload.user_id,
    )


@router.post(
    "/{session_id}/end",
    response_model=InteractiveSessionDetail,
    summary="End the study session and generate a learning summary",
)
def end_study_session(
    session_id: uuid.UUID,
    payload: EndSessionRequest | None = None,
    user_id: uuid.UUID | None = Query(
        default=None, description="Optional owner user UUID"
    ),
    db: Session = Depends(get_db),
) -> InteractiveSessionDetail:
    """Complete the study session and return a structured learning summary."""
    req_payload = payload or EndSessionRequest()
    service = StudySessionService(db)
    return service.end_session(
        session_id=session_id,
        payload=req_payload,
        requesting_user_id=user_id or req_payload.user_id,
    )


@router.get(
    "/{session_id}/activities/{activity_id}/rubric",
    response_model=ActivityRubric,
    summary="Retrieve the explicit grading rubric for an activity",
)
def get_activity_rubric(
    session_id: uuid.UUID,
    activity_id: uuid.UUID,
    user_id: uuid.UUID | None = Query(
        default=None, description="Optional owner user UUID"
    ),
    db: Session = Depends(get_db),
) -> ActivityRubric:
    """Return the explicit ActivityRubric (required ideas, criteria, misconception patterns, numeric check)."""
    service = StudySessionService(db)
    return service.get_activity_rubric(
        session_id=session_id,
        activity_id=activity_id,
        requesting_user_id=user_id,
    )
