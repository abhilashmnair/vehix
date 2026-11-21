"""AC-F3: uniform error envelope and exception handlers."""

import secrets
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import APIRouter, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field

from app.errors import (
    AppError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
)
from app.main import create_app


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=3)
    password: str = Field(min_length=12)


def build_router() -> APIRouter:
    router = APIRouter()

    @router.get("/raise/401")
    def raise_401() -> None:
        raise UnauthorizedError()

    @router.get("/raise/403")
    def raise_403() -> None:
        raise ForbiddenError()

    @router.get("/raise/404")
    def raise_404() -> None:
        raise NotFoundError("Vehicle not found.")

    @router.get("/raise/409")
    def raise_409() -> None:
        raise ConflictError("Vehicle is already booked for these dates.", code="rental_overlap")

    @router.get("/raise/app")
    def raise_app() -> None:
        raise AppError()

    @router.get("/raise/http-418")
    def raise_http() -> None:
        raise HTTPException(status_code=418, detail="teapot")

    @router.get("/raise/500")
    def raise_500() -> None:
        raise RuntimeError("SELECT * FROM users; secret-internal-detail")

    @router.post("/validate")
    def validate(payload: Payload) -> dict[str, str]:
        return {"name": payload.name}

    return router


@pytest.fixture
def api() -> Iterator[TestClient]:
    app = create_app()
    app.include_router(build_router())
    # The 500 handler must answer the client instead of re-raising into the test.
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def error_of(response: Any) -> dict[str, Any]:
    body = response.json()
    assert set(body) == {"error"}
    error: dict[str, Any] = body["error"]
    assert {"code", "message"} <= set(error)
    return error


def test_401_has_envelope_and_www_authenticate(api: TestClient) -> None:
    response = api.get("/raise/401")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert error_of(response)["code"] == "unauthorized"


def test_403_envelope(api: TestClient) -> None:
    response = api.get("/raise/403")
    assert response.status_code == 403
    assert error_of(response)["code"] == "forbidden"


def test_404_envelope_with_custom_message(api: TestClient) -> None:
    response = api.get("/raise/404")
    assert response.status_code == 404
    assert error_of(response) == {"code": "not_found", "message": "Vehicle not found."}


def test_409_envelope_with_custom_code(api: TestClient) -> None:
    response = api.get("/raise/409")
    assert response.status_code == 409
    assert error_of(response) == {
        "code": "rental_overlap",
        "message": "Vehicle is already booked for these dates.",
    }


def test_unknown_route_uses_envelope(api: TestClient) -> None:
    response = api.get("/does-not-exist")
    assert response.status_code == 404
    assert error_of(response)["code"] == "not_found"


def test_wrong_method_uses_envelope(api: TestClient) -> None:
    response = api.post("/api/v1/health")
    assert response.status_code == 405
    assert error_of(response)["code"] == "method_not_allowed"


def test_other_http_exceptions_use_envelope(api: TestClient) -> None:
    response = api.get("/raise/http-418")
    assert response.status_code == 418
    assert error_of(response) == {"code": "http_error", "message": "teapot"}


def test_422_envelope_lists_fields_and_never_echoes_input(api: TestClient) -> None:
    submitted = secrets.token_urlsafe(4)  # 6 chars: too short for `password`
    response = api.post("/validate", json={"name": "ok-name", "password": submitted, "x": 1})
    assert response.status_code == 422
    error = error_of(response)
    assert error["code"] == "validation_error"
    locations = {tuple(d["loc"]) for d in error["details"]}
    assert ("body", "password") in locations
    assert ("body", "x") in locations
    assert all(set(d) == {"loc", "msg", "type"} for d in error["details"])
    assert submitted not in response.text


def test_422_for_malformed_json(api: TestClient) -> None:
    response = api.post(
        "/validate", content="{not json", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
    assert error_of(response)["code"] == "validation_error"


def test_500_hides_internal_details(api: TestClient) -> None:
    response = api.get("/raise/500")
    assert response.status_code == 500
    assert error_of(response) == {"code": "internal_error", "message": "Internal server error."}
    assert "SELECT" not in response.text
    assert "Traceback" not in response.text


def test_base_app_error_is_500(api: TestClient) -> None:
    response = api.get("/raise/app")
    assert response.status_code == 500
    assert error_of(response)["code"] == "internal_error"
