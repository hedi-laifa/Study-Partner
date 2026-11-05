"""ASGI authentication middleware binding bearer-token identity to every protected API request.

Behaviour:
- Public paths (health, readiness, login, registration, docs) are never checked.
- If an ``Authorization: Bearer <token>`` header is present it is always validated:
  * malformed/forged token  -> ``401 INVALID_TOKEN``
  * expired token           -> ``401 TOKEN_EXPIRED`` (frontend signs the user out)
  * the authenticated user is then *bound* to the request: the ``user_id`` query parameter
    (and a top-level ``user_id`` JSON body field) is forced to the token subject; a conflicting
    value is rejected with ``403 FORBIDDEN_IDENTITY_MISMATCH``. This guarantees existing service-level
    ownership checks (which read ``user_id``) can never be skipped or spoofed by an authenticated client.
- If no token is present: ``401 AUTH_REQUIRED`` when ``settings.AUTH_REQUIRED`` is true, otherwise the
  request passes through unchanged (local single-user development mode).
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import parse_qsl, urlencode

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings
from app.core.tokens import TokenError, decode_access_token

PUBLIC_API_SUFFIXES: tuple[str, ...] = (
    "/health",
    "/health/ready",
    "/ready",
    "/auth/login",
    "/auth/register",
)
MAX_JSON_BODY_BYTES = 1_000_000


def _strip_api_prefix(path: str) -> str | None:
    """Return the path relative to the API prefix, or None for non-API paths."""
    for prefix in (settings.API_V1_PREFIX, "/api"):
        if path == prefix or path.startswith(prefix + "/"):
            return path[len(prefix):] or "/"
    return None


async def _send_json_error(send: Send, status_code: int, detail: str, error_code: str) -> None:
    body = json.dumps({"detail": detail, "error_code": error_code}).encode("utf-8")
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode("ascii")),
    ]
    if status_code == 401:
        headers.append((b"www-authenticate", b'Bearer realm="study-partner"'))
    await send({"type": "http.response.start", "status": status_code, "headers": headers})
    await send({"type": "http.response.body", "body": body})


class AuthIdentityMiddleware:
    """Validate bearer tokens and bind the authenticated user to the request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return

        relative = _strip_api_prefix(scope.get("path", ""))
        if relative is None or relative.rstrip("/") in PUBLIC_API_SUFFIXES:
            await self.app(scope, receive, send)
            return

        token = self._extract_bearer_token(scope)
        if token is None:
            if settings.AUTH_REQUIRED:
                await _send_json_error(
                    send, 401, "Authentication is required. Please sign in.", "AUTH_REQUIRED"
                )
                return
            await self.app(scope, receive, send)
            return

        try:
            claims = decode_access_token(token, secret=settings.AUTH_SECRET_KEY)
        except TokenError as exc:
            await _send_json_error(send, 401, exc.detail, exc.error_code)
            return

        subject = str(claims.user_id)

        # 1. Bind query-string identity
        query_pairs = parse_qsl(scope.get("query_string", b"").decode("latin-1"), keep_blank_values=True)
        supplied = [v for k, v in query_pairs if k == "user_id" and v]
        if any(v.lower() != subject for v in supplied):
            await _send_json_error(
                send,
                403,
                "The requested user does not match the authenticated account.",
                "FORBIDDEN_IDENTITY_MISMATCH",
            )
            return
        rebuilt = [(k, v) for k, v in query_pairs if k != "user_id"] + [("user_id", subject)]

        new_scope: dict[str, Any] = dict(scope)
        new_scope["query_string"] = urlencode(rebuilt).encode("latin-1")
        state = dict(scope.get("state") or {})
        state["auth_user_id"] = subject
        new_scope["state"] = state

        # 2. Bind top-level JSON body identity for write requests
        content_type = self._header(scope, b"content-type") or ""
        if scope.get("method") in {"POST", "PUT", "PATCH"} and content_type.startswith("application/json"):
            raw_body = await self._read_body(receive)
            if raw_body is None:
                await _send_json_error(send, 413, "Request body too large.", "PAYLOAD_TOO_LARGE")
                return
            patched = raw_body
            if raw_body.strip():
                try:
                    parsed = json.loads(raw_body)
                except json.JSONDecodeError:
                    parsed = None  # let FastAPI produce its standard validation error
                if isinstance(parsed, dict) and "user_id" in parsed:
                    body_user = parsed.get("user_id")
                    if body_user is not None and str(body_user).lower() != subject:
                        await _send_json_error(
                            send,
                            403,
                            "The payload user does not match the authenticated account.",
                            "FORBIDDEN_IDENTITY_MISMATCH",
                        )
                        return
                    parsed["user_id"] = subject
                    patched = json.dumps(parsed).encode("utf-8")
            new_scope["headers"] = [
                (k, v) for k, v in scope.get("headers", []) if k != b"content-length"
            ] + [(b"content-length", str(len(patched)).encode("ascii"))]

            replayed = False

            async def replay_receive() -> Message:
                nonlocal replayed
                if not replayed:
                    replayed = True
                    return {"type": "http.request", "body": patched, "more_body": False}
                return await receive()

            await self.app(new_scope, replay_receive, send)
            return

        await self.app(new_scope, receive, send)

    @staticmethod
    def _header(scope: Scope, name: bytes) -> str | None:
        for key, value in scope.get("headers", []):
            if key == name:
                return value.decode("latin-1")
        return None

    def _extract_bearer_token(self, scope: Scope) -> str | None:
        raw = self._header(scope, b"authorization")
        if not raw:
            return None
        scheme, _, credentials = raw.partition(" ")
        if scheme.lower() != "bearer" or not credentials.strip():
            return None
        return credentials.strip()

    @staticmethod
    async def _read_body(receive: Receive) -> bytes | None:
        chunks: list[bytes] = []
        total = 0
        while True:
            message = await receive()
            if message["type"] != "http.request":
                break
            chunk = message.get("body", b"")
            total += len(chunk)
            if total > MAX_JSON_BODY_BYTES:
                return None
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        return b"".join(chunks)
