import json
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

from core.config import DB_PATH


METRICS_PATH = Path(
    "artifacts/metrics.json"
)

FORECAST_PATH = Path(
    "data/processed/latest_forecast.json"
)

VALIDATION_PATH = Path(
    "data/processed/validation_predictions.csv"
)

TEST_PATH = Path(
    "data/processed/test_predictions.csv"
)


@st.cache_data(ttl=300)
def load_recent_margin(
    days: int = 7,
) -> pd.DataFrame:
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

    with sqlite3.connect(
        str(DB_PATH)
    ) as conn:
        df = pd.read_sql_query(
            query,
            conn,
            params=(rows,),
        )

    if df.empty:
        return df

    df["event_time_utc"] = (
        pd.to_datetime(
            df["event_time_utc"],
            utc=True,
        )
    )

    return (
        df.sort_values(
            "event_time_utc"
        )
        .reset_index(
            drop=True
        )
    )


@st.cache_data(ttl=300)
def load_recent_demand(
    days: int = 7,
) -> pd.DataFrame:
    rows = days * 48

    query = """
        SELECT
            event_time_utc,
            demand_mw
        FROM elexon_demand_indo
        ORDER BY event_time_utc DESC
        LIMIT ?;
    """

    with sqlite3.connect(
        str(DB_PATH)
    ) as conn:
        df = pd.read_sql_query(
            query,
            conn,
            params=(rows,),
        )

    if df.empty:
        return df

    df["event_time_utc"] = (
        pd.to_datetime(
            df["event_time_utc"],
            utc=True,
        )
    )

    return (
        df.sort_values(
            "event_time_utc"
        )
        .reset_index(
            drop=True
        )
    )


@st.cache_data(ttl=300)
def load_recent_generation(
    days: int = 7,
) -> pd.DataFrame:
    """
    Load all FUELHH categories.

    Keeping the full mix matters for the doughnut and movement views;
    chart builders decide how to group small slices for presentation.
    """
    query = """
        SELECT
            event_time_utc,
            fuel_type,
            generation_mw
        FROM elexon_generation_fuelhh
        ORDER BY event_time_utc;
    """

    with sqlite3.connect(
        str(DB_PATH)
    ) as conn:
        df = pd.read_sql_query(
            query,
            conn,
        )

    if df.empty:
        return df

    df["event_time_utc"] = (
        pd.to_datetime(
            df["event_time_utc"],
            utc=True,
        )
    )

    latest = df[
        "event_time_utc"
    ].max()

    cutoff = (
        latest
        - pd.Timedelta(
            days=days
        )
    )

    df = df[
        df["event_time_utc"]
        >= cutoff
    ].copy()

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

    with sqlite3.connect(
        str(DB_PATH)
    ) as conn:
        df = pd.read_sql_query(
            query,
            conn,
        )

    return df[
        "derated_margin_mw"
    ]


@st.cache_data
def load_model_metrics() -> dict:
    if not METRICS_PATH.exists():
        return {}

    with METRICS_PATH.open(
        encoding="utf-8",
    ) as file:
        return json.load(
            file
        )


@st.cache_data(ttl=60)
def load_latest_forecast(
) -> dict | None:
    if not FORECAST_PATH.exists():
        return None

    with FORECAST_PATH.open(
        encoding="utf-8",
    ) as file:
        return json.load(
            file
        )


@st.cache_data
def load_validation_predictions(
) -> pd.DataFrame:
    path = (
        VALIDATION_PATH
        if VALIDATION_PATH.exists()
        else TEST_PATH
    )

    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(
        path
    )

    if (
        "target_time_utc"
        in df.columns
    ):
        df[
            "target_time_utc"
        ] = pd.to_datetime(
            df[
                "target_time_utc"
            ],
            utc=True,
        )

    return df
