import enum
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String, Text, Uuid, text
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin


class RentalStatus(enum.StrEnum):
    RESERVED = "reserved"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Rental(IdMixin, TimestampMixin, Base):
    __tablename__ = "rentals"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("vehicles.id", ondelete="RESTRICT"), nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=RentalStatus.RESERVED.value
    )
    total_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("end_date >= start_date", name="dates_ordered"),
        CheckConstraint(
            "status IN ('reserved', 'active', 'completed', 'cancelled')", name="status_valid"
        ),
        CheckConstraint("total_price >= 0", name="total_price_non_negative"),
        # No two reserved/active rentals of one vehicle may share a calendar day (inclusive).
        ExcludeConstraint(
            ("vehicle_id", "="),
            (text("daterange(start_date, end_date, '[]')"), "&&"),
            name="ex_rentals_vehicle_no_overlap",
            using="gist",
            where=text("status IN ('reserved', 'active')"),
        ),
    )
