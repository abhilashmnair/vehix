"""AC-R5: cancel and status transitions follow the state machine."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import RentalFactory, UserCred, UserFactory, VehicleFactory
from tests.helpers import auth

RENTALS = "/api/v1/rentals"
ACTIONS = {"activate": "active", "complete": "completed", "cancel": "cancelled"}
STATUSES = ["reserved", "active", "completed", "cancelled"]
# (current status, action) pairs the state machine allows.
ALLOWED = {
    ("reserved", "activate"),
    ("reserved", "cancel"),
    ("active", "complete"),
    ("active", "cancel"),
}


def act(client: TestClient, token: str, rental_id: uuid.UUID, action: str) -> Any:
    return client.post(f"{RENTALS}/{rental_id}/{action}", headers=auth(token))


@pytest.mark.parametrize("action", list(ACTIONS))
@pytest.mark.parametrize("current", STATUSES)
def test_admin_transition_matrix(
    client: TestClient,
    admin_token: str,
    user: UserCred,
    rental_factory: RentalFactory,
    current: str,
    action: str,
) -> None:
    rental_id = rental_factory(user.id, status=current)
    response = act(client, admin_token, rental_id, action)
    if (current, action) in ALLOWED:
        assert response.status_code == 200
        assert response.json()["status"] == ACTIONS[action]
        stored = client.get(f"{RENTALS}/{rental_id}", headers=auth(admin_token)).json()
        assert stored["status"] == ACTIONS[action]
    else:
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "invalid_state"
        stored = client.get(f"{RENTALS}/{rental_id}", headers=auth(admin_token)).json()
        assert stored["status"] == current


def test_full_happy_path(
    client: TestClient, admin_token: str, user: UserCred, rental_factory: RentalFactory
) -> None:
    rental_id = rental_factory(user.id)
    assert act(client, admin_token, rental_id, "activate").json()["status"] == "active"
    assert act(client, admin_token, rental_id, "complete").json()["status"] == "completed"
    assert act(client, admin_token, rental_id, "cancel").status_code == 409


@pytest.mark.parametrize("current", ["reserved", "active"])
def test_owner_can_cancel_own_open_rental(
    client: TestClient,
    user: UserCred,
    user_token: str,
    rental_factory: RentalFactory,
    current: str,
) -> None:
    rental_id = rental_factory(user.id, status=current)
    response = act(client, user_token, rental_id, "cancel")
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert response.json()["id"] == str(rental_id)


@pytest.mark.parametrize("current", ["completed", "cancelled"])
def test_owner_cannot_cancel_finished_rental(
    client: TestClient,
    user: UserCred,
    user_token: str,
    rental_factory: RentalFactory,
    current: str,
) -> None:
    rental_id = rental_factory(user.id, status=current)
    assert act(client, user_token, rental_id, "cancel").status_code == 409


def test_cancelling_frees_the_dates(
    client: TestClient,
    user: UserCred,
    user_token: str,
    vehicle_factory: VehicleFactory,
    rental_factory: RentalFactory,
) -> None:
    vehicle_id = vehicle_factory()
    start = datetime.now(UTC).date() + timedelta(days=10)
    rental_id = rental_factory(
        user.id, vehicle_id, start_date=start, end_date=start + timedelta(days=2)
    )
    new = {
        "vehicle_id": str(vehicle_id),
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=1)).isoformat(),
    }
    assert client.post(RENTALS, headers=auth(user_token), json=new).status_code == 409
    assert act(client, user_token, rental_id, "cancel").status_code == 200
    assert client.post(RENTALS, headers=auth(user_token), json=new).status_code == 201


def test_cancelling_twice_is_409(
    client: TestClient, user: UserCred, user_token: str, rental_factory: RentalFactory
) -> None:
    rental_id = rental_factory(user.id)
    assert act(client, user_token, rental_id, "cancel").status_code == 200
    assert act(client, user_token, rental_id, "cancel").status_code == 409


def test_user_cannot_touch_other_users_rental(
    client: TestClient, user_token: str, user_factory: UserFactory, rental_factory: RentalFactory
) -> None:
    other = user_factory()
    rental_id = rental_factory(other.id)
    assert act(client, user_token, rental_id, "cancel").status_code == 404
    assert act(client, user_token, uuid.uuid4(), "cancel").status_code == 404


def test_admin_can_cancel_any_rental(
    client: TestClient, admin_token: str, user: UserCred, rental_factory: RentalFactory
) -> None:
    rental_id = rental_factory(user.id)
    assert act(client, admin_token, rental_id, "cancel").status_code == 200


@pytest.mark.parametrize("action", ["activate", "complete"])
def test_activate_and_complete_are_admin_only(
    client: TestClient,
    user: UserCred,
    user_token: str,
    rental_factory: RentalFactory,
    action: str,
) -> None:
    rental_id = rental_factory(user.id, status="active")
    assert act(client, user_token, rental_id, action).status_code == 403
    stored = client.get(f"{RENTALS}/{rental_id}", headers=auth(user_token)).json()
    assert stored["status"] == "active"


@pytest.mark.parametrize("action", list(ACTIONS))
def test_unknown_rental_malformed_id_and_anonymous(
    client: TestClient, admin_token: str, user: UserCred, rental_factory: RentalFactory, action: str
) -> None:
    assert act(client, admin_token, uuid.uuid4(), action).status_code == 404
    assert client.post(f"{RENTALS}/nope/{action}", headers=auth(admin_token)).status_code == 422
    rental_id = rental_factory(user.id)
    assert client.post(f"{RENTALS}/{rental_id}/{action}").status_code == 401
