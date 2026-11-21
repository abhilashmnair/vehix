from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine

ROOT = Path(__file__).resolve().parent.parent


def alembic_config(engine: Engine) -> Config:
    """Alembic config that runs against `engine`, so no URL (or password) is ever stringified."""
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.attributes["engine"] = engine
    cfg.attributes["skip_logging_config"] = True
    return cfg


def upgrade(engine: Engine, revision: str = "head") -> None:
    command.upgrade(alembic_config(engine), revision)


def downgrade(engine: Engine, revision: str = "base") -> None:
    command.downgrade(alembic_config(engine), revision)


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
