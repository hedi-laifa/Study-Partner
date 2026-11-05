"""Deterministic Python state machine for StudySession transitions and difficulty adaptation."""

from __future__ import annotations

from fastapi import status

from app.core.exceptions import AppException
from app.models.session import Activity, StudySession

DIFFICULTY_LEVELS: tuple[str, ...] = ("BASIC", "INTERMEDIATE", "ADVANCED")


class InvalidSessionStateError(AppException):
    """Raised when an invalid StudySession or Activity state transition is attempted."""

    def __init__(self, detail: str) -> None:
        super().__init__(
            detail=detail,
            error_code="INVALID_SESSION_STATE",
            status_code=status.HTTP_409_CONFLICT,
        )


class SessionStateMachine:
    """Enforces valid StudySession and Activity state transitions and difficulty adaptation."""

    @staticmethod
    def validate_session_not_completed(session: StudySession, action: str) -> None:
        """Raise InvalidSessionStateError if the session has already ended."""
        if session.state == "COMPLETED" or session.completed_at is not None:
            raise InvalidSessionStateError(
                f"Cannot {action} because study session '{session.id}' is already COMPLETED."
            )

    @classmethod
    def validate_can_submit_answer(
        cls,
        session: StudySession,
        active_activity: Activity | None,
    ) -> Activity:
        """Verify the session has an active unanswered question ready for submission."""
        cls.validate_session_not_completed(session, "submit an answer")
        if active_activity is None or active_activity.status != "ACTIVE":
            raise InvalidSessionStateError(
                "There is no active question awaiting an answer in this study session. "
                "Generate the next activity or end the session."
            )
        return active_activity

    @classmethod
    def validate_can_request_hint(
        cls,
        session: StudySession,
        active_activity: Activity | None,
    ) -> Activity:
        """Verify a hint can be requested for the current active question."""
        cls.validate_session_not_completed(session, "request a hint")
        if active_activity is None or active_activity.status != "ACTIVE":
            raise InvalidSessionStateError(
                "Hints can only be requested while a question is actively awaiting your answer."
            )
        return active_activity

    @classmethod
    def validate_can_request_explanation(cls, session: StudySession) -> None:
        """Verify a concept/question explanation can be requested in the current session."""
        cls.validate_session_not_completed(session, "request an explanation")

    @classmethod
    def validate_can_advance_activity(
        cls,
        session: StudySession,
        active_activity: Activity | None,
        active_attempts_count: int,
    ) -> None:
        """Verify the student has completed the current question before generating the next activity."""
        cls.validate_session_not_completed(session, "generate the next activity")
        if active_activity is not None and active_activity.status == "ACTIVE" and active_attempts_count == 0:
            raise InvalidSessionStateError(
                "Please submit your answer and reasoning for the current question before advancing to the next activity."
            )

    @classmethod
    def validate_can_end_session(cls, session: StudySession) -> None:
        """Verify the session can be ended."""
        cls.validate_session_not_completed(session, "end the session")

    @staticmethod
    def compute_next_difficulty(
        current_difficulty: str,
        last_score: float | None,
    ) -> str:
        """Adapt question difficulty based on student performance on the previous question."""
        normalized = current_difficulty.upper() if current_difficulty else "INTERMEDIATE"
        if normalized not in DIFFICULTY_LEVELS:
            normalized = "INTERMEDIATE"
        idx = DIFFICULTY_LEVELS.index(normalized)

        if last_score is None:
            return normalized
        if last_score >= 80.0 and idx < len(DIFFICULTY_LEVELS) - 1:
            return DIFFICULTY_LEVELS[idx + 1]
        if last_score < 50.0 and idx > 0:
            return DIFFICULTY_LEVELS[idx - 1]
        return normalized
