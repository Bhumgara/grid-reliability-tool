"""Data for the demand charts."""

from __future__ import annotations

import pandas as pd

from core.views.common import require_columns

SETTLEMENT_COLUMNS = [
    "event_time_utc",
    "demand_mw",
    "display_demand_mw",
    "demand_gw",
    "estimated",
]


def demand_settlement_view(
    demand: pd.DataFrame,
) -> pd.DataFrame:
    """
    One row per half-hour settlement period, with internal gaps estimated.

    Missing half-hours between the first and last observation are linearly
    interpolated (by time) for display only. Leading and trailing gaps are
    left out. Nothing is written back to the source data.

    Columns:
        event_time_utc     UTC start of the settlement period
        demand_mw          observed demand; NaN where estimated
        display_demand_mw  observed or estimated demand (MW)
        demand_gw          display_demand_mw in GW
        estimated          True where the value was interpolated
    """
    require_columns(
        demand,
        ["event_time_utc", "demand_mw"],
        "Demand settlement bars",
    )

    data = demand[["event_time_utc", "demand_mw"]].copy()

    data["event_time_utc"] = pd.to_datetime(
        data["event_time_utc"],
        utc=True,
    )

    data = (
        data.sort_values("event_time_utc")
        .drop_duplicates("event_time_utc", keep="last")
        .set_index("event_time_utc")
    )

    if data.empty:
        return pd.DataFrame(columns=SETTLEMENT_COLUMNS)

    complete_index = pd.date_range(
        start=data.index.min(),
        end=data.index.max(),
        freq="30min",
        tz="UTC",
    )

    data = data.reindex(complete_index)
    data.index.name = "event_time_utc"

    data["estimated"] = data["demand_mw"].isna()

    data["display_demand_mw"] = data["demand_mw"].interpolate(
        method="time",
        limit_area="inside",
    )

    data = (
        data.reset_index()
        .dropna(subset=["display_demand_mw"])
    )

    data["demand_gw"] = data["display_demand_mw"] / 1000

    return data[SETTLEMENT_COLUMNS]
