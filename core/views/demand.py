"""Data for the demand charts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

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


# A local day counts as a full profile with at least this many settlement
# slots (46 allows for the short day when clocks go forward).
FULL_DAY_MIN_SLOTS = 46


@dataclass(frozen=True)
class TypicalDayView:
    """
    Today's demand profile against earlier days, by UK settlement slot.

    Slots are numbered 1-48 from local (Europe/London) midnight.

    typical      settlement_slot, q25, median, q75 (GW) over all earlier days
    current      settlement_slot, demand_gw for the latest local day so far
    latest_full  settlement_slot, demand_gw for the most recent earlier day
                 with a full profile (or the most recent earlier day if none
                 is full)
    """

    typical: pd.DataFrame
    current: pd.DataFrame
    latest_full: pd.DataFrame
    current_date: date
    latest_full_date: date


def typical_day_view(
    demand_history: pd.DataFrame,
) -> TypicalDayView:
    """
    Build the typical-day view from ``load_recent_demand`` output (ideally
    several weeks of history).

    Raises ValueError if there is no earlier local day to compare against.
    """
    require_columns(
        demand_history,
        ["event_time_utc", "demand_mw"],
        "Typical-day demand",
    )

    data = demand_history[["event_time_utc", "demand_mw"]].dropna().copy()

    data["event_time_utc"] = pd.to_datetime(
        data["event_time_utc"],
        utc=True,
    )

    local = data["event_time_utc"].dt.tz_convert("Europe/London")

    data["local_date"] = local.dt.date
    data["settlement_slot"] = local.dt.hour * 2 + local.dt.minute // 30 + 1
    data["demand_gw"] = data["demand_mw"] / 1000

    latest_date = data["local_date"].max()

    reference = data[data["local_date"] < latest_date].copy()

    if reference.empty:
        raise ValueError(
            "Typical-day demand needs at least "
            "one earlier local day for comparison."
        )

    profile_counts = (
        reference.groupby("local_date")["settlement_slot"]
        .nunique()
    )

    complete_dates = profile_counts[
        profile_counts >= FULL_DAY_MIN_SLOTS
    ].index

    if len(complete_dates):
        latest_full_date = max(complete_dates)
    else:
        latest_full_date = reference["local_date"].max()

    typical = (
        reference.groupby("settlement_slot")["demand_gw"]
        .agg(
            q25=lambda values: values.quantile(0.25),
            median="median",
            q75=lambda values: values.quantile(0.75),
        )
        .reset_index()
    )

    profile_columns = ["settlement_slot", "demand_gw"]

    return TypicalDayView(
        typical=typical,
        current=data[data["local_date"] == latest_date][profile_columns].copy(),
        latest_full=data[data["local_date"] == latest_full_date][profile_columns].copy(),
        current_date=latest_date,
        latest_full_date=latest_full_date,
    )
