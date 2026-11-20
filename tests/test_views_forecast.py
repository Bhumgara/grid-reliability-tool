import pandas as pd
import pytest

from core import queries
from core.margin import calculate_margin_percentile, describe_margin_percentile
from core.views.forecast import drm_bridge_view, forecast_hero_view, forecast_view
from tests.fixtures.grid_db import FIXTURE_END

FORECAST = {
    "target_time_utc": (FIXTURE_END + pd.Timedelta(hours=24)).isoformat(),
    "predicted_drm_mw": 4200.0,
    "latest_drm_mw": 3600.0,
}


def test_forecast_view(grid_db):
    margin = queries.load_recent_margin(7, db_path=grid_db)

    view = forecast_view(margin, FORECAST)

    assert list(view.history.columns) == [
        "event_time_utc", "derated_margin_mw", "drm_gw",
    ]
    assert len(view.history) == len(margin)
    assert view.history["drm_gw"].tolist() == pytest.approx(
        (margin["derated_margin_mw"] / 1000).tolist()
    )
    assert view.target_time_utc == pd.Timestamp(FIXTURE_END) + pd.Timedelta(hours=24)
    assert view.predicted_drm_gw == pytest.approx(4.2)
    assert view.latest_drm_gw == pytest.approx(3.6)


@pytest.mark.parametrize(
    ("current_mw", "predicted_mw", "direction", "axis"),
    [
        # Small change: minimum padding of 0.65 GW applies.
        (3600.0, 4200.0, "up", (2.95, 4.85)),
        (5600.0, 4200.0, "down", (3.55, 6.25)),
        (3600.0, 3600.0, "flat", (2.95, 4.25)),
        # Large change: padding is 30% of the span.
        (1000.0, 12000.0, "up", (-2.3, 15.3)),
    ],
)
def test_drm_bridge_view(current_mw, predicted_mw, direction, axis):
    view = drm_bridge_view({"predicted_drm_mw": predicted_mw}, current_mw)

    assert view.current_drm_gw == pytest.approx(current_mw / 1000)
    assert view.predicted_drm_gw == pytest.approx(predicted_mw / 1000)
    assert view.change_gw == pytest.approx((predicted_mw - current_mw) / 1000)
    assert view.direction == direction
    assert (view.axis_min_gw, view.axis_max_gw) == pytest.approx(axis)


HERO_FORECAST = {
    **FORECAST,
    "forecast_origin_utc": FIXTURE_END.isoformat(),
    "generated_at_utc": "2026-09-25T00:05:00+00:00",
}


def test_forecast_hero_view(grid_db):
    margin = queries.load_recent_margin(7, db_path=grid_db)
    history = queries.load_margin_history(db_path=grid_db)

    view = forecast_hero_view(HERO_FORECAST, margin, history)

    # Same numbers the dashboard's render_forecast_hero computes.
    latest_mw = margin.iloc[-1]["derated_margin_mw"]
    expected_percentile = calculate_margin_percentile(4200.0, history)

    assert view.target_time_utc == pd.Timestamp(FIXTURE_END) + pd.Timedelta(hours=24)
    assert view.forecast_origin_utc == pd.Timestamp(FIXTURE_END)
    assert view.generated_at_utc == pd.Timestamp("2026-09-25T00:05:00Z")
    assert view.predicted_drm_gw == pytest.approx(4.2)
    assert view.latest_drm_gw == pytest.approx(latest_mw / 1000)
    assert view.latest_time_utc == pd.Timestamp(FIXTURE_END)
    assert view.percentile == pytest.approx(expected_percentile)
    assert view.percentile_description == describe_margin_percentile(expected_percentile)
    assert view.bridge == drm_bridge_view(HERO_FORECAST, latest_mw)


def test_forecast_hero_view_takes_naive_times_as_utc(grid_db):
    margin = queries.load_recent_margin(7, db_path=grid_db)
    forecast = {**FORECAST, "target_time_utc": "2026-09-25T23:30:00"}

    view = forecast_hero_view(forecast, margin, pd.Series(dtype=float))

    assert view.target_time_utc == pd.Timestamp("2026-09-25T23:30:00Z")
    # No history: the percentile falls back to the middle.
    assert view.percentile == 50.0


def test_forecast_hero_view_ignores_bad_optional_times(grid_db):
    margin = queries.load_recent_margin(7, db_path=grid_db)
    forecast = {**FORECAST, "generated_at_utc": "not a time", "forecast_origin_utc": None}

    view = forecast_hero_view(forecast, margin, pd.Series(dtype=float))

    assert view.generated_at_utc is None
    assert view.forecast_origin_utc is None


def test_forecast_hero_view_needs_recent_margin(empty_grid_db):
    margin = queries.load_recent_margin(7, db_path=empty_grid_db)

    with pytest.raises(ValueError, match="No recent de-rated margin"):
        forecast_hero_view(FORECAST, margin, pd.Series(dtype=float))


@pytest.mark.parametrize(
    "forecast",
    [
        {"predicted_drm_mw": 4200.0},
        {"target_time_utc": FORECAST["target_time_utc"]},
        {**FORECAST, "target_time_utc": "soon"},
        {**FORECAST, "predicted_drm_mw": "lots"},
        {**FORECAST, "predicted_drm_mw": None},
    ],
    ids=["no-target", "no-prediction", "bad-target", "bad-prediction", "null-prediction"],
)
def test_forecast_hero_view_rejects_incomplete_forecast(grid_db, forecast):
    margin = queries.load_recent_margin(7, db_path=grid_db)

    with pytest.raises(ValueError, match="incomplete"):
        forecast_hero_view(forecast, margin, pd.Series(dtype=float))
