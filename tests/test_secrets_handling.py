"""AC-F0: secrets handling."""

import secrets
import subprocess
from pathlib import Path

import pytest
from dotenv import dotenv_values
from pydantic import SecretStr

from app import config
from app.cli import main
from app.config import PLACEHOLDER, REQUIRED_VARS, Settings

ROOT = Path(__file__).resolve().parent.parent
SECRET_VARS = ("DB_PASSWORD", "JWT_SECRET", "ADMIN_PASSWORD")


@pytest.fixture(autouse=True)
def clean_environ(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in REQUIRED_VARS:
        monkeypatch.delenv(name, raising=False)


def write_env(path: Path, values: dict[str, str]) -> Path:
    path.write_text("".join(f"{k}={v}\n" for k, v in values.items()))
    return path


def valid_values() -> dict[str, str]:
    values = {name: "x" for name in REQUIRED_VARS}
    values.update(DB_PORT="5432", JWT_EXPIRE_MINUTES="30", ADMIN_EMAIL="admin@example.com")
    for name in SECRET_VARS:
        values[name] = secrets.token_urlsafe(24)
    return values


def test_env_file_is_git_ignored() -> None:
    result = subprocess.run(
        ["git", "check-ignore", ".env"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.stdout.strip() == ".env"


def test_env_example_has_placeholders_only() -> None:
    example = dotenv_values(ROOT / ".env.example")
    assert set(example) == set(REQUIRED_VARS)
    for name in SECRET_VARS:
        assert example[name] == PLACEHOLDER


def test_settings_use_secretstr_and_never_repr_secrets() -> None:
    values = valid_values()
    for field in ("db_password", "jwt_secret", "admin_password"):
        assert Settings.model_fields[field].annotation is SecretStr
    settings = Settings(**{k.lower(): v for k, v in values.items()})  # type: ignore[arg-type]
    for name in SECRET_VARS:
        assert values[name] not in repr(settings)
        assert values[name] not in str(settings)
    assert values["DB_PASSWORD"] not in str(settings.database_url())
    assert values["DB_PASSWORD"] in settings.database_url().render_as_string(hide_password=False)


def test_check_env_ok(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    env = write_env(tmp_path / ".env", valid_values())
    assert main(["check-env", "--env-file", str(env)]) == 0
    assert "OK" in capsys.readouterr().out


def test_check_env_missing_file_says_to_populate_env(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["check-env", "--env-file", str(tmp_path / ".env")]) == 1
    err = capsys.readouterr().err
    assert "Copy .env.example to .env" in err
    assert "populate" in err


def test_check_env_reports_names_of_missing_and_placeholder_without_values(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    values = valid_values()
    leaked = values["DB_PASSWORD"]
    del values["DB_HOST"]
    values["JWT_SECRET"] = PLACEHOLDER
    values["ADMIN_EMAIL"] = ""
    env = write_env(tmp_path / ".env", values)
    assert main(["check-env", "--env-file", str(env)]) == 1
    captured = capsys.readouterr()
    output = captured.out + captured.err
    for name in ("DB_HOST", "JWT_SECRET", "ADMIN_EMAIL"):
        assert name in output
    assert "DB_PASSWORD" not in output
    assert leaked not in output


def test_process_environment_can_replace_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name, value in valid_values().items():
        monkeypatch.setenv(name, value)
    assert config.find_env_problems(tmp_path / ".env") == []
