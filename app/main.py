from fastapi import FastAPI

from app.errors import register_exception_handlers
from app.routers import API_PREFIX, auth, health, users


def create_app() -> FastAPI:
    app = FastAPI(title="Vehicle Management API", version="0.1.0")
    register_exception_handlers(app)
    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(users.router, prefix=API_PREFIX)
    return app


app = create_app()
