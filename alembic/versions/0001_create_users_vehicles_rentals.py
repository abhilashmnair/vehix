"""create users, vehicles and rentals

Revision ID: 0001
Revises:
Create Date: 2026-11-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[sa.DateTime]]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    # Needed for the rentals exclusion constraint (uuid "=" inside a GiST index).
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        *_timestamps(),
        sa.CheckConstraint("role IN ('admin', 'user')", name=op.f("ck_users_role_valid")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index("uq_users_email_lower", "users", [sa.text("lower(email)")], unique=True)

    op.create_table(
        "vehicles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("license_plate", sa.String(length=20), nullable=False),
        sa.Column("vin", sa.String(length=17), nullable=True),
        sa.Column("make", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("daily_rate", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("daily_rate > 0", name=op.f("ck_vehicles_daily_rate_positive")),
        sa.CheckConstraint("year >= 1950", name=op.f("ck_vehicles_year_min")),
        sa.CheckConstraint(
            "status IN ('available', 'maintenance', 'retired')",
            name=op.f("ck_vehicles_status_valid"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vehicles")),
        sa.UniqueConstraint("license_plate", name=op.f("uq_vehicles_license_plate")),
        sa.UniqueConstraint("vin", name=op.f("uq_vehicles_vin")),
    )

    op.create_table(
        "rentals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_id", sa.Uuid(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("total_price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("end_date >= start_date", name=op.f("ck_rentals_dates_ordered")),
        sa.CheckConstraint(
            "status IN ('reserved', 'active', 'completed', 'cancelled')",
            name=op.f("ck_rentals_status_valid"),
        ),
        sa.CheckConstraint("total_price >= 0", name=op.f("ck_rentals_total_price_non_negative")),
        postgresql.ExcludeConstraint(
            ("vehicle_id", "="),
            (sa.text("daterange(start_date, end_date, '[]')"), "&&"),
            name="ex_rentals_vehicle_no_overlap",
            using="gist",
            where=sa.text("status IN ('reserved', 'active')"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_rentals_user_id_users"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_id"],
            ["vehicles.id"],
            name=op.f("fk_rentals_vehicle_id_vehicles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rentals")),
    )


def downgrade() -> None:
    op.drop_table("rentals")
    op.drop_table("vehicles")
    op.drop_index("uq_users_email_lower", table_name="users")
    op.drop_table("users")
