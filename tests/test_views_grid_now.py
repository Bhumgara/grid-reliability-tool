import pandas as pd
import pytest

from core import queries
from core.views.grid_now import STALE_AFTER, grid_now_view
from tests.fixtures.grid_db import FIXTURE_END


def _load(db, days=7):
    return (
        queries.load_recent_margin(days, db_path=db),
        queries.load_recent_demand(days, db_path=db),
        queries.load_recent_generation(days, db_path=db),
    )


def test_grid_now_view(grid_db):
    margin, demand, generation = _load(grid_db)

    view = grid_now_view(margin, demand, generation)

    # Same numbers the dashboard's render_grid_context computes.
    latest_generation = generation.iloc[-1]
    expected_generation = latest_generation[latest_generation > 0].sum() / 1000

    assert view.drm_gw == pytest.approx(margin.iloc[-1]["derated_margin_mw"] / 1000)
    assert view.demand_gw == pytest.approx(demand.iloc[-1]["demand_mw"] / 1000)
    assert view.tracked_generation_gw == pytest.approx(expected_generation)
    assert view.drm_time_utc == pd.Timestamp(FIXTURE_END)
    assert view.demand_time_utc == pd.Timestamp(FIXTURE_END)
    assert view.generation_time_utc == pd.Timestamp(FIXTURE_END)
    assert view.stale_after_utc == pd.Timestamp(FIXTURE_END) + STALE_AFTER
    assert STALE_AFTER == pd.Timedelta(minutes=90)


def test_generation_ignores_zero_negative_and_missing_fuels():
    margin = pd.DataFrame({
        "event_time_utc": pd.to_datetime(["2026-11-20T10:00Z"]),
        "derated_margin_mw": [5000.0],
    })
    demand = pd.DataFrame({
        "event_time_utc": pd.to_datetime(["2026-11-20T10:00Z"]),
        "demand_mw": [30000.0],
    })
    generation = pd.DataFrame(
        {"CCGT": [10000.0], "COAL": [0.0], "PS": [-500.0], "WIND": [float("nan")]},
        index=pd.to_datetime(["2026-11-20T10:00Z"]),
    )

    view = grid_now_view(margin, demand, generation)

    assert view.tracked_generation_gw == pytest.approx(10.0)


def test_no_generation_gives_none(grid_db):
    margin, demand, _ = _load(grid_db)

    view = grid_now_view(margin, demand, pd.DataFrame())

    assert view.tracked_generation_gw is None
    assert view.generation_time_utc is None


def test_demand_uses_latest_non_missing_value(grid_db):
    margin, demand, generation = _load(grid_db)
    demand.loc[demand.index[-1], "demand_mw"] = None

    view = grid_now_view(margin, demand, generation)

    assert view.demand_gw == pytest.approx(demand.iloc[-2]["demand_mw"] / 1000)
    assert view.demand_time_utc == demand.iloc[-2]["event_time_utc"]


def test_needs_margin(grid_db, empty_grid_db):
    _, demand, generation = _load(grid_db)
    margin, _, _ = _load(empty_grid_db)

    with pytest.raises(ValueError, match="margin"):
        grid_now_view(margin, demand, generation)


@pytest.mark.parametrize(
    "demand",
    [
        pd.DataFrame(),
        pd.DataFrame({"event_time_utc": pd.to_datetime(["2026-11-20T10:00Z"]), "demand_mw": [None]}),
    ],
    ids=["empty", "all-missing"],
)
def test_needs_a_demand_value(grid_db, demand):
    margin, _, generation = _load(grid_db)

    with pytest.raises(ValueError, match="demand"):
        grid_now_view(margin, demand, generation)
