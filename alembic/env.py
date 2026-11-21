from logging.config import fileConfig

from alembic import context
from sqlalchemy import Engine

from app.db import get_engine
from app.models import Base

config = context.config
if config.config_file_name is not None and not config.attributes.get("skip_logging_config"):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _engine() -> Engine:
    # Tests inject their engine; otherwise the URL is built from .env (never from alembic.ini).
    engine: Engine | None = config.attributes.get("engine")
    return engine if engine is not None else get_engine()


def run_migrations_online() -> None:
    with _engine().connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
        connection.commit()


run_migrations_online()
