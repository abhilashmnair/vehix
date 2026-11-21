from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text

from app.config import EnvConfigError, Settings, get_settings, validate_env
from app.db import get_engine
from app.main import create_app
from tests.helpers import upgrade


def pytest_sessionstart(session: pytest.Session) -> None:
    """Fail fast, listing variable names only, if `.env` is missing or incomplete."""
    try:
        validate_env()
    except EnvConfigError as exc:
        raise pytest.UsageError(f"Test environment is not configured. {exc}") from exc
    # Never run against the dev database by accident.
    settings = get_settings()
    if settings.test_db_name == settings.db_name:
        raise pytest.UsageError("TEST_DB_NAME must differ from DB_NAME in .env.")


@pytest.fixture(scope="session")
def settings() -> Settings:
    return get_settings()


@pytest.fixture(scope="session")
def test_engine(settings: Settings) -> Iterator[Engine]:
    """Engine for `vehicles_test`, reset to an empty schema and migrated to head once."""
    engine = create_engine(settings.database_url(settings.test_db_name), pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    upgrade(engine)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_tables(test_engine: Engine) -> Iterator[None]:
    """Each test starts and ends with empty tables, so tests do not depend on order."""
    yield
    with test_engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE rentals, vehicles, users CASCADE"))


@pytest.fixture
def client(test_engine: Engine) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_engine] = lambda: test_engine
    with TestClient(app) as test_client:
        yield test_client
