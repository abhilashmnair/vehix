import logging
from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db import SessionDep

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


class HealthRead(BaseModel):
    status: Literal["ok", "unavailable"]


@router.get(
    "/health",
    response_model=HealthRead,
    status_code=status.HTTP_200_OK,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthRead}},
)
def health(session: SessionDep, response: Response) -> HealthRead:
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.error("Health check failed: database unavailable")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthRead(status="unavailable")
    return HealthRead(status="ok")
