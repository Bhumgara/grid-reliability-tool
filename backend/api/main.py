"""
FastAPI app for the Flutter client.

Run locally from the repo root:

    uvicorn backend.api.main:app --reload

``create_app()`` builds a fresh app, so tests (and other hosts) can create
their own instance instead of sharing the module-level ``app``.
"""

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

API_PREFIX = "/api"


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


def create_app() -> FastAPI:
    app = FastAPI(title="Grid Reliability API")

    @app.get(f"{API_PREFIX}/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        """Liveness check: the process is up and serving requests."""
        return HealthResponse()

    return app


app = create_app()
