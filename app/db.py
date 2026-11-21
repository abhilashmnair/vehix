"""Database engine and per-request session dependency."""

from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.config import get_settings


@lru_cache
def _create_engine() -> Engine:
    return create_engine(get_settings().database_url(), pool_pre_ping=True)


def get_engine() -> Engine:
    """Dependency returning the application engine (overridden in tests)."""
    return _create_engine()


def get_session(engine: Annotated[Engine, Depends(get_engine)]) -> Iterator[Session]:
    """One session per request. Commit and rollback happen here and nowhere else.

    Services must `flush()` when a constraint violation has to be mapped to an HTTP
    error, because this commit runs after the route has returned.
    """
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


SessionDep = Annotated[Session, Depends(get_session)]
