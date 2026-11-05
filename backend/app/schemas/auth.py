"""Pydantic schemas for authentication."""
from pydantic import BaseModel, Field

from app.schemas.user import UserRead


class LoginRequest(BaseModel):
    """Email/password login payload."""

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    """Access token plus the authenticated user profile."""

    access_token: str
    token_type: str = "bearer"
    expires_at: int
    user: UserRead
