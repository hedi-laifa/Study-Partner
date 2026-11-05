"""Phase 8 authentication tests: register, login, token expiry, identity binding."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.tokens import TokenError, create_access_token, decode_access_token


def _register(client: TestClient, email: str = "a@uni.edu") -> dict:
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Ada Student", "password": "StrongPass123!"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_token_roundtrip_expiry_and_tamper() -> None:
    uid = uuid.uuid4()
    token, exp = create_access_token(uid, secret="s" * 20, ttl_seconds=60, now=1000)
    assert decode_access_token(token, secret="s" * 20, now=1001).user_id == uid
    with pytest.raises(TokenError) as expired:
        decode_access_token(token, secret="s" * 20, now=exp + 1)
    assert expired.value.error_code == "TOKEN_EXPIRED"
    with pytest.raises(TokenError):
        decode_access_token(token, secret="x" * 20, now=1001)
    with pytest.raises(TokenError):
        decode_access_token(token[:-2] + "ab", secret="s" * 20, now=1001)


def test_register_login_me_and_no_password_hash(client: TestClient) -> None:
    reg = _register(client)
    assert "password_hash" not in reg["user"]
    dup = client.post(
        "/api/v1/auth/register",
        json={"email": "A@uni.edu", "full_name": "Dup", "password": "StrongPass123!"},
    )
    assert dup.status_code == 409

    bad = client.post("/api/v1/auth/login", json={"email": "a@uni.edu", "password": "wrong"})
    assert bad.status_code == 401 and bad.json()["error_code"] == "INVALID_CREDENTIALS"
    unknown = client.post("/api/v1/auth/login", json={"email": "no@uni.edu", "password": "x"})
    assert unknown.status_code == 401 and unknown.json()["detail"] == bad.json()["detail"]

    ok = client.post("/api/v1/auth/login", json={"email": "a@uni.edu", "password": "StrongPass123!"})
    assert ok.status_code == 200
    token = ok.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers=_auth(token))
    assert me.status_code == 200 and me.json()["email"] == "a@uni.edu"
    assert client.get("/api/v1/auth/me").status_code == 401


def test_expired_and_forged_tokens_rejected(client: TestClient) -> None:
    reg = _register(client)
    uid = uuid.UUID(reg["user"]["id"])
    expired, _ = create_access_token(
        uid, secret=settings.AUTH_SECRET_KEY, ttl_seconds=10, now=1000
    )
    resp = client.get("/api/v1/courses", headers=_auth(expired))
    assert resp.status_code == 401 and resp.json()["error_code"] == "TOKEN_EXPIRED"
    forged = client.get("/api/v1/courses", headers=_auth("abc.def"))
    assert forged.status_code == 401 and forged.json()["error_code"] == "INVALID_TOKEN"


def test_identity_binding_prevents_cross_user_access(client: TestClient) -> None:
    a = _register(client, "a@uni.edu")
    b = _register(client, "b@uni.edu")
    ha, hb = _auth(a["access_token"]), _auth(b["access_token"])

    # Body user_id is forced to the token subject; spoofing is rejected
    spoof = client.post(
        "/api/v1/courses",
        json={"user_id": b["user"]["id"], "title": "Spoofed"},
        headers=ha,
    )
    assert spoof.status_code == 403
    assert spoof.json()["error_code"] == "FORBIDDEN_IDENTITY_MISMATCH"

    # Omitting user_id in the query uses the token identity
    created = client.post(
        "/api/v1/courses", json={"user_id": a["user"]["id"], "title": "Algorithms"}, headers=ha
    )
    assert created.status_code == 201
    course_id = created.json()["id"]
    assert [c["id"] for c in client.get("/api/v1/courses", headers=ha).json()] == [course_id]
    assert client.get("/api/v1/courses", headers=hb).json() == []

    # Other user cannot read it, even by passing the owner's id
    assert client.get(f"/api/v1/courses/{course_id}", headers=hb).status_code in {403, 404}
    assert (
        client.get(f"/api/v1/courses/{course_id}?user_id={a['user']['id']}", headers=hb).status_code
        == 403
    )


def test_auth_required_mode(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "AUTH_REQUIRED", True)
    assert client.get("/api/v1/health").status_code == 200
    resp = client.get("/api/v1/courses")
    assert resp.status_code == 401 and resp.json()["error_code"] == "AUTH_REQUIRED"
    reg = _register(client)
    assert client.get("/api/v1/courses", headers=_auth(reg["access_token"])).status_code == 200


def test_document_file_download_owner_only(client: TestClient) -> None:
    import fitz

    a = _register(client, "a@uni.edu")
    b = _register(client, "b@uni.edu")
    ha, hb = _auth(a["access_token"]), _auth(b["access_token"])
    course = client.post(
        "/api/v1/courses", json={"user_id": a["user"]["id"], "title": "OS"}, headers=ha
    ).json()
    doc = fitz.open()
    doc.new_page().insert_text((50, 60), "Virtual memory maps pages to frames in RAM. " * 6)
    up = client.post(
        f"/api/v1/courses/{course['id']}/documents",
        files={"file": ("os.pdf", doc.tobytes(), "application/pdf")},
        headers=ha,
    )
    assert up.status_code == 201
    doc_id = up.json()["id"]
    ok = client.get(f"/api/v1/documents/{doc_id}/file", headers=ha)
    assert ok.status_code == 200 and ok.content.startswith(b"%PDF")
    assert ok.headers["content-type"] == "application/pdf"
    assert client.get(f"/api/v1/documents/{doc_id}/file", headers=hb).status_code == 403
