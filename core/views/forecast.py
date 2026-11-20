"""Data for the 24-hour-ahead forecast charts."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.views.common import series_gw


@dataclass(frozen=True)
class ForecastView:
    """
    Recent de-rated margin history alongside the latest forecast.

    ``history`` has columns ``event_time_utc`` (UTC), ``derated_margin_mw``
    and ``drm_gw``.
    """

    history: pd.DataFrame
    target_time_utc: pd.Timestamp
    predicted_drm_gw: float
    latest_drm_gw: float


def forecast_view(
    recent_margin: pd.DataFrame,
    forecast: dict,
) -> ForecastView:
    """
    Build the forecast view from ``load_recent_margin`` output and the
    ``load_latest_forecast`` dict (``target_time_utc``, ``predicted_drm_mw``,
    ``latest_drm_mw``).
    """
    return ForecastView(
        history=series_gw(
            recent_margin,
            "event_time_utc",
            "derated_margin_mw",
            "drm_gw",
        ),
        target_time_utc=pd.Timestamp(forecast["target_time_utc"]),
        predicted_drm_gw=float(forecast["predicted_drm_mw"]) / 1000,
        latest_drm_gw=float(forecast["latest_drm_mw"]) / 1000,
    )
