import pandas as pd
import pytest

from core.views.model import (
    VALIDATION_COLUMNS,
    find_baseline_column,
    model_metrics_view,
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


@pytest.mark.parametrize(
    "column",
    ["target_drm_mw", "predicted_drm_mw", "baseline_drm_yesterday_mw"],
)
def test_model_vs_persistence_needs_a_complete_row(predictions, column):
    incomplete = predictions.assign(**{column: float("nan")})

    with pytest.raises(ValueError, match="at least one prediction"):
        model_vs_persistence_view(incomplete)


def test_model_vs_persistence_uses_only_complete_rows(predictions):
    partly_missing = predictions.copy()
    partly_missing.loc[1:, "predicted_drm_mw"] = float("nan")

    view = model_vs_persistence_view(partly_missing)

    assert set(view.compare["segment"]) == {"Overall", "Lowest 10% DRM"}
    assert view.compare["mae_gw"].tolist() == pytest.approx([0.3, 0.1, 0.3, 0.1])


@pytest.mark.parametrize("column", VALIDATION_COLUMNS)
def test_validation_view_missing_column_raises_value_error(predictions, column):
    with pytest.raises(ValueError, match="requires columns"):
        validation_view(predictions.drop(columns=column))


# --- model_metrics_view -------------------------------------------------------

METRICS = {
    "model": "Ridge Regression",
    "alpha": 350.0,
    "forecast_horizon_hours": 24,
    "test_start": "2026-01-01T00:00:00+00:00",
    "test_end": "2026-09-21T00:00:00+00:00",
    "test_rows": 12356,
    "model_mae_mw": 3400.0,
    "model_rmse_mw": 4300.0,
    "baseline_mae_mw": 4100.0,
    "baseline_rmse_mw": 5300.0,
    "mae_improvement_pct": 17.5,
}


def test_model_metrics_view():
    view = model_metrics_view(METRICS)

    assert view.model == "Ridge Regression"
    assert view.alpha == 350.0
    assert view.forecast_horizon_hours == 24
    assert view.model_mae_gw == pytest.approx(3.4)
    assert view.baseline_mae_gw == pytest.approx(4.1)
    assert view.mae_improvement_pct == 17.5
    assert view.model_rmse_gw == pytest.approx(4.3)
    assert view.baseline_rmse_gw == pytest.approx(5.3)
    assert view.test_start_utc == pd.Timestamp("2026-01-01T00:00Z")
    assert view.test_end_utc == pd.Timestamp("2026-09-21T00:00Z")
    assert view.test_rows == 12356


def test_model_metrics_view_optional_fields():
    view = model_metrics_view({
        "model_mae_mw": 3400.0,
        "baseline_mae_mw": 4100.0,
        "mae_improvement_pct": 17.5,
        "alpha": "high",
        "test_end": "later",
    })

    assert view.model == "Unknown model"
    assert view.alpha is None
    assert view.forecast_horizon_hours is None
    assert view.model_rmse_gw is None
    assert view.test_end_utc is None
    assert view.test_rows is None


@pytest.mark.parametrize("key", ["model_mae_mw", "baseline_mae_mw", "mae_improvement_pct"])
@pytest.mark.parametrize("value", ["missing", None, "n/a"])
def test_model_metrics_view_needs_the_headline_scores(key, value):
    metrics = dict(METRICS)
    if value == "missing":
        del metrics[key]
    else:
        metrics[key] = value

    with pytest.raises(ValueError, match="incomplete"):
        model_metrics_view(metrics)
