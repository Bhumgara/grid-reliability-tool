"""Data for the model performance charts."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.views.common import require_columns, timestamp_utc_or_none


VALIDATION_COLUMNS = [
    "target_time_utc",
    "target_drm_mw",
    "predicted_drm_mw",
    "error_mw",
    "absolute_error_mw",
]


@dataclass(frozen=True)
class ModelMetricsView:
    """Final holdout scores from ``artifacts/metrics.json``, in GW."""

    model: str
    alpha: float | None
    forecast_horizon_hours: int | None
    model_mae_gw: float
    baseline_mae_gw: float
    mae_improvement_pct: float
    model_rmse_gw: float | None
    baseline_rmse_gw: float | None
    test_start_utc: pd.Timestamp | None
    test_end_utc: pd.Timestamp | None
    test_rows: int | None


def _optional_number(metrics: dict, key: str, kind=float):
    try:
        return kind(metrics[key])
    except (KeyError, TypeError, ValueError):
        return None


def model_metrics_view(
    metrics: dict,
) -> ModelMetricsView:
    """
    Build the metrics view from ``load_model_metrics`` output.

    Raises ValueError if the three scores the dashboard shows
    (``model_mae_mw``, ``baseline_mae_mw``, ``mae_improvement_pct``) are
    missing or not numbers. Other fields are optional.
    """
    try:
        model_mae = float(metrics["model_mae_mw"])
        baseline_mae = float(metrics["baseline_mae_mw"])
        improvement = float(metrics["mae_improvement_pct"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("The saved model metrics are incomplete.") from error

    model_rmse = _optional_number(metrics, "model_rmse_mw")
    baseline_rmse = _optional_number(metrics, "baseline_rmse_mw")

    return ModelMetricsView(
        model=str(metrics.get("model") or "Unknown model"),
        alpha=_optional_number(metrics, "alpha"),
        forecast_horizon_hours=_optional_number(metrics, "forecast_horizon_hours", int),
        model_mae_gw=model_mae / 1000,
        baseline_mae_gw=baseline_mae / 1000,
        mae_improvement_pct=improvement,
        model_rmse_gw=model_rmse / 1000 if model_rmse is not None else None,
        baseline_rmse_gw=baseline_rmse / 1000 if baseline_rmse is not None else None,
        test_start_utc=timestamp_utc_or_none(metrics.get("test_start")),
        test_end_utc=timestamp_utc_or_none(metrics.get("test_end")),
        test_rows=_optional_number(metrics, "test_rows", int),
    )


def validation_view(
    predictions: pd.DataFrame,
) -> pd.DataFrame:
    """
    Prediction results with GW columns added for charting.

    Expects ``load_validation_predictions`` output: ``target_time_utc``,
    ``target_drm_mw``, ``predicted_drm_mw``, ``error_mw`` and
    ``absolute_error_mw``. Returns a copy with ``target_time_utc`` parsed as
    UTC and ``actual_gw``, ``predicted_gw``, ``error_gw`` and
    ``absolute_error_gw`` added; other columns are kept.

    Raises ValueError if any expected column is missing.
    """
    require_columns(
        predictions,
        VALIDATION_COLUMNS,
        "Validation predictions",
    )

    data = predictions.copy()
    data["target_time_utc"] = pd.to_datetime(data["target_time_utc"], utc=True)
    data["actual_gw"] = data["target_drm_mw"] / 1000
    data["predicted_gw"] = data["predicted_drm_mw"] / 1000
    data["error_gw"] = data["error_mw"] / 1000
    data["absolute_error_gw"] = data["absolute_error_mw"] / 1000
    return data


# Column names the persistence baseline has used, in order of preference.
BASELINE_COLUMNS = [
    "baseline_drm_yesterday_mw",
    "baseline_prediction_mw",
    "persistence_drm_mw",
    "baseline_drm_mw",
]


def find_baseline_column(
    predictions: pd.DataFrame,
) -> str:
    """First of ``BASELINE_COLUMNS`` present in ``predictions``."""
    for column in BASELINE_COLUMNS:
        if column in predictions.columns:
            return column

    raise ValueError(
        "Model-vs-persistence chart needs a "
        "baseline prediction column. Expected "
        f"one of: {BASELINE_COLUMNS}"
    )


# Fraction of the MAE range (and minimum, in GW) added above and below so
# the gap between methods is legible without starting the axis at zero.
_MAE_PADDING_FRACTION = 0.35
_MAE_MIN_PADDING_GW = 0.35

MODEL_LABEL = "Ridge"
BASELINE_LABEL = "Persistence"
TIGHT_SEGMENT_QUANTILE = 0.10


@dataclass(frozen=True)
class ModelComparisonView:
    """
    Mean absolute error of the model against the persistence baseline.

    ``compare`` has columns ``segment`` (``Overall`` and
    ``Lowest 10% DRM``), ``method`` (``Persistence`` or ``Ridge``) and
    ``mae_gw``. ``axis_min_gw`` / ``axis_max_gw`` give a padded range
    (never below zero).
    """

    compare: pd.DataFrame
    axis_min_gw: float
    axis_max_gw: float
    baseline_column: str


def model_vs_persistence_view(
    predictions: pd.DataFrame,
    baseline_col: str | None = None,
) -> ModelComparisonView:
    """
    Compare model and baseline errors overall and on the tightest 10% of
    actual margins.

    ``baseline_col`` defaults to the first of ``BASELINE_COLUMNS`` found.
    Raises ValueError if required columns are missing or no row has all
    three values.
    """
    require_columns(
        predictions,
        ["target_drm_mw", "predicted_drm_mw"],
        "Model-vs-persistence",
    )

    if baseline_col is None:
        baseline_col = find_baseline_column(predictions)

    require_columns(
        predictions,
        [baseline_col],
        "Model-vs-persistence",
    )

    data = predictions[
        ["target_drm_mw", "predicted_drm_mw", baseline_col]
    ].dropna().copy()

    data["model_abs_error_mw"] = (
        data["predicted_drm_mw"] - data["target_drm_mw"]
    ).abs()

    data["baseline_abs_error_mw"] = (
        data[baseline_col] - data["target_drm_mw"]
    ).abs()

    threshold = data["target_drm_mw"].quantile(TIGHT_SEGMENT_QUANTILE)

    rows = []

    for label, segment in [
        ("Overall", data),
        ("Lowest 10% DRM", data[data["target_drm_mw"] <= threshold]),
    ]:
        if segment.empty:
            continue

        rows.extend(
            [
                {
                    "segment": label,
                    "method": BASELINE_LABEL,
                    "mae_gw": segment["baseline_abs_error_mw"].mean() / 1000,
                },
                {
                    "segment": label,
                    "method": MODEL_LABEL,
                    "mae_gw": segment["model_abs_error_mw"].mean() / 1000,
                },
            ]
        )

    if not rows:
        raise ValueError(
            "Model-vs-persistence needs at least one prediction "
            "with actual, model and baseline values."
        )

    compare = pd.DataFrame(rows)

    minimum = float(compare["mae_gw"].min())
    maximum = float(compare["mae_gw"].max())

    padding = max(
        (maximum - minimum) * _MAE_PADDING_FRACTION,
        _MAE_MIN_PADDING_GW,
    )

    return ModelComparisonView(
        compare=compare,
        axis_min_gw=max(0, minimum - padding),
        axis_max_gw=maximum + padding,
        baseline_column=baseline_col,
    )
