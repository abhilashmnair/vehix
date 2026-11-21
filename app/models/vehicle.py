import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Numeric, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin

MIN_VEHICLE_YEAR = 1950


class VehicleStatus(enum.StrEnum):
    AVAILABLE = "available"
    MAINTENANCE = "maintenance"
    RETIRED = "retired"


class Vehicle(IdMixin, TimestampMixin, Base):
    __tablename__ = "vehicles"

    license_plate: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    vin: Mapped[str | None] = mapped_column(String(17), unique=True, nullable=True)
    make: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    daily_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=VehicleStatus.AVAILABLE.value
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("daily_rate > 0", name="daily_rate_positive"),
        CheckConstraint(f"year >= {MIN_VEHICLE_YEAR}", name="year_min"),
        CheckConstraint("status IN ('available', 'maintenance', 'retired')", name="status_valid"),
    )
