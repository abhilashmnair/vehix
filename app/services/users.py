import uuid
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ConflictError, ForbiddenError, NotFoundError
from app.models import Rental, RentalStatus, User, UserRole
from app.schemas.common import PageParams
from app.schemas.user import UserAdminUpdate, UserCreate, UserSelfUpdate
from app.security import hash_password, verify_password
from app.services.db_errors import violated_constraint
from app.services.pagination import paginate

EMAIL_UNIQUE_CONSTRAINT = "uq_users_email_lower"


def email_conflict() -> ConflictError:
    return ConflictError("A user with this email already exists.", code="email_conflict")


def flush_user(session: Session) -> None:
    """Flush so a duplicate email surfaces here (as 409), not in the later commit."""
    try:
        session.flush()
    except IntegrityError as exc:
        if violated_constraint(exc) == EMAIL_UNIQUE_CONSTRAINT:
            raise email_conflict() from exc
        raise


def update_self(session: Session, user: User, data: UserSelfUpdate) -> User:
    # Refuse before applying anything, so a rejected request changes nothing.
    if "role" in data.model_fields_set or "is_active" in data.model_fields_set:
        raise ForbiddenError("You cannot change your own role or active status.")
    if data.password is not None and not verify_password(
        user.password_hash, data.current_password or ""
    ):
        raise ForbiddenError("Current password is incorrect.", code="invalid_current_password")

    if data.full_name is not None:
        user.full_name = data.full_name
    if data.email is not None:
        user.email = data.email
    if data.password is not None:
        user.password_hash = hash_password(data.password)
    flush_user(session)
    session.refresh(user)
    return user


def create_user(session: Session, data: UserCreate) -> User:
    user = User(
        email=data.email,
        full_name=data.full_name,
        password_hash=hash_password(data.password),
        role=data.role.value,
        is_active=data.is_active,
    )
    session.add(user)
    flush_user(session)
    session.refresh(user)
    return user


def list_users(session: Session, params: PageParams) -> tuple[list[User], int]:
    stmt = select(User).order_by(User.created_at, User.id)
    return paginate(session, stmt, params)


def get_user(session: Session, user_id: uuid.UUID) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found.")
    return user


def ensure_not_last_admin(session: Session, user: User) -> None:
    """Raise 409 if `user` is the only active admin (so it cannot be removed/demoted).

    The active admins are locked (`FOR UPDATE`) so two concurrent requests cannot both pass.
    """
    admins = select(User.id).where(User.role == UserRole.ADMIN.value, User.is_active.is_(True))
    others = session.scalars(admins.where(User.id != user.id).with_for_update()).all()
    if not others:
        raise ConflictError("At least one active admin must remain.", code="last_admin")


def update_user(session: Session, user_id: uuid.UUID, data: UserAdminUpdate) -> User:
    user = get_user(session, user_id)
    was_active_admin = user.role == UserRole.ADMIN.value and user.is_active
    new_role = data.role.value if data.role is not None else user.role
    new_active = data.is_active if data.is_active is not None else user.is_active
    if was_active_admin and not (new_role == UserRole.ADMIN.value and new_active):
        ensure_not_last_admin(session, user)

    if data.full_name is not None:
        user.full_name = data.full_name
    if data.email is not None:
        user.email = data.email
    if data.password is not None:
        user.password_hash = hash_password(data.password)
    user.role = new_role
    user.is_active = new_active
    flush_user(session)
    session.refresh(user)
    return user


def delete_user(session: Session, user_id: uuid.UUID) -> None:
    user = get_user(session, user_id)
    if user.role == UserRole.ADMIN.value and user.is_active:
        ensure_not_last_admin(session, user)
    statuses = set(session.scalars(select(Rental.status).where(Rental.user_id == user.id)))
    if statuses & {RentalStatus.RESERVED.value, RentalStatus.ACTIVE.value}:
        raise ConflictError(
            "User has reserved or active rentals and cannot be deleted.",
            code="user_has_active_rentals",
        )
    if statuses:
        raise ConflictError(
            "User has rental history and cannot be deleted; deactivate the user instead.",
            code="user_has_rental_history",
        )
    session.delete(user)
    session.flush()


def ensure_admin(session: Session, email: str, password: str) -> Literal["created", "exists"]:
    """Idempotent admin seed. Never modifies an existing user.

    Returns "exists" if an active admin with this email is already present. If the email belongs
    to a user who is not an active admin, raises a conflict instead of silently changing them.
    """
    existing = session.scalar(select(User).where(func.lower(User.email) == email.lower()))
    if existing is not None:
        if existing.role == UserRole.ADMIN.value and existing.is_active:
            return "exists"
        raise ConflictError(
            "A user with the configured admin email exists but is not an active admin; "
            "it was left unchanged.",
            code="admin_seed_conflict",
        )
    session.add(
        User(
            email=email.lower(),
            full_name="Administrator",
            password_hash=hash_password(password),
            role=UserRole.ADMIN.value,
            is_active=True,
        )
    )
    try:
        flush_user(session)
    except ConflictError:  # another process created it between our check and insert
        session.rollback()
        return "exists"
    return "created"
