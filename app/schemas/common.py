from typing import Annotated

from fastapi import Depends, Query
from pydantic import BaseModel

MAX_LIMIT = 100
DEFAULT_LIMIT = 20


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int


class PageParams(BaseModel):
    limit: int
    offset: int


def page_params(
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PageParams:
    """`limit` is 1-100 (default 20); out-of-range values are a 422."""
    return PageParams(limit=limit, offset=offset)


PageParamsDep = Annotated[PageParams, Depends(page_params)]
