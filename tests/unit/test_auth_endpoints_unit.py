from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoints import auth as auth_endpoints
from app.core.config import settings
from app.core.security import get_password_hash
from app.services import user_service


def _client():
    app = FastAPI()
    app.include_router(auth_endpoints.router, prefix=f"{settings.API_V1_STR}/auth")
    return TestClient(app)


def test_auth_login_uses_matching_candidate_when_duplicate_phone_exists(monkeypatch):
    client = _client()
    hashed = get_password_hash("correct-password")

    monkeypatch.setattr(
        user_service,
        "get_admin_or_officer_candidates",
        lambda _identifier: [
            {
                "id": "off-wrong",
                "name": "Wrong Officer",
                "email": "wrong@example.com",
                "password": get_password_hash("some-other-password"),
                "role_id": 2,
                "role": "officer",
            },
            {
                "id": "off-right",
                "name": "Right Officer",
                "email": "right@example.com",
                "password": hashed,
                "role_id": 2,
                "role": "officer",
            },
        ],
    )
    monkeypatch.setattr(auth_endpoints.security, "create_access_token", lambda **_kwargs: "token-123")

    resp = client.post(
        f"{settings.API_V1_STR}/auth/login",
        data={"mobile_number": "9999999999", "password": "correct-password"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"] == "token-123"
    assert body["user"]["id"] == "off-right"
    assert body["user"]["role"] == "officer"


def test_auth_login_hashes_only_the_matching_legacy_plaintext_user(monkeypatch):
    client = _client()
    updated = {}

    monkeypatch.setattr(
        user_service,
        "get_admin_or_officer_candidates",
        lambda _identifier: [
            {
                "id": "off-wrong",
                "name": "Wrong Officer",
                "email": "wrong@example.com",
                "password": "different-plaintext",
                "role_id": 2,
                "role": "officer",
            },
            {
                "id": "off-right",
                "name": "Right Officer",
                "email": "right@example.com",
                "password": "correct-password",
                "role_id": 2,
                "role": "officer",
            },
        ],
    )
    monkeypatch.setattr(auth_endpoints.security, "create_access_token", lambda **_kwargs: "token-123")
    monkeypatch.setattr(auth_endpoints.security, "get_password_hash", lambda _pw: "hashed-password")
    monkeypatch.setattr(
        user_service,
        "update_user_password",
        lambda user_id, hashed_password: updated.update({"user_id": user_id, "password": hashed_password}) or True,
    )

    resp = client.post(
        f"{settings.API_V1_STR}/auth/login",
        data={"mobile_number": "9999999999", "password": "correct-password"},
    )

    assert resp.status_code == 200
    assert updated == {"user_id": "off-right", "password": "hashed-password"}
