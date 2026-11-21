"""AC-R2: overlapping rentals are rejected; adjacent and cancelled-overlap bookings are allowed."""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.db import get_engine
from app.main import create_app
from app.security import create_access_token
from tests.conftest import RentalFactory, UserCred, UserFactory, VehicleFactory
from tests.helpers import auth

RENTALS = "/api/v1/rentals"


def base_day() -> date:
    return datetime.now(UTC).date() + timedelta(days=30)


def book(
    client: TestClient, token: str, vehicle_id: uuid.UUID, first: int, last: int
) -> tuple[int, dict[str, object]]:
    """Book day offsets [first, last] (inclusive) counted from `base_day()`."""
    payload = {
        "vehicle_id": str(vehicle_id),
        "start_date": (base_day() + timedelta(days=first)).isoformat(),
        "end_date": (base_day() + timedelta(days=last)).isoformat(),
    }
    response = client.post(RENTALS, headers=auth(token), json=payload)
    return response.status_code, response.json()


def count_rentals(engine: Engine) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text("SELECT count(*) FROM rentals")).scalar_one())


@pytest.mark.parametrize(
    ("first", "last"),
    [
        (10, 14),  # identical
        (12, 20),  # overlaps the end
        (5, 10),  # overlaps the start by one shared day
        (14, 14),  # touches the last day only
        (11, 12),  # fully inside
        (0, 30),  # fully around
    ],
)
def test_overlapping_booking_is_409(
    client: TestClient,
    test_engine: Engine,
    user_token: str,
    vehicle_factory: VehicleFactory,
    first: int,
    last: int,
) -> None:
    vehicle_id = vehicle_factory()
    assert book(client, user_token, vehicle_id, 10, 14)[0] == 201
    status, body = book(client, user_token, vehicle_id, first, last)
    assert status == 409
    assert body["error"] == {
        "code": "rental_overlap",
        "message": "Vehicle is already booked for these dates.",
    }
    assert count_rentals(test_engine) == 1  # the rejected booking left nothing behind


def test_adjacent_bookings_are_allowed(
    client: TestClient, user_token: str, vehicle_factory: VehicleFactory
) -> None:
    vehicle_id = vehicle_factory()
    assert book(client, user_token, vehicle_id, 10, 14)[0] == 201
    assert book(client, user_token, vehicle_id, 15, 18)[0] == 201  # starts the day after
    assert book(client, user_token, vehicle_id, 5, 9)[0] == 201  # ends the day before


def test_same_dates_on_another_vehicle_are_allowed(
    client: TestClient, user_token: str, vehicle_factory: VehicleFactory
) -> None:
    assert book(client, user_token, vehicle_factory(), 10, 14)[0] == 201
    assert book(client, user_token, vehicle_factory(), 10, 14)[0] == 201


def test_a_different_user_cannot_book_taken_dates(
    client: TestClient, user_token: str, admin_token: str, vehicle_factory: VehicleFactory
) -> None:
    vehicle_id = vehicle_factory()
    assert book(client, user_token, vehicle_id, 10, 14)[0] == 201
    assert book(client, admin_token, vehicle_id, 12, 13)[0] == 409


def test_cancelled_booking_does_not_block_new_booking(
    client: TestClient,
    user: UserCred,
    user_token: str,
    vehicle_factory: VehicleFactory,
    rental_factory: RentalFactory,
) -> None:
    vehicle_id = vehicle_factory()
    rental_factory(
        user.id,
        vehicle_id,
        status="cancelled",
        start_date=base_day() + timedelta(days=10),
        end_date=base_day() + timedelta(days=14),
    )
    assert book(client, user_token, vehicle_id, 10, 14)[0] == 201


@pytest.mark.parametrize("status", ["reserved", "active"])
def test_reserved_and_active_bookings_block(
    client: TestClient,
    user: UserCred,
    user_token: str,
    vehicle_factory: VehicleFactory,
    rental_factory: RentalFactory,
    status: str,
) -> None:
    vehicle_id = vehicle_factory()
    rental_factory(
        user.id,
        vehicle_id,
        status=status,
        start_date=base_day() + timedelta(days=10),
        end_date=base_day() + timedelta(days=14),
    )
    assert book(client, user_token, vehicle_id, 13, 16)[0] == 409


def test_concurrent_requests_for_the_same_dates_only_one_wins(
    test_engine: Engine, user_factory: UserFactory, vehicle_factory: VehicleFactory
) -> None:
    workers = 8
    vehicle_id = vehicle_factory()
    tokens = []
    for _ in range(workers):
        person = user_factory()
        tokens.append(create_access_token(person.id, person.role)[0])

    app = create_app()
    app.dependency_overrides[get_engine] = lambda: test_engine
    barrier = threading.Barrier(workers)

    def attempt(token: str) -> int:
        with TestClient(app) as local_client:
            barrier.wait(timeout=30)
            return book(local_client, token, vehicle_id, 10, 14)[0]

    with ThreadPoolExecutor(max_workers=workers) as pool:
        statuses = list(pool.map(attempt, tokens))

    assert sorted(statuses) == [201] + [409] * (workers - 1)
    assert count_rentals(test_engine) == 1
