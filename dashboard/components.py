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
    margin_history: pd.Series,
    latest_margin_mw: float,
) -> None:
    st.markdown(
        "## 24-hour-ahead forecast"
    )

    if forecast is None:
        st.info(
            "Forecast generation is not connected yet. "
            "The saved Ridge model will be wired into "
            "this panel next."
        )

        return

    predicted_drm_mw = float(
        forecast["predicted_drm_mw"]
    )

    target_time = pd.Timestamp(
        forecast["target_time_utc"]
    )

    if target_time.tzinfo is None:
        target_time = target_time.tz_localize(
            "UTC"
        )

    target_local = target_time.tz_convert(
        "Europe/London"
    )

    percentile = calculate_margin_percentile(
        predicted_drm_mw,
        margin_history,
    )

    description = describe_margin_percentile(
        percentile
    )

    difference_mw = (
        predicted_drm_mw
        - latest_margin_mw
    )

    marker_position = min(
        max(percentile, 1),
        99,
    )

    st.markdown(
        f"""
        <div class="forecast-card">

            <div class="forecast-top">

                <div>
                    <div class="forecast-label">
                        Predicted de-rated margin
                    </div>

                    <div class="forecast-value">
                        {predicted_drm_mw / 1000:.1f}
                        <span class="forecast-unit">
                            GW
                        </span>
                    </div>

                    <div class="forecast-description">
                        {description}
                    </div>
                </div>

                <div class="forecast-target">
                    <strong>Forecast target</strong><br>
                    {target_local.strftime("%d %b %Y")}<br>
                    {target_local.strftime("%H:%M %Z")}
                </div>

            </div>

            <div class="margin-scale">
                <div
                    class="margin-marker"
                    style="left: {marker_position}%;">
                </div>
            </div>

            <div class="scale-labels">
                <span>Historically tight</span>
                <span>Typical</span>
                <span>High margin</span>
            </div>

            <div class="forecast-context">

                <div>
                    <span class="context-label">
                        Historical percentile:
                    </span>
                    <span class="context-value">
                        {percentile:.0f}th
                    </span>
                </div>

                <div>
                    <span class="context-label">
                        Latest margin:
                    </span>
                    <span class="context-value">
                        {latest_margin_mw / 1000:.1f} GW
                    </span>
                </div>

                <div>
                    <span class="context-label">
                        Change vs latest:
                    </span>
                    <span class="context-value">
                        {difference_mw / 1000:+.1f} GW
                    </span>
                </div>

            </div>

        </div>
        """,
        unsafe_allow_html=True,
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