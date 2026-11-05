"""User CRUD API routes."""
import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.exceptions import OwnershipViolationError
from app.db.session import get_db
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


def _verify_user_self_access(request: Request, target_user_id: uuid.UUID) -> None:
    auth_uid = getattr(request.state, "auth_user_id", None)
    if auth_uid is not None and str(auth_uid).lower() != str(target_user_id).lower():
        raise OwnershipViolationError("Cannot access or modify another user's profile.")


@router.get(
    "/default",
    response_model=UserRead,
    summary="Get or initialize default local student user",
)
def get_default_user(db: Session = Depends(get_db)) -> UserRead:
    """Return the default student profile for local single-user workspace mode."""
    service = UserService(db)
    user = service.get_or_create_default_user()
    return UserRead.model_validate(user)


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
)
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> UserRead:
    """Register a new user account without exposing password hashes."""
    service = UserService(db)
    user = service.create_user(payload)
    return UserRead.model_validate(user)


@router.get(
    "/{user_id}",
    response_model=UserRead,
    summary="Get user by ID",
)
def get_user(
    user_id: uuid.UUID, request: Request, db: Session = Depends(get_db)
) -> UserRead:
    """Retrieve a user profile by UUID."""
    _verify_user_self_access(request, user_id)
    service = UserService(db)
    user = service.get_user(user_id)
    return UserRead.model_validate(user)


@router.patch(
    "/{user_id}",
    response_model=UserRead,
    summary="Update user profile",
)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
) -> UserRead:
    """Update a user's mutable profile fields."""
    _verify_user_self_access(request, user_id)
    service = UserService(db)
    user = service.update_user(user_id, payload)
    return UserRead.model_validate(user)
