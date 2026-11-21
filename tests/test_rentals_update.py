"""AC-R4: PATCH /rentals/{id}."""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import RentalFactory, UserCred, UserFactory, VehicleFactory
from tests.helpers import auth

RENTALS = "/api/v1/rentals"
VEHICLES = "/api/v1/vehicles"


def today() -> date:
    return datetime.now(UTC).date()


def day(offset: int) -> date:
    return today() + timedelta(days=offset)


def patch(client: TestClient, token: str, rental_id: uuid.UUID, **body: Any) -> Any:
    return client.patch(f"{RENTALS}/{rental_id}", headers=auth(token), json=body)


@pytest.fixture
def mine(
    user: UserCred, vehicle_factory: VehicleFactory, rental_factory: RentalFactory
) -> tuple[uuid.UUID, uuid.UUID]:
    """(rental_id, vehicle_id): a reserved 3-day rental at 100.00/day."""
    vehicle_id = vehicle_factory(daily_rate=Decimal("100.00"))
    rental_id = rental_factory(
        user.id,
        vehicle_id,
        start_date=day(10),
        end_date=day(12),
        total_price=Decimal("300.00"),
    )
    return rental_id, vehicle_id


def test_owner_edits_dates_and_price_is_recomputed(
    client: TestClient, user_token: str, mine: tuple[uuid.UUID, uuid.UUID]
) -> None:
    rental_id, _ = mine
    response = patch(
        client, user_token, rental_id, start_date=day(20).isoformat(), end_date=day(24).isoformat()
    )
    assert response.status_code == 200
    body = response.json()
    assert body["start_date"] == day(20).isoformat()
    assert body["end_date"] == day(24).isoformat()
    assert body["total_price"] == "500.00"  # 5 days x 100.00
    assert body["status"] == "reserved"
    assert body["updated_at"] >= body["created_at"]


def test_changing_one_date_uses_the_other_existing_date(
    client: TestClient, user_token: str, mine: tuple[uuid.UUID, uuid.UUID]
) -> None:
    rental_id, _ = mine
    only_end = patch(client, user_token, rental_id, end_date=day(11).isoformat())
    assert only_end.json()["total_price"] == "200.00"
    only_start = patch(client, user_token, rental_id, start_date=day(9).isoformat())
    assert only_start.json()["total_price"] == "300.00"


def test_price_uses_the_rate_frozen_at_creation_not_the_current_rate(
    client: TestClient,
    admin_token: str,
    user_token: str,
    mine: tuple[uuid.UUID, uuid.UUID],
) -> None:
    rental_id, vehicle_id = mine
    client.patch(
        f"{VEHICLES}/{vehicle_id}", headers=auth(admin_token), json={"daily_rate": "999.00"}
    )
    response = patch(client, user_token, rental_id, end_date=day(13).isoformat())
    assert response.json()["total_price"] == "400.00"


def test_notes_can_be_set_and_cleared(
    client: TestClient, user_token: str, mine: tuple[uuid.UUID, uuid.UUID]
) -> None:
    rental_id, _ = mine
    assert patch(client, user_token, rental_id, notes=" hello ").json()["notes"] == "hello"
    cleared = patch(client, user_token, rental_id, notes=None)
    assert cleared.status_code == 200
    assert cleared.json()["notes"] is None


def test_empty_body_is_a_no_op(
    client: TestClient, user_token: str, mine: tuple[uuid.UUID, uuid.UUID]
) -> None:
    rental_id, _ = mine
    response = patch(client, user_token, rental_id)
    assert response.status_code == 200
    assert response.json()["total_price"] == "300.00"


@pytest.mark.parametrize("status", ["active", "completed", "cancelled"])
def test_owner_cannot_edit_once_not_reserved(
    client: TestClient,
    user: UserCred,
    user_token: str,
    rental_factory: RentalFactory,
    status: str,
) -> None:
    rental_id = rental_factory(user.id, status=status)
    for body in ({"end_date": day(50).isoformat()}, {"notes": "late note"}):
        response = patch(client, user_token, rental_id, **body)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "invalid_state"


def test_overlap_is_rechecked_on_edit(
    client: TestClient,
    user: UserCred,
    user_token: str,
    mine: tuple[uuid.UUID, uuid.UUID],
    rental_factory: RentalFactory,
) -> None:
    rental_id, vehicle_id = mine
    rental_factory(user.id, vehicle_id, start_date=day(14), end_date=day(16))
    clash = patch(client, user_token, rental_id, end_date=day(14).isoformat())
    assert clash.status_code == 409
    assert clash.json()["error"]["code"] == "rental_overlap"
    # Nothing changed, and an extension that stops one day short is fine.
    assert client.get(f"{RENTALS}/{rental_id}", headers=auth(user_token)).json()["end_date"] == (
        day(12).isoformat()
    )
    assert patch(client, user_token, rental_id, end_date=day(13).isoformat()).status_code == 200


def test_editing_never_collides_with_itself(
    client: TestClient, user_token: str, mine: tuple[uuid.UUID, uuid.UUID]
) -> None:
    rental_id, _ = mine
    response = patch(client, user_token, rental_id, end_date=day(12).isoformat())
    assert response.status_code == 200


def test_a_cancelled_rental_on_the_dates_does_not_block_an_edit(
    client: TestClient,
    user: UserCred,
    user_token: str,
    mine: tuple[uuid.UUID, uuid.UUID],
    rental_factory: RentalFactory,
) -> None:
    rental_id, vehicle_id = mine
    rental_factory(user.id, vehicle_id, status="cancelled", start_date=day(13), end_date=day(15))
    assert patch(client, user_token, rental_id, end_date=day(14).isoformat()).status_code == 200


def test_user_cannot_move_start_into_the_past_but_admin_can(
    client: TestClient, user_token: str, admin_token: str, mine: tuple[uuid.UUID, uuid.UUID]
) -> None:
    rental_id, _ = mine
    yesterday = (today() - timedelta(days=1)).isoformat()
    refused = patch(client, user_token, rental_id, start_date=yesterday)
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "invalid_dates"
    assert patch(client, admin_token, rental_id, start_date=yesterday).status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {"end_date": (today() + timedelta(days=5)).isoformat()},  # before the existing start
        {"start_date": (today() + timedelta(days=40)).isoformat()},  # after the existing end
    ],
)
def test_resulting_range_must_be_ordered(
    client: TestClient, user_token: str, mine: tuple[uuid.UUID, uuid.UUID], body: dict[str, str]
) -> None:
    rental_id, _ = mine
    assert patch(client, user_token, rental_id, **body).status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"start_date": "nope"},
        {"start_date": None},
        {"end_date": None},
        {"status": "completed"},
        {"total_price": "1.00"},
        {"user_id": str(uuid.uuid4())},
        {"vehicle_id": str(uuid.uuid4())},
        {"notes": "n" * 1001},
    ],
)
def test_invalid_or_forbidden_fields_are_422(
    client: TestClient, user_token: str, mine: tuple[uuid.UUID, uuid.UUID], body: dict[str, Any]
) -> None:
    rental_id, _ = mine
    assert patch(client, user_token, rental_id, **body).status_code == 422


def test_swapped_dates_in_one_request_are_422(
    client: TestClient, user_token: str, mine: tuple[uuid.UUID, uuid.UUID]
) -> None:
    rental_id, _ = mine
    response = patch(
        client, user_token, rental_id, start_date=day(30).isoformat(), end_date=day(20).isoformat()
    )
    assert response.status_code == 422


def test_other_users_rental_is_404_for_user(
    client: TestClient, user_token: str, user_factory: UserFactory, rental_factory: RentalFactory
) -> None:
    other = user_factory()
    rental_id = rental_factory(other.id)
    assert patch(client, user_token, rental_id, notes="x").status_code == 404
    assert patch(client, user_token, uuid.uuid4(), notes="x").status_code == 404


def test_admin_can_edit_any_rental(
    client: TestClient, admin_token: str, mine: tuple[uuid.UUID, uuid.UUID]
) -> None:
    rental_id, _ = mine
    response = patch(client, admin_token, rental_id, end_date=day(11).isoformat(), notes="by admin")
    assert response.status_code == 200
    assert response.json()["total_price"] == "200.00"
    assert response.json()["notes"] == "by admin"


def test_admin_can_edit_dates_of_active_rental_but_not_finished_ones(
    client: TestClient,
    admin_token: str,
    user: UserCred,
    rental_factory: RentalFactory,
) -> None:
    active = rental_factory(user.id, status="active", start_date=day(1), end_date=day(2))
    assert patch(client, admin_token, active, end_date=day(3).isoformat()).status_code == 200
    for finished in ("completed", "cancelled"):
        rental_id = rental_factory(user.id, status=finished)
        dates = patch(client, admin_token, rental_id, end_date=day(60).isoformat())
        assert dates.status_code == 409
        assert dates.json()["error"]["code"] == "invalid_state"
        assert patch(client, admin_token, rental_id, notes="audit").status_code == 200


def test_malformed_id_is_422_and_anonymous_is_401(
    client: TestClient, user_token: str, mine: tuple[uuid.UUID, uuid.UUID]
) -> None:
    rental_id, _ = mine
    assert client.patch(f"{RENTALS}/nope", headers=auth(user_token), json={}).status_code == 422
    assert client.patch(f"{RENTALS}/{rental_id}", json={"notes": "x"}).status_code == 401
