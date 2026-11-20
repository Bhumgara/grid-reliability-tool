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
