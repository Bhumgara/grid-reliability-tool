"""
Read-only loaders for the dashboard and API.

These are the loaders from dashboard/data.py without any Streamlit
dependency. Callers add their own caching (st.cache_data in the Streamlit app,
a TTL cache in the API).

The database loaders delegate to the storage backend (``core.storage``;
SQLite today), so the SQL lives in one place. The JSON/CSV loaders read files.

Every loader accepts an optional path (``db_path`` for database queries, a
file path for the JSON/CSV loaders) so tests can point it at fixtures. When
omitted, the matching ``core.config`` path is read at call time.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from core import config
from core.storage import SQLiteStore

# Defined with the storage interface; re-exported here for existing callers.
from core.storage.base import DatabaseUnavailableError  # noqa: F401


def _store(db_path: Path | None) -> SQLiteStore:
    return SQLiteStore(db_path)


def load_recent_margin(
    days: int = 7,
    db_path: Path | None = None,
) -> pd.DataFrame:
    """Latest ``days`` of 1-hour-ahead de-rated margin, oldest first."""
    return _store(db_path).recent_margin(days)


def load_recent_demand(
    days: int = 7,
    db_path: Path | None = None,
) -> pd.DataFrame:
    """Latest ``days`` of INDO demand, oldest first."""
    return _store(db_path).recent_demand(days)


def load_recent_generation(
    days: int = 7,
    db_path: Path | None = None,
) -> pd.DataFrame:
    """
    FUELHH generation for the ``days`` before the latest settlement period.

    Returns a wide frame: one row per timestamp, one column per fuel type.
    """
    return _store(db_path).recent_generation(days)


def load_live_generation_mix(
    db_path: Path | None = None,
) -> pd.DataFrame:
    """
    Latest FUELINST snapshot combined with NESO embedded wind and solar.

    Gas types are merged into CCGT, embedded wind is added to WIND, and
    SOLAR comes entirely from NESO. NESO actuals ('A') are preferred over
    forecasts; ``embedded_data_status`` records which one was used.
    """
    return _store(db_path).live_generation_mix()


def load_live_interconnectors(
    db_path: Path | None = None,
) -> pd.DataFrame:
    """Interconnector flows (fuel types starting INT) from the latest FUELINST snapshot."""
    return _store(db_path).live_interconnectors()


def load_margin_history(
    db_path: Path | None = None,
) -> pd.Series:
    """Every non-null 1-hour-ahead de-rated margin, for percentile context."""
    return _store(db_path).margin_history()


def load_model_metrics(
    path: Path | None = None,
) -> dict:
    """Model evaluation metrics, or ``{}`` if the file does not exist yet."""
    path = path or config.METRICS_PATH

    if not path.exists():
        return {}

    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _read_json_or_none(path: Path) -> dict | None:
    """
    Read a JSON file the refresh worker may be rewriting.

    Returns None if the file is missing, unreadable or half-written.
    """
    if not path.exists():
        return None

    try:
        with path.open(encoding="utf-8") as file:
            return json.load(file)
    except (
        OSError,
        json.JSONDecodeError,
    ):
        return None


def load_latest_forecast(
    path: Path | None = None,
) -> dict | None:
    """Latest 24-hour-ahead forecast, or None if unavailable."""
    return _read_json_or_none(path or config.FORECAST_PATH)


def load_refresh_status(
    path: Path | None = None,
) -> dict:
    """Live refresh status, or ``{}`` if unavailable."""
    return _read_json_or_none(path or config.STATUS_PATH) or {}


def load_last_refresh_completed(
    path: Path | None = None,
) -> pd.Timestamp | None:
    """
    When the refresh worker last finished a check (UTC), or None if it hasn't
    yet, or the file is unreadable.
    """
    record = _read_json_or_none(path or config.LAST_REFRESH_PATH)

    if not isinstance(record, dict):
        return None

    try:
        completed = pd.Timestamp(record.get("last_refresh_completed_utc"))
    except (ValueError, TypeError):
        return None

    if completed is pd.NaT:
        return None

    if completed.tzinfo is None:
        return completed.tz_localize("UTC")
    return completed.tz_convert("UTC")


def load_validation_predictions(
    validation_path: Path | None = None,
    test_path: Path | None = None,
) -> pd.DataFrame:
    """
    Model predictions for the performance section.

    Uses validation predictions, falling back to test predictions. Returns an
    empty frame if neither exists.
    """
    validation_path = validation_path or config.VALIDATION_PATH
    test_path = test_path or config.TEST_PATH

    path = (
        validation_path
        if validation_path.exists()
        else test_path
    )

    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path)

    if "target_time_utc" in df.columns:
        df["target_time_utc"] = pd.to_datetime(
            df["target_time_utc"],
            utc=True,
        )

    return df
