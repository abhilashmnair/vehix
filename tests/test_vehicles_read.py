"""AC-V2: GET /vehicles and GET /vehicles/{id}."""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import RentalFactory, UserCred, VehicleFactory
from tests.helpers import auth

VEHICLES = "/api/v1/vehicles"


def ids(response: Any) -> list[str]:
    return [item["id"] for item in response.json()["items"]]


def test_any_authenticated_user_can_list(
    client: TestClient, user_token: str, admin_token: str, vehicle_factory: VehicleFactory
) -> None:
    created = [str(vehicle_factory()) for _ in range(3)]
    for token in (user_token, admin_token):
        response = client.get(VEHICLES, headers=auth(token))
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"items", "total", "limit", "offset"}
        assert body["total"] == 3
        assert ids(response) == created
        assert "deleted_at" not in body["items"][0]


def test_pagination_and_stable_order(
    client: TestClient, user_token: str, vehicle_factory: VehicleFactory
) -> None:
    created = [str(vehicle_factory()) for _ in range(5)]
    seen: list[str] = []
    for offset in (0, 2, 4):
        response = client.get(
            VEHICLES, headers=auth(user_token), params={"limit": 2, "offset": offset}
        )
        assert response.json()["total"] == 5
        seen += ids(response)
    assert seen == created


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}])
def test_invalid_pagination_is_422(
    client: TestClient, user_token: str, params: dict[str, int]
) -> None:
    assert client.get(VEHICLES, headers=auth(user_token), params=params).status_code == 422


def test_filter_by_status_and_make(
    client: TestClient, user_token: str, vehicle_factory: VehicleFactory
) -> None:
    available = vehicle_factory(make="Toyota")
    maintenance = vehicle_factory(make="Toyota", status="maintenance")
    honda = vehicle_factory(make="Honda")
    headers = auth(user_token)
    by_status = client.get(VEHICLES, headers=headers, params={"status": "maintenance"})
    assert ids(by_status) == [str(maintenance)]
    by_make = client.get(VEHICLES, headers=headers, params={"make": "tOyOtA"})
    assert ids(by_make) == [str(available), str(maintenance)]
    both = client.get(VEHICLES, headers=headers, params={"make": "toyota", "status": "available"})
    assert ids(both) == [str(available)]
    assert str(honda) in ids(client.get(VEHICLES, headers=headers))


def test_invalid_filter_values_are_422(client: TestClient, user_token: str) -> None:
    headers = auth(user_token)
    assert client.get(VEHICLES, headers=headers, params={"status": "stolen"}).status_code == 422
    assert client.get(VEHICLES, headers=headers, params={"available_from": "x"}).status_code == 422
    reversed_range = {"available_from": "2030-02-02", "available_to": "2030-02-01"}
    assert client.get(VEHICLES, headers=headers, params=reversed_range).status_code == 422


def test_availability_filter(
    client: TestClient,
    user_token: str,
    user: UserCred,
    vehicle_factory: VehicleFactory,
    rental_factory: RentalFactory,
) -> None:
    free = vehicle_factory()
    booked = vehicle_factory()
    cancelled_only = vehicle_factory()
    adjacent = vehicle_factory()
    maintenance = vehicle_factory(status="maintenance")
    rental_factory(user.id, booked, start_date="2030-03-10", end_date="2030-03-15")
    rental_factory(
        user.id, cancelled_only, start_date="2030-03-10", end_date="2030-03-15", status="cancelled"
    )
    rental_factory(user.id, adjacent, start_date="2030-03-01", end_date="2030-03-09")
    window = {"available_from": "2030-03-10", "available_to": "2030-03-12"}
    result = ids(client.get(VEHICLES, headers=auth(user_token), params=window))
    assert str(free) in result
    assert str(cancelled_only) in result
    assert str(adjacent) in result  # ends the day before the window
    assert str(booked) not in result
    assert str(maintenance) not in result  # not rentable
    # Touching on a single shared day is a conflict (ranges are inclusive).
    touching = {"available_from": "2030-03-15", "available_to": "2030-03-20"}
    assert str(booked) not in ids(client.get(VEHICLES, headers=auth(user_token), params=touching))
    # Only one bound given means a single day.
    single = {"available_from": "2030-03-12"}
    assert str(booked) not in ids(client.get(VEHICLES, headers=auth(user_token), params=single))
    assert str(free) in ids(client.get(VEHICLES, headers=auth(user_token), params=single))


def test_soft_deleted_vehicles_are_hidden_from_list_and_404_on_get(
    client: TestClient, user_token: str, vehicle_factory: VehicleFactory
) -> None:
    visible = vehicle_factory()
    deleted = vehicle_factory(deleted_at=datetime.now(UTC))
    listing = client.get(VEHICLES, headers=auth(user_token))
    assert ids(listing) == [str(visible)]
    assert listing.json()["total"] == 1
    assert client.get(f"{VEHICLES}/{deleted}", headers=auth(user_token)).status_code == 404


def test_get_vehicle_by_id(
    client: TestClient, user_token: str, vehicle_factory: VehicleFactory
) -> None:
    vehicle_id = vehicle_factory(license_plate="GET-1", vin=None)
    response = client.get(f"{VEHICLES}/{vehicle_id}", headers=auth(user_token))
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(vehicle_id)
    assert body["license_plate"] == "GET-1"
    assert body["daily_rate"] == "50.00"


def test_unknown_vehicle_is_404_and_malformed_id_is_422(
    client: TestClient, user_token: str
) -> None:
    response = client.get(f"{VEHICLES}/{uuid.uuid4()}", headers=auth(user_token))
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert client.get(f"{VEHICLES}/nope", headers=auth(user_token)).status_code == 422


def test_anonymous_is_401(client: TestClient, vehicle_factory: VehicleFactory) -> None:
    vehicle_id = vehicle_factory()
    assert client.get(VEHICLES).status_code == 401
    assert client.get(f"{VEHICLES}/{vehicle_id}").status_code == 401
