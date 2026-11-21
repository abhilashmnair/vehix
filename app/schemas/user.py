import uuid
from datetime import datetime
from typing import Annotated, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    model_validator,
)

from app.models import UserRole

# Upper bound protects argon2 from huge inputs; the lower bound is the project minimum.
Password = Annotated[str, Field(min_length=12, max_length=128)]
FullName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
NormalizedEmail = Annotated[EmailStr, AfterValidator(lambda value: value.strip().lower())]


class UserRead(BaseModel):
    """Public representation of a user. Never contains password data."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    """POST /users (admin only)."""

    model_config = ConfigDict(extra="forbid")

    email: NormalizedEmail
    full_name: FullName
    password: Password
    role: UserRole = UserRole.USER
    is_active: bool = True


class UserSelfUpdate(BaseModel):
    """PATCH /users/me. `role` and `is_active` are accepted only so they can be refused (403)."""

    model_config = ConfigDict(extra="forbid")

    full_name: FullName | None = None
    email: NormalizedEmail | None = None
    password: Password | None = None
    current_password: str | None = None
    role: str | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def _check(self) -> Self:
        for name in ("full_name", "email", "password"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} must not be null")
        if self.password is not None and not self.current_password:
            raise ValueError("current_password is required to change the password")
        return self
