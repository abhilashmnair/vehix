"""AC-U3: admin GET /users and GET /users/{id}."""

import uuid

import pytest
from fastapi.testclient import TestClient

from tests.conftest import UserCred, UserFactory
from tests.helpers import auth

USERS = "/api/v1/users"
READ_FIELDS = {"id", "email", "full_name", "role", "is_active", "created_at", "updated_at"}


def test_list_users_is_paginated_and_never_leaks_password_data(
    client: TestClient, admin: UserCred, admin_token: str, user_factory: UserFactory
) -> None:
    for _ in range(4):
        user_factory()
    response = client.get(USERS, headers=auth(admin_token))
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "total", "limit", "offset"}
    assert (body["total"], body["limit"], body["offset"]) == (5, 20, 0)
    assert len(body["items"]) == 5
    assert all(set(item) == READ_FIELDS for item in body["items"])
    assert "password" not in response.text.lower()


def test_pagination_limit_offset_and_stable_order(
    client: TestClient, admin_token: str, admin: UserCred, user_factory: UserFactory
) -> None:
    created = [admin.id, *(user_factory().id for _ in range(6))]
    seen: list[str] = []
    for offset in (0, 3, 6):
        response = client.get(
            USERS, headers=auth(admin_token), params={"limit": 3, "offset": offset}
        )
        body = response.json()
        assert body["total"] == 7
        assert body["limit"] == 3
        seen += [item["id"] for item in body["items"]]
    assert len(seen) == 7
    assert len(set(seen)) == 7
    assert seen == [str(i) for i in created]  # ordered by created_at, then id
    again = client.get(USERS, headers=auth(admin_token), params={"limit": 100}).json()
    assert [item["id"] for item in again["items"]] == seen


def test_offset_past_the_end_returns_empty_items(client: TestClient, admin_token: str) -> None:
    body = client.get(USERS, headers=auth(admin_token), params={"offset": 50}).json()
    assert body["items"] == []
    assert body["total"] == 1


@pytest.mark.parametrize(
    "params", [{"limit": 0}, {"limit": 101}, {"limit": -1}, {"offset": -1}, {"limit": "abc"}]
)
def test_invalid_pagination_is_422(
    client: TestClient, admin_token: str, params: dict[str, object]
) -> None:
    response = client.get(USERS, headers=auth(admin_token), params=params)  # type: ignore[arg-type]
    assert response.status_code == 422


def test_max_limit_is_accepted(client: TestClient, admin_token: str) -> None:
    assert client.get(USERS, headers=auth(admin_token), params={"limit": 100}).status_code == 200


def test_get_user_by_id(client: TestClient, admin_token: str, user: UserCred) -> None:
    response = client.get(f"{USERS}/{user.id}", headers=auth(admin_token))
    assert response.status_code == 200
    body = response.json()
    assert set(body) == READ_FIELDS
    assert body["id"] == str(user.id)
    assert body["email"] == user.email


def test_get_unknown_user_is_404(client: TestClient, admin_token: str) -> None:
    response = client.get(f"{USERS}/{uuid.uuid4()}", headers=auth(admin_token))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_get_user_with_malformed_id_is_422(client: TestClient, admin_token: str) -> None:
    assert client.get(f"{USERS}/not-a-uuid", headers=auth(admin_token)).status_code == 422


def test_non_admin_gets_403_even_for_own_id(
    client: TestClient, user: UserCred, user_token: str, admin: UserCred
) -> None:
    headers = auth(user_token)
    assert client.get(USERS, headers=headers).status_code == 403
    assert client.get(f"{USERS}/{user.id}", headers=headers).status_code == 403
    assert client.get(f"{USERS}/{admin.id}", headers=headers).status_code == 403
    assert client.get(f"{USERS}/{uuid.uuid4()}", headers=headers).status_code == 403


def test_anonymous_is_401(client: TestClient, user: UserCred) -> None:
    assert client.get(USERS).status_code == 401
    assert client.get(f"{USERS}/{user.id}").status_code == 401


def test_me_route_is_not_shadowed_by_id_route(client: TestClient, admin_token: str) -> None:
    assert client.get(f"{USERS}/me", headers=auth(admin_token)).status_code == 200
