"""
FastAPI app for the Flutter client.

Run locally from the repo root:

    uvicorn backend.api.main:app --reload

``create_app()`` builds a fresh app, so tests (and other hosts) can create
their own instance instead of sharing the module-level ``app``.

Settings come from environment variables; see ``.env.example``.
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.loaders import Loaders
from backend.api.models import EmptyState, HealthResponse
from backend.api.routes import demand, forecast, generation, grid, history, model, status
from core.queries import DatabaseUnavailableError

logger = logging.getLogger(__name__)

API_PREFIX = "/api"

# Comma-separated browser origins allowed to call the API, e.g.
# "http://localhost:5000,https://grid.example.com". Unset or empty means no
# cross-origin access. Only the web build needs this; the native apps don't
# send an Origin header.
CORS_ORIGINS_ENV = "GRID_CORS_ORIGINS"

DATABASE_UNAVAILABLE_MESSAGE = "Grid data is not available yet. Try again shortly."


def cors_origins_from_env() -> list[str]:
    """The allowed origins from ``GRID_CORS_ORIGINS``, blanks and trailing slashes removed."""
    raw = os.environ.get(CORS_ORIGINS_ENV, "")
    return [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]


def create_app(
    cors_origins: list[str] | None = None,
    *,
    cache: bool = True,
) -> FastAPI:
    """
    Build the API app.

    ``cors_origins`` defaults to ``GRID_CORS_ORIGINS``, read when the app is
    built. ``cache=False`` turns off the loader cache (see
    ``backend.api.loaders``).
    """
    if cors_origins is None:
        cors_origins = cors_origins_from_env()

    app = FastAPI(title="Grid Reliability API")
    app.state.loaders = Loaders(enabled=cache)

    @app.exception_handler(DatabaseUnavailableError)
    def database_unavailable(
        request: Request,
        error: DatabaseUnavailableError,
    ) -> JSONResponse:
        # The path stays in the server log, not the response.
        logger.warning("%s %s: %s", request.method, request.url.path, error)
        body = EmptyState(state="unavailable", message=DATABASE_UNAVAILABLE_MESSAGE)
        return JSONResponse(status_code=503, content=body.model_dump())

    if cors_origins:
        # The API is read-only, so browsers only need GET (and the preflight).
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_methods=["GET"],
        )

    @app.get(f"{API_PREFIX}/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        """Liveness check: the process is up and serving requests."""
        return HealthResponse()

    for module in (status, forecast, grid, history, demand, generation, model):
        app.include_router(module.router, prefix=API_PREFIX)

    return app


app = create_app()
