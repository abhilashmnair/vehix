"""AC-F2: Alembic migration and database constraints."""

import uuid
from collections.abc import Iterator
from typing import Any

import psycopg.errors
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Connection, Engine, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.models import Base
from tests.helpers import downgrade, upgrade

TABLES = {"users", "vehicles", "rentals"}


@pytest.fixture
def scratch_engine(settings: Settings) -> Iterator[Engine]:
    """A brand-new empty database, so the migration is proven on an empty DB."""
    name = f"vehicles_mig_{uuid.uuid4().hex[:12]}"
    admin = create_engine(settings.database_url("postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    engine = create_engine(settings.database_url(name))
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def test_migration_applies_on_empty_database_and_reverts(scratch_engine: Engine) -> None:
    upgrade(scratch_engine)
    inspector = inspect(scratch_engine)
    assert TABLES <= set(inspector.get_table_names())
    with scratch_engine.connect() as conn:
        extensions = conn.execute(text("SELECT extname FROM pg_extension")).scalars().all()
        assert "btree_gist" in extensions
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    assert version == "0001"

    downgrade(scratch_engine)
    assert not TABLES & set(inspect(scratch_engine).get_table_names())


def test_models_match_migration(scratch_engine: Engine) -> None:
    upgrade(scratch_engine)
    with scratch_engine.connect() as conn:
        context = MigrationContext.configure(conn, opts={"compare_type": True})
        assert compare_metadata(context, Base.metadata) == []


# --- Constraint behaviour (runs on the migrated test database, rolled back per test) ----------


@pytest.fixture
def conn(test_engine: Engine) -> Iterator[Connection]:
    with test_engine.connect() as connection:
        transaction = connection.begin()
        yield connection
        transaction.rollback()


def insert_user(conn: Connection, email: str = "a@example.com", role: str = "user") -> uuid.UUID:
    user_id = uuid.uuid4()
    conn.execute(
        text(
            "INSERT INTO users (id, email, full_name, password_hash, role) "
            "VALUES (:id, :email, 'Name', 'hash', :role)"
        ),
        {"id": user_id, "email": email, "role": role},
    )
    return user_id


def insert_vehicle(
    conn: Connection,
    plate: str = "AB123CD",
    vin: str | None = None,
    rate: str = "50.00",
    year: int = 2020,
    status: str = "available",
) -> uuid.UUID:
    vehicle_id = uuid.uuid4()
    conn.execute(
        text(
            "INSERT INTO vehicles (id, license_plate, vin, make, model, year, daily_rate, status) "
            "VALUES (:id, :plate, :vin, 'Make', 'Model', :year, :rate, :status)"
        ),
        {
            "id": vehicle_id,
            "plate": plate,
            "vin": vin,
            "year": year,
            "rate": rate,
            "status": status,
        },
    )
    return vehicle_id


def insert_rental(
    conn: Connection,
    user_id: uuid.UUID,
    vehicle_id: uuid.UUID,
    start: str,
    end: str,
    status: str = "reserved",
) -> None:
    conn.execute(
        text(
            "INSERT INTO rentals (id, user_id, vehicle_id, start_date, end_date, status, "
            "total_price) VALUES (:id, :u, :v, :s, :e, :st, 100)"
        ),
        {"id": uuid.uuid4(), "u": user_id, "v": vehicle_id, "s": start, "e": end, "st": status},
    )


def violates(conn: Connection, exc_type: type[Exception], func: Any, *args: Any, **kw: Any) -> None:
    """Run `func` in a savepoint and assert it fails with the given Postgres error."""
    with pytest.raises(IntegrityError) as info:
        with conn.begin_nested():
            func(conn, *args, **kw)
    assert isinstance(info.value.orig, exc_type)


def test_user_role_must_be_valid(conn: Connection) -> None:
    violates(conn, psycopg.errors.CheckViolation, insert_user, role="superuser")


def test_user_email_unique_case_insensitively(conn: Connection) -> None:
    insert_user(conn, "Person@Example.com")
    violates(conn, psycopg.errors.UniqueViolation, insert_user, "person@example.COM")


def test_vehicle_constraints(conn: Connection) -> None:
    insert_vehicle(conn, plate="AAA111", vin="VIN00000000000001")
    violates(conn, psycopg.errors.UniqueViolation, insert_vehicle, plate="AAA111")
    violates(
        conn,
        psycopg.errors.UniqueViolation,
        insert_vehicle,
        plate="BBB222",
        vin="VIN00000000000001",
    )
    violates(conn, psycopg.errors.CheckViolation, insert_vehicle, plate="CCC333", rate="0")
    violates(conn, psycopg.errors.CheckViolation, insert_vehicle, plate="DDD444", year=1900)
    violates(conn, psycopg.errors.CheckViolation, insert_vehicle, plate="EEE555", status="stolen")
    # VIN is nullable and NULLs do not collide.
    insert_vehicle(conn, plate="FFF666")
    insert_vehicle(conn, plate="GGG777")


def test_rental_end_date_not_before_start_date(conn: Connection) -> None:
    user, vehicle = insert_user(conn), insert_vehicle(conn)
    insert_rental(conn, user, vehicle, "2030-01-01", "2030-01-01")  # same day is valid
    violates(
        conn,
        psycopg.errors.CheckViolation,
        insert_rental,
        user,
        vehicle,
        "2030-02-02",
        "2030-02-01",
    )


def test_overlapping_rentals_rejected_by_exclusion_constraint(conn: Connection) -> None:
    user, vehicle = insert_user(conn), insert_vehicle(conn)
    insert_rental(conn, user, vehicle, "2030-01-10", "2030-01-15")
    exclusion = psycopg.errors.ExclusionViolation
    violates(
        conn, exclusion, insert_rental, user, vehicle, "2030-01-15", "2030-01-20"
    )  # shared day
    violates(conn, exclusion, insert_rental, user, vehicle, "2030-01-01", "2030-01-10")
    violates(conn, exclusion, insert_rental, user, vehicle, "2030-01-11", "2030-01-12")
    violates(conn, exclusion, insert_rental, user, vehicle, "2030-01-12", "2030-01-12", "active")


def test_adjacent_cancelled_and_other_vehicle_rentals_allowed(conn: Connection) -> None:
    user, vehicle, other = insert_user(conn), insert_vehicle(conn), insert_vehicle(conn, "ZZ999")
    insert_rental(conn, user, vehicle, "2030-01-10", "2030-01-15")
    insert_rental(conn, user, vehicle, "2030-01-16", "2030-01-20")  # adjacent
    insert_rental(conn, user, vehicle, "2030-01-12", "2030-01-13", "cancelled")  # cancelled overlap
    insert_rental(
        conn, user, vehicle, "2030-01-12", "2030-01-13", "completed"
    )  # not reserved/active
    insert_rental(conn, user, other, "2030-01-10", "2030-01-15")  # other vehicle


def test_foreign_keys_restrict_deletes(conn: Connection) -> None:
    user, vehicle = insert_user(conn), insert_vehicle(conn)
    insert_rental(conn, user, vehicle, "2030-01-10", "2030-01-15")
    for table, key in (("users", user), ("vehicles", vehicle)):
        with pytest.raises(IntegrityError) as info:
            with conn.begin_nested():
                conn.execute(text(f"DELETE FROM {table} WHERE id = :id"), {"id": key})  # noqa: S608
        assert isinstance(info.value.orig, psycopg.errors.ForeignKeyViolation)
