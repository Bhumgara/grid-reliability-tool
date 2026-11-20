"""Data for the model performance charts."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.views.common import require_columns


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
    """
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
