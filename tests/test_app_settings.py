"""PROJECT.md 6.6: CORS, OpenAPI docs toggle, request IDs and access logging."""

import logging
import re
import secrets

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import Settings
from app.main import create_app


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "db_host": "localhost",
        "db_port": 5432,
        "db_user": "u",
        "db_password": SecretStr(secrets.token_urlsafe(8)),
        "db_name": "n",
        "test_db_name": "t",
        "jwt_secret": SecretStr(secrets.token_urlsafe(32)),
        "jwt_expire_minutes": 30,
        "admin_email": "admin@example.com",
        "admin_password": SecretStr(secrets.token_urlsafe(16)),
    }
    return Settings(**{**values, **overrides})  # type: ignore[arg-type]


def test_cors_is_disabled_by_default() -> None:
    with TestClient(create_app(make_settings())) as client:
        response = client.get("/api/v1/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers


def test_cors_allows_only_configured_origins() -> None:
    settings = make_settings(cors_origins="https://app.example.com, https://admin.example.com")
    assert settings.cors_origins == ["https://app.example.com", "https://admin.example.com"]
    with TestClient(create_app(settings)) as client:
        allowed = client.get("/api/v1/health", headers={"Origin": "https://app.example.com"})
        denied = client.get("/api/v1/health", headers={"Origin": "https://evil.example"})
    assert allowed.headers["access-control-allow-origin"] == "https://app.example.com"
    assert "access-control-allow-origin" not in denied.headers


def test_docs_are_enabled_by_default_and_can_be_switched_off() -> None:
    with TestClient(create_app(make_settings())) as client:
        assert client.get("/docs").status_code == 200
        assert client.get("/openapi.json").status_code == 200
    with TestClient(create_app(make_settings(docs_enabled=False))) as client:
        for path in ("/docs", "/redoc", "/openapi.json"):
            response = client.get(path)
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "not_found"


def test_every_response_has_a_unique_request_id(client: TestClient) -> None:
    first = client.get("/api/v1/health").headers["X-Request-ID"]
    second = client.get("/api/v1/health").headers["X-Request-ID"]
    assert re.fullmatch(r"[0-9a-f]{32}", first)
    assert first != second
    assert client.get("/api/v1/users/me").headers["X-Request-ID"]  # also on errors


def test_a_valid_inbound_request_id_is_kept_and_a_bad_one_replaced(client: TestClient) -> None:
    kept = client.get("/api/v1/health", headers={"X-Request-ID": "trace-123"})
    assert kept.headers["X-Request-ID"] == "trace-123"
    bad = client.get("/api/v1/health", headers={"X-Request-ID": "bad id\twith spaces"})
    assert re.fullmatch(r"[0-9a-f]{32}", bad.headers["X-Request-ID"])


def test_access_log_has_request_id_and_no_query_string_or_credentials(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    secret_query = secrets.token_urlsafe(8)
    with caplog.at_level(logging.INFO, logger="app.access"):
        response = client.get(
            f"/api/v1/health?email=person@example.com&q={secret_query}",
            headers={"Authorization": "Bearer abc.def.ghi"},
        )
    records = [r for r in caplog.records if r.name == "app.access"]
    assert len(records) == 1
    assert records[0].request_id == response.headers["X-Request-ID"]  # type: ignore[attr-defined]
    text = records[0].getMessage()
    assert "GET /api/v1/health -> 200" in text
    assert secret_query not in text
    assert "person@example.com" not in text
    assert "abc.def.ghi" not in text
