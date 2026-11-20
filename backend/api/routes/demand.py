"""GET /api/demand/typical-day: today's demand against a typical day."""

from __future__ import annotations

import datetime as dt

import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel

from backend.api.loaders import LoadersDep
from backend.api.models import DataResponse, EmptyState
from core.views.demand import typical_day_view

router = APIRouter()

# Days of demand history for the typical-day profile, as the dashboard.
HISTORY_DAYS = 90


class TypicalSlot(BaseModel):
    # Settlement slot 1-48, counted from UK local midnight.
    slot: int
    q25_gw: float
    median_gw: float
    q75_gw: float


class ProfilePoint(BaseModel):
    slot: int
    demand_gw: float


class TypicalDayResponse(DataResponse):
    """
    The latest local day's demand so far and the latest full day, against the
    median and interquartile range of all earlier days, by settlement slot.
    ``as_of_utc`` is the latest demand time.
    """

    current_date: dt.date
    latest_full_date: dt.date
    typical: list[TypicalSlot]
    current: list[ProfilePoint]
    latest_full: list[ProfilePoint]


def _profile(frame: pd.DataFrame) -> list[ProfilePoint]:
    return [
        ProfilePoint(slot=int(slot), demand_gw=float(value))
        for slot, value in zip(frame["settlement_slot"], frame["demand_gw"])
    ]


@router.get("/demand/typical-day", response_model=TypicalDayResponse | EmptyState)
def get_typical_day(loaders: LoadersDep) -> TypicalDayResponse | EmptyState:
    demand = loaders.load_recent_demand(HISTORY_DAYS)

    if demand.empty:
        return EmptyState(state="unavailable", message="Demand history is unavailable.")

    try:
        view = typical_day_view(demand)
    except ValueError as error:
        return EmptyState.from_error(error)

    return TypicalDayResponse(
        as_of_utc=demand["event_time_utc"].max(),
        current_date=view.current_date,
        latest_full_date=view.latest_full_date,
        typical=[
            TypicalSlot(
                slot=int(row.settlement_slot),
                q25_gw=float(row.q25),
                median_gw=float(row.median),
                q75_gw=float(row.q75),
            )
            for row in view.typical.itertuples(index=False)
        ],
        current=_profile(view.current),
        latest_full=_profile(view.latest_full),
    )
