from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import ConflictError, ForbiddenError
from app.models import User
from app.schemas.user import UserSelfUpdate
from app.security import hash_password, verify_password

EMAIL_UNIQUE_CONSTRAINT = "uq_users_email_lower"


def email_conflict() -> ConflictError:
    return ConflictError("A user with this email already exists.", code="email_conflict")


def flush_user(session: Session) -> None:
    """Flush so a duplicate email surfaces here (as 409), not in the later commit."""
    try:
        session.flush()
    except IntegrityError as exc:
        if getattr(getattr(exc.orig, "diag", None), "constraint_name", None) == (
            EMAIL_UNIQUE_CONSTRAINT
        ):
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
