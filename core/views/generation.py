"""Data for the generation charts."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.views.common import require_columns


def latest_generation_snapshot(
    generation: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Timestamp]:
    """
    Latest generation snapshot in long form, largest source first.

    Accepts either long data (``event_time_utc``, ``fuel_type``,
    ``generation_mw``) or wide data with one column per fuel (``event_time_utc``
    as a column or the index), such as ``load_recent_generation`` output.

    Missing and non-positive values are dropped.

    Returns ``(mix, latest_time)``, where ``mix`` has columns ``fuel_type``,
    ``generation_mw``, ``generation_gw`` and ``share`` (0-1).
    """
    wide = generation.copy()

    if "event_time_utc" not in wide.columns:
        wide = wide.reset_index()

    require_columns(
        wide,
        ["event_time_utc"],
        "Generation snapshot",
    )

    wide["event_time_utc"] = pd.to_datetime(
        wide["event_time_utc"],
        utc=True,
    )

    latest_time = wide["event_time_utc"].max()

    latest = wide[wide["event_time_utc"] == latest_time].copy()

    if {"fuel_type", "generation_mw"}.issubset(latest.columns):
        mix = latest[["fuel_type", "generation_mw"]].copy()
    else:
        fuels = [
            column
            for column in latest.columns
            if column != "event_time_utc"
        ]

        mix = latest.melt(
            id_vars="event_time_utc",
            value_vars=fuels,
            var_name="fuel_type",
            value_name="generation_mw",
        )

    mix = (
        mix.dropna(subset=["generation_mw"])
        .groupby("fuel_type", as_index=False)["generation_mw"]
        .sum()
    )

    mix = mix[mix["generation_mw"] > 0].copy()

    mix["generation_gw"] = mix["generation_mw"] / 1000

    total = mix["generation_gw"].sum()

    if total > 0:
        mix["share"] = mix["generation_gw"] / total
    else:
        mix["share"] = 0.0

    mix = mix.sort_values("generation_gw", ascending=False)

    return mix, latest_time


# Sources below this share of the total are grouped into OTHER.
DEFAULT_MINIMUM_SHARE = 0.0025


@dataclass(frozen=True)
class GenerationMixView:
    """
    Current generation mix for the doughnut chart.

    ``mix`` has columns ``fuel_type``, ``generation_gw`` and ``share`` (0-1),
    largest first, with small sources grouped into ``OTHER``.
    """

    mix: pd.DataFrame
    total_gw: float
    event_time_utc: pd.Timestamp


def generation_mix_view(
    generation: pd.DataFrame,
    minimum_share: float = DEFAULT_MINIMUM_SHARE,
) -> GenerationMixView:
    """
    Build the current mix from generation data (see
    ``latest_generation_snapshot`` for accepted shapes), typically
    ``load_live_generation_mix`` output.

    Raises ValueError if there is no positive generation to show.
    """
    mix, latest_time = latest_generation_snapshot(generation)

    if mix.empty:
        raise ValueError("No generation mix available.")

    small = mix["share"] < minimum_share

    if small.any():
        other_gw = mix.loc[small, "generation_gw"].sum()

        mix = mix.loc[~small].copy()

        if other_gw > 0:
            mix = pd.concat(
                [
                    mix,
                    pd.DataFrame(
                        {
                            "fuel_type": ["OTHER"],
                            "generation_gw": [other_gw],
                        }
                    ),
                ],
                ignore_index=True,
            )

    mix = (
        mix.groupby("fuel_type", as_index=False)["generation_gw"]
        .sum()
    )

    total_gw = mix["generation_gw"].sum()

    if total_gw <= 0:
        raise ValueError("Generation mix total must be positive.")

    mix["share"] = mix["generation_gw"] / total_gw

    mix = (
        mix.sort_values("generation_gw", ascending=False)
        .reset_index(drop=True)
    )

    return GenerationMixView(
        mix=mix,
        total_gw=total_gw,
        event_time_utc=latest_time,
    )


@dataclass(frozen=True)
class GenerationChangeView:
    """
    Biggest changes in output per fuel between two snapshots.

    ``movement`` has columns ``fuel_type``, ``delta_gw`` (latest minus
    earlier), ``absolute_change`` and ``movement_strength`` (absolute change
    relative to the largest one, 0-1), largest change first.
    """

    movement: pd.DataFrame
    latest_time: pd.Timestamp
    earlier_time: pd.Timestamp


def generation_change_view(
    generation: pd.DataFrame,
    lookback_hours: int = 4,
    top_n: int = 8,
) -> GenerationChangeView:
    """
    Compare the latest snapshot with the last one at least ``lookback_hours``
    earlier, from wide generation data (``load_recent_generation`` output).

    Keeps the ``top_n`` largest movements; fuels missing at either time are
    skipped. Raises ValueError if there is not enough history or no movement
    to show.
    """
    wide = generation.copy()

    if "event_time_utc" not in wide.columns:
        wide = wide.reset_index()

    require_columns(
        wide,
        ["event_time_utc"],
        "Generation movement",
    )

    wide["event_time_utc"] = pd.to_datetime(
        wide["event_time_utc"],
        utc=True,
    )

    wide = wide.sort_values("event_time_utc")

    latest_time = wide["event_time_utc"].max()

    earlier = wide[
        wide["event_time_utc"]
        <= latest_time - pd.Timedelta(hours=lookback_hours)
    ]

    if earlier.empty:
        raise ValueError(
            "Not enough generation history "
            "for movement chart."
        )

    latest_row = wide.iloc[-1]
    earlier_row = earlier.iloc[-1]

    rows = []

    for fuel in [
        column
        for column in wide.columns
        if column != "event_time_utc"
    ]:
        latest_value = latest_row[fuel]
        earlier_value = earlier_row[fuel]

        if pd.isna(latest_value) or pd.isna(earlier_value):
            continue

        delta_gw = (float(latest_value) - float(earlier_value)) / 1000

        rows.append(
            {
                "fuel_type": fuel,
                "delta_gw": delta_gw,
                "absolute_change": abs(delta_gw),
            }
        )

    # Note: if every fuel is skipped, ``rows`` is empty and sort_values
    # raises KeyError before the ValueError below. Kept as-is for now.
    movement = (
        pd.DataFrame(rows)
        .sort_values("absolute_change", ascending=False)
        .head(top_n)
    )

    if movement.empty:
        raise ValueError("No generation movements available.")

    max_change = movement["absolute_change"].max()

    movement["movement_strength"] = (
        movement["absolute_change"] / max_change
        if max_change
        else 0
    )

    return GenerationChangeView(
        movement=movement,
        latest_time=latest_time,
        earlier_time=earlier_row["event_time_utc"],
    )
