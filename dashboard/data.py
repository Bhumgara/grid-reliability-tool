"""
Streamlit data loaders for the dashboard.

Database queries live in core.queries; this module only adds Streamlit
caching on top so a completed background refresh shows up within the TTL.
"""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from core import queries


METRICS_PATH = Path("artifacts/metrics.json")
FORECAST_PATH = Path("data/processed/latest_forecast.json")
STATUS_PATH = Path("data/processed/refresh_status.json")
VALIDATION_PATH = Path("data/processed/validation_predictions.csv")
TEST_PATH = Path("data/processed/test_predictions.csv")

LIVE_CACHE_TTL = 45


@st.cache_data(ttl=LIVE_CACHE_TTL)
def load_recent_margin(days: int = 7) -> pd.DataFrame:
    return queries.load_recent_margin(days)


@st.cache_data(ttl=LIVE_CACHE_TTL)
def load_recent_demand(days: int = 7) -> pd.DataFrame:
    return queries.load_recent_demand(days)


@st.cache_data(ttl=LIVE_CACHE_TTL)
def load_recent_generation(days: int = 7) -> pd.DataFrame:
    return queries.load_recent_generation(days)


@st.cache_data(ttl=LIVE_CACHE_TTL)
def load_live_generation_mix() -> pd.DataFrame:
    return queries.load_live_generation_mix()


@st.cache_data(ttl=LIVE_CACHE_TTL)
def load_live_interconnectors() -> pd.DataFrame:
    return queries.load_live_interconnectors()


@st.cache_data
def load_margin_history() -> pd.Series:
    return queries.load_margin_history()


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
