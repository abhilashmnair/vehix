"""AC-H1: every endpoint is called as anonymous, user and admin and must match section 2.

A completeness test fails if a route exists that the matrix does not cover.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import (
    RentalFactory,
    UserCred,
    UserFactory,
    VehicleFactory,
)
from tests.helpers import auth

API = "/api/v1"


@dataclass
class Ctx:
    """Fresh state for one matrix case. `user` is the 'user' caller, `other` a different user."""

    user: UserCred
    other: UserCred
    spare: UserCred  # has no rentals, so it can be deleted
    vehicle: uuid.UUID
    spare_vehicle: uuid.UUID  # has no rentals, so it can be deleted
    book_vehicle: uuid.UUID  # free to rent
    own_rental: uuid.UUID  # reserved, belongs to `user`
    own_active_rental: uuid.UUID  # active, belongs to `user`
    other_rental: uuid.UUID  # reserved, belongs to `other`


@dataclass(frozen=True)
class Case:
    name: str
    method: str
    route: str  # exact FastAPI path template, used by the completeness test
    anonymous: int
    user: int
    admin: int
    args: Callable[[Ctx], dict[str, Any]] = lambda _ctx: {}
    body: Callable[[Ctx], dict[str, Any] | None] = lambda _ctx: None


def rental_body(ctx: Ctx, **extra: Any) -> dict[str, Any]:
    start = datetime.now(UTC).date() + timedelta(days=20)
    return {
        "vehicle_id": str(ctx.book_vehicle),
        "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=1)).isoformat(),
        **extra,
    }


CASES = [
    Case("health", "GET", f"{API}/health", 200, 200, 200),
    Case(
        "login",
        "POST",
        f"{API}/auth/login",
        200,
        200,
        200,
        body=lambda c: {"email": c.user.email, "password": c.user.password},
    ),
    Case("me-get", "GET", f"{API}/users/me", 401, 200, 200),
    Case(
        "me-patch",
        "PATCH",
        f"{API}/users/me",
        401,
        200,
        200,
        body=lambda c: {"full_name": "Renamed Self"},
    ),
    Case("users-list", "GET", f"{API}/users", 401, 403, 200),
    Case(
        "users-create",
        "POST",
        f"{API}/users",
        401,
        403,
        201,
        body=lambda c: {
            "email": "created@example.com",
            "full_name": "Created",
            "password": "a-long-enough-password-" + uuid.uuid4().hex,
        },
    ),
    Case(
        "users-get",
        "GET",
        f"{API}/users/{{user_id}}",
        401,
        403,
        200,
        args=lambda c: {"user_id": c.other.id},
    ),
    Case(
        "users-patch",
        "PATCH",
        f"{API}/users/{{user_id}}",
        401,
        403,
        200,
        args=lambda c: {"user_id": c.other.id},
        body=lambda c: {"full_name": "Renamed Other"},
    ),
    Case(
        "users-delete",
        "DELETE",
        f"{API}/users/{{user_id}}",
        401,
        403,
        204,
        args=lambda c: {"user_id": c.spare.id},
    ),
    Case("vehicles-list", "GET", f"{API}/vehicles", 401, 200, 200),
    Case(
        "vehicles-get",
        "GET",
        f"{API}/vehicles/{{vehicle_id}}",
        401,
        200,
        200,
        args=lambda c: {"vehicle_id": c.vehicle},
    ),
    Case(
        "vehicles-create",
        "POST",
        f"{API}/vehicles",
        401,
        403,
        201,
        body=lambda c: {
            "license_plate": "NEW-" + uuid.uuid4().hex[:6].upper(),
            "make": "Kia",
            "model": "Rio",
            "year": 2023,
            "daily_rate": "30.00",
        },
    ),
    Case(
        "vehicles-patch",
        "PATCH",
        f"{API}/vehicles/{{vehicle_id}}",
        401,
        403,
        200,
        args=lambda c: {"vehicle_id": c.vehicle},
        body=lambda c: {"make": "Skoda"},
    ),
    Case(
        "vehicles-delete",
        "DELETE",
        f"{API}/vehicles/{{vehicle_id}}",
        401,
        403,
        204,
        args=lambda c: {"vehicle_id": c.spare_vehicle},
    ),
    Case("rentals-list", "GET", f"{API}/rentals", 401, 200, 200),
    Case("rentals-create-self", "POST", f"{API}/rentals", 401, 201, 201, body=rental_body),
    Case(
        "rentals-create-for-other",
        "POST",
        f"{API}/rentals",
        401,
        403,
        201,
        body=lambda c: rental_body(c, user_id=str(c.other.id)),
    ),
    Case(
        "rentals-get-own",
        "GET",
        f"{API}/rentals/{{rental_id}}",
        401,
        200,
        200,
        args=lambda c: {"rental_id": c.own_rental},
    ),
    Case(
        "rentals-get-other",
        "GET",
        f"{API}/rentals/{{rental_id}}",
        401,
        404,
        200,
        args=lambda c: {"rental_id": c.other_rental},
    ),
    Case(
        "rentals-patch-own",
        "PATCH",
        f"{API}/rentals/{{rental_id}}",
        401,
        200,
        200,
        args=lambda c: {"rental_id": c.own_rental},
        body=lambda c: {"notes": "updated"},
    ),
    Case(
        "rentals-patch-other",
        "PATCH",
        f"{API}/rentals/{{rental_id}}",
        401,
        404,
        200,
        args=lambda c: {"rental_id": c.other_rental},
        body=lambda c: {"notes": "updated"},
    ),
    Case(
        "rentals-cancel-own",
        "POST",
        f"{API}/rentals/{{rental_id}}/cancel",
        401,
        200,
        200,
        args=lambda c: {"rental_id": c.own_rental},
    ),
    Case(
        "rentals-cancel-other",
        "POST",
        f"{API}/rentals/{{rental_id}}/cancel",
        401,
        404,
        200,
        args=lambda c: {"rental_id": c.other_rental},
    ),
    Case(
        "rentals-activate",
        "POST",
        f"{API}/rentals/{{rental_id}}/activate",
        401,
        403,
        200,
        args=lambda c: {"rental_id": c.own_rental},
    ),
    Case(
        "rentals-complete",
        "POST",
        f"{API}/rentals/{{rental_id}}/complete",
        401,
        403,
        200,
        args=lambda c: {"rental_id": c.own_active_rental},
    ),
    Case(
        "rentals-delete",
        "DELETE",
        f"{API}/rentals/{{rental_id}}",
        401,
        403,
        204,
        args=lambda c: {"rental_id": c.own_rental},
    ),
]


@pytest.fixture
def ctx(
    user: UserCred,
    user_factory: UserFactory,
    vehicle_factory: VehicleFactory,
    rental_factory: RentalFactory,
) -> Ctx:
    other = user_factory()
    return Ctx(
        user=user,
        other=other,
        spare=user_factory(),
        vehicle=vehicle_factory(),
        spare_vehicle=vehicle_factory(),
        book_vehicle=vehicle_factory(),
        own_rental=rental_factory(user.id),
        own_active_rental=rental_factory(user.id, status="active"),
        other_rental=rental_factory(other.id),
    )


@pytest.mark.parametrize("role", ["anonymous", "user", "admin"])
@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_permission_matrix(
    client: TestClient,
    ctx: Ctx,
    user_token: str,
    admin_token: str,
    case: Case,
    role: str,
) -> None:
    headers = {"anonymous": {}, "user": auth(user_token), "admin": auth(admin_token)}[role]
    path = case.route.format(**case.args(ctx))
    response = client.request(case.method, path, headers=headers, json=case.body(ctx))
    expected = getattr(case, role)
    assert response.status_code == expected, (
        f"{role} {case.method} {path}: expected {expected}, got {response.status_code} "
        f"{response.text[:200]}"
    )
    if response.status_code == 401 and case.route != f"{API}/auth/login":
        assert response.headers["WWW-Authenticate"] == "Bearer"
    if response.status_code >= 400:
        assert set(response.json()) == {"error"}


def test_matrix_covers_every_route() -> None:
    paths = create_app().openapi()["paths"]
    routes = {
        (method.upper(), path)
        for path, operations in paths.items()
        for method in operations
        if path.startswith(API)
    }
    covered = {(case.method, case.route) for case in CASES}
    assert routes - covered == set(), "endpoints missing from the permission matrix"
    assert covered - routes == set(), "matrix cases that do not match a real route"
