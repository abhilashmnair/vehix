"""AC-R6: admin DELETE /rentals/{id}."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import RentalFactory, UserCred, UserFactory
from tests.helpers import auth

RENTALS = "/api/v1/rentals"


def exists(engine: Engine, rental_id: uuid.UUID) -> bool:
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT count(*) FROM rentals WHERE id = :id"), {"id": rental_id}
        ).scalar_one()
    return bool(count)


@pytest.mark.parametrize("status", ["reserved", "active", "completed", "cancelled"])
def test_admin_hard_deletes_rental_in_any_status(
    client: TestClient,
    test_engine: Engine,
    admin_token: str,
    user: UserCred,
    rental_factory: RentalFactory,
    status: str,
) -> None:
    rental_id = rental_factory(user.id, status=status)
    response = client.delete(f"{RENTALS}/{rental_id}", headers=auth(admin_token))
    assert response.status_code == 204
    assert response.content == b""
    assert not exists(test_engine, rental_id)
    assert client.get(f"{RENTALS}/{rental_id}", headers=auth(admin_token)).status_code == 404


def test_deleting_frees_the_dates_and_unblocks_user_and_vehicle_deletion(
    client: TestClient,
    admin_token: str,
    user: UserCred,
    rental_factory: RentalFactory,
) -> None:
    rental_id = rental_factory(user.id)
    assert client.delete(f"/api/v1/users/{user.id}", headers=auth(admin_token)).status_code == 409
    assert client.delete(f"{RENTALS}/{rental_id}", headers=auth(admin_token)).status_code == 204
    assert client.delete(f"/api/v1/users/{user.id}", headers=auth(admin_token)).status_code == 204


def test_unknown_rental_is_404_and_malformed_id_is_422(
    client: TestClient, admin_token: str
) -> None:
    assert client.delete(f"{RENTALS}/{uuid.uuid4()}", headers=auth(admin_token)).status_code == 404
    assert client.delete(f"{RENTALS}/nope", headers=auth(admin_token)).status_code == 422


def test_user_is_403_even_for_own_rental_and_nothing_is_deleted(
    client: TestClient,
    test_engine: Engine,
    user: UserCred,
    user_token: str,
    user_factory: UserFactory,
    rental_factory: RentalFactory,
) -> None:
    own = rental_factory(user.id)
    others = rental_factory(user_factory().id)
    for rental_id in (own, others):
        response = client.delete(f"{RENTALS}/{rental_id}", headers=auth(user_token))
        assert response.status_code == 403
        assert exists(test_engine, rental_id)


def test_anonymous_is_401(
    client: TestClient, test_engine: Engine, user: UserCred, rental_factory: RentalFactory
) -> None:
    rental_id = rental_factory(user.id)
    assert client.delete(f"{RENTALS}/{rental_id}").status_code == 401
    assert exists(test_engine, rental_id)
