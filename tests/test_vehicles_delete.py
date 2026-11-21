"""AC-V4: admin DELETE /vehicles/{id} (soft delete)."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import RentalFactory, UserCred, VehicleFactory
from tests.helpers import auth

VEHICLES = "/api/v1/vehicles"


def deleted_at(engine: Engine, vehicle_id: uuid.UUID) -> object:
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT deleted_at FROM vehicles WHERE id = :id"), {"id": vehicle_id}
        ).scalar_one()


def test_delete_soft_deletes_and_hides_the_vehicle(
    client: TestClient,
    test_engine: Engine,
    admin_token: str,
    user_token: str,
    vehicle_factory: VehicleFactory,
) -> None:
    vehicle_id = vehicle_factory()
    response = client.delete(f"{VEHICLES}/{vehicle_id}", headers=auth(admin_token))
    assert response.status_code == 204
    assert response.content == b""
    # The row is kept, flagged as deleted ...
    assert deleted_at(test_engine, vehicle_id) is not None
    # ... and is invisible to everyone.
    for token in (admin_token, user_token):
        assert client.get(f"{VEHICLES}/{vehicle_id}", headers=auth(token)).status_code == 404
        assert client.get(VEHICLES, headers=auth(token)).json()["total"] == 0


def test_deleting_twice_or_unknown_is_404(
    client: TestClient, admin_token: str, vehicle_factory: VehicleFactory
) -> None:
    vehicle_id = vehicle_factory()
    assert client.delete(f"{VEHICLES}/{vehicle_id}", headers=auth(admin_token)).status_code == 204
    assert client.delete(f"{VEHICLES}/{vehicle_id}", headers=auth(admin_token)).status_code == 404
    assert client.delete(f"{VEHICLES}/{uuid.uuid4()}", headers=auth(admin_token)).status_code == 404
    assert client.delete(f"{VEHICLES}/nope", headers=auth(admin_token)).status_code == 422


@pytest.mark.parametrize("status", ["reserved", "active"])
def test_vehicle_with_reserved_or_active_rentals_is_409(
    client: TestClient,
    test_engine: Engine,
    admin_token: str,
    user: UserCred,
    vehicle_factory: VehicleFactory,
    rental_factory: RentalFactory,
    status: str,
) -> None:
    vehicle_id = vehicle_factory()
    rental_factory(user.id, vehicle_id, status=status)
    response = client.delete(f"{VEHICLES}/{vehicle_id}", headers=auth(admin_token))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "vehicle_has_active_rentals"
    assert deleted_at(test_engine, vehicle_id) is None
    assert client.get(f"{VEHICLES}/{vehicle_id}", headers=auth(admin_token)).status_code == 200


@pytest.mark.parametrize("status", ["completed", "cancelled"])
def test_vehicle_with_only_finished_rentals_can_be_deleted(
    client: TestClient,
    admin_token: str,
    user: UserCred,
    vehicle_factory: VehicleFactory,
    rental_factory: RentalFactory,
    status: str,
) -> None:
    vehicle_id = vehicle_factory()
    rental_factory(user.id, vehicle_id, status=status)
    assert client.delete(f"{VEHICLES}/{vehicle_id}", headers=auth(admin_token)).status_code == 204


def test_non_admin_is_403_and_anonymous_is_401(
    client: TestClient, user_token: str, vehicle_factory: VehicleFactory
) -> None:
    vehicle_id = vehicle_factory()
    assert client.delete(f"{VEHICLES}/{vehicle_id}", headers=auth(user_token)).status_code == 403
    assert client.delete(f"{VEHICLES}/{vehicle_id}").status_code == 401
    assert client.get(f"{VEHICLES}/{vehicle_id}", headers=auth(user_token)).status_code == 200
