"""AC-F1: scaffold, config, health, test database connectivity."""

from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text

from app.config import Settings
from app.db import get_engine
from app.main import create_app


def test_health_ok(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_needs_no_authentication(client: TestClient) -> None:
    assert "Authorization" not in client.headers
    assert client.get("/api/v1/health").status_code == 200


def test_health_returns_503_when_database_is_down(settings: Settings) -> None:
    # Real engine pointed at a closed port: no mocking of the database.
    url = settings.database_url().set(port=1)
    dead_engine = create_engine(url, connect_args={"connect_timeout": 2})
    app = create_app()
    app.dependency_overrides[get_engine] = lambda: dead_engine
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
    dead_engine.dispose()
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


def test_tests_run_against_the_test_database(test_engine: Engine, settings: Settings) -> None:
    with test_engine.connect() as conn:
        current = conn.execute(text("SELECT current_database()")).scalar_one()
    assert current == settings.test_db_name
    assert current != settings.db_name
