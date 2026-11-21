"""Application settings, loaded from `.env` (or the process environment).

No secret has a default value. Missing or placeholder values are reported by
variable *name* only; values are never printed.
"""

import os
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from dotenv import dotenv_values
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import URL

PLACEHOLDER = "CHANGE_ME"
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

# Needed to serve requests (and to run migrations).
SERVER_VARS: tuple[str, ...] = (
    "DB_HOST",
    "DB_PORT",
    "DB_USER",
    "DB_PASSWORD",
    "DB_NAME",
    "JWT_SECRET",
    "JWT_EXPIRE_MINUTES",
)
# Needed only by `python -m app.cli create-admin`.
ADMIN_VARS: tuple[str, ...] = ("ADMIN_EMAIL", "ADMIN_PASSWORD")
# Needed only by the test suite.
TEST_VARS: tuple[str, ...] = ("TEST_DB_NAME",)
# Every variable that must appear in `.env.example`.
REQUIRED_VARS: tuple[str, ...] = SERVER_VARS + ADMIN_VARS + TEST_VARS


class EnvConfigError(RuntimeError):
    """Base class for environment configuration problems (messages hold names only)."""


class MissingEnvFileError(EnvConfigError):
    def __init__(self, env_file: Path) -> None:
        super().__init__(
            f"{env_file.name} not found. Copy .env.example to .env and populate every "
            f"{PLACEHOLDER} placeholder with your own values."
        )


class InvalidEnvError(EnvConfigError):
    def __init__(self, names: list[str]) -> None:
        self.names = names
        super().__init__(
            "Missing or placeholder environment variables: "
            + ", ".join(names)
            + ". Populate them in .env (see .env.example)."
        )


def find_env_problems(
    env_file: Path = ENV_FILE,
    environ: Mapping[str, str] | None = None,
    required: tuple[str, ...] = SERVER_VARS,
) -> list[str]:
    """Return names of variables that are missing, empty or still a placeholder.

    A variable in `required` must be set. Any other known variable is optional, but if it is
    present it must not be empty or a placeholder.

    Raises MissingEnvFileError if the file does not exist and no known variable is
    provided through the process environment.
    """
    environ = os.environ if environ is None else environ
    values: dict[str, str | None] = {}
    if env_file.is_file():
        values.update(dotenv_values(env_file))
    elif not any(name in environ for name in REQUIRED_VARS):
        raise MissingEnvFileError(env_file)
    for name in REQUIRED_VARS:
        if name in environ:
            values[name] = environ[name]

    def unusable(name: str) -> bool:
        value = values.get(name)
        return value is None or value.strip() in ("", PLACEHOLDER)

    return [
        name for name in REQUIRED_VARS if (name in required or name in values) and unusable(name)
    ]


def validate_env(
    env_file: Path = ENV_FILE,
    environ: Mapping[str, str] | None = None,
    required: tuple[str, ...] = SERVER_VARS,
) -> None:
    problems = find_env_problems(env_file, environ, required)
    if problems:
        raise InvalidEnvError(problems)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    db_host: str
    db_port: int
    db_user: str
    db_password: SecretStr
    db_name: str
    jwt_secret: SecretStr
    jwt_expire_minutes: int
    # Optional: only the test suite and `create-admin` need these (see TEST_VARS, ADMIN_VARS).
    test_db_name: str | None = None
    admin_email: str | None = None
    admin_password: SecretStr | None = None
    # Optional. CORS is disabled unless origins are listed (comma separated in `.env`).
    cors_origins: Annotated[list[str], NoDecode] = []
    # OpenAPI docs (/docs, /redoc, /openapi.json); set DOCS_ENABLED=false in production.
    docs_enabled: bool = True

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    def database_url(self, database: str | None = None) -> URL:
        """Build the SQLAlchemy URL from its parts; the password lives only in `.env`."""
        return URL.create(
            "postgresql+psycopg",
            username=self.db_user,
            password=self.db_password.get_secret_value(),
            host=self.db_host,
            port=self.db_port,
            database=database or self.db_name,
        )


@lru_cache
def get_settings() -> Settings:
    validate_env()
    return Settings()
