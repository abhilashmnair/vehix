"""AC-U2: admin POST /users."""

import secrets
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import UserCred
from tests.helpers import auth

USERS = "/api/v1/users"
LOGIN = "/api/v1/auth/login"
READ_FIELDS = {"id", "email", "full_name", "role", "is_active", "created_at", "updated_at"}


def payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "email": f"new-{secrets.token_hex(4)}@example.com",
        "full_name": "New Person",
        "password": secrets.token_urlsafe(24),
    }
    return {**base, **overrides}


def test_admin_creates_user(client: TestClient, admin_token: str) -> None:
    body = payload(email="Fresh.User@Example.com")
    response = client.post(USERS, headers=auth(admin_token), json=body)
    assert response.status_code == 201
    created = response.json()
    assert set(created) == READ_FIELDS
    assert created["email"] == "fresh.user@example.com"
    assert created["role"] == "user"
    assert created["is_active"] is True
    assert response.headers["Location"] == f"/api/v1/users/{created['id']}"
    assert body["password"] not in response.text
    # The new user can log in with the password that was set.
    login = client.post(LOGIN, json={"email": body["email"], "password": body["password"]})
    assert login.status_code == 200


def test_admin_can_create_admin_and_inactive_user(client: TestClient, admin_token: str) -> None:
    response = client.post(
        USERS, headers=auth(admin_token), json=payload(role="admin", is_active=False)
    )
    assert response.status_code == 201
    assert response.json()["role"] == "admin"
    assert response.json()["is_active"] is False


def test_password_is_stored_hashed(
    client: TestClient, test_engine: Engine, admin_token: str
) -> None:
    body = payload()
    created = client.post(USERS, headers=auth(admin_token), json=body).json()
    with test_engine.connect() as conn:
        stored = conn.execute(
            text("SELECT password_hash FROM users WHERE id = :id"), {"id": created["id"]}
        ).scalar_one()
    assert stored.startswith("$argon2")
    assert body["password"] not in stored


def test_duplicate_email_is_409_case_insensitive(
    client: TestClient, admin: UserCred, admin_token: str
) -> None:
    response = client.post(
        USERS, headers=auth(admin_token), json=payload(email=admin.email.upper())
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_conflict"


@pytest.mark.parametrize(
    "overrides",
    [
        {"password": "x" * 11},  # weak: below the 12 character minimum
        {"password": "x" * 129},
        {"email": "not-an-email"},
        {"email": ""},
        {"full_name": ""},
        {"role": "superuser"},
        {"is_active": "maybe"},
        {"unknown_field": 1},
    ],
)
def test_invalid_payload_is_422(
    client: TestClient, admin_token: str, overrides: dict[str, Any]
) -> None:
    response = client.post(USERS, headers=auth(admin_token), json=payload(**overrides))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize("missing", ["email", "full_name", "password"])
def test_missing_required_field_is_422(client: TestClient, admin_token: str, missing: str) -> None:
    body = payload()
    del body[missing]
    assert client.post(USERS, headers=auth(admin_token), json=body).status_code == 422


def test_non_admin_is_403(client: TestClient, user_token: str, test_engine: Engine) -> None:
    body = payload()
    response = client.post(USERS, headers=auth(user_token), json=body)
    assert response.status_code == 403
    with test_engine.connect() as conn:
        count = conn.execute(
            text("SELECT count(*) FROM users WHERE email = :e"), {"e": body["email"]}
        ).scalar_one()
    assert count == 0


def test_anonymous_is_401(client: TestClient) -> None:
    assert client.post(USERS, json=payload()).status_code == 401
