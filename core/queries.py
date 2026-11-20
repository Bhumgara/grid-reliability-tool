"""
Read-only loaders for the dashboard and API.

These are the loaders from dashboard/data.py without any Streamlit
dependency. Callers add their own caching (st.cache_data in the Streamlit app,
a TTL cache in the API).

Every loader accepts an optional path (``db_path`` for database queries, a
file path for the JSON/CSV loaders) so tests can point it at fixtures. When
omitted, the matching ``core.config`` path is read at call time.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

from core import config


@contextmanager
def _connect(db_path: Path | None) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(
        str(db_path or config.DB_PATH),
        timeout=10,
    )
    try:
        yield conn
    finally:
        conn.close()


def _sorted_by_time(df: pd.DataFrame) -> pd.DataFrame:
    df["event_time_utc"] = pd.to_datetime(
        df["event_time_utc"],
        utc=True,
    )

    return (
        df.sort_values("event_time_utc")
        .reset_index(drop=True)
    )


def load_recent_margin(
    days: int = 7,
    db_path: Path | None = None,
) -> pd.DataFrame:
    """Latest ``days`` of 1-hour-ahead de-rated margin, oldest first."""
    query = """
        SELECT
            event_time_utc,
            derated_margin_mw
        FROM elexon_margin_lolpdrm
        WHERE forecast_horizon_hours = 1
          AND derated_margin_mw IS NOT NULL
        ORDER BY event_time_utc DESC
        LIMIT ?;
    """

    with _connect(db_path) as conn:
        df = pd.read_sql_query(
            query,
            conn,
            params=(days * 48,),
        )

    if df.empty:
        return df

    return _sorted_by_time(df)


def load_recent_demand(
    days: int = 7,
    db_path: Path | None = None,
) -> pd.DataFrame:
    """Latest ``days`` of INDO demand, oldest first."""
    query = """
        SELECT
            event_time_utc,
            demand_mw
        FROM elexon_demand_indo
        ORDER BY event_time_utc DESC
        LIMIT ?;
    """

    with _connect(db_path) as conn:
        df = pd.read_sql_query(
            query,
            conn,
            params=(days * 48,),
        )

    if df.empty:
        return df

    return _sorted_by_time(df)


def load_recent_generation(
    days: int = 7,
    db_path: Path | None = None,
) -> pd.DataFrame:
    """
    FUELHH generation for the ``days`` before the latest settlement period.

    Returns a wide frame: one row per timestamp, one column per fuel type.
    """
    with _connect(db_path) as conn:
        latest_raw = conn.execute(
            """
            SELECT MAX(event_time_utc)
            FROM elexon_generation_fuelhh;
            """
        ).fetchone()[0]

        if latest_raw is None:
            return pd.DataFrame()

        latest = pd.Timestamp(latest_raw)

        if latest.tzinfo is None:
            latest = latest.tz_localize("UTC")
        else:
            latest = latest.tz_convert("UTC")

        cutoff = latest - pd.Timedelta(days=days)

        df = pd.read_sql_query(
            """
            SELECT
                event_time_utc,
                fuel_type,
                generation_mw
            FROM elexon_generation_fuelhh
            WHERE event_time_utc >= ?
            ORDER BY event_time_utc;
            """,
            conn,
            params=(cutoff.isoformat(),),
        )

    if df.empty:
        return df

    df["event_time_utc"] = pd.to_datetime(
        df["event_time_utc"],
        utc=True,
    )

    return (
        df.pivot_table(
            index="event_time_utc",
            columns="fuel_type",
            values="generation_mw",
            aggfunc="sum",
        )
        .sort_index()
    )


def load_live_generation_mix(
    db_path: Path | None = None,
) -> pd.DataFrame:
    """
    Latest FUELINST snapshot combined with NESO embedded wind and solar.

    Gas types are merged into CCGT, embedded wind is added to WIND, and
    SOLAR comes entirely from NESO. NESO actuals ('A') are preferred over
    forecasts; ``embedded_data_status`` records which one was used.
    """
    with _connect(db_path) as conn:
        latest_fuelinst = pd.read_sql_query(
            """
            SELECT
                event_time_utc,
                settlement_date,
                settlement_period,
                fuel_type,
                generation_mw
            FROM elexon_generation_fuelinst
            WHERE event_time_utc = (
                SELECT MAX(event_time_utc)
                FROM elexon_generation_fuelinst
            )
            """,
            conn,
        )

        if latest_fuelinst.empty:
            return pd.DataFrame()

        settlement_date = latest_fuelinst["settlement_date"].iloc[0]
        settlement_period = int(
            latest_fuelinst["settlement_period"].iloc[0]
        )

        neso = pd.read_sql_query(
            """
            SELECT
                embedded_wind_mw,
                embedded_solar_mw,
                forecast_actual_indicator
            FROM neso_demand_update
            WHERE settlement_date = ?
            AND settlement_period = ?
            ORDER BY
                CASE
                    WHEN forecast_actual_indicator = 'A'
                    THEN 0
                    ELSE 1
                END
            LIMIT 1
            """,
            conn,
            params=(
                settlement_date,
                settlement_period,
            ),
        )

    fuelinst = (
        latest_fuelinst
        .set_index("fuel_type")["generation_mw"]
        .to_dict()
    )

    if neso.empty:
        neso_indicator = None
        embedded_wind = 0.0
        embedded_solar = 0.0
    else:
        neso_indicator = neso["forecast_actual_indicator"].iloc[0]
        embedded_wind = float(
            neso["embedded_wind_mw"].fillna(0.0).iloc[0]
        )
        embedded_solar = float(
            neso["embedded_solar_mw"].fillna(0.0).iloc[0]
        )

    generation_mix = {
        "CCGT": (
            fuelinst.get("CCGT", 0.0)
            + fuelinst.get("OCGT", 0.0)
        ),
        "COAL": fuelinst.get("COAL", 0.0),
        "OIL": fuelinst.get("OIL", 0.0),
        "NUCLEAR": fuelinst.get("NUCLEAR", 0.0),
        "BIOMASS": fuelinst.get("BIOMASS", 0.0),
        "NPSHYD": fuelinst.get("NPSHYD", 0.0),
        "OTHER": fuelinst.get("OTHER", 0.0),
        "WIND": (
            fuelinst.get("WIND", 0.0)
            + embedded_wind
        ),
        "SOLAR": embedded_solar,
    }

    event_time = latest_fuelinst["event_time_utc"].iloc[0]

    return pd.DataFrame(
        [
            {
                "event_time_utc": event_time,
                "fuel_type": fuel,
                "generation_mw": mw,
                "embedded_data_status": neso_indicator,
            }
            for fuel, mw in generation_mix.items()
        ]
    )


def load_live_interconnectors(
    db_path: Path | None = None,
) -> pd.DataFrame:
    """Interconnector flows (fuel types starting INT) from the latest FUELINST snapshot."""
    with _connect(db_path) as conn:
        return pd.read_sql_query(
            """
            SELECT
                event_time_utc,
                fuel_type,
                generation_mw
            FROM elexon_generation_fuelinst
            WHERE event_time_utc = (
                SELECT MAX(event_time_utc)
                FROM elexon_generation_fuelinst
            )
            AND fuel_type LIKE 'INT%'
            ORDER BY fuel_type
            """,
            conn,
        )


def load_margin_history(
    db_path: Path | None = None,
) -> pd.Series:
    """Every non-null 1-hour-ahead de-rated margin, for percentile context."""
    query = """
        SELECT derated_margin_mw
        FROM elexon_margin_lolpdrm
        WHERE forecast_horizon_hours = 1
          AND derated_margin_mw IS NOT NULL;
    """

    with _connect(db_path) as conn:
        df = pd.read_sql_query(
            query,
            conn,
        )

    return df["derated_margin_mw"]


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
