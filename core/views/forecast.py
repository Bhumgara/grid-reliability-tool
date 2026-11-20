"""Data for the 24-hour-ahead forecast charts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

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


# Minimum axis span and padding (GW) so small changes still read clearly.
_BRIDGE_MIN_SPAN_GW = 0.5
_BRIDGE_MIN_PADDING_GW = 0.65
_BRIDGE_PADDING_FRACTION = 0.30


@dataclass(frozen=True)
class DrmBridgeView:
    """
    Change from the current de-rated margin to the 24-hour forecast.

    ``axis_min_gw`` / ``axis_max_gw`` give a padded range that keeps both
    points (and their labels) comfortably inside the chart.
    """

    current_drm_gw: float
    predicted_drm_gw: float
    change_gw: float
    direction: Literal["up", "down", "flat"]
    axis_min_gw: float
    axis_max_gw: float


def drm_bridge_view(
    forecast: dict,
    current_drm_mw: float,
) -> DrmBridgeView:
    """Build the bridge view from the forecast dict and the latest DRM (MW)."""
    current = float(current_drm_mw) / 1000
    predicted = float(forecast["predicted_drm_mw"]) / 1000
    change = predicted - current

    lower = min(current, predicted)
    upper = max(current, predicted)
    span = max(upper - lower, _BRIDGE_MIN_SPAN_GW)
    padding = max(span * _BRIDGE_PADDING_FRACTION, _BRIDGE_MIN_PADDING_GW)

    if change > 0:
        direction = "up"
    elif change < 0:
        direction = "down"
    else:
        direction = "flat"

    return DrmBridgeView(
        current_drm_gw=current,
        predicted_drm_gw=predicted,
        change_gw=change,
        direction=direction,
        axis_min_gw=lower - padding,
        axis_max_gw=upper + padding,
    )
