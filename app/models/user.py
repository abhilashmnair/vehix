import enum

from sqlalchemy import CheckConstraint, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin


class UserRole(enum.StrEnum):
    ADMIN = "admin"
    USER = "user"


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False, default=UserRole.USER.value)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True, server_default="true")

    __table_args__ = (
        CheckConstraint("role IN ('admin', 'user')", name="role_valid"),
        # Case-insensitive uniqueness without requiring the citext extension.
        Index("uq_users_email_lower", func.lower(email), unique=True),
    )
