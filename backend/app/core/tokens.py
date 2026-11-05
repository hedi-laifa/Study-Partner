"""Stateless access tokens signed with HMAC-SHA256 (stdlib only, no extra dependencies).

Token format: ``<base64url(json payload)>.<base64url(hmac_sha256(payload_b64, secret))>``
Payload claims: ``sub`` (user UUID), ``iat`` and ``exp`` (UNIX seconds), ``typ`` = ``"access"``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass


class TokenError(Exception):
    """Raised when a token is malformed, has an invalid signature, or is expired."""

    def __init__(self, detail: str, error_code: str) -> None:
        super().__init__(detail)
        self.detail = detail
        self.error_code = error_code


@dataclass(frozen=True)
class TokenClaims:
    """Validated access-token claims."""

    user_id: uuid.UUID
    issued_at: int
    expires_at: int


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def _sign(payload_segment: str, secret: str) -> str:
    digest = hmac.new(
        secret.encode("utf-8"), payload_segment.encode("ascii"), hashlib.sha256
    ).digest()
    return _b64encode(digest)


def create_access_token(
    user_id: uuid.UUID,
    *,
    secret: str,
    ttl_seconds: int,
    now: int | None = None,
) -> tuple[str, int]:
    """Create a signed access token and return ``(token, expires_at_unix)``."""
    issued_at = int(now if now is not None else time.time())
    expires_at = issued_at + int(ttl_seconds)
    payload = {"sub": str(user_id), "iat": issued_at, "exp": expires_at, "typ": "access"}
    payload_segment = _b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    return f"{payload_segment}.{_sign(payload_segment, secret)}", expires_at


def decode_access_token(token: str, *, secret: str, now: int | None = None) -> TokenClaims:
    """Validate signature and expiry, returning claims or raising ``TokenError``."""
    try:
        payload_segment, signature_segment = token.strip().split(".", 1)
    except ValueError as exc:
        raise TokenError("Malformed access token.", "INVALID_TOKEN") from exc

    expected = _sign(payload_segment, secret)
    if not hmac.compare_digest(expected, signature_segment):
        raise TokenError("Access token signature is invalid.", "INVALID_TOKEN")

    try:
        payload = json.loads(_b64decode(payload_segment))
        user_id = uuid.UUID(str(payload["sub"]))
        issued_at = int(payload["iat"])
        expires_at = int(payload["exp"])
        if payload.get("typ") != "access":
            raise ValueError("unexpected token type")
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise TokenError("Access token payload is invalid.", "INVALID_TOKEN") from exc

    current = int(now if now is not None else time.time())
    if current >= expires_at:
        raise TokenError("Your session has expired. Please sign in again.", "TOKEN_EXPIRED")

    return TokenClaims(user_id=user_id, issued_at=issued_at, expires_at=expires_at)
