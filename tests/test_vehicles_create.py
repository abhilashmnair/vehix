"""AC-V1: admin POST /vehicles."""

import secrets
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import VehicleFactory
from tests.helpers import auth

VEHICLES = "/api/v1/vehicles"
READ_FIELDS = {
    "id",
    "license_plate",
    "vin",
    "make",
    "model",
    "year",
    "daily_rate",
    "status",
    "created_at",
    "updated_at",
}


def payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "license_plate": f"AB{secrets.token_hex(3).upper()}",
        "make": "Toyota",
        "model": "Corolla",
        "year": 2022,
        "daily_rate": "49.90",
    }
    return {**base, **overrides}


def vin() -> str:
    return "1HGCM82633A" + "".join(
        secrets.choice("0123456789ABCDEFGHJKLMNPRSTUVWXYZ") for _ in range(6)
    )


def test_admin_creates_vehicle(client: TestClient, admin_token: str) -> None:
    body = payload(license_plate="  ab-123 cd ", vin=vin().lower())
    response = client.post(VEHICLES, headers=auth(admin_token), json=body)
    assert response.status_code == 201
    created = response.json()
    assert set(created) == READ_FIELDS
    assert created["license_plate"] == "AB-123 CD"
    assert created["vin"] == body["vin"].upper()
    assert created["daily_rate"] == "49.90"
    assert created["status"] == "available"
    assert response.headers["Location"] == f"/api/v1/vehicles/{created['id']}"


def test_vin_is_optional_and_nulls_do_not_collide(client: TestClient, admin_token: str) -> None:
    for _ in range(2):
        response = client.post(VEHICLES, headers=auth(admin_token), json=payload())
        assert response.status_code == 201
        assert response.json()["vin"] is None


def test_can_create_vehicle_in_maintenance(client: TestClient, admin_token: str) -> None:
    response = client.post(VEHICLES, headers=auth(admin_token), json=payload(status="maintenance"))
    assert response.status_code == 201
    assert response.json()["status"] == "maintenance"


def test_numeric_json_rate_is_accepted(client: TestClient, admin_token: str) -> None:
    response = client.post(VEHICLES, headers=auth(admin_token), json=payload(daily_rate=75.5))
    assert response.status_code == 201
    assert response.json()["daily_rate"] == "75.50"


def test_duplicate_license_plate_is_409_after_normalisation(
    client: TestClient, admin_token: str
) -> None:
    client.post(VEHICLES, headers=auth(admin_token), json=payload(license_plate="XY-999"))
    response = client.post(
        VEHICLES, headers=auth(admin_token), json=payload(license_plate=" xy-999 ")
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "license_plate_conflict"


def test_duplicate_vin_is_409(client: TestClient, admin_token: str) -> None:
    same_vin = vin()
    assert (
        client.post(VEHICLES, headers=auth(admin_token), json=payload(vin=same_vin)).status_code
        == 201
    )
    response = client.post(VEHICLES, headers=auth(admin_token), json=payload(vin=same_vin.lower()))
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "vin_conflict"


@pytest.mark.parametrize(
    "overrides",
    [
        {"daily_rate": "0"},
        {"daily_rate": "-5.00"},
        {"daily_rate": "10.999"},
        {"daily_rate": "abc"},
        {"daily_rate": "1000000.00"},
        {"year": 1949},
        {"year": datetime.now(UTC).year + 2},
        {"year": "twenty"},
        {"license_plate": "   "},
        {"license_plate": "X" * 21},
        {"vin": "TOO-SHORT"},
        {"vin": "1HGCM82633A00000O"},  # contains the letter O
        {"make": ""},
        {"model": "M" * 101},
        {"status": "stolen"},
        {"id": "abc"},
        {"deleted_at": "2030-01-01T00:00:00Z"},
    ],
)
def test_invalid_data_is_422(
    client: TestClient, admin_token: str, overrides: dict[str, Any]
) -> None:
    response = client.post(VEHICLES, headers=auth(admin_token), json=payload(**overrides))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize("missing", ["license_plate", "make", "model", "year", "daily_rate"])
def test_missing_required_field_is_422(client: TestClient, admin_token: str, missing: str) -> None:
    body = payload()
    del body[missing]
    assert client.post(VEHICLES, headers=auth(admin_token), json=body).status_code == 422


def test_year_boundaries_are_accepted(client: TestClient, admin_token: str) -> None:
    for year in (1950, datetime.now(UTC).year + 1):
        response = client.post(VEHICLES, headers=auth(admin_token), json=payload(year=year))
        assert response.status_code == 201


def test_duplicate_of_existing_fixture_vehicle_is_409(
    client: TestClient, admin_token: str, vehicle_factory: VehicleFactory
) -> None:
    vehicle_factory(license_plate="DUP-1")
    response = client.post(VEHICLES, headers=auth(admin_token), json=payload(license_plate="dup-1"))
    assert response.status_code == 409


def test_non_admin_is_403_and_anonymous_is_401(client: TestClient, user_token: str) -> None:
    assert client.post(VEHICLES, headers=auth(user_token), json=payload()).status_code == 403
    assert client.post(VEHICLES, json=payload()).status_code == 401
