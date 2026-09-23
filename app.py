import streamlit as st

from dashboard.components import (
    render_forecast_hero,
    render_grid_context,
    render_model_performance,
)
from dashboard.data import (
    load_latest_forecast,
    load_margin_history,
    load_model_metrics,
    load_recent_demand,
    load_recent_generation,
    load_recent_margin,
)
from dashboard.styles import apply_styles


st.set_page_config(
    page_title="UK Energy Reliability Tool",
    page_icon="⚡",
    layout="wide",
)


apply_styles()


st.title(
    "UK Energy Reliability Tool"
)

st.caption(
    "Forecasting Great Britain's electricity "
    "supply-demand margin 24 hours ahead"
)


margin = load_recent_margin(
    days=7,
)

demand = load_recent_demand(
    days=7,
)

generation = load_recent_generation(
    days=7,
)

margin_history = load_margin_history()

metrics = load_model_metrics()

forecast = load_latest_forecast()


latest_margin_mw = float(
    margin.iloc[-1]["derated_margin_mw"]
)


# ==================================================
# Forecast
# ==================================================

render_forecast_hero(
    forecast,
    margin_history,
    latest_margin_mw,
)


# ==================================================
# Current grid context
# ==================================================

render_grid_context(
    margin,
    demand,
)


# ==================================================
# Recent history
# ==================================================

st.markdown(
    "## Recent grid history"
)

left, right = st.columns(2)


with left:
    st.markdown(
        "### De-rated margin"
    )

    st.line_chart(
        margin.set_index(
            "event_time_utc"
        )[
            ["derated_margin_mw"]
        ],
        y_label="DRM (MW)",
    )


with right:
    st.markdown(
        "### Electricity demand"
    )

    st.line_chart(
        demand.set_index(
            "event_time_utc"
        )[
            ["demand_mw"]
        ],
        y_label="Demand (MW)",
    )


st.markdown(
    "### Generation by fuel"
)

st.line_chart(
    generation,
    y_label="Generation (MW)",
)


# ==================================================
# Model validation
# ==================================================

render_model_performance(
    metrics
)