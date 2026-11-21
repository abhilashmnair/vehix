"""Request IDs and one access-log line per request (no query strings, bodies or PII)."""

import contextvars
import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

REQUEST_ID_HEADER = "X-Request-ID"
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
logger = logging.getLogger("app.access")

_original_factory = logging.getLogRecordFactory()


def _record_factory(*args: object, **kwargs: object) -> logging.LogRecord:
    record = _original_factory(*args, **kwargs)
    record.request_id = request_id_var.get()
    return record


def configure_logging() -> None:
    """Attach `request_id` to every log record and use a format that shows it."""
    logging.setLogRecordFactory(_record_factory)
    log_format = "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"
    logging.basicConfig(level=logging.INFO, format=log_format)


def add_request_context(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        inbound = request.headers.get(REQUEST_ID_HEADER, "")
        request_id = inbound if _VALID_REQUEST_ID.fullmatch(inbound) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = request_id
            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "%s %s -> %s (%.1f ms)",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
            )
            return response
        finally:
            request_id_var.reset(token)
