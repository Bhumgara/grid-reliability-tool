"""GET /api/forecast/hero: the headline 24-hour-ahead forecast."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from backend.api.models import DataResponse, EmptyState, UtcDatetime
from core import queries
from core.views.forecast import forecast_hero_view

router = APIRouter()

# Days of recent margin used for the latest published value, as the dashboard.
RECENT_MARGIN_DAYS = 7

NO_FORECAST_MESSAGE = "A saved forecast is not currently available."


class DrmBridge(BaseModel):
    """Change from the latest margin to the forecast, with a padded axis range."""

    current_drm_gw: float
    predicted_drm_gw: float
    change_gw: float
    direction: Literal["up", "down", "flat"]
    axis_min_gw: float
    axis_max_gw: float


class ForecastHeroResponse(DataResponse):
    """``as_of_utc`` is when the forecast was generated."""

    target_time_utc: UtcDatetime
    forecast_origin_utc: UtcDatetime | None
    generated_at_utc: UtcDatetime | None
    predicted_drm_gw: float
    latest_drm_gw: float
    latest_time_utc: UtcDatetime | None
    # Percentage of historical margins below the prediction (0-100).
    percentile: float
    percentile_description: str
    bridge: DrmBridge


@router.get(
    "/forecast/hero",
    response_model=ForecastHeroResponse | EmptyState,
)
def get_forecast_hero() -> ForecastHeroResponse | EmptyState:
    forecast = queries.load_latest_forecast()
    margin = queries.load_recent_margin(RECENT_MARGIN_DAYS)

    if forecast is None or margin.empty:
        return EmptyState(state="unavailable", message=NO_FORECAST_MESSAGE)

    try:
        view = forecast_hero_view(forecast, margin, queries.load_margin_history())
    except ValueError as error:
        return EmptyState.from_error(error)

    bridge = view.bridge

    return ForecastHeroResponse(
        as_of_utc=view.generated_at_utc,
        target_time_utc=view.target_time_utc,
        forecast_origin_utc=view.forecast_origin_utc,
        generated_at_utc=view.generated_at_utc,
        predicted_drm_gw=view.predicted_drm_gw,
        latest_drm_gw=view.latest_drm_gw,
        latest_time_utc=view.latest_time_utc,
        percentile=view.percentile,
        percentile_description=view.percentile_description,
        bridge=DrmBridge(
            current_drm_gw=bridge.current_drm_gw,
            predicted_drm_gw=bridge.predicted_drm_gw,
            change_gw=bridge.change_gw,
            direction=bridge.direction,
            axis_min_gw=bridge.axis_min_gw,
            axis_max_gw=bridge.axis_max_gw,
        ),
    )
