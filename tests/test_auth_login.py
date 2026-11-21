"""AC-A1: POST /auth/login."""

import secrets

import jwt
from fastapi.testclient import TestClient

from app.config import get_settings
from tests.conftest import UserCred, UserFactory

LOGIN = "/api/v1/auth/login"
INVALID = {"error": {"code": "unauthorized", "message": "Invalid email or password."}}


def test_login_succeeds_with_valid_credentials(client: TestClient, user: UserCred) -> None:
    response = client.post(LOGIN, json={"email": user.email, "password": user.password})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == get_settings().jwt_expire_minutes * 60
    claims = jwt.decode(
        body["access_token"], get_settings().jwt_secret.get_secret_value(), algorithms=["HS256"]
    )
    assert claims["sub"] == str(user.id)
    assert claims["role"] == "user"
    assert "exp" in claims
    assert user.password not in response.text


def test_login_email_is_case_insensitive(client: TestClient, user_factory: UserFactory) -> None:
    person = user_factory(email="Mixed.Case@Example.com")
    response = client.post(
        LOGIN, json={"email": "MIXED.case@example.COM", "password": person.password}
    )
    assert response.status_code == 200


def test_wrong_password_unknown_email_and_inactive_user_are_indistinguishable(
    client: TestClient, user: UserCred, user_factory: UserFactory
) -> None:
    inactive = user_factory(is_active=False)
    attempts = [
        {"email": user.email, "password": secrets.token_urlsafe(24)},
        {"email": f"nobody-{secrets.token_hex(4)}@example.com", "password": user.password},
        {"email": inactive.email, "password": inactive.password},  # correct password, inactive
    ]
    responses = [client.post(LOGIN, json=attempt) for attempt in attempts]
    for response in responses:
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert response.json() == INVALID


def test_login_validation_errors(client: TestClient) -> None:
    assert client.post(LOGIN, json={"email": "not-an-email", "password": "x"}).status_code == 422
    assert client.post(LOGIN, json={"email": "a@example.com"}).status_code == 422
    assert client.post(LOGIN, json={}).status_code == 422
    extra = {"email": "a@example.com", "password": "x", "role": "admin"}
    assert client.post(LOGIN, json=extra).status_code == 422
