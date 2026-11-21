"""AC-U1: GET/PATCH /users/me."""

import secrets

from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import UserCred, UserFactory
from tests.helpers import auth

ME = "/api/v1/users/me"
LOGIN = "/api/v1/auth/login"
READ_FIELDS = {"id", "email", "full_name", "role", "is_active", "created_at", "updated_at"}


def login(client: TestClient, email: str, password: str) -> int:
    return client.post(LOGIN, json={"email": email, "password": password}).status_code


def test_get_me_returns_own_profile_without_password_data(
    client: TestClient, user: UserCred, user_token: str
) -> None:
    response = client.get(ME, headers=auth(user_token))
    assert response.status_code == 200
    body = response.json()
    assert set(body) == READ_FIELDS
    assert body["id"] == str(user.id)
    assert body["email"] == user.email
    assert body["role"] == "user"
    assert "password" not in response.text.lower()
    assert user.password not in response.text


def test_get_me_requires_authentication(client: TestClient) -> None:
    response = client.get(ME)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_patch_me_requires_authentication(client: TestClient) -> None:
    assert client.patch(ME, json={"full_name": "X"}).status_code == 401


def test_patch_full_name_and_email(client: TestClient, user: UserCred, user_token: str) -> None:
    new_email = f"New.{secrets.token_hex(3)}@Example.com"
    response = client.patch(
        ME, headers=auth(user_token), json={"full_name": "  New Name ", "email": new_email}
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == READ_FIELDS
    assert body["full_name"] == "New Name"
    assert body["email"] == new_email.lower()
    assert login(client, new_email, user.password) == 200
    assert login(client, user.email, user.password) == 401


def test_patch_empty_body_changes_nothing(
    client: TestClient, user: UserCred, user_token: str
) -> None:
    response = client.patch(ME, headers=auth(user_token), json={})
    assert response.status_code == 200
    assert response.json()["email"] == user.email


def test_patch_email_conflict_is_409_case_insensitive(
    client: TestClient, user_factory: UserFactory, user_token: str
) -> None:
    other = user_factory(email="taken@example.com")
    response = client.patch(ME, headers=auth(user_token), json={"email": other.email.upper()})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_conflict"


def test_patch_own_current_email_is_not_a_conflict(
    client: TestClient, user: UserCred, user_token: str
) -> None:
    response = client.patch(ME, headers=auth(user_token), json={"email": user.email.upper()})
    assert response.status_code == 200


def test_patch_validation_errors(client: TestClient, user_token: str) -> None:
    headers = auth(user_token)
    assert client.patch(ME, headers=headers, json={"email": "nope"}).status_code == 422
    assert client.patch(ME, headers=headers, json={"full_name": ""}).status_code == 422
    assert client.patch(ME, headers=headers, json={"full_name": None}).status_code == 422
    assert client.patch(ME, headers=headers, json={"email": None}).status_code == 422


def test_password_change_requires_current_password(
    client: TestClient, user: UserCred, user_token: str
) -> None:
    new_password = secrets.token_urlsafe(24)
    response = client.patch(ME, headers=auth(user_token), json={"password": new_password})
    assert response.status_code == 422
    assert login(client, user.email, user.password) == 200


def test_password_change_with_wrong_current_password_is_403(
    client: TestClient, user: UserCred, user_token: str
) -> None:
    body = {"password": secrets.token_urlsafe(24), "current_password": secrets.token_urlsafe(24)}
    response = client.patch(ME, headers=auth(user_token), json=body)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "invalid_current_password"
    assert login(client, user.email, user.password) == 200
    assert login(client, user.email, body["password"]) == 401


def test_password_change_succeeds(client: TestClient, user: UserCred, user_token: str) -> None:
    new_password = secrets.token_urlsafe(24)
    response = client.patch(
        ME,
        headers=auth(user_token),
        json={"password": new_password, "current_password": user.password},
    )
    assert response.status_code == 200
    assert new_password not in response.text
    assert user.password not in response.text
    assert login(client, user.email, new_password) == 200
    assert login(client, user.email, user.password) == 401


def test_new_password_must_be_at_least_12_characters(
    client: TestClient, user: UserCred, user_token: str
) -> None:
    too_short = secrets.token_hex(4)  # 8 characters
    response = client.patch(
        ME,
        headers=auth(user_token),
        json={"password": too_short, "current_password": user.password},
    )
    assert response.status_code == 422
    assert too_short not in response.text


def test_changing_own_role_or_active_flag_is_403_for_user_and_admin(
    client: TestClient,
    test_engine: Engine,
    user: UserCred,
    user_token: str,
    admin: UserCred,
    admin_token: str,
) -> None:
    for token, person in ((user_token, user), (admin_token, admin)):
        for payload in (
            {"role": "admin"},
            {"role": "user"},
            {"is_active": False},
            {"is_active": True},
            {"role": "admin", "full_name": "Should Not Apply"},
        ):
            response = client.patch(ME, headers=auth(token), json=payload)
            assert response.status_code == 403, payload
            assert response.json()["error"]["code"] == "forbidden"
        with test_engine.connect() as conn:
            row = conn.execute(
                text("SELECT role, is_active, full_name FROM users WHERE id = :id"),
                {"id": person.id},
            ).one()
        assert (row.role, row.is_active) == (person.role, True)
        assert row.full_name != "Should Not Apply"


def test_cannot_modify_another_users_data_by_passing_an_id(
    client: TestClient, test_engine: Engine, user_factory: UserFactory, user_token: str
) -> None:
    other = user_factory(full_name="Other Person")
    for payload in ({"id": str(other.id)}, {"user_id": str(other.id), "full_name": "Hacked"}):
        response = client.patch(ME, headers=auth(user_token), json=payload)
        assert response.status_code == 422
    with test_engine.connect() as conn:
        name = conn.execute(
            text("SELECT full_name FROM users WHERE id = :id"), {"id": other.id}
        ).scalar_one()
    assert name == "Other Person"
