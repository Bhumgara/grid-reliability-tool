import altair as alt
import pandas as pd
import streamlit as st


def calculate_margin_percentile(
    predicted_drm_mw: float,
    history: pd.Series,
) -> float:
    if history.empty:
        return 50.0

    percentile = (
        (history < predicted_drm_mw)
        .mean()
        * 100
    )

    return float(percentile)


def describe_margin_percentile(
    percentile: float,
) -> str:
    if percentile <= 10:
        return "Historically tight"

    if percentile <= 25:
        return "Below typical"

    if percentile <= 75:
        return "Typical"

    return "High margin"


def render_forecast_hero(
    forecast: dict | None,
    margin: pd.DataFrame,
    margin_history: pd.Series,
) -> None:
    st.markdown(
        "## 24-hour-ahead forecast"
    )

    if forecast is None:
        st.info(
            "Forecast generation is not connected yet."
        )
        return

    predicted_drm_mw = float(
        forecast["predicted_drm_mw"]
    )

    forecast_origin = pd.Timestamp(
        forecast["forecast_origin_utc"]
    )

    target_time = pd.Timestamp(
        forecast["target_time_utc"]
    )

    if forecast_origin.tzinfo is None:
        forecast_origin = (
            forecast_origin.tz_localize("UTC")
        )

    if target_time.tzinfo is None:
        target_time = (
            target_time.tz_localize("UTC")
        )

    latest_margin_mw = float(
        margin.iloc[-1]["derated_margin_mw"]
    )

    percentile = calculate_margin_percentile(
        predicted_drm_mw,
        margin_history,
    )

    description = describe_margin_percentile(
        percentile
    )

    change_mw = (
        predicted_drm_mw
        - latest_margin_mw
    )

    # ----------------------------------------------
    # Headline metrics
    # ----------------------------------------------

    forecast_col, position_col, change_col = (
        st.columns([2, 1, 1])
    )

    forecast_col.metric(
        "Predicted de-rated margin",
        f"{predicted_drm_mw / 1000:.1f} GW",
    )

    position_col.metric(
        "Historical position",
        f"{percentile:.0f}th percentile",
    )

    change_col.metric(
        "Vs latest margin",
        f"{change_mw / 1000:+.1f} GW",
    )

    st.caption(
        f"{description} · "
        f"Forecast for "
        f"{target_time.tz_convert('Europe/London').strftime('%d %b %Y · %H:%M %Z')}"
    )

    # ----------------------------------------------
    # Recent actual DRM
    # ----------------------------------------------

    recent = margin.copy()

    recent = recent[
        recent["event_time_utc"]
        >= (
            forecast_origin
            - pd.Timedelta(hours=48)
        )
    ].copy()

    recent["drm_gw"] = (
        recent["derated_margin_mw"]
        / 1000
    )

    # ----------------------------------------------
    # Forecast point
    # ----------------------------------------------

    forecast_point = pd.DataFrame(
        {
            "event_time_utc": [
                target_time
            ],
            "drm_gw": [
                predicted_drm_mw / 1000
            ],
            "label": [
                f"{predicted_drm_mw / 1000:.1f} GW"
            ],
        }
    )

    # ----------------------------------------------
    # Actual history line
    # ----------------------------------------------

    history_line = (
        alt.Chart(recent)
        .mark_line(
            strokeWidth=2,
        )
        .encode(
            x=alt.X(
                "event_time_utc:T",
                title=None,
            ),
            y=alt.Y(
                "drm_gw:Q",
                title="De-rated margin (GW)",
                scale=alt.Scale(
                    zero=False,
                ),
            ),
            tooltip=[
                alt.Tooltip(
                    "event_time_utc:T",
                    title="Time",
                ),
                alt.Tooltip(
                    "drm_gw:Q",
                    title="DRM",
                    format=".1f",
                ),
            ],
        )
    )

    # ----------------------------------------------
    # Forecast marker
    # ----------------------------------------------

    forecast_dot = (
        alt.Chart(forecast_point)
        .mark_point(
            filled=True,
            size=180,
        )
        .encode(
            x="event_time_utc:T",
            y="drm_gw:Q",
            tooltip=[
                alt.Tooltip(
                    "event_time_utc:T",
                    title="Forecast target",
                ),
                alt.Tooltip(
                    "drm_gw:Q",
                    title="Predicted DRM",
                    format=".1f",
                ),
            ],
        )
    )

    forecast_label = (
        alt.Chart(forecast_point)
        .mark_text(
            align="left",
            dx=12,
            dy=-12,
            fontSize=14,
            fontWeight="bold",
        )
        .encode(
            x="event_time_utc:T",
            y="drm_gw:Q",
            text="label:N",
        )
    )

    # ----------------------------------------------
    # Dashed forecast-target marker
    # ----------------------------------------------

    target_rule = (
        alt.Chart(
            pd.DataFrame(
                {
                    "event_time_utc": [
                        target_time
                    ]
                }
            )
        )
        .mark_rule(
            strokeDash=[5, 5],
        )
        .encode(
            x="event_time_utc:T"
        )
    )

    chart = (
        history_line
        + target_rule
        + forecast_dot
        + forecast_label
    ).properties(
        height=320,
    ).interactive()

    st.altair_chart(
        chart,
        width="stretch",
    )

    st.caption(
        "Solid line: recently published DRM · "
        "Dot: model prediction exactly 24 hours ahead"
    )


def render_grid_context(
    margin: pd.DataFrame,
    demand: pd.DataFrame,
) -> None:
    st.markdown(
        "## Current grid context"
    )

    latest_margin = margin.iloc[-1]
    latest_demand = demand.iloc[-1]

    columns = st.columns(3)

    columns[0].metric(
        "Current DRM",
        (
            f"{latest_margin['derated_margin_mw'] / 1000:.1f} "
            "GW"
        ),
    )

    columns[1].metric(
        "Current demand",
        (
            f"{latest_demand['demand_mw'] / 1000:.1f} "
            "GW"
        ),
    )

    columns[2].metric(
        "Data updated",
        latest_margin[
            "event_time_utc"
        ].strftime(
            "%d %b · %H:%M UTC"
        ),
    )


def render_model_performance(
    metrics: dict,
) -> None:
    st.markdown(
        "## Model validation"
    )

    if not metrics:
        st.info(
            "Final model metrics are unavailable."
        )

        return

    columns = st.columns(3)

    columns[0].metric(
        "Ridge MAE",
        (
            f"{metrics['model_mae_mw'] / 1000:.2f} "
            "GW"
        ),
    )

    columns[1].metric(
        "Persistence MAE",
        (
            f"{metrics['baseline_mae_mw'] / 1000:.2f} "
            "GW"
        ),
    )

    columns[2].metric(
        "MAE improvement",
        f"{metrics['mae_improvement_pct']:.2f}%",
    )

    st.caption(
        "Final holdout · Ridge Regression · "
        "alpha=350 · 24-hour forecast horizon"
    )