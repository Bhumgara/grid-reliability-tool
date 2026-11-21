"""Live refresh status, parsed from the file pipelines.refresh writes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from core.views.common import timestamp_utc_or_none

RefreshState = Literal[
    # No status file yet: the refresh worker has not finished a first check.
    "starting",
    "fresh",
    "refreshing",
    "degraded",
    "failed",
    # A state this code doesn't recognise.
    "unknown",
]

_KNOWN_STATES = {"fresh", "refreshing", "degraded", "failed"}

STARTING_MESSAGE = (
    "Live refresh worker is starting; "
    "showing cached data until the first check completes."
)


@dataclass(frozen=True)
class SourceStatus:
    """Freshness of one source table, from the status file's ``sources``."""

    name: str
    required: bool
    latest_event_utc: pd.Timestamp | None
    age_minutes: float | None
    stale: bool


@dataclass(frozen=True)
class RefreshStatusView:
    state: RefreshState
    message: str
    started_at_utc: pd.Timestamp | None
    completed_at_utc: pd.Timestamp | None
    forecast_generated_at_utc: pd.Timestamp | None
    sources: tuple[SourceStatus, ...]
    # "<source>: <error>" lines for failed refresh steps, as the dashboard shows.
    errors: tuple[str, ...]


def _float_or_none(raw) -> float | None:
    try:
        return None if raw is None else float(raw)
    except (ValueError, TypeError):
        return None


def _sources(raw) -> tuple[SourceStatus, ...]:
    if not isinstance(raw, dict):
        return ()

    return tuple(
        SourceStatus(
            name=str(details.get("name") or key),
            required=bool(details.get("required", False)),
            latest_event_utc=timestamp_utc_or_none(details.get("latest_event_utc")),
            age_minutes=_float_or_none(details.get("age_minutes")),
            stale=bool(details.get("stale", True)),
        )
        for key, details in raw.items()
        if isinstance(details, dict)
    )


def _errors(status: dict) -> tuple[str, ...]:
    errors = []

    source_refresh = status.get("source_refresh")
    if isinstance(source_refresh, dict):
        for name, result in source_refresh.items():
            if isinstance(result, dict) and result.get("error"):
                errors.append(f"{name}: {result['error']}")

    prediction = status.get("prediction")
    if isinstance(prediction, dict) and prediction.get("error"):
        errors.append(f"Prediction: {prediction['error']}")

    return tuple(errors)


def refresh_status_view(status: dict) -> RefreshStatusView:
    """
    Build the status view from ``load_refresh_status`` output.

    An empty dict (no status file yet) gives state ``"starting"``. Malformed
    fields are treated as missing, because the worker may rewrite the file at
    any time.
    """
    if not status:
        return RefreshStatusView(
            state="starting",
            message=STARTING_MESSAGE,
            started_at_utc=None,
            completed_at_utc=None,
            forecast_generated_at_utc=None,
            sources=(),
            errors=(),
        )

    raw_state = status.get("state")
    state = raw_state if raw_state in _KNOWN_STATES else "unknown"

    prediction = status.get("prediction")
    generated = (
        prediction.get("generated_at_utc")
        if isinstance(prediction, dict)
        else None
    )

    return RefreshStatusView(
        state=state,
        message=str(status.get("message") or ""),
        started_at_utc=timestamp_utc_or_none(status.get("started_at_utc")),
        completed_at_utc=timestamp_utc_or_none(status.get("completed_at_utc")),
        forecast_generated_at_utc=timestamp_utc_or_none(generated),
        sources=_sources(status.get("sources")),
        errors=_errors(status),
    )
