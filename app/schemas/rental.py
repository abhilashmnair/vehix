import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from app.models import RentalStatus

Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]


class RentalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    vehicle_id: uuid.UUID
    start_date: date
    end_date: date
    status: str
    total_price: Decimal
    notes: str | None
    created_at: datetime
    updated_at: datetime


class RentalCreate(BaseModel):
    """POST /rentals. `total_price` and `status` are server-controlled and rejected if sent."""

    model_config = ConfigDict(extra="forbid")

    vehicle_id: uuid.UUID
    start_date: date
    end_date: date
    notes: Notes | None = None
    user_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _check_dates(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        return self


class RentalFilters(BaseModel):
    """Query filters for GET /rentals. Non-admins only ever see their own rentals."""

    user_id: uuid.UUID | None = None
    vehicle_id: uuid.UUID | None = None
    status: RentalStatus | None = None
