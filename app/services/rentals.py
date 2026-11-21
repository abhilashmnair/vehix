import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ConflictError, ForbiddenError, NotFoundError, UnprocessableError
from app.models import Rental, RentalStatus, User, UserRole, Vehicle, VehicleStatus
from app.schemas.common import PageParams
from app.schemas.rental import RentalCreate, RentalFilters, RentalUpdate
from app.services.db_errors import violated_constraint
from app.services.pagination import paginate
from app.services.vehicles import get_vehicle

OVERLAP_CONSTRAINT = "ex_rentals_vehicle_no_overlap"
MAX_RENTAL_DAYS = 365
MAX_TOTAL_PRICE = Decimal("99999999.99")  # Numeric(10, 2)


def rental_days(start: date, end: date) -> int:
    """Number of calendar days, both ends inclusive."""
    return (end - start).days + 1


def compute_total_price(daily_rate: Decimal, start: date, end: date) -> Decimal:
    days = rental_days(start, end)
    if days > MAX_RENTAL_DAYS:
        raise UnprocessableError(
            f"A rental cannot be longer than {MAX_RENTAL_DAYS} days.", code="invalid_dates"
        )
    total = (daily_rate * days).quantize(Decimal("0.01"))
    if total > MAX_TOTAL_PRICE:
        raise UnprocessableError("The total price is too large.", code="invalid_dates")
    return total


def flush_rental(session: Session) -> None:
    """Flush so the DB exclusion constraint is reported here, mapped to 409.

    The database (not a read-then-write check) decides, so concurrent requests cannot both win.
    """
    try:
        session.flush()
    except IntegrityError as exc:
        if violated_constraint(exc) == OVERLAP_CONSTRAINT:
            raise ConflictError(
                "Vehicle is already booked for these dates.", code="rental_overlap"
            ) from exc
        raise


def create_rental(session: Session, actor: User, data: RentalCreate) -> Rental:
    is_admin = actor.role == UserRole.ADMIN.value
    owner_id = data.user_id or actor.id
    if owner_id != actor.id and not is_admin:
        raise ForbiddenError("You can only create rentals for yourself.")
    if owner_id != actor.id:
        owner = session.get(User, owner_id)
        if owner is None:
            raise NotFoundError("User not found.")
        if not owner.is_active:
            raise ConflictError("The user is not active.", code="user_inactive")

    vehicle: Vehicle = get_vehicle(session, data.vehicle_id)
    if vehicle.status != VehicleStatus.AVAILABLE.value:
        raise ConflictError("Vehicle is not available for rental.", code="vehicle_not_rentable")
    if not is_admin and data.start_date < datetime.now(UTC).date():
        raise UnprocessableError("start_date cannot be in the past.", code="invalid_dates")

    rental = Rental(
        user_id=owner_id,
        vehicle_id=vehicle.id,
        start_date=data.start_date,
        end_date=data.end_date,
        total_price=compute_total_price(vehicle.daily_rate, data.start_date, data.end_date),
        notes=data.notes,
    )
    session.add(rental)
    flush_rental(session)
    session.refresh(rental)
    return rental


def list_rentals(
    session: Session, actor: User, filters: RentalFilters, params: PageParams
) -> tuple[list[Rental], int]:
    stmt = select(Rental)
    if actor.role != UserRole.ADMIN.value:
        stmt = stmt.where(Rental.user_id == actor.id)
    if filters.user_id is not None:
        stmt = stmt.where(Rental.user_id == filters.user_id)
    if filters.vehicle_id is not None:
        stmt = stmt.where(Rental.vehicle_id == filters.vehicle_id)
    if filters.status is not None:
        stmt = stmt.where(Rental.status == filters.status.value)
    return paginate(session, stmt.order_by(Rental.created_at, Rental.id), params)


def get_rental(session: Session, actor: User, rental_id: uuid.UUID) -> Rental:
    """Return the rental, or 404 if it does not exist or a non-admin does not own it."""
    rental = session.get(Rental, rental_id)
    if rental is None or (actor.role != UserRole.ADMIN.value and rental.user_id != actor.id):
        raise NotFoundError("Rental not found.")
    return rental


def update_rental(
    session: Session, actor: User, rental_id: uuid.UUID, data: RentalUpdate
) -> Rental:
    """Edit dates/notes.

    Users: only their own rental and only while `reserved`. Admins: any rental, but dates can
    only change while it is `reserved` or `active`. Overlap is re-checked by the database, and
    the price is recomputed from the rate frozen at creation (not the vehicle's current rate).
    """
    rental = get_rental(session, actor, rental_id)
    if not data.model_fields_set:
        return rental
    is_admin = actor.role == UserRole.ADMIN.value
    changes_dates = bool({"start_date", "end_date"} & data.model_fields_set)
    if not is_admin:
        editable = {RentalStatus.RESERVED.value}
    elif changes_dates:
        editable = {RentalStatus.RESERVED.value, RentalStatus.ACTIVE.value}
    else:
        editable = {status.value for status in RentalStatus}
    if rental.status not in editable:
        raise ConflictError(
            f"A {rental.status} rental cannot be edited this way.", code="invalid_state"
        )

    if "notes" in data.model_fields_set:
        rental.notes = data.notes
    if changes_dates:
        start = data.start_date or rental.start_date
        end = data.end_date or rental.end_date
        if end < start:
            raise UnprocessableError(
                "end_date must not be before start_date.", code="invalid_dates"
            )
        if (
            not is_admin
            and data.start_date is not None
            and data.start_date != rental.start_date
            and data.start_date < datetime.now(UTC).date()
        ):
            raise UnprocessableError("start_date cannot be in the past.", code="invalid_dates")
        frozen_rate = rental.total_price / rental_days(rental.start_date, rental.end_date)
        rental.total_price = compute_total_price(frozen_rate, start, end)
        rental.start_date = start
        rental.end_date = end
    flush_rental(session)
    session.refresh(rental)
    return rental


# State machine: reserved -> active -> completed; reserved|active -> cancelled.
TRANSITIONS: dict[str, set[str]] = {
    RentalStatus.RESERVED.value: {RentalStatus.ACTIVE.value, RentalStatus.CANCELLED.value},
    RentalStatus.ACTIVE.value: {RentalStatus.COMPLETED.value, RentalStatus.CANCELLED.value},
    RentalStatus.COMPLETED.value: set(),
    RentalStatus.CANCELLED.value: set(),
}


def transition_rental(
    session: Session, actor: User, rental_id: uuid.UUID, target: RentalStatus
) -> Rental:
    """Move a rental to `target` if the state machine allows it, else 409.

    Cancelling is allowed for the owner and admins; activating and completing are admin-only
    (enforced by the router dependency).
    """
    rental = get_rental(session, actor, rental_id)
    if target.value not in TRANSITIONS[rental.status]:
        raise ConflictError(
            f"A {rental.status} rental cannot become {target.value}.", code="invalid_state"
        )
    rental.status = target.value
    flush_rental(session)
    session.refresh(rental)
    return rental
