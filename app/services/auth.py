from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import UnauthorizedError
from app.models import User
from app.security import DUMMY_PASSWORD_HASH, verify_password

INVALID_CREDENTIALS = "Invalid email or password."


def authenticate(session: Session, email: str, password: str) -> User:
    """Return the active user for valid credentials.

    Unknown email, wrong password and inactive user all raise the same error, and the
    password hash is verified in every case so the failures are indistinguishable.
    """
    user = session.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))
    password_ok = verify_password(user.password_hash if user else DUMMY_PASSWORD_HASH, password)
    if user is None or not password_ok or not user.is_active:
        raise UnauthorizedError(INVALID_CREDENTIALS)
    return user
