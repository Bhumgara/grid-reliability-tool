from datetime import date

import pandas as pd
import pytest

from core import queries
from core.views.demand import (
    FULL_DAY_MIN_SLOTS,
    SETTLEMENT_COLUMNS,
    demand_settlement_view,
    typical_day_view,
)
from tests.fixtures.grid_db import build_grid_db


@pytest.fixture
def demand(grid_db):
    return queries.load_recent_demand(7, db_path=grid_db)


@pytest.fixture
def demand_90d(tmp_path):
    db = build_grid_db(tmp_path / "grid90.db", days=90)
    return queries.load_recent_demand(90, db_path=db)


# --- demand_settlement_view ---------------------------------------------------


def test_settlement_view_complete_data_has_no_estimates(demand):
    view = demand_settlement_view(demand)

    assert list(view.columns) == SETTLEMENT_COLUMNS
    assert len(view) == len(demand)
    assert not view["estimated"].any()
    assert view["demand_gw"].tolist() == pytest.approx(
        (demand["demand_mw"] / 1000).tolist()
    )


def test_settlement_view_interpolates_internal_gaps(demand):
    gappy = demand.drop(index=[10, 11, 12, 200])

    view = demand_settlement_view(gappy)

    assert len(view) == len(demand)
    assert view["estimated"].sum() == 4

    gap = view.iloc[200]
    assert gap["estimated"]
    assert pd.isna(gap["demand_mw"])
    assert gap["display_demand_mw"] == pytest.approx(
        (demand["demand_mw"].iloc[199] + demand["demand_mw"].iloc[201]) / 2
    )


def test_settlement_view_drops_leading_and_trailing_gaps(demand):
    edges = demand.copy()
    edges.loc[:3, "demand_mw"] = None
    edges.loc[len(edges) - 2:, "demand_mw"] = None

    view = demand_settlement_view(edges)

    assert len(view) == len(demand) - 6
    assert not view["estimated"].any()


def test_settlement_view_keeps_last_duplicate(demand):
    dupes = pd.concat([demand, demand.tail(1).assign(demand_mw=1.0)])

    view = demand_settlement_view(dupes)

    assert len(view) == len(demand)
    assert view["demand_mw"].iloc[-1] == 1.0


def test_settlement_view_empty_and_invalid_input(demand):
    empty = demand_settlement_view(demand.iloc[0:0])
    assert empty.empty
    assert list(empty.columns) == SETTLEMENT_COLUMNS

    with pytest.raises(ValueError, match="requires columns"):
        demand_settlement_view(demand[["event_time_utc"]])


# --- typical_day_view ---------------------------------------------------------


def test_typical_day_view(demand_90d):
    view = typical_day_view(demand_90d)

    # Fixture ends 23:30 UTC on 24 Sep = 00:30 BST on 25 Sep: two slots so far.
    assert view.current_date == date(2026, 9, 25)
    assert view.current["settlement_slot"].tolist() == [1, 2]

    assert view.latest_full_date == date(2026, 9, 24)
    assert len(view.latest_full) == 48

    typical = view.typical
    assert typical["settlement_slot"].tolist() == list(range(1, 49))
    assert (typical["q25"] <= typical["median"]).all()
    assert (typical["median"] <= typical["q75"]).all()


def test_typical_day_counts_clocks_forward_day_as_full():
    # 29 Mar 2026 (clocks go forward) has 46 local settlement slots.
    times = pd.date_range(
        "2026-03-27T00:00Z", "2026-03-29T23:30Z", freq="30min"
    )
    demand = pd.DataFrame({"event_time_utc": times, "demand_mw": 30000.0})

    view = typical_day_view(demand)

    assert view.current_date == date(2026, 3, 30)
    assert view.latest_full_date == date(2026, 3, 29)
    assert len(view.latest_full) == FULL_DAY_MIN_SLOTS == 46


def test_typical_day_falls_back_when_no_full_day(demand_90d):
    sparse = demand_90d.tail(48 * 3).iloc[::2]

    view = typical_day_view(sparse)

    assert len(view.latest_full) < FULL_DAY_MIN_SLOTS
    assert view.latest_full_date == date(2026, 9, 24)


def test_typical_day_needs_an_earlier_day(demand_90d):
    with pytest.raises(ValueError, match="at least one earlier local day"):
        typical_day_view(demand_90d.tail(2))

    with pytest.raises(ValueError, match="requires columns"):
        typical_day_view(demand_90d[["demand_mw"]])
