"""Command line entry points: `python -m app.cli <command>`."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.config import ADMIN_VARS, ENV_FILE, SERVER_VARS, EnvConfigError, get_settings, validate_env
from app.db import get_engine
from app.errors import AppError
from app.schemas.user import NormalizedEmail, Password
from app.services import users as users_service


def check_env(env_file: Path) -> int:
    try:
        validate_env(env_file)
    except EnvConfigError as exc:
        print(f"check-env failed: {exc}", file=sys.stderr)
        return 1
    print("check-env OK: all required variables are set.")
    return 0


def create_admin(engine: Engine, email: str, password: str) -> int:
    """Create the first admin if it does not exist yet. Never prints the email or password."""
    try:
        valid_email = TypeAdapter(NormalizedEmail).validate_python(email)
        TypeAdapter(Password).validate_python(password)
    except ValidationError:
        print(
            "create-admin failed: ADMIN_EMAIL must be a valid email and ADMIN_PASSWORD "
            "must be 12-128 characters. Fix them in .env.",
            file=sys.stderr,
        )
        return 1
    try:
        with Session(engine) as session:
            result = users_service.ensure_admin(session, valid_email, password)
            session.commit()
    except AppError as exc:
        print(f"create-admin failed: {exc.message}", file=sys.stderr)
        return 1
    print("Admin user created." if result == "created" else "Admin user already exists.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check-env", help="validate .env without revealing values")
    check.add_argument("--env-file", type=Path, default=ENV_FILE)
    sub.add_parser("create-admin", help="idempotently create the first admin from .env")
    args = parser.parse_args(argv)
    if args.command == "check-env":
        return check_env(args.env_file)
    try:
        validate_env(ENV_FILE, required=SERVER_VARS + ADMIN_VARS)
    except EnvConfigError as exc:
        print(f"create-admin failed: {exc}", file=sys.stderr)
        return 1
    settings = get_settings()
    if settings.admin_email is None or settings.admin_password is None:  # pragma: no cover
        print("create-admin failed: ADMIN_EMAIL and ADMIN_PASSWORD are required.", file=sys.stderr)
        return 1
    return create_admin(
        get_engine(), settings.admin_email, settings.admin_password.get_secret_value()
    )


if __name__ == "__main__":
    sys.exit(main())
