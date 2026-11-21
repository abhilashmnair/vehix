"""AC-U5: admin DELETE /users/{id}."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import RentalFactory, UserCred, UserFactory
from tests.helpers import auth

USERS = "/api/v1/users"


def exists(engine: Engine, user_id: uuid.UUID) -> bool:
    with engine.connect() as conn:
        return bool(
            conn.execute(
                text("SELECT count(*) FROM users WHERE id = :id"), {"id": user_id}
            ).scalar_one()
        )


def test_admin_deletes_user(
    client: TestClient, test_engine: Engine, admin_token: str, user: UserCred
) -> None:
    response = client.delete(f"{USERS}/{user.id}", headers=auth(admin_token))
    assert response.status_code == 204
    assert response.content == b""
    assert not exists(test_engine, user.id)
    assert client.get(f"{USERS}/{user.id}", headers=auth(admin_token)).status_code == 404


def test_unknown_user_is_404(client: TestClient, admin_token: str) -> None:
    response = client.delete(f"{USERS}/{uuid.uuid4()}", headers=auth(admin_token))
    assert response.status_code == 404


def test_malformed_id_is_422(client: TestClient, admin_token: str) -> None:
    assert client.delete(f"{USERS}/nope", headers=auth(admin_token)).status_code == 422


@pytest.mark.parametrize("status", ["reserved", "active"])
def test_user_with_active_rentals_is_409(
    client: TestClient,
    test_engine: Engine,
    admin_token: str,
    user: UserCred,
    rental_factory: RentalFactory,
    status: str,
) -> None:
    rental_factory(user.id, status=status)
    response = client.delete(f"{USERS}/{user.id}", headers=auth(admin_token))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "user_has_active_rentals"
    assert exists(test_engine, user.id)


@pytest.mark.parametrize("status", ["completed", "cancelled"])
def test_user_with_rental_history_is_409_and_can_be_deactivated_instead(
    client: TestClient,
    test_engine: Engine,
    admin_token: str,
    user: UserCred,
    rental_factory: RentalFactory,
    status: str,
) -> None:
    rental_factory(user.id, status=status)
    response = client.delete(f"{USERS}/{user.id}", headers=auth(admin_token))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "user_has_rental_history"
    assert exists(test_engine, user.id)
    deactivate = client.patch(
        f"{USERS}/{user.id}", headers=auth(admin_token), json={"is_active": False}
    )
    assert deactivate.status_code == 200


def test_last_active_admin_cannot_be_deleted(
    client: TestClient, test_engine: Engine, admin: UserCred, admin_token: str
) -> None:
    response = client.delete(f"{USERS}/{admin.id}", headers=auth(admin_token))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "last_admin"
    assert exists(test_engine, admin.id)


def test_admin_can_delete_self_when_another_active_admin_exists(
    client: TestClient,
    test_engine: Engine,
    admin: UserCred,
    admin_token: str,
    user_factory: UserFactory,
) -> None:
    user_factory(role="admin")
    assert client.delete(f"{USERS}/{admin.id}", headers=auth(admin_token)).status_code == 204
    assert not exists(test_engine, admin.id)


def test_admin_can_delete_an_inactive_admin(
    client: TestClient, admin_token: str, user_factory: UserFactory
) -> None:
    inactive_admin = user_factory(role="admin", is_active=False)
    response = client.delete(f"{USERS}/{inactive_admin.id}", headers=auth(admin_token))
    assert response.status_code == 204


def test_non_admin_is_403_and_anonymous_is_401(
    client: TestClient, test_engine: Engine, user: UserCred, user_token: str, admin: UserCred
) -> None:
    for target in (user.id, admin.id):
        assert client.delete(f"{USERS}/{target}", headers=auth(user_token)).status_code == 403
    assert client.delete(f"{USERS}/{user.id}").status_code == 401
    assert exists(test_engine, user.id)
    assert exists(test_engine, admin.id)
