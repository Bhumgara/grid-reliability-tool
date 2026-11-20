"""
Streamlit data loaders for the dashboard.

Loading logic lives in core.queries; this module only adds Streamlit
caching on top so a completed background refresh shows up within the TTL.
"""

import pandas as pd
import streamlit as st

from core import queries


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
    return queries.load_model_metrics()


@st.cache_data(ttl=15)
def load_latest_forecast() -> dict | None:
    return queries.load_latest_forecast()


@st.cache_data(ttl=5)
def load_refresh_status() -> dict:
    return queries.load_refresh_status()


@st.cache_data
def load_validation_predictions() -> pd.DataFrame:
    return queries.load_validation_predictions()
