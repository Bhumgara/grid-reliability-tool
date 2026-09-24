import json
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

from core.config import DB_PATH


METRICS_PATH = Path("artifacts/metrics.json")
FORECAST_PATH = Path("data/processed/latest_forecast.json")
STATUS_PATH = Path("data/processed/refresh_status.json")
VALIDATION_PATH = Path("data/processed/validation_predictions.csv")
TEST_PATH = Path("data/processed/test_predictions.csv")

LIVE_CACHE_TTL = 45


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(
        str(DB_PATH),
        timeout=10,
    )


@st.cache_data(ttl=LIVE_CACHE_TTL)
def load_recent_margin(days: int = 7) -> pd.DataFrame:
    rows = days * 48

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

    with _connect() as conn:
        df = pd.read_sql_query(
            query,
            conn,
            params=(rows,),
        )

    if df.empty:
        return df

    df["event_time_utc"] = pd.to_datetime(
        df["event_time_utc"],
        utc=True,
    )

    return (
        df.sort_values("event_time_utc")
        .reset_index(drop=True)
    )


@st.cache_data(ttl=LIVE_CACHE_TTL)
def load_recent_demand(days: int = 7) -> pd.DataFrame:
    rows = days * 48

    query = """
        SELECT
            event_time_utc,
            demand_mw
        FROM elexon_demand_indo
        ORDER BY event_time_utc DESC
        LIMIT ?;
    """

    with _connect() as conn:
        df = pd.read_sql_query(
            query,
            conn,
            params=(rows,),
        )

    if df.empty:
        return df

    df["event_time_utc"] = pd.to_datetime(
        df["event_time_utc"],
        utc=True,
    )

    return (
        df.sort_values("event_time_utc")
        .reset_index(drop=True)
    )


@st.cache_data(ttl=LIVE_CACHE_TTL)
def load_recent_generation(days: int = 7) -> pd.DataFrame:
    """
    Load all FUELHH categories only for the requested recent window.
    """
    with _connect() as conn:
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


@st.cache_data
def load_margin_history() -> pd.Series:
    query = """
        SELECT derated_margin_mw
        FROM elexon_margin_lolpdrm
        WHERE forecast_horizon_hours = 1
          AND derated_margin_mw IS NOT NULL;
    """

    with _connect() as conn:
        df = pd.read_sql_query(
            query,
            conn,
        )

    return df["derated_margin_mw"]


@st.cache_data
def load_model_metrics() -> dict:
    if not METRICS_PATH.exists():
        return {}

    with METRICS_PATH.open(encoding="utf-8") as file:
        return json.load(file)


@st.cache_data(ttl=15)
def load_latest_forecast() -> dict | None:
    if not FORECAST_PATH.exists():
        return None

    try:
        with FORECAST_PATH.open(encoding="utf-8") as file:
            return json.load(file)
    except (
        OSError,
        json.JSONDecodeError,
    ):
        return None


@st.cache_data(ttl=5)
def load_refresh_status() -> dict:
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


@st.cache_data
def load_validation_predictions() -> pd.DataFrame:
    path = (
        VALIDATION_PATH
        if VALIDATION_PATH.exists()
        else TEST_PATH
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
