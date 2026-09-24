"""
Incremental live-data refresh orchestration.

This module contains no Streamlit code. It:
1. checks whether locally stored source data is stale;
2. incrementally refreshes stale sources with a small overlap;
3. regenerates the latest 24-hour DRM forecast;
4. writes an atomic status file for the dashboard.

The dashboard can continue serving cached SQLite/forecast data if any
external source fails.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

import pandas as pd

from core.config import DB_PATH
from pipelines.ingest import (
    backfill_fuelhh,
    backfill_indo,
    backfill_lolpdrm,
    backfill_neso_generation_mix,
)
from pipelines.predict import run_prediction


STATUS_PATH = Path("data/processed/refresh_status.json")
FORECAST_PATH = Path("data/processed/latest_forecast.json")

STALE_AFTER = pd.Timedelta(minutes=45)
OVERLAP = pd.Timedelta(hours=2)
DEFAULT_LOOKBACK = pd.Timedelta(days=2)
MAX_LIVE_CATCHUP = pd.Timedelta(days=7)

_REFRESH_LOCK = threading.Lock()


@dataclass(frozen=True)
class SourceSpec:
    name: str
    table: str
    refresh: Callable[[str, str], None]
    required: bool = True
    fetch_ahead_minutes: int = 0


SOURCES = (
    SourceSpec(
        name="LOLPDRM",
        table="elexon_margin_lolpdrm",
        refresh=backfill_lolpdrm,
        # LOLPDRM contains short-horizon forecasts whose event time can
        # sit ahead of the forecast origin. Fetch slightly into the future
        # so the latest published horizon=1 record is available as a feature.
        fetch_ahead_minutes=120,
    ),
    SourceSpec(
        name="Demand",
        table="elexon_demand_indo",
        refresh=backfill_indo,
    ),
    SourceSpec(
        name="FUELHH",
        table="elexon_generation_fuelhh",
        refresh=backfill_fuelhh,
    ),
    SourceSpec(
        name="NESO generation mix",
        table="neso_generation_mix",
        refresh=backfill_neso_generation_mix,
        required=False,
    ),
)


def utc_now() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC")


def iso_utc(value: pd.Timestamp | datetime | None) -> str | None:
    if value is None:
        return None

    ts = pd.Timestamp(value)

    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")

    return ts.isoformat()


def api_time(value: pd.Timestamp) -> str:
    return value.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        LIMIT 1;
        """,
        (table,),
    ).fetchone()

    return row is not None


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not table_exists(conn, table):
        return set()

    rows = conn.execute(
        f'PRAGMA table_info("{table}")'
    ).fetchall()

    return {row[1] for row in rows}


def max_timestamp(
    conn: sqlite3.Connection,
    table: str,
    candidates: tuple[str, ...],
) -> pd.Timestamp | None:
    columns = table_columns(conn, table)

    column = next(
        (
            candidate
            for candidate in candidates
            if candidate in columns
        ),
        None,
    )

    if column is None:
        return None

    value = conn.execute(
        f'SELECT MAX("{column}") FROM "{table}"'
    ).fetchone()[0]

    if value is None:
        return None

    ts = pd.Timestamp(value)

    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")

    return ts


def source_state(
    spec: SourceSpec,
    now: pd.Timestamp | None = None,
) -> dict:
    now = now if now is not None else utc_now()

    if not Path(DB_PATH).exists():
        return {
            "name": spec.name,
            "required": spec.required,
            "latest_event_utc": None,
            "latest_freshness_utc": None,
            "age_minutes": None,
            "stale": True,
        }

    with sqlite3.connect(str(DB_PATH)) as conn:
        latest_event = max_timestamp(
            conn,
            spec.table,
            (
                "event_time_utc",
                "interval_start_utc",
                "start_time_utc",
            ),
        )

        latest_freshness = max_timestamp(
            conn,
            spec.table,
            (
                "published_at_utc",
                "event_time_utc",
                "interval_start_utc",
                "start_time_utc",
            ),
        )

    if latest_freshness is None:
        age_minutes = None
        stale = True
    else:
        age = max(
            now - latest_freshness,
            pd.Timedelta(0),
        )
        age_minutes = age.total_seconds() / 60
        stale = age > STALE_AFTER

    return {
        "name": spec.name,
        "required": spec.required,
        "latest_event_utc": iso_utc(latest_event),
        "latest_freshness_utc": iso_utc(latest_freshness),
        "age_minutes": (
            round(age_minutes, 1)
            if age_minutes is not None
            else None
        ),
        "stale": stale,
    }


def inspect_sources(
    now: pd.Timestamp | None = None,
) -> dict[str, dict]:
    now = now if now is not None else utc_now()

    return {
        spec.name: source_state(spec, now)
        for spec in SOURCES
    }


def forecast_generated_at() -> pd.Timestamp | None:
    if not FORECAST_PATH.exists():
        return None

    try:
        with FORECAST_PATH.open(encoding="utf-8") as file:
            payload = json.load(file)

        value = payload.get("generated_at_utc")
        if not value:
            return None

        ts = pd.Timestamp(value)

        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        else:
            ts = ts.tz_convert("UTC")

        return ts

    except (
        OSError,
        json.JSONDecodeError,
        ValueError,
        TypeError,
    ):
        return None


def forecast_is_stale(
    now: pd.Timestamp | None = None,
) -> bool:
    now = now if now is not None else utc_now()
    generated = forecast_generated_at()

    if generated is None:
        return True

    return now - generated > STALE_AFTER


def needs_refresh(
    now: pd.Timestamp | None = None,
) -> bool:
    now = now if now is not None else utc_now()
    sources = inspect_sources(now)

    required_stale = any(
        source["stale"]
        for source in sources.values()
        if source["required"]
    )

    return required_stale or forecast_is_stale(now)


def read_status() -> dict:
    if not STATUS_PATH.exists():
        return {}

    try:
        with STATUS_PATH.open(encoding="utf-8") as file:
            return json.load(file)
    except (
        OSError,
        json.JSONDecodeError,
    ):
        return {}


def write_status(payload: dict) -> None:
    STATUS_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = STATUS_PATH.with_suffix(".tmp")

    with temporary.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)

    temporary.replace(STATUS_PATH)


def refresh_window(
    source: dict,
    now: pd.Timestamp,
    fetch_ahead_minutes: int = 0,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """
    Refresh from slightly before the latest event to tolerate delayed
    publications/revisions. If the source is empty, fetch only a short
    bootstrap window rather than attempting a historical rebuild.
    """
    end = (
        now.floor("30min")
        + pd.Timedelta(
            minutes=fetch_ahead_minutes
        )
    )
    latest_raw = source.get("latest_event_utc")

    if latest_raw:
        latest = pd.Timestamp(latest_raw)

        if latest.tzinfo is None:
            latest = latest.tz_localize("UTC")
        else:
            latest = latest.tz_convert("UTC")

        # Even if a forecast-style source has events slightly ahead of now,
        # re-fetch the latest overlap so new publications/revisions arrive.
        start = min(
            latest - OVERLAP,
            end - OVERLAP,
        )
    else:
        start = end - DEFAULT_LOOKBACK

    # A live dashboard refresh is not a historical backfill job. Cap the
    # automatic catch-up window so a very old deployment cannot unexpectedly
    # launch months of API requests on startup.
    start = max(
        start,
        end - MAX_LIVE_CATCHUP,
    )

    return start, end


def refresh_live_data(force: bool = False) -> dict:
    """
    Refresh source data and regenerate the latest forecast.

    Another concurrent call returns the currently persisted status instead
    of starting a second API refresh.
    """
    acquired = _REFRESH_LOCK.acquire(blocking=False)

    if not acquired:
        status = read_status()
        return status or {
            "state": "refreshing",
            "message": "A live refresh is already running.",
        }

    started = utc_now()

    try:
        before = inspect_sources(started)
        should_refresh = force or needs_refresh(started)

        if not should_refresh:
            payload = {
                "state": "fresh",
                "message": "Local data and forecast are fresh.",
                "started_at_utc": iso_utc(started),
                "completed_at_utc": iso_utc(utc_now()),
                "sources": before,
                "prediction": {
                    "status": "current",
                    "generated_at_utc": iso_utc(
                        forecast_generated_at()
                    ),
                },
            }
            write_status(payload)
            return payload

        write_status(
            {
                "state": "refreshing",
                "message": "Refreshing source data in the background.",
                "started_at_utc": iso_utc(started),
                "sources": before,
            }
        )

        source_results = {}

        for spec in SOURCES:
            source_before = before[spec.name]
            start, end = refresh_window(
                source_before,
                started,
                fetch_ahead_minutes=(
                    spec.fetch_ahead_minutes
                ),
            )

            result = {
                **source_before,
                "refresh_from_utc": iso_utc(start),
                "refresh_to_utc": iso_utc(end),
                "refresh_status": "skipped",
                "error": None,
            }

            if force or source_before["stale"]:
                try:
                    if start < end:
                        spec.refresh(
                            api_time(start),
                            api_time(end),
                        )
                    result["refresh_status"] = "updated"
                except Exception as exc:
                    result["refresh_status"] = "error"
                    result["error"] = (
                        f"{type(exc).__name__}: {exc}"
                    )

            source_results[spec.name] = result

        prediction_result = {
            "status": "not_run",
            "generated_at_utc": None,
            "error": None,
        }

        # Try prediction even if an optional source failed. The model can
        # continue from existing cached Elexon data when available.
        try:
            forecast = run_prediction()
            prediction_result["status"] = "updated"
            prediction_result["generated_at_utc"] = forecast.get(
                "generated_at_utc"
            )
            prediction_result["forecast_origin_utc"] = forecast.get(
                "forecast_origin_utc"
            )
            prediction_result["target_time_utc"] = forecast.get(
                "target_time_utc"
            )
        except Exception as exc:
            prediction_result["status"] = "error"
            prediction_result["error"] = (
                f"{type(exc).__name__}: {exc}"
            )

        after = inspect_sources(utc_now())

        required_errors = [
            name
            for name, result in source_results.items()
            if (
                result["required"]
                and result["refresh_status"] == "error"
            )
        ]

        optional_errors = [
            name
            for name, result in source_results.items()
            if (
                not result["required"]
                and result["refresh_status"] == "error"
            )
        ]

        required_still_stale = [
            name
            for name, result in after.items()
            if result["required"] and result["stale"]
        ]

        if (
            prediction_result["status"] == "error"
            and (required_errors or required_still_stale)
        ):
            state = "failed"
        elif (
            prediction_result["status"] == "error"
            or required_errors
            or required_still_stale
        ):
            state = "degraded"
        else:
            state = "fresh"

        if state == "fresh" and optional_errors:
            message = (
                "Core live data and forecast refreshed; "
                "an optional context source is unavailable."
            )
        else:
            message = {
                "fresh": "Live data and forecast refreshed successfully.",
                "degraded": (
                    "Refresh completed but required data is still stale "
                    "or a core step failed; cached values remain available."
                ),
                "failed": (
                    "Live refresh failed; serving cached values."
                ),
            }[state]

        payload = {
            "state": state,
            "message": message,
            "started_at_utc": iso_utc(started),
            "completed_at_utc": iso_utc(utc_now()),
            "sources_before": before,
            "sources": after,
            "source_refresh": source_results,
            "prediction": prediction_result,
        }

        write_status(payload)
        return payload

    finally:
        _REFRESH_LOCK.release()


def main() -> None:
    status = refresh_live_data(force=True)
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
