import uuid

from sqlalchemy import exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ConflictError, NotFoundError
from app.models import Rental, RentalStatus, Vehicle, VehicleStatus
from app.schemas.common import PageParams
from app.schemas.vehicle import VehicleCreate, VehicleFilters, VehicleUpdate
from app.services.db_errors import violated_constraint
from app.services.pagination import paginate

CONFLICTS = {
    "uq_vehicles_license_plate": ("license_plate_conflict", "License plate is already in use."),
    "uq_vehicles_vin": ("vin_conflict", "VIN is already in use."),
}


def flush_vehicle(session: Session) -> None:
    """Flush so uniqueness violations surface here (as 409), not in the later commit."""
    try:
        session.flush()
    except IntegrityError as exc:
        conflict = CONFLICTS.get(violated_constraint(exc) or "")
        if conflict is None:
            raise
        raise ConflictError(conflict[1], code=conflict[0]) from exc


def create_vehicle(session: Session, data: VehicleCreate) -> Vehicle:
    vehicle = Vehicle(
        license_plate=data.license_plate,
        vin=data.vin,
        make=data.make,
        model=data.model,
        year=data.year,
        daily_rate=data.daily_rate,
        status=data.status.value,
    )
    session.add(vehicle)
    flush_vehicle(session)
    session.refresh(vehicle)
    return vehicle


def list_vehicles(
    session: Session, filters: VehicleFilters, params: PageParams
) -> tuple[list[Vehicle], int]:
    stmt = select(Vehicle).where(Vehicle.deleted_at.is_(None))
    if filters.status is not None:
        stmt = stmt.where(Vehicle.status == filters.status.value)
    if filters.make is not None:
        stmt = stmt.where(func.lower(Vehicle.make) == filters.make.lower())
    if filters.available_from is not None or filters.available_to is not None:
        start = filters.available_from or filters.available_to
        end = filters.available_to or filters.available_from
        booked = exists().where(
            Rental.vehicle_id == Vehicle.id,
            Rental.status.in_([RentalStatus.RESERVED.value, RentalStatus.ACTIVE.value]),
            Rental.start_date <= end,
            Rental.end_date >= start,
        )
        stmt = stmt.where(Vehicle.status == VehicleStatus.AVAILABLE.value, ~booked)
    return paginate(session, stmt.order_by(Vehicle.created_at, Vehicle.id), params)


def get_vehicle(session: Session, vehicle_id: uuid.UUID) -> Vehicle:
    """Return a non-deleted vehicle or raise 404 (soft-deleted vehicles do not exist)."""
    vehicle = session.get(Vehicle, vehicle_id)
    if vehicle is None or vehicle.deleted_at is not None:
        raise NotFoundError("Vehicle not found.")
    return vehicle


def update_vehicle(session: Session, vehicle_id: uuid.UUID, data: VehicleUpdate) -> Vehicle:
    vehicle = get_vehicle(session, vehicle_id)
    for name in data.model_fields_set:
        value = getattr(data, name)
        setattr(vehicle, name, value.value if isinstance(value, VehicleStatus) else value)
    flush_vehicle(session)
    session.refresh(vehicle)
    return vehicle
