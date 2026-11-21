"""Domain exceptions and their mapping to the uniform error envelope.

Every error response has the shape ``{"error": {"code": ..., "message": ...}}``.
Validation errors (422) additionally carry ``details`` (location, message, type; never the
submitted input, which could contain passwords).
"""

import logging
from typing import Any, cast

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[dict[str, Any]] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


def error_responses(*codes: int) -> dict[int | str, dict[str, Any]]:
    """OpenAPI `responses=` helper documenting the envelope for the given status codes."""
    return {code: {"model": ErrorResponse} for code in codes}


class AppError(Exception):
    """Base class for errors that map to an HTTP response."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "internal_error"
    default_message = "Internal server error."

    def __init__(self, message: str | None = None, *, code: str | None = None) -> None:
        self.message = message or self.default_message
        if code is not None:
            self.code = code
        super().__init__(self.message)

    @property
    def headers(self) -> dict[str, str] | None:
        return None


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"
    default_message = "Not authenticated."

    @property
    def headers(self) -> dict[str, str] | None:
        return {"WWW-Authenticate": "Bearer"}


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"
    default_message = "You do not have permission to perform this action."


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    default_message = "Resource not found."


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"
    default_message = "The request conflicts with the current state of the resource."


_STATUS_CODES = {
    status.HTTP_400_BAD_REQUEST: "bad_request",
    status.HTTP_401_UNAUTHORIZED: "unauthorized",
    status.HTTP_403_FORBIDDEN: "forbidden",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_405_METHOD_NOT_ALLOWED: "method_not_allowed",
    status.HTTP_409_CONFLICT: "conflict",
    status.HTTP_422_UNPROCESSABLE_CONTENT: "validation_error",
    status.HTTP_503_SERVICE_UNAVAILABLE: "service_unavailable",
}


def _envelope(
    status_code: int,
    code: str,
    message: str,
    headers: dict[str, str] | None = None,
    details: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return JSONResponse(status_code=status_code, content={"error": error}, headers=headers)


async def _app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    exc = cast(AppError, exc)
    return _envelope(exc.status_code, exc.code, exc.message, exc.headers)


async def _http_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    exc = cast(StarletteHTTPException, exc)
    code = _STATUS_CODES.get(exc.status_code, "http_error")
    headers = dict(exc.headers) if exc.headers else None
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        headers = {**(headers or {}), "WWW-Authenticate": "Bearer"}
    return _envelope(exc.status_code, code, str(exc.detail), headers)


async def _validation_error_handler(_: Request, exc: Exception) -> JSONResponse:
    exc = cast(RequestValidationError, exc)
    details = [
        {"loc": list(err["loc"]), "msg": err["msg"], "type": err["type"]} for err in exc.errors()
    ]
    return _envelope(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "validation_error",
        "Request validation failed.",
        details=details,
    )


async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Log the traceback server-side only; the client never sees stack traces or SQL.
    logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return _envelope(
        status.HTTP_500_INTERNAL_SERVER_ERROR, "internal_error", "Internal server error."
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)
