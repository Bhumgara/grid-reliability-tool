"""Current grid context: the latest margin, demand and tracked generation."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.views.common import timestamp_utc_or_none

# The dashboard warns that the dataset is stale when the latest margin is
# older than this.
STALE_AFTER = pd.Timedelta(minutes=90)


@dataclass(frozen=True)
class GridNowView:
    drm_gw: float
    drm_time_utc: pd.Timestamp | None
    demand_gw: float
    demand_time_utc: pd.Timestamp | None
    # Sum of positive FUELHH generation at the latest settlement period. None
    # when there is no generation data.
    tracked_generation_gw: float | None
    generation_time_utc: pd.Timestamp | None
    # When the data counts as stale: the latest margin time plus STALE_AFTER.
    # A time rather than a flag, so it stays correct however long a client
    # (or cache) holds the response.
    stale_after_utc: pd.Timestamp | None


def grid_now_view(
    recent_margin: pd.DataFrame,
    recent_demand: pd.DataFrame,
    recent_generation: pd.DataFrame,
) -> GridNowView:
    """
    Build the view from ``load_recent_margin``, ``load_recent_demand`` and
    ``load_recent_generation`` output.

    Raises ValueError if there is no margin, or no demand value.
    """
    if recent_margin.empty:
        raise ValueError("No recent de-rated margin is available.")

    demand = (
        recent_demand.dropna(subset=["demand_mw"])
        if "demand_mw" in recent_demand.columns
        else pd.DataFrame()
    )

    if demand.empty:
        raise ValueError("No recent demand value is available.")

    latest_margin = recent_margin.iloc[-1]
    latest_demand = demand.iloc[-1]
    drm_time = timestamp_utc_or_none(latest_margin["event_time_utc"])

    tracked_generation = None
    generation_time = None

    if not recent_generation.empty:
        latest_generation = recent_generation.iloc[-1]
        tracked_generation = float(
            latest_generation[latest_generation > 0].sum() / 1000
        )
        generation_time = timestamp_utc_or_none(recent_generation.index[-1])

    return GridNowView(
        drm_gw=float(latest_margin["derated_margin_mw"]) / 1000,
        drm_time_utc=drm_time,
        demand_gw=float(latest_demand["demand_mw"]) / 1000,
        demand_time_utc=timestamp_utc_or_none(latest_demand["event_time_utc"]),
        tracked_generation_gw=tracked_generation,
        generation_time_utc=generation_time,
        stale_after_utc=drm_time + STALE_AFTER if drm_time is not None else None,
    )
