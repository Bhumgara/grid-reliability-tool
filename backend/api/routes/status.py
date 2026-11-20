"""GET /api/status: the live refresh status."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.api.loaders import LoadersDep
from backend.api.models import DataResponse, UtcDatetime
from core.views.status import RefreshState, refresh_status_view

router = APIRouter()


class SourceStatusModel(BaseModel):
    name: str
    required: bool
    latest_event_utc: UtcDatetime | None
    age_minutes: float | None
    stale: bool


class StatusResponse(DataResponse):
    """
    Refresh status. ``as_of_utc`` is when the last refresh check completed.

    ``refresh_state`` is separate from ``state`` (always ``"ok"`` here):
    this endpoint answers even before the first refresh, with ``"starting"``.
    """

    refresh_state: RefreshState
    message: str
    started_at_utc: UtcDatetime | None
    completed_at_utc: UtcDatetime | None
    forecast_generated_at_utc: UtcDatetime | None
    sources: list[SourceStatusModel]
    errors: list[str]


@router.get("/status", response_model=StatusResponse)
def get_status(loaders: LoadersDep) -> StatusResponse:
    view = refresh_status_view(loaders.load_refresh_status())

    return StatusResponse(
        as_of_utc=view.completed_at_utc,
        refresh_state=view.state,
        message=view.message,
        started_at_utc=view.started_at_utc,
        completed_at_utc=view.completed_at_utc,
        forecast_generated_at_utc=view.forecast_generated_at_utc,
        sources=[
            SourceStatusModel(
                name=source.name,
                required=source.required,
                latest_event_utc=source.latest_event_utc,
                age_minutes=source.age_minutes,
                stale=source.stale,
            )
            for source in view.sources
        ],
        errors=list(view.errors),
    )
