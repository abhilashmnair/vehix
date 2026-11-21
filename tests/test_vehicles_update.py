"""AC-V3: admin PATCH /vehicles/{id}."""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import VehicleFactory
from tests.helpers import auth

VEHICLES = "/api/v1/vehicles"
VIN_A = "1HGCM82633A004352"
VIN_B = "1HGCM82633A004353"


def test_admin_updates_fields(
    client: TestClient, admin_token: str, vehicle_factory: VehicleFactory
) -> None:
    vehicle_id = vehicle_factory(license_plate="OLD-1")
    response = client.patch(
        f"{VEHICLES}/{vehicle_id}",
        headers=auth(admin_token),
        json={
            "license_plate": " new-2 ",
            "make": "Honda",
            "model": "Civic",
            "year": 2024,
            "daily_rate": "65.25",
            "status": "maintenance",
            "vin": VIN_A.lower(),
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(vehicle_id)
    assert body["license_plate"] == "NEW-2"
    assert (body["make"], body["model"], body["year"]) == ("Honda", "Civic", 2024)
    assert body["daily_rate"] == "65.25"
    assert body["status"] == "maintenance"
    assert body["vin"] == VIN_A
    got = client.get(f"{VEHICLES}/{vehicle_id}", headers=auth(admin_token)).json()
    assert got == body


def test_partial_update_leaves_other_fields_alone(
    client: TestClient, admin_token: str, vehicle_factory: VehicleFactory
) -> None:
    vehicle_id = vehicle_factory(license_plate="KEEP-1", make="Toyota")
    response = client.patch(
        f"{VEHICLES}/{vehicle_id}", headers=auth(admin_token), json={"daily_rate": "10.00"}
    )
    body = response.json()
    assert body["license_plate"] == "KEEP-1"
    assert body["make"] == "Toyota"
    assert body["daily_rate"] == "10.00"


def test_vin_can_be_cleared_with_null(
    client: TestClient, admin_token: str, vehicle_factory: VehicleFactory
) -> None:
    vehicle_id = vehicle_factory(vin=VIN_A)
    response = client.patch(
        f"{VEHICLES}/{vehicle_id}", headers=auth(admin_token), json={"vin": None}
    )
    assert response.status_code == 200
    assert response.json()["vin"] is None


def test_empty_body_is_a_no_op(
    client: TestClient, admin_token: str, vehicle_factory: VehicleFactory
) -> None:
    vehicle_id = vehicle_factory()
    response = client.patch(f"{VEHICLES}/{vehicle_id}", headers=auth(admin_token), json={})
    assert response.status_code == 200


def test_updating_to_own_current_values_is_not_a_conflict(
    client: TestClient, admin_token: str, vehicle_factory: VehicleFactory
) -> None:
    vehicle_id = vehicle_factory(license_plate="SAME-1", vin=VIN_A)
    response = client.patch(
        f"{VEHICLES}/{vehicle_id}",
        headers=auth(admin_token),
        json={"license_plate": "same-1", "vin": VIN_A},
    )
    assert response.status_code == 200


def test_plate_and_vin_conflicts_are_409(
    client: TestClient, admin_token: str, vehicle_factory: VehicleFactory
) -> None:
    vehicle_factory(license_plate="TAKEN-1", vin=VIN_A)
    vehicle_id = vehicle_factory(license_plate="MINE-1", vin=VIN_B)
    plate = client.patch(
        f"{VEHICLES}/{vehicle_id}", headers=auth(admin_token), json={"license_plate": "taken-1"}
    )
    assert plate.status_code == 409
    assert plate.json()["error"]["code"] == "license_plate_conflict"
    vin = client.patch(f"{VEHICLES}/{vehicle_id}", headers=auth(admin_token), json={"vin": VIN_A})
    assert vin.status_code == 409
    assert vin.json()["error"]["code"] == "vin_conflict"
    unchanged = client.get(f"{VEHICLES}/{vehicle_id}", headers=auth(admin_token)).json()
    assert unchanged["license_plate"] == "MINE-1"
    assert unchanged["vin"] == VIN_B


@pytest.mark.parametrize(
    "payload",
    [
        {"daily_rate": "0"},
        {"daily_rate": "-1"},
        {"year": 1949},
        {"year": datetime.now(UTC).year + 2},
        {"status": "stolen"},
        {"vin": "short"},
        {"license_plate": "  "},
        {"make": None},
        {"daily_rate": None},
        {"id": str(uuid.uuid4())},
        {"deleted_at": "2030-01-01T00:00:00Z"},
        {"created_at": "2030-01-01T00:00:00Z"},
    ],
)
def test_invalid_payload_is_422(
    client: TestClient,
    admin_token: str,
    vehicle_factory: VehicleFactory,
    payload: dict[str, Any],
) -> None:
    vehicle_id = vehicle_factory()
    response = client.patch(f"{VEHICLES}/{vehicle_id}", headers=auth(admin_token), json=payload)
    assert response.status_code == 422


def test_unknown_or_soft_deleted_vehicle_is_404(
    client: TestClient, admin_token: str, vehicle_factory: VehicleFactory
) -> None:
    deleted = vehicle_factory(deleted_at=datetime.now(UTC))
    for target in (uuid.uuid4(), deleted):
        response = client.patch(
            f"{VEHICLES}/{target}", headers=auth(admin_token), json={"make": "Honda"}
        )
        assert response.status_code == 404


def test_non_admin_is_403_and_anonymous_is_401(
    client: TestClient, user_token: str, vehicle_factory: VehicleFactory
) -> None:
    vehicle_id = vehicle_factory(make="Toyota")
    body = {"make": "Hacked"}
    assert (
        client.patch(f"{VEHICLES}/{vehicle_id}", headers=auth(user_token), json=body).status_code
        == 403
    )
    assert client.patch(f"{VEHICLES}/{vehicle_id}", json=body).status_code == 401
    unchanged = client.get(f"{VEHICLES}/{vehicle_id}", headers=auth(user_token)).json()
    assert unchanged["make"] == "Toyota"
