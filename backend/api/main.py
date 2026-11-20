"""
FastAPI app for the Flutter client.

Run locally from the repo root:

    uvicorn backend.api.main:app --reload

``create_app()`` builds a fresh app, so tests (and other hosts) can create
their own instance instead of sharing the module-level ``app``.

Settings come from environment variables; see ``.env.example``.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.models import HealthResponse

API_PREFIX = "/api"

# Comma-separated browser origins allowed to call the API, e.g.
# "http://localhost:5000,https://grid.example.com". Unset or empty means no
# cross-origin access. Only the web build needs this; the native apps don't
# send an Origin header.
CORS_ORIGINS_ENV = "GRID_CORS_ORIGINS"


def cors_origins_from_env() -> list[str]:
    """The allowed origins from ``GRID_CORS_ORIGINS``, blanks and trailing slashes removed."""
    raw = os.environ.get(CORS_ORIGINS_ENV, "")
    return [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]


def create_app(cors_origins: list[str] | None = None) -> FastAPI:
    """
    Build the API app.

    ``cors_origins`` defaults to ``GRID_CORS_ORIGINS``, read when the app is
    built.
    """
    if cors_origins is None:
        cors_origins = cors_origins_from_env()

    app = FastAPI(title="Grid Reliability API")

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

    return app


app = create_app()
