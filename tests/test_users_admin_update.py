"""AC-U4: admin PATCH /users/{id}."""

import secrets
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import UserCred, UserFactory
from tests.helpers import auth

USERS = "/api/v1/users"
LOGIN = "/api/v1/auth/login"


def login_status(client: TestClient, person: UserCred, password: str | None = None) -> int:
    body = {"email": person.email, "password": password or person.password}
    return client.post(LOGIN, json=body).status_code


def test_admin_updates_profile_fields(client: TestClient, admin_token: str, user: UserCred) -> None:
    new_email = f"Renamed.{secrets.token_hex(3)}@Example.com"
    response = client.patch(
        f"{USERS}/{user.id}",
        headers=auth(admin_token),
        json={"full_name": "Renamed", "email": new_email},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Renamed"
    assert body["email"] == new_email.lower()
    assert body["role"] == "user"
    assert "password" not in response.text.lower()


def test_admin_changes_role_and_active_flag(
    client: TestClient, admin_token: str, user: UserCred, user_token: str
) -> None:
    headers = auth(admin_token)
    promoted = client.patch(f"{USERS}/{user.id}", headers=headers, json={"role": "admin"})
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "admin"
    # Effective immediately: the user's existing token now passes admin checks.
    assert client.get(USERS, headers=auth(user_token)).status_code == 200

    deactivated = client.patch(f"{USERS}/{user.id}", headers=headers, json={"is_active": False})
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False
    assert client.get(USERS, headers=auth(user_token)).status_code == 401
    assert login_status(client, user) == 401

    reactivated = client.patch(f"{USERS}/{user.id}", headers=headers, json={"is_active": True})
    assert reactivated.json()["is_active"] is True
    assert login_status(client, user) == 200


def test_admin_resets_password_without_current_password(
    client: TestClient, admin_token: str, user: UserCred
) -> None:
    new_password = secrets.token_urlsafe(24)
    response = client.patch(
        f"{USERS}/{user.id}", headers=auth(admin_token), json={"password": new_password}
    )
    assert response.status_code == 200
    assert new_password not in response.text
    assert login_status(client, user, new_password) == 200
    assert login_status(client, user) == 401


def test_empty_body_is_a_no_op(client: TestClient, admin_token: str, user: UserCred) -> None:
    response = client.patch(f"{USERS}/{user.id}", headers=auth(admin_token), json={})
    assert response.status_code == 200
    assert response.json()["email"] == user.email


def test_unknown_user_is_404(client: TestClient, admin_token: str) -> None:
    response = client.patch(
        f"{USERS}/{uuid.uuid4()}", headers=auth(admin_token), json={"full_name": "X"}
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_email_conflict_is_409(
    client: TestClient, admin_token: str, user: UserCred, user_factory: UserFactory
) -> None:
    other = user_factory()
    response = client.patch(
        f"{USERS}/{user.id}", headers=auth(admin_token), json={"email": other.email.upper()}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_conflict"


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "nope"},
        {"password": "x" * 11},
        {"role": "superuser"},
        {"is_active": "maybe"},
        {"full_name": None},
        {"role": None},
        {"id": str(uuid.uuid4())},
        {"password_hash": "x"},
    ],
)
def test_invalid_payload_is_422(
    client: TestClient, admin_token: str, user: UserCred, payload: dict[str, Any]
) -> None:
    response = client.patch(f"{USERS}/{user.id}", headers=auth(admin_token), json=payload)
    assert response.status_code == 422


def test_malformed_id_is_422(client: TestClient, admin_token: str) -> None:
    assert client.patch(f"{USERS}/nope", headers=auth(admin_token), json={}).status_code == 422


def test_non_admin_is_403_and_anonymous_is_401(
    client: TestClient, user: UserCred, user_token: str, admin: UserCred
) -> None:
    body = {"role": "admin"}
    assert (
        client.patch(f"{USERS}/{user.id}", headers=auth(user_token), json=body).status_code == 403
    )
    assert (
        client.patch(f"{USERS}/{admin.id}", headers=auth(user_token), json=body).status_code == 403
    )
    assert client.patch(f"{USERS}/{user.id}", json=body).status_code == 401
    # The refused attempt changed nothing.
    assert client.get(USERS, headers=auth(user_token)).status_code == 403


def test_last_active_admin_cannot_be_demoted_or_deactivated(
    client: TestClient, admin: UserCred, admin_token: str
) -> None:
    headers = auth(admin_token)
    for payload in ({"role": "user"}, {"is_active": False}, {"role": "user", "is_active": False}):
        response = client.patch(f"{USERS}/{admin.id}", headers=headers, json=payload)
        assert response.status_code == 409, payload
        assert response.json()["error"]["code"] == "last_admin"
    # Harmless edits to the last admin are still fine.
    assert (
        client.patch(f"{USERS}/{admin.id}", headers=headers, json={"role": "admin"}).status_code
        == 200
    )


def test_admin_can_demote_self_when_another_active_admin_exists(
    client: TestClient, admin: UserCred, admin_token: str, user_factory: UserFactory
) -> None:
    user_factory(role="admin")
    response = client.patch(f"{USERS}/{admin.id}", headers=auth(admin_token), json={"role": "user"})
    assert response.status_code == 200


def test_inactive_admin_does_not_count_as_another_admin(
    client: TestClient, admin: UserCred, admin_token: str, user_factory: UserFactory
) -> None:
    user_factory(role="admin", is_active=False)
    response = client.patch(
        f"{USERS}/{admin.id}", headers=auth(admin_token), json={"is_active": False}
    )
    assert response.status_code == 409
