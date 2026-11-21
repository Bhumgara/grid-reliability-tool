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
    Refresh status.

    ``last_refresh_completed_utc`` is what polling clients compare with their
    own copy: when it is newer, the data may have changed, so refetch. It is
    the refresh worker's record, falling back to the status file's
    ``completed_at_utc`` when there is no record (e.g. the dashboard thread
    refreshes instead). Unlike ``completed_at_utc``, it keeps its value while
    a refresh is running. ``as_of_utc`` is the same time. Both are None only
    before any refresh has finished.

    ``refresh_state`` is separate from ``state`` (always ``"ok"`` here):
    this endpoint answers even before the first refresh, with ``"starting"``.
    """

    last_refresh_completed_utc: UtcDatetime | None
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
    last_completed = loaders.load_last_refresh_completed()
    if last_completed is None:
        last_completed = view.completed_at_utc

    return StatusResponse(
        as_of_utc=last_completed,
        last_refresh_completed_utc=last_completed,
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
