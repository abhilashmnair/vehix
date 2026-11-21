import secrets
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

from app.config import SERVER_VARS, TEST_VARS, EnvConfigError, Settings, get_settings, validate_env
from app.db import get_engine
from app.models import Rental, User, UserRole, Vehicle
from app.security import create_access_token, hash_password
from tests.helpers import upgrade


def pytest_sessionstart(session: pytest.Session) -> None:
    """Fail fast, listing variable names only, if `.env` is missing or incomplete."""
    try:
        validate_env(required=SERVER_VARS + TEST_VARS)
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
    assert settings.test_db_name, "checked in pytest_sessionstart"
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
    from app.main import create_app  # lazy: needs a valid .env, checked in pytest_sessionstart

    app = create_app()
    app.dependency_overrides[get_engine] = lambda: test_engine
    with TestClient(app) as test_client:
        yield test_client


@dataclass
class UserCred:
    """A user created for a test, with the throwaway password it was created with."""

    id: uuid.UUID
    email: str
    password: str
    role: str


UserFactory = Callable[..., UserCred]


@pytest.fixture
def user_factory(test_engine: Engine) -> UserFactory:
    def create(
        *,
        email: str | None = None,
        password: str | None = None,
        role: str = UserRole.USER.value,
        is_active: bool = True,
        full_name: str = "Test Person",
    ) -> UserCred:
        email = email or f"user-{secrets.token_hex(4)}@example.com"
        password = password or secrets.token_urlsafe(24)
        with Session(test_engine) as session:
            user = User(
                email=email.lower(),
                full_name=full_name,
                password_hash=hash_password(password),
                role=role,
                is_active=is_active,
            )
            session.add(user)
            session.commit()
            return UserCred(id=user.id, email=user.email, password=password, role=role)

    return create


@pytest.fixture
def admin(user_factory: UserFactory) -> UserCred:
    return user_factory(role=UserRole.ADMIN.value, full_name="Admin Person")


@pytest.fixture
def user(user_factory: UserFactory) -> UserCred:
    return user_factory()


@pytest.fixture
def admin_token(admin: UserCred) -> str:
    return create_access_token(admin.id, admin.role)[0]


@pytest.fixture
def user_token(user: UserCred) -> str:
    return create_access_token(user.id, user.role)[0]


VehicleFactory = Callable[..., uuid.UUID]
RentalFactory = Callable[..., uuid.UUID]


@pytest.fixture
def vehicle_factory(test_engine: Engine) -> VehicleFactory:
    def create(**overrides: object) -> uuid.UUID:
        values: dict[str, object] = {
            "license_plate": f"T{secrets.token_hex(3).upper()}",
            "make": "Toyota",
            "model": "Corolla",
            "year": 2022,
            "daily_rate": Decimal("50.00"),
            "status": "available",
        }
        values.update(overrides)
        with Session(test_engine) as session:
            vehicle = Vehicle(**values)
            session.add(vehicle)
            session.commit()
            return vehicle.id

    return create


@pytest.fixture
def rental_factory(test_engine: Engine, vehicle_factory: VehicleFactory) -> RentalFactory:
    """Insert a rental straight into the DB (bypassing the API), for arranging test state."""

    def create(
        user_id: uuid.UUID, vehicle_id: uuid.UUID | None = None, **overrides: object
    ) -> uuid.UUID:
        values: dict[str, object] = {
            "user_id": user_id,
            "vehicle_id": vehicle_id or vehicle_factory(),
            "start_date": date(2030, 1, 10),
            "end_date": date(2030, 1, 12),
            "status": "reserved",
            "total_price": Decimal("150.00"),
        }
        values.update(overrides)
        with Session(test_engine) as session:
            rental = Rental(**values)
            session.add(rental)
            session.commit()
            return rental.id

    return create
