import pandas as pd
import pytest

from core import queries
from core.views.forecast import drm_bridge_view, forecast_view
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
