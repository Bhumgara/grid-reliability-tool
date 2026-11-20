"""GET /api/model/metrics and /api/model/validation: how good the model is."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from backend.api.models import DataResponse, EmptyState, UtcDatetime
from core import queries
from core.views.model import (
    model_metrics_view,
    model_vs_persistence_view,
    validation_view,
)

router = APIRouter()


class ModelMetricsResponse(DataResponse):
    """Final holdout scores. ``as_of_utc`` is the end of the test period."""

    model: str
    alpha: float | None
    forecast_horizon_hours: int | None
    model_mae_gw: float
    baseline_mae_gw: float
    mae_improvement_pct: float
    model_rmse_gw: float | None
    baseline_rmse_gw: float | None
    test_start_utc: UtcDatetime | None
    test_end_utc: UtcDatetime | None
    test_rows: int | None


class ValidationPoint(BaseModel):
    time_utc: UtcDatetime
    actual_gw: float
    predicted_gw: float
    # Predicted minus actual: positive means the model was too high.
    error_gw: float


class MaeBar(BaseModel):
    segment: Literal["Overall", "Lowest 10% DRM"]
    method: Literal["Persistence", "Ridge"]
    mae_gw: float


class ModelComparison(BaseModel):
    bars: list[MaeBar]
    # Padded axis range (never below zero), so the gap is legible.
    axis_min_gw: float
    axis_max_gw: float


class ModelValidationResponse(DataResponse):
    """
    Saved predictions against actuals, oldest first, and the model against
    the persistence baseline. ``as_of_utc`` is the last prediction target.

    ``comparison`` is None when it can't be built (e.g. no baseline column);
    ``comparison_message`` then says why, and the points are still shown.
    """

    points: list[ValidationPoint]
    comparison: ModelComparison | None
    comparison_message: str | None


@router.get("/model/metrics", response_model=ModelMetricsResponse | EmptyState)
def get_model_metrics() -> ModelMetricsResponse | EmptyState:
    metrics = queries.load_model_metrics()

    if not metrics:
        return EmptyState(state="unavailable", message="Final model metrics are unavailable.")

    try:
        view = model_metrics_view(metrics)
    except ValueError as error:
        return EmptyState.from_error(error)

    return ModelMetricsResponse(
        as_of_utc=view.test_end_utc,
        model=view.model,
        alpha=view.alpha,
        forecast_horizon_hours=view.forecast_horizon_hours,
        model_mae_gw=view.model_mae_gw,
        baseline_mae_gw=view.baseline_mae_gw,
        mae_improvement_pct=view.mae_improvement_pct,
        model_rmse_gw=view.model_rmse_gw,
        baseline_rmse_gw=view.baseline_rmse_gw,
        test_start_utc=view.test_start_utc,
        test_end_utc=view.test_end_utc,
        test_rows=view.test_rows,
    )


@router.get("/model/validation", response_model=ModelValidationResponse | EmptyState)
def get_model_validation() -> ModelValidationResponse | EmptyState:
    predictions = queries.load_validation_predictions()

    if predictions.empty:
        return EmptyState(state="unavailable", message="Validation predictions are unavailable.")

    try:
        data = validation_view(predictions)
    except ValueError as error:
        return EmptyState.from_error(error)

    # JSON has no NaN; rows missing any plotted value are left out.
    data = (
        data.dropna(subset=["target_time_utc", "actual_gw", "predicted_gw", "error_gw"])
        .sort_values("target_time_utc")
    )

    if data.empty:
        return EmptyState(
            state="insufficient",
            message="No validation prediction has both an actual and a predicted value.",
        )

    points = [
        ValidationPoint(
            time_utc=row.target_time_utc,
            actual_gw=float(row.actual_gw),
            predicted_gw=float(row.predicted_gw),
            error_gw=float(row.error_gw),
        )
        for row in data.itertuples(index=False)
    ]

    try:
        comparison_view = model_vs_persistence_view(predictions)
    except ValueError as error:
        comparison = None
        comparison_message = str(error)
    else:
        comparison = ModelComparison(
            bars=[
                MaeBar(segment=row.segment, method=row.method, mae_gw=float(row.mae_gw))
                for row in comparison_view.compare.itertuples(index=False)
            ],
            axis_min_gw=comparison_view.axis_min_gw,
            axis_max_gw=comparison_view.axis_max_gw,
        )
        comparison_message = None

    return ModelValidationResponse(
        as_of_utc=points[-1].time_utc,
        points=points,
        comparison=comparison,
        comparison_message=comparison_message,
    )
