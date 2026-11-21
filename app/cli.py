"""Command line entry points: `python -m app.cli <command>`."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from app.config import ENV_FILE, EnvConfigError, validate_env


def check_env(env_file: Path) -> int:
    try:
        validate_env(env_file)
    except EnvConfigError as exc:
        print(f"check-env failed: {exc}", file=sys.stderr)
        return 1
    print("check-env OK: all required variables are set.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check-env", help="validate .env without revealing values")
    check.add_argument("--env-file", type=Path, default=ENV_FILE)
    args = parser.parse_args(argv)
    if args.command == "check-env":
        return check_env(args.env_file)
    return 2  # pragma: no cover


if __name__ == "__main__":
    sys.exit(main())
