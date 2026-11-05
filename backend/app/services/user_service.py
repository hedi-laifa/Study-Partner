"""CRUD service for User accounts."""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, EntityNotFoundError
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.utils.security import hash_password

DEFAULT_STUDENT_EMAIL = "student@studypartner.local"
DEFAULT_STUDENT_NAME = "University Student"


class UserService:
    """Encapsulates User persistence operations."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_user(self, payload: UserCreate) -> User:
        """Create a new user after checking for email uniqueness and hashing password."""
        normalized_email = payload.email.strip().lower()
        existing = self.get_user_by_email(normalized_email)
        if existing is not None:
            raise ConflictError(f"User with email '{normalized_email}' already exists.")

        user = User(
            email=normalized_email,
            full_name=payload.full_name.strip(),
            password_hash=hash_password(payload.password),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_or_create_default_user(self) -> User:
        """Retrieve or initialize the default local student profile for single-user workspace mode."""
        existing = self.get_user_by_email(DEFAULT_STUDENT_EMAIL)
        if existing is not None:
            return existing
        user = User(
            email=DEFAULT_STUDENT_EMAIL,
            full_name=DEFAULT_STUDENT_NAME,
            password_hash=hash_password("LocalStudentDefaultPass123!"),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_user(self, user_id: uuid.UUID) -> User:
        """Retrieve a User by UUID or raise EntityNotFoundError."""
        user = self.db.get(User, user_id)
        if user is None:
            raise EntityNotFoundError("User", user_id)
        return user

    def get_user_by_email(self, email: str) -> User | None:
        """Retrieve a User by email address if present."""
        stmt = select(User).where(User.email == email.strip().lower())
        return self.db.scalars(stmt).first()

    def update_user(self, user_id: uuid.UUID, payload: UserUpdate) -> User:
        """Update mutable user profile attributes."""
        user = self.get_user(user_id)
        if payload.full_name is not None:
            user.full_name = payload.full_name.strip()
        if payload.is_active is not None:
            user.is_active = payload.is_active
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete_user(self, user_id: uuid.UUID) -> None:
        """Delete a user and cascade to owned entities."""
        user = self.get_user(user_id)
        self.db.delete(user)
        self.db.commit()
