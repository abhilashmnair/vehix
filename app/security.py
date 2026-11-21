"""Password hashing, JWT handling and the authentication/authorization dependencies."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.db import SessionDep
from app.errors import ForbiddenError, UnauthorizedError
from app.models import User, UserRole

JWT_ALGORITHM = "HS256"

_hasher = PasswordHasher()
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Constant-time verification provided by argon2; never raises on a bad password."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


# Verified against when the email is unknown, so both failure paths cost the same.
DUMMY_PASSWORD_HASH = hash_password("dummy-password-for-timing-equalisation")


def create_access_token(
    user_id: uuid.UUID, role: str, expires_delta: timedelta | None = None
) -> tuple[str, int]:
    """Return `(token, expires_in_seconds)`. Claims: sub, role, iat, exp."""
    settings = get_settings()
    delta = expires_delta or timedelta(minutes=settings.jwt_expire_minutes)
    now = datetime.now(UTC)
    claims = {"sub": str(user_id), "role": role, "iat": now, "exp": now + delta}
    token = jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm=JWT_ALGORITHM)
    return token, int(delta.total_seconds())


def decode_access_token(token: str) -> uuid.UUID:
    """Validate signature and expiry; return the user id. Raises UnauthorizedError otherwise."""
    try:
        claims = jwt.decode(
            token,
            get_settings().jwt_secret.get_secret_value(),
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "exp"]},
        )
        return uuid.UUID(str(claims["sub"]))
    except (jwt.PyJWTError, ValueError) as exc:
        raise UnauthorizedError("Invalid or expired token.") from exc


def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    """Authenticate the request. Role and `is_active` always come from the database."""
    if credentials is None:
        raise UnauthorizedError("Not authenticated.")
    user = session.get(User, decode_access_token(credentials.credentials))
    if user is None or not user.is_active:
        raise UnauthorizedError("Invalid or expired token.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role != UserRole.ADMIN.value:
        raise ForbiddenError()
    return user


AdminUser = Annotated[User, Depends(require_admin)]
