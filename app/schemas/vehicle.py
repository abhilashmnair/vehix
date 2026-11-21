import re
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from app.models import VehicleStatus
from app.models.vehicle import MIN_VEHICLE_YEAR

VIN_PATTERN = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")


def _normalize_plate(value: str) -> str:
    return value.strip().upper()


def _normalize_vin(value: str) -> str:
    vin = value.strip().upper()
    if not VIN_PATTERN.fullmatch(vin):
        raise ValueError("vin must be 17 characters (letters except I, O, Q, and digits)")
    return vin


def _check_year(value: int) -> int:
    max_year = datetime.now(UTC).year + 1
    if not MIN_VEHICLE_YEAR <= value <= max_year:
        raise ValueError(f"year must be between {MIN_VEHICLE_YEAR} and {max_year}")
    return value


LicensePlate = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=20),
    AfterValidator(_normalize_plate),
]
Vin = Annotated[str, AfterValidator(_normalize_vin)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Year = Annotated[int, AfterValidator(_check_year)]
DailyRate = Annotated[Decimal, Field(gt=0, max_digits=8, decimal_places=2)]


class VehicleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    license_plate: str
    vin: str | None
    make: str
    model: str
    year: int
    daily_rate: Decimal
    status: str
    created_at: datetime
    updated_at: datetime


class VehicleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    license_plate: LicensePlate
    vin: Vin | None = None
    make: Name
    model: Name
    year: Year
    daily_rate: DailyRate
    status: VehicleStatus = VehicleStatus.AVAILABLE


class VehicleUpdate(BaseModel):
    """PATCH /vehicles/{id}: partial update. Only `vin` may be set to null (to clear it)."""

    model_config = ConfigDict(extra="forbid")

    license_plate: LicensePlate | None = None
    vin: Vin | None = None
    make: Name | None = None
    model: Name | None = None
    year: Year | None = None
    daily_rate: DailyRate | None = None
    status: VehicleStatus | None = None

    @model_validator(mode="after")
    def _no_nulls(self) -> Self:
        for name in self.model_fields_set - {"vin"}:
            if getattr(self, name) is None:
                raise ValueError(f"{name} must not be null")
        return self


class VehicleFilters(BaseModel):
    """Query filters for GET /vehicles.

    `available_from`/`available_to` select vehicles that are rentable (status `available`) and
    have no reserved/active rental touching that inclusive date range. Giving only one of them
    means a single day.
    """

    status: VehicleStatus | None = None
    make: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)] | None = None
    available_from: date | None = None
    available_to: date | None = None

    @model_validator(mode="after")
    def _check_range(self) -> Self:
        if self.available_from and self.available_to and self.available_from > self.available_to:
            raise ValueError("available_from must not be after available_to")
        return self
