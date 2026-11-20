import pandas as pd
import pytest

from core import queries
from core.views.generation import (
    generation_change_view,
    generation_mix_view,
    latest_generation_snapshot,
)
from tests.fixtures.grid_db import FIXTURE_END, FUEL_BASE_MW, FUELINST_LATEST


@pytest.fixture
def live_mix(grid_db):
    return queries.load_live_generation_mix(db_path=grid_db)


@pytest.fixture
def wide_generation(grid_db):
    return queries.load_recent_generation(7, db_path=grid_db)


# --- latest_generation_snapshot -----------------------------------------------


def test_snapshot_from_long_data(live_mix):
    mix, latest_time = latest_generation_snapshot(live_mix)

    assert latest_time == pd.Timestamp(FUELINST_LATEST)
    # Zero-output fuels (coal, oil, solar in the fixture) are dropped.
    assert not {"COAL", "OIL", "SOLAR"} & set(mix["fuel_type"])
    assert mix["generation_gw"].is_monotonic_decreasing
    assert mix["share"].sum() == pytest.approx(1.0)


def test_snapshot_from_wide_data_uses_latest_row(wide_generation):
    mix, latest_time = latest_generation_snapshot(wide_generation)

    assert latest_time == pd.Timestamp(FIXTURE_END)
    assert set(mix["fuel_type"]) == {
        fuel for fuel, mw in FUEL_BASE_MW.items() if mw > 0
    }


# --- generation_mix_view ------------------------------------------------------


def test_mix_view(live_mix):
    view = generation_mix_view(live_mix)

    assert list(view.mix.columns) == ["fuel_type", "generation_gw", "share"]
    assert view.mix["generation_gw"].is_monotonic_decreasing
    assert view.mix["share"].sum() == pytest.approx(1.0)
    assert view.total_gw == pytest.approx(view.mix["generation_gw"].sum())
    assert view.event_time_utc == pd.Timestamp(FUELINST_LATEST)


def test_mix_view_groups_small_sources_into_other(live_mix):
    view = generation_mix_view(live_mix, minimum_share=0.05)
    mix = view.mix.set_index("fuel_type")["generation_gw"]

    assert "NPSHYD" not in mix
    # Hydro (0.3 GW) merges with the existing OTHER (0.15 GW).
    assert mix["OTHER"] == pytest.approx(0.45)
    assert view.total_gw == pytest.approx(
        generation_mix_view(live_mix).total_gw
    )


def test_mix_view_rejects_empty_or_zero_data(live_mix):
    with pytest.raises(ValueError, match="No generation mix available"):
        generation_mix_view(live_mix.iloc[0:0])

    with pytest.raises(ValueError, match="No generation mix available"):
        generation_mix_view(live_mix.assign(generation_mw=0.0))


# --- generation_change_view ---------------------------------------------------


def test_change_view(wide_generation):
    view = generation_change_view(wide_generation, lookback_hours=4)

    latest = pd.Timestamp(FIXTURE_END)
    earlier = latest - pd.Timedelta(hours=4)
    assert view.latest_time == latest
    assert view.earlier_time == earlier

    movement = view.movement
    assert list(movement.columns) == [
        "fuel_type", "delta_gw", "absolute_change", "movement_strength",
    ]
    assert len(movement) == 8

    # Only gas varies in the fixture, so it is the biggest mover.
    top = movement.iloc[0]
    assert top["fuel_type"] == "CCGT"
    assert top["delta_gw"] == pytest.approx(
        (wide_generation.loc[latest, "CCGT"] - wide_generation.loc[earlier, "CCGT"])
        / 1000
    )
    assert top["movement_strength"] == 1.0


def test_change_view_top_n_and_missing_fuels(wide_generation):
    assert len(generation_change_view(wide_generation, top_n=3).movement) == 3

    missing_wind = wide_generation.copy()
    missing_wind.iloc[-1, missing_wind.columns.get_loc("WIND")] = float("nan")

    movement = generation_change_view(missing_wind, top_n=20).movement
    assert "WIND" not in set(movement["fuel_type"])


def test_change_view_needs_enough_history(wide_generation):
    with pytest.raises(ValueError, match="Not enough generation history"):
        generation_change_view(wide_generation.tail(3))


@pytest.mark.parametrize("row", [-1, -9], ids=["latest", "earlier"])
def test_change_view_rejects_snapshot_with_no_values(wide_generation, row):
    # Row -9 is the earlier snapshot: 4 hours (8 half-hours) before the latest.
    missing = wide_generation.copy()
    missing.iloc[row, :] = float("nan")

    with pytest.raises(ValueError, match="No generation movements available"):
        generation_change_view(missing, lookback_hours=4)
