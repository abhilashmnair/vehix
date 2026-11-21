from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.schemas.common import PageParams


def paginate[T](session: Session, stmt: Select[T], params: PageParams) -> tuple[list[T], int]:
    """Run an already ordered SELECT with limit/offset and also return the unpaged total."""
    count_stmt: Select[Any] = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = int(session.scalar(count_stmt) or 0)
    items = list(session.scalars(stmt.limit(params.limit).offset(params.offset)))
    return items, total
