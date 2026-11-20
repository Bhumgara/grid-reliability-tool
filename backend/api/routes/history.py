"""GET /api/history/margin and /api/history/demand: recent time series."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.api.loaders import LoadersDep
from backend.api.models import DataResponse, EmptyState, UtcDatetime
from core.views.common import series_gw
from core.views.demand import demand_settlement_view

router = APIRouter()

DEFAULT_DAYS = 7
# The longest window the dashboard loads (the typical-day demand history).
MAX_DAYS = 90

Days = Annotated[
    int,
    Query(ge=1, le=MAX_DAYS, description="Days of history, latest first."),
]


class MarginPoint(BaseModel):
    time_utc: UtcDatetime
    drm_gw: float


class MarginHistoryResponse(DataResponse):
    """1-hour-ahead de-rated margin, oldest first. ``as_of_utc`` is the last point."""

    points: list[MarginPoint]


class DemandPoint(BaseModel):
    time_utc: UtcDatetime
    demand_gw: float
    # True for display-only estimates filling internal gaps (faded bars).
    estimated: bool


class DemandHistoryResponse(DataResponse):
    """
    Demand per settlement period, oldest first, with internal gaps estimated.
    ``as_of_utc`` is the last period.
    """

    points: list[DemandPoint]


@router.get("/history/margin", response_model=MarginHistoryResponse | EmptyState)
def get_margin_history(
    loaders: LoadersDep,
    days: Days = DEFAULT_DAYS,
) -> MarginHistoryResponse | EmptyState:
    margin = loaders.load_recent_margin(days)

    if margin.empty:
        return EmptyState(state="unavailable", message="Margin history is unavailable.")

    series = series_gw(margin, "event_time_utc", "derated_margin_mw", "drm_gw")
    points = [
        MarginPoint(time_utc=time, drm_gw=value)
        for time, value in zip(series["event_time_utc"], series["drm_gw"])
    ]

    return MarginHistoryResponse(as_of_utc=points[-1].time_utc, points=points)


@router.get("/history/demand", response_model=DemandHistoryResponse | EmptyState)
def get_demand_history(
    loaders: LoadersDep,
    days: Days = DEFAULT_DAYS,
) -> DemandHistoryResponse | EmptyState:
    demand = loaders.load_recent_demand(days)

    if demand.empty:
        return EmptyState(state="unavailable", message="Demand history is unavailable.")

    try:
        settlement = demand_settlement_view(demand)
    except ValueError as error:
        return EmptyState.from_error(error)

    if settlement.empty:
        return EmptyState(state="unavailable", message="Demand history is unavailable.")

    points = [
        DemandPoint(time_utc=time, demand_gw=value, estimated=bool(estimated))
        for time, value, estimated in zip(
            settlement["event_time_utc"],
            settlement["demand_gw"],
            settlement["estimated"],
        )
    ]

    return DemandHistoryResponse(as_of_utc=points[-1].time_utc, points=points)
