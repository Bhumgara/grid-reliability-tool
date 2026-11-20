"""GET /api/grid/now: the current margin, demand and generation metrics."""

from __future__ import annotations

from fastapi import APIRouter

from backend.api.loaders import LoadersDep
from backend.api.models import DataResponse, EmptyState, UtcDatetime
from core.views.grid_now import grid_now_view

router = APIRouter()

# Days loaded to find the latest values, as the dashboard.
RECENT_DAYS = 7

NO_CONTEXT_MESSAGE = "Current grid context is unavailable."


class GridNowResponse(DataResponse):
    """
    Latest grid metrics. ``as_of_utc`` is the latest margin time (the
    dashboard's "Data updated").

    Show the stale warning once the clock passes ``stale_after_utc``.
    """

    drm_gw: float
    drm_time_utc: UtcDatetime | None
    demand_gw: float
    demand_time_utc: UtcDatetime | None
    tracked_generation_gw: float | None
    generation_time_utc: UtcDatetime | None
    stale_after_utc: UtcDatetime | None


@router.get("/grid/now", response_model=GridNowResponse | EmptyState)
def get_grid_now(loaders: LoadersDep) -> GridNowResponse | EmptyState:
    margin = loaders.load_recent_margin(RECENT_DAYS)
    demand = loaders.load_recent_demand(RECENT_DAYS)

    if margin.empty or demand.empty:
        return EmptyState(state="unavailable", message=NO_CONTEXT_MESSAGE)

    try:
        view = grid_now_view(
            margin,
            demand,
            loaders.load_recent_generation(RECENT_DAYS),
        )
    except ValueError as error:
        return EmptyState.from_error(error)

    return GridNowResponse(
        as_of_utc=view.drm_time_utc,
        drm_gw=view.drm_gw,
        drm_time_utc=view.drm_time_utc,
        demand_gw=view.demand_gw,
        demand_time_utc=view.demand_time_utc,
        tracked_generation_gw=view.tracked_generation_gw,
        generation_time_utc=view.generation_time_utc,
        stale_after_utc=view.stale_after_utc,
    )
