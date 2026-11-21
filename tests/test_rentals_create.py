"""AC-R1: POST /rentals."""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from tests.conftest import UserCred, UserFactory, VehicleFactory
from tests.helpers import auth

RENTALS = "/api/v1/rentals"
VEHICLES = "/api/v1/vehicles"
READ_FIELDS = {
    "id",
    "user_id",
    "vehicle_id",
    "start_date",
    "end_date",
    "status",
    "total_price",
    "notes",
    "created_at",
    "updated_at",
}


def today() -> date:
    return datetime.now(UTC).date()


def body(
    vehicle_id: uuid.UUID, start: date | None = None, days: int = 3, **extra: Any
) -> dict[str, Any]:
    start = start or today() + timedelta(days=10)
    base = {
        "vehicle_id": str(vehicle_id),
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=days - 1)).isoformat(),
    }
    return {**base, **extra}


def test_user_creates_rental_for_self(
    client: TestClient, user: UserCred, user_token: str, vehicle_factory: VehicleFactory
) -> None:
    vehicle_id = vehicle_factory(daily_rate=Decimal("49.99"))
    response = client.post(
        RENTALS, headers=auth(user_token), json=body(vehicle_id, days=4, notes="  Airport pickup ")
    )
    assert response.status_code == 201
    rental = response.json()
    assert set(rental) == READ_FIELDS
    assert rental["user_id"] == str(user.id)
    assert rental["vehicle_id"] == str(vehicle_id)
    assert rental["status"] == "reserved"
    assert rental["total_price"] == "199.96"  # 49.99 x 4 days
    assert rental["notes"] == "Airport pickup"
    assert response.headers["Location"] == f"/api/v1/rentals/{rental['id']}"


def test_single_day_rental_counts_as_one_day(
    client: TestClient, user_token: str, vehicle_factory: VehicleFactory
) -> None:
    vehicle_id = vehicle_factory(daily_rate=Decimal("80.00"))
    response = client.post(RENTALS, headers=auth(user_token), json=body(vehicle_id, days=1))
    assert response.status_code == 201
    assert response.json()["total_price"] == "80.00"
    assert response.json()["start_date"] == response.json()["end_date"]


def test_starting_today_is_allowed(
    client: TestClient, user_token: str, vehicle_factory: VehicleFactory
) -> None:
    response = client.post(
        RENTALS, headers=auth(user_token), json=body(vehicle_factory(), start=today())
    )
    assert response.status_code == 201


def test_price_is_frozen_when_the_vehicle_rate_changes(
    client: TestClient, admin_token: str, user_token: str, vehicle_factory: VehicleFactory
) -> None:
    vehicle_id = vehicle_factory(daily_rate=Decimal("100.00"))
    created = client.post(RENTALS, headers=auth(user_token), json=body(vehicle_id, days=2)).json()
    client.patch(
        f"{VEHICLES}/{vehicle_id}", headers=auth(admin_token), json={"daily_rate": "500.00"}
    )
    assert created["total_price"] == "200.00"


@pytest.mark.parametrize("extra", [{"total_price": "1.00"}, {"status": "completed"}, {"id": "x"}])
def test_server_controlled_fields_are_rejected(
    client: TestClient, user_token: str, vehicle_factory: VehicleFactory, extra: dict[str, Any]
) -> None:
    response = client.post(RENTALS, headers=auth(user_token), json=body(vehicle_factory(), **extra))
    assert response.status_code == 422


def test_end_before_start_is_422(
    client: TestClient, user_token: str, vehicle_factory: VehicleFactory
) -> None:
    payload = body(vehicle_factory())
    payload["end_date"] = (today() + timedelta(days=5)).isoformat()
    payload["start_date"] = (today() + timedelta(days=6)).isoformat()
    assert client.post(RENTALS, headers=auth(user_token), json=payload).status_code == 422


@pytest.mark.parametrize("field", ["vehicle_id", "start_date", "end_date"])
def test_missing_required_field_is_422(
    client: TestClient, user_token: str, vehicle_factory: VehicleFactory, field: str
) -> None:
    payload = body(vehicle_factory())
    del payload[field]
    assert client.post(RENTALS, headers=auth(user_token), json=payload).status_code == 422


@pytest.mark.parametrize(
    "overrides",
    [
        {"start_date": "not-a-date"},
        {"vehicle_id": "not-a-uuid"},
        {"notes": "n" * 1001},
        {"user_id": "not-a-uuid"},
    ],
)
def test_malformed_values_are_422(
    client: TestClient,
    user_token: str,
    vehicle_factory: VehicleFactory,
    overrides: dict[str, Any],
) -> None:
    payload = {**body(vehicle_factory()), **overrides}
    assert client.post(RENTALS, headers=auth(user_token), json=payload).status_code == 422


def test_rental_longer_than_a_year_is_422(
    client: TestClient, user_token: str, vehicle_factory: VehicleFactory
) -> None:
    response = client.post(
        RENTALS, headers=auth(user_token), json=body(vehicle_factory(), days=366)
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_dates"
    ok = client.post(RENTALS, headers=auth(user_token), json=body(vehicle_factory(), days=365))
    assert ok.status_code == 201


def test_user_cannot_start_in_the_past_but_admin_can_backdate(
    client: TestClient, user_token: str, admin_token: str, vehicle_factory: VehicleFactory
) -> None:
    yesterday = today() - timedelta(days=1)
    as_user = client.post(
        RENTALS, headers=auth(user_token), json=body(vehicle_factory(), start=yesterday)
    )
    assert as_user.status_code == 422
    assert as_user.json()["error"]["code"] == "invalid_dates"
    as_admin = client.post(
        RENTALS, headers=auth(admin_token), json=body(vehicle_factory(), start=yesterday)
    )
    assert as_admin.status_code == 201


@pytest.mark.parametrize("status", ["maintenance", "retired"])
def test_non_rentable_vehicle_is_409(
    client: TestClient, user_token: str, vehicle_factory: VehicleFactory, status: str
) -> None:
    response = client.post(
        RENTALS, headers=auth(user_token), json=body(vehicle_factory(status=status))
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "vehicle_not_rentable"


def test_unknown_or_deleted_vehicle_is_404(
    client: TestClient, user_token: str, vehicle_factory: VehicleFactory
) -> None:
    deleted = vehicle_factory(deleted_at=datetime.now(UTC))
    for vehicle_id in (uuid.uuid4(), deleted):
        response = client.post(RENTALS, headers=auth(user_token), json=body(vehicle_id))
        assert response.status_code == 404


def test_user_may_name_themselves_but_not_others(
    client: TestClient,
    test_engine: Engine,
    user: UserCred,
    user_token: str,
    user_factory: UserFactory,
    vehicle_factory: VehicleFactory,
) -> None:
    other = user_factory()
    vehicle_id = vehicle_factory()
    own = client.post(
        RENTALS, headers=auth(user_token), json=body(vehicle_id, user_id=str(user.id))
    )
    assert own.status_code == 201
    forbidden = client.post(
        RENTALS,
        headers=auth(user_token),
        json=body(vehicle_id, start=today() + timedelta(days=100), user_id=str(other.id)),
    )
    assert forbidden.status_code == 403
    with test_engine.connect() as conn:
        count = conn.execute(text("SELECT count(*) FROM rentals")).scalar_one()
    assert count == 1


def test_admin_can_create_for_any_user(
    client: TestClient,
    admin_token: str,
    user: UserCred,
    vehicle_factory: VehicleFactory,
) -> None:
    response = client.post(
        RENTALS, headers=auth(admin_token), json=body(vehicle_factory(), user_id=str(user.id))
    )
    assert response.status_code == 201
    assert response.json()["user_id"] == str(user.id)


def test_admin_without_user_id_rents_for_self(
    client: TestClient, admin: UserCred, admin_token: str, vehicle_factory: VehicleFactory
) -> None:
    response = client.post(RENTALS, headers=auth(admin_token), json=body(vehicle_factory()))
    assert response.json()["user_id"] == str(admin.id)


def test_admin_for_unknown_or_inactive_user(
    client: TestClient,
    admin_token: str,
    user_factory: UserFactory,
    vehicle_factory: VehicleFactory,
) -> None:
    inactive = user_factory(is_active=False)
    vehicle_id = vehicle_factory()
    unknown = client.post(
        RENTALS, headers=auth(admin_token), json=body(vehicle_id, user_id=str(uuid.uuid4()))
    )
    assert unknown.status_code == 404
    gone = client.post(
        RENTALS, headers=auth(admin_token), json=body(vehicle_id, user_id=str(inactive.id))
    )
    assert gone.status_code == 409
    assert gone.json()["error"]["code"] == "user_inactive"


def test_anonymous_is_401(client: TestClient, vehicle_factory: VehicleFactory) -> None:
    assert client.post(RENTALS, json=body(vehicle_factory())).status_code == 401
