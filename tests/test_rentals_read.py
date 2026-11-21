"""AC-R3: GET /rentals and GET /rentals/{id}."""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.security import create_access_token
from tests.conftest import RentalFactory, UserCred, UserFactory, VehicleFactory
from tests.helpers import auth

RENTALS = "/api/v1/rentals"


def ids(response: Any) -> list[str]:
    return [item["id"] for item in response.json()["items"]]


def token_for(person: UserCred) -> str:
    return create_access_token(person.id, person.role)[0]


def test_user_sees_only_own_rentals(
    client: TestClient,
    user: UserCred,
    user_token: str,
    user_factory: UserFactory,
    rental_factory: RentalFactory,
) -> None:
    other = user_factory()
    mine = [str(rental_factory(user.id)) for _ in range(2)]
    rental_factory(other.id)
    response = client.get(RENTALS, headers=auth(user_token))
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "total", "limit", "offset"}
    assert body["total"] == 2
    assert ids(response) == mine


def test_user_cannot_widen_scope_with_user_id_filter(
    client: TestClient,
    user: UserCred,
    user_token: str,
    user_factory: UserFactory,
    rental_factory: RentalFactory,
) -> None:
    other = user_factory()
    rental_factory(other.id)
    mine = rental_factory(user.id)
    response = client.get(RENTALS, headers=auth(user_token), params={"user_id": str(other.id)})
    assert response.json()["items"] == []
    own = client.get(RENTALS, headers=auth(user_token), params={"user_id": str(user.id)})
    assert ids(own) == [str(mine)]


def test_admin_sees_all_and_can_filter(
    client: TestClient,
    admin_token: str,
    user: UserCred,
    user_factory: UserFactory,
    vehicle_factory: VehicleFactory,
    rental_factory: RentalFactory,
) -> None:
    other = user_factory()
    car_a, car_b = vehicle_factory(), vehicle_factory()
    r1 = str(rental_factory(user.id, car_a, status="reserved"))
    r2 = str(rental_factory(user.id, car_b, status="completed"))
    r3 = str(rental_factory(other.id, car_a, status="cancelled"))
    headers = auth(admin_token)
    assert ids(client.get(RENTALS, headers=headers)) == [r1, r2, r3]
    by_user = client.get(RENTALS, headers=headers, params={"user_id": str(user.id)})
    assert ids(by_user) == [r1, r2]
    by_vehicle = client.get(RENTALS, headers=headers, params={"vehicle_id": str(car_a)})
    assert ids(by_vehicle) == [r1, r3]
    by_status = client.get(RENTALS, headers=headers, params={"status": "completed"})
    assert ids(by_status) == [r2]
    combined = {"user_id": str(user.id), "vehicle_id": str(car_a), "status": "reserved"}
    assert ids(client.get(RENTALS, headers=headers, params=combined)) == [r1]


def test_user_can_filter_own_rentals_by_status(
    client: TestClient, user: UserCred, user_token: str, rental_factory: RentalFactory
) -> None:
    rental_factory(user.id, status="completed")
    active = rental_factory(user.id, status="reserved")
    response = client.get(RENTALS, headers=auth(user_token), params={"status": "reserved"})
    assert ids(response) == [str(active)]


def test_pagination_and_stable_order(
    client: TestClient, admin_token: str, user: UserCred, rental_factory: RentalFactory
) -> None:
    created = [str(rental_factory(user.id)) for _ in range(5)]
    seen: list[str] = []
    for offset in (0, 2, 4):
        response = client.get(
            RENTALS, headers=auth(admin_token), params={"limit": 2, "offset": offset}
        )
        assert response.json()["total"] == 5
        seen += ids(response)
    assert seen == created


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"status": "lost"},
        {"user_id": "nope"},
        {"vehicle_id": "nope"},
    ],
)
def test_invalid_query_is_422(client: TestClient, user_token: str, params: dict[str, Any]) -> None:
    assert client.get(RENTALS, headers=auth(user_token), params=params).status_code == 422


def test_get_own_rental(
    client: TestClient, user: UserCred, user_token: str, rental_factory: RentalFactory
) -> None:
    rental_id = rental_factory(user.id)
    response = client.get(f"{RENTALS}/{rental_id}", headers=auth(user_token))
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(rental_id)
    assert body["user_id"] == str(user.id)
    assert body["total_price"] == "150.00"


def test_other_users_rental_is_404_for_user_but_200_for_admin(
    client: TestClient,
    admin_token: str,
    user_token: str,
    user_factory: UserFactory,
    rental_factory: RentalFactory,
) -> None:
    other = user_factory()
    rental_id = rental_factory(other.id)
    hidden = client.get(f"{RENTALS}/{rental_id}", headers=auth(user_token))
    assert hidden.status_code == 404
    missing = client.get(f"{RENTALS}/{uuid.uuid4()}", headers=auth(user_token))
    assert hidden.json() == missing.json()  # existence does not leak
    assert client.get(f"{RENTALS}/{rental_id}", headers=auth(admin_token)).status_code == 200
    assert client.get(f"{RENTALS}/{rental_id}", headers=auth(token_for(other))).status_code == 200


def test_unknown_rental_is_404_and_malformed_id_is_422(
    client: TestClient, admin_token: str
) -> None:
    assert client.get(f"{RENTALS}/{uuid.uuid4()}", headers=auth(admin_token)).status_code == 404
    assert client.get(f"{RENTALS}/nope", headers=auth(admin_token)).status_code == 422


def test_anonymous_is_401(
    client: TestClient, user: UserCred, rental_factory: RentalFactory
) -> None:
    rental_id = rental_factory(user.id)
    assert client.get(RENTALS).status_code == 401
    assert client.get(f"{RENTALS}/{rental_id}").status_code == 401
