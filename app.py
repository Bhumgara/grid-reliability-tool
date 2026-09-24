import streamlit as st

from dashboard.components import (
    render_demand_context,
    render_forecast_hero,
    render_generation_section,
    render_grid_context,
    render_model_performance,
    render_recent_grid_history,
)
from dashboard.data import (
    load_latest_forecast,
    load_margin_history,
    load_model_metrics,
    load_recent_demand,
    load_recent_generation,
    load_recent_margin,
    load_validation_predictions,
)
from dashboard.styles import (
    apply_styles,
)


st.set_page_config(
    page_title=(
        "UK Energy Reliability Tool"
    ),
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


# Short windows for the main dashboard.
margin = load_recent_margin(
    days=7,
)

demand = load_recent_demand(
    days=7,
)

generation = (
    load_recent_generation(
        days=7,
    )
)

# Longer demand history supports the typical-day comparison.
demand_history = (
    load_recent_demand(
        days=90,
    )
)

margin_history = (
    load_margin_history()
)

metrics = (
    load_model_metrics()
)

forecast = (
    load_latest_forecast()
)

predictions = (
    load_validation_predictions()
)


# ==================================================
# What do we expect?
# ==================================================

render_forecast_hero(
    forecast=forecast,
    margin=margin,
    margin_history=margin_history,
)


# ==================================================
# What is happening now?
# ==================================================

render_grid_context(
    margin=margin,
    demand=demand,
    generation=generation,
)


# ==================================================
# What has been happening?
# ==================================================

render_recent_grid_history(
    margin=margin,
    demand=demand,
)

render_demand_context(
    demand_history=demand_history,
)

render_generation_section(
    generation=generation,
)


# ==================================================
# How good is the model?
# ==================================================

render_model_performance(
    metrics=metrics,
    predictions=predictions,
)
