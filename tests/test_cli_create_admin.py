"""AC-U6: `python -m app.cli create-admin` is idempotent."""

import secrets
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, text

import app.cli
from app.cli import create_admin, main
from app.config import REQUIRED_VARS, Settings
from tests.conftest import UserFactory

LOGIN = "/api/v1/auth/login"


def creds() -> tuple[str, str]:
    return f"seed-{secrets.token_hex(4)}@example.com", secrets.token_urlsafe(24)


def rows(engine: Engine, email: str) -> list[tuple[str, bool]]:
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT role, is_active FROM users WHERE lower(email) = lower(:e)"), {"e": email}
        )
        return [(r.role, r.is_active) for r in result]


def test_creates_admin_who_can_log_in(
    test_engine: Engine, client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    email, password = creds()
    assert create_admin(test_engine, email, password) == 0
    assert rows(test_engine, email) == [("admin", True)]
    output = capsys.readouterr()
    assert "created" in output.out
    assert email not in output.out + output.err
    assert password not in output.out + output.err
    assert client.post(LOGIN, json={"email": email, "password": password}).status_code == 200


def test_running_twice_is_idempotent_and_keeps_the_original_password(
    test_engine: Engine, client: TestClient, capsys: pytest.CaptureFixture[str]
) -> None:
    email, password = creds()
    assert create_admin(test_engine, email, password) == 0
    other_password = secrets.token_urlsafe(24)
    assert create_admin(test_engine, email.upper(), other_password) == 0
    assert "already exists" in capsys.readouterr().out
    assert rows(test_engine, email) == [("admin", True)]
    assert client.post(LOGIN, json={"email": email, "password": password}).status_code == 200
    assert client.post(LOGIN, json={"email": email, "password": other_password}).status_code == 401


def test_existing_non_admin_is_left_unchanged_and_reported(
    test_engine: Engine, user_factory: UserFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    person = user_factory(email=creds()[0])
    assert create_admin(test_engine, person.email, secrets.token_urlsafe(24)) == 1
    assert "left unchanged" in capsys.readouterr().err
    assert rows(test_engine, person.email) == [("user", True)]


def test_existing_inactive_admin_is_left_unchanged(
    test_engine: Engine, user_factory: UserFactory
) -> None:
    person = user_factory(email=creds()[0], role="admin", is_active=False)
    assert create_admin(test_engine, person.email, secrets.token_urlsafe(24)) == 1
    assert rows(test_engine, person.email) == [("admin", False)]


def test_invalid_email_or_weak_password_creates_nothing(
    test_engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    email, _ = creds()
    weak = secrets.token_hex(4)
    assert create_admin(test_engine, email, weak) == 1
    assert create_admin(test_engine, "not-an-email", secrets.token_urlsafe(24)) == 1
    err = capsys.readouterr().err
    assert weak not in err
    assert rows(test_engine, email) == []


def test_main_reads_credentials_from_settings(
    test_engine: Engine, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    email, password = creds()
    settings = Settings(
        db_host="h",
        db_port=1,
        db_user="u",
        db_password=SecretStr("x"),
        db_name="n",
        test_db_name="t",
        jwt_secret=SecretStr("x"),
        jwt_expire_minutes=1,
        admin_email=email,
        admin_password=SecretStr(password),
    )
    monkeypatch.setattr(app.cli, "get_settings", lambda: settings)
    monkeypatch.setattr(app.cli, "get_engine", lambda: test_engine)
    assert main(["create-admin"]) == 0
    assert main(["create-admin"]) == 0
    assert rows(test_engine, email) == [("admin", True)]
    assert password not in capsys.readouterr().out


def test_command_fails_clearly_when_env_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for name in REQUIRED_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(app.cli, "ENV_FILE", tmp_path / ".env")
    assert main(["create-admin"]) == 1
    assert "populate" in capsys.readouterr().err
