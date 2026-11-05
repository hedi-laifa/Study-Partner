"""Authentication routes: register, login, current user."""
import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppException
from app.core.tokens import create_access_token
from app.db.session import get_db
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserCreate, UserRead
from app.services.user_service import UserService
from app.utils.security import hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Used to equalize timing when the account does not exist.
_DUMMY_HASH = hash_password("not-a-real-password")


def _issue(user) -> TokenResponse:
    token, expires_at = create_access_token(
        user.id,
        secret=settings.AUTH_SECRET_KEY,
        ttl_seconds=settings.AUTH_TOKEN_TTL_MINUTES * 60,
    )
    return TokenResponse(
        access_token=token, expires_at=expires_at, user=UserRead.model_validate(user)
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new student account and sign in",
)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> TokenResponse:
    user = UserService(db).create_user(payload)
    return _issue(user)


@router.post("/login", response_model=TokenResponse, summary="Sign in with email and password")
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = UserService(db).get_user_by_email(payload.email)
    stored = user.password_hash if user is not None else _DUMMY_HASH
    valid = verify_password(payload.password, stored)
    if user is None or not valid or not user.is_active:
        raise AppException(
            "Invalid email or password.", "INVALID_CREDENTIALS", status.HTTP_401_UNAUTHORIZED
        )
    return _issue(user)


@router.get("/me", response_model=UserRead, summary="Get the authenticated user")
def me(request: Request, db: Session = Depends(get_db)) -> UserRead:
    subject = getattr(request.state, "auth_user_id", None)
    if subject is None:
        raise AppException(
            "Authentication is required. Please sign in.",
            "AUTH_REQUIRED",
            status.HTTP_401_UNAUTHORIZED,
        )
    return UserRead.model_validate(UserService(db).get_user(uuid.UUID(subject)))
