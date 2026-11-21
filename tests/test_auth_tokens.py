"""AC-A2: token authentication; role and is_active re-checked from the database."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.config import get_settings
from app.db import get_engine
from app.main import create_app
from app.security import AdminUser, CurrentUser, create_access_token
from tests.conftest import UserCred, UserFactory
from tests.helpers import auth


def build_router() -> APIRouter:
    router = APIRouter()

    @router.get("/probe/user")
    def probe_user(current: CurrentUser) -> dict[str, str]:
        return {"id": str(current.id), "role": current.role}

    @router.get("/probe/admin")
    def probe_admin(current: AdminUser) -> dict[str, str]:
        return {"id": str(current.id)}

    return router


@pytest.fixture
def api(test_engine: Engine) -> Iterator[TestClient]:
    app = create_app()
    app.include_router(build_router())
    app.dependency_overrides[get_engine] = lambda: test_engine
    with TestClient(app) as test_client:
        yield test_client


def sign(claims: dict[str, object], key: str | None = None, algorithm: str = "HS256") -> str:
    secret = key or get_settings().jwt_secret.get_secret_value()
    return jwt.encode(claims, secret, algorithm=algorithm)


def claims_for(user_id: uuid.UUID, **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "sub": str(user_id),
        "role": "user",
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }
    return {**base, **overrides}


def assert_401(response: Any) -> None:
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "unauthorized"


def test_valid_token_authenticates(api: TestClient, user: UserCred, user_token: str) -> None:
    response = api.get("/probe/user", headers=auth(user_token))
    assert response.status_code == 200
    assert response.json() == {"id": str(user.id), "role": "user"}


def test_missing_token_is_401(api: TestClient) -> None:
    assert_401(api.get("/probe/user"))
    assert_401(api.get("/probe/admin"))


@pytest.mark.parametrize("header", ["Bearer", "Bearer not-a-jwt", "Basic dXNlcjpwYXNz", "token"])
def test_malformed_authorization_header_is_401(api: TestClient, header: str) -> None:
    assert_401(api.get("/probe/user", headers={"Authorization": header}))


def test_token_signed_with_wrong_key_is_401(api: TestClient, user: UserCred) -> None:
    forged = sign(claims_for(user.id), key="x" * 64)
    assert_401(api.get("/probe/user", headers=auth(forged)))


def test_unsigned_alg_none_token_is_401(api: TestClient, user: UserCred) -> None:
    unsigned = jwt.encode(claims_for(user.id), key=None, algorithm="none")
    assert_401(api.get("/probe/user", headers=auth(unsigned)))


def test_expired_token_is_401(api: TestClient, user: UserCred) -> None:
    expired = sign(claims_for(user.id, exp=datetime.now(UTC) - timedelta(seconds=5)))
    assert_401(api.get("/probe/user", headers=auth(expired)))


def test_token_without_exp_or_sub_is_401(api: TestClient, user: UserCred) -> None:
    no_exp = sign({"sub": str(user.id), "role": "user"})
    no_sub = sign({"role": "user", "exp": datetime.now(UTC) + timedelta(minutes=5)})
    assert_401(api.get("/probe/user", headers=auth(no_exp)))
    assert_401(api.get("/probe/user", headers=auth(no_sub)))


def test_token_with_non_uuid_subject_is_401(api: TestClient) -> None:
    assert_401(api.get("/probe/user", headers=auth(sign(claims_for(uuid.uuid4(), sub="42")))))


def test_token_for_unknown_user_is_401(api: TestClient) -> None:
    token, _ = create_access_token(uuid.uuid4(), "user")
    assert_401(api.get("/probe/user", headers=auth(token)))


def test_deactivated_user_loses_access_immediately(
    api: TestClient, test_engine: Engine, user: UserCred, user_token: str
) -> None:
    assert api.get("/probe/user", headers=auth(user_token)).status_code == 200
    with test_engine.begin() as conn:
        conn.execute(text("UPDATE users SET is_active = false WHERE id = :id"), {"id": user.id})
    assert_401(api.get("/probe/user", headers=auth(user_token)))


def test_deleted_user_token_is_401(
    api: TestClient, test_engine: Engine, user: UserCred, user_token: str
) -> None:
    with test_engine.begin() as conn:
        conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": user.id})
    assert_401(api.get("/probe/user", headers=auth(user_token)))


def test_role_is_taken_from_db_not_from_token(
    api: TestClient, test_engine: Engine, admin: UserCred, admin_token: str, user_token: str
) -> None:
    assert api.get("/probe/admin", headers=auth(admin_token)).status_code == 200
    # A regular user cannot reach admin routes ...
    forbidden = api.get("/probe/admin", headers=auth(user_token))
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "forbidden"
    # ... even with a token that claims to be admin ...
    user_id = jwt.decode(user_token, options={"verify_signature": False})["sub"]
    claims_admin = sign(claims_for(uuid.UUID(user_id), role="admin"))
    assert api.get("/probe/admin", headers=auth(claims_admin)).status_code == 403
    # ... and demoting an admin takes effect immediately, with the same token.
    with test_engine.begin() as conn:
        conn.execute(text("UPDATE users SET role = 'user' WHERE id = :id"), {"id": admin.id})
    assert api.get("/probe/admin", headers=auth(admin_token)).status_code == 403


def test_promotion_takes_effect_immediately(
    api: TestClient, test_engine: Engine, user: UserCred, user_token: str
) -> None:
    assert api.get("/probe/admin", headers=auth(user_token)).status_code == 403
    with test_engine.begin() as conn:
        conn.execute(text("UPDATE users SET role = 'admin' WHERE id = :id"), {"id": user.id})
    assert api.get("/probe/admin", headers=auth(user_token)).status_code == 200


def test_health_and_login_remain_public(api: TestClient, user_factory: UserFactory) -> None:
    assert api.get("/api/v1/health").status_code == 200
    person = user_factory()
    body = {"email": person.email, "password": person.password}
    assert api.post("/api/v1/auth/login", json=body).status_code == 200
