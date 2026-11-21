"""Application settings, loaded from `.env` (or the process environment).

No secret has a default value. Missing or placeholder values are reported by
variable *name* only; values are never printed.
"""

import os
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

PLACEHOLDER = "CHANGE_ME"
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

REQUIRED_VARS: tuple[str, ...] = (
    "DB_HOST",
    "DB_PORT",
    "DB_USER",
    "DB_PASSWORD",
    "DB_NAME",
    "TEST_DB_NAME",
    "JWT_SECRET",
    "JWT_EXPIRE_MINUTES",
    "ADMIN_EMAIL",
    "ADMIN_PASSWORD",
)


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
    env_file: Path = ENV_FILE, environ: Mapping[str, str] | None = None
) -> list[str]:
    """Return names of required variables that are missing, empty or still a placeholder.

    Raises MissingEnvFileError if the file does not exist and no required variable is
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
    return [
        name
        for name in REQUIRED_VARS
        if (value := values.get(name)) is None or value.strip() in ("", PLACEHOLDER)
    ]


def validate_env(env_file: Path = ENV_FILE, environ: Mapping[str, str] | None = None) -> None:
    problems = find_env_problems(env_file, environ)
    if problems:
        raise InvalidEnvError(problems)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    db_host: str
    db_port: int
    db_user: str
    db_password: SecretStr
    db_name: str
    test_db_name: str
    jwt_secret: SecretStr
    jwt_expire_minutes: int
    admin_email: str
    admin_password: SecretStr

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
