from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ConflictError
from app.models import Vehicle
from app.schemas.vehicle import VehicleCreate
from app.services.db_errors import violated_constraint

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
