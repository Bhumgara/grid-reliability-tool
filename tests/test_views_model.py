import pandas as pd
import pytest

from core.views.model import (
    find_baseline_column,
    model_vs_persistence_view,
    validation_view,
)


@pytest.fixture
def predictions():
    """Ten predictions: model is always 100 MW high, baseline 300 MW high."""
    target = [1000.0 * i for i in range(1, 11)]
    data = pd.DataFrame(
        {
            "target_time_utc": pd.date_range(
                "2026-06-01T00:00Z", periods=10, freq="h"
            ).astype(str),
            "target_drm_mw": target,
            "predicted_drm_mw": [t + 100 for t in target],
            "baseline_drm_yesterday_mw": [t + 300 for t in target],
        }
    )
    data["error_mw"] = data["predicted_drm_mw"] - data["target_drm_mw"]
    data["absolute_error_mw"] = data["error_mw"].abs()
    return data


def test_validation_view_adds_gw_columns(predictions):
    view = validation_view(predictions)

    assert set(predictions.columns) <= set(view.columns)
    assert str(view["target_time_utc"].dt.tz) == "UTC"
    assert view["actual_gw"].iloc[0] == pytest.approx(1.0)
    assert view["predicted_gw"].iloc[0] == pytest.approx(1.1)
    assert view["error_gw"].iloc[0] == pytest.approx(0.1)
    assert view["absolute_error_gw"].iloc[0] == pytest.approx(0.1)


def test_find_baseline_column_prefers_earlier_names(predictions):
    both = predictions.assign(baseline_drm_mw=0.0)

    assert find_baseline_column(both) == "baseline_drm_yesterday_mw"
    assert (
        find_baseline_column(
            both.drop(columns="baseline_drm_yesterday_mw")
        )
        == "baseline_drm_mw"
    )

    with pytest.raises(ValueError, match="baseline prediction column"):
        find_baseline_column(predictions[["target_drm_mw"]])


def test_model_vs_persistence_view(predictions):
    view = model_vs_persistence_view(predictions)

    assert view.baseline_column == "baseline_drm_yesterday_mw"
    assert view.compare.to_dict("records") == [
        {"segment": "Overall", "method": "Persistence", "mae_gw": pytest.approx(0.3)},
        {"segment": "Overall", "method": "Ridge", "mae_gw": pytest.approx(0.1)},
        {"segment": "Lowest 10% DRM", "method": "Persistence", "mae_gw": pytest.approx(0.3)},
        {"segment": "Lowest 10% DRM", "method": "Ridge", "mae_gw": pytest.approx(0.1)},
    ]
    # Padding is the 0.35 GW minimum; the lower bound never goes below zero.
    assert view.axis_min_gw == 0
    assert view.axis_max_gw == pytest.approx(0.65)


def test_model_vs_persistence_explicit_baseline(predictions):
    renamed = predictions.rename(
        columns={"baseline_drm_yesterday_mw": "my_baseline"}
    )

    view = model_vs_persistence_view(renamed, baseline_col="my_baseline")

    assert view.baseline_column == "my_baseline"


def test_model_vs_persistence_missing_columns(predictions):
    with pytest.raises(ValueError, match="requires columns"):
        model_vs_persistence_view(predictions.drop(columns="target_drm_mw"))

    with pytest.raises(ValueError, match="baseline prediction column"):
        model_vs_persistence_view(
            predictions.drop(columns="baseline_drm_yesterday_mw")
        )

    with pytest.raises(ValueError, match="requires columns"):
        model_vs_persistence_view(predictions, baseline_col="nope")
