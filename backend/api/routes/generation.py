"""
GET /api/generation/live, /api/generation/change and /api/interconnectors/live.
"""

from __future__ import annotations

from typing import Literal

import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel

from backend.api.models import DataResponse, EmptyState, UtcDatetime
from core import queries
from core.views.common import timestamp_utc_or_none
from core.views.generation import generation_change_view, generation_mix_view
from core.views.interconnectors import interconnector_view

router = APIRouter()

# The dashboard draws every positive source as its own slice.
MIX_MINIMUM_SHARE = 0.0
# Generation change compares the latest snapshot with one this many hours
# earlier, from this many days of FUELHH data, keeping the largest movements.
CHANGE_LOOKBACK_HOURS = 4
CHANGE_HISTORY_DAYS = 7
CHANGE_TOP_N = 8


class MixSlice(BaseModel):
    fuel_type: str
    generation_gw: float
    # Share of the total, 0-1.
    share: float


class GenerationLiveResponse(DataResponse):
    """
    Latest FUELINST snapshot with NESO embedded wind and solar, largest first.
    ``as_of_utc`` is the snapshot time.
    """

    total_gw: float
    # True if the embedded wind and solar are NESO actuals, False if
    # forecasts, None if there was no NESO row for the period.
    embedded_is_actual: bool | None
    slices: list[MixSlice]


class Movement(BaseModel):
    fuel_type: str
    # Latest minus earlier output.
    delta_gw: float
    # Size relative to the largest movement, 0-1.
    movement_strength: float


class GenerationChangeResponse(DataResponse):
    """Largest changes in FUELHH output per fuel. ``as_of_utc`` is ``latest_time_utc``."""

    latest_time_utc: UtcDatetime
    earlier_time_utc: UtcDatetime
    movements: list[Movement]


class Flow(BaseModel):
    country: str
    # Positive is an import into GB, negative an export.
    flow_gw: float
    direction: Literal["Import", "Export", "Idle"]


class InterconnectorsResponse(DataResponse):
    """Current flows by country. ``as_of_utc`` is the snapshot time."""

    net_flow_gw: float
    flows: list[Flow]


@router.get("/generation/live", response_model=GenerationLiveResponse | EmptyState)
def get_generation_live() -> GenerationLiveResponse | EmptyState:
    live = queries.load_live_generation_mix()

    if live.empty:
        return EmptyState(state="unavailable", message="Live generation data is unavailable.")

    try:
        view = generation_mix_view(live, minimum_share=MIX_MINIMUM_SHARE)
    except ValueError as error:
        return EmptyState.from_error(error)

    indicator = live["embedded_data_status"].iloc[0]

    return GenerationLiveResponse(
        as_of_utc=view.event_time_utc,
        total_gw=view.total_gw,
        embedded_is_actual=None if pd.isna(indicator) else indicator == "A",
        slices=[
            MixSlice(
                fuel_type=row.fuel_type,
                generation_gw=float(row.generation_gw),
                share=float(row.share),
            )
            for row in view.mix.itertuples(index=False)
        ],
    )


@router.get("/generation/change", response_model=GenerationChangeResponse | EmptyState)
def get_generation_change() -> GenerationChangeResponse | EmptyState:
    generation = queries.load_recent_generation(CHANGE_HISTORY_DAYS)

    if generation.empty:
        return EmptyState(state="unavailable", message="Generation data is unavailable.")

    try:
        view = generation_change_view(
            generation,
            lookback_hours=CHANGE_LOOKBACK_HOURS,
            top_n=CHANGE_TOP_N,
        )
    except ValueError as error:
        return EmptyState.from_error(error)

    return GenerationChangeResponse(
        as_of_utc=view.latest_time,
        latest_time_utc=view.latest_time,
        earlier_time_utc=view.earlier_time,
        movements=[
            Movement(
                fuel_type=row.fuel_type,
                delta_gw=float(row.delta_gw),
                movement_strength=float(row.movement_strength),
            )
            for row in view.movement.itertuples(index=False)
        ],
    )


@router.get("/interconnectors/live", response_model=InterconnectorsResponse | EmptyState)
def get_interconnectors_live() -> InterconnectorsResponse | EmptyState:
    interconnectors = queries.load_live_interconnectors()

    if interconnectors.empty:
        return EmptyState(state="unavailable", message="No current interconnector data.")

    try:
        view = interconnector_view(interconnectors)
    except ValueError as error:
        return EmptyState.from_error(error)

    return InterconnectorsResponse(
        as_of_utc=timestamp_utc_or_none(interconnectors["event_time_utc"].max()),
        net_flow_gw=view.net_flow_gw,
        flows=[
            Flow(
                country=row.country,
                flow_gw=float(row.flow_gw),
                direction=row.direction,
            )
            for row in view.flows.itertuples(index=False)
        ],
    )
