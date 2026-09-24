import pandas as pd
import streamlit as st

from dashboard.graphs import (
    build_demand_settlement_bars,
    build_drm_change_bridge,
    build_forecast_graphs,
    build_generation_change_dashboard,
    build_generation_doughnut_dashboard,
    build_margin_graphs,
    build_model_vs_persistence_vertical,
    build_typical_day_demand_dashboard,
    build_validation_graphs,
)

def render_refresh_status(
    status: dict,
) -> None:
    """Render a compact live/cached-data status message."""
    if not status:
        st.caption(
            "Live refresh worker is starting · "
            "showing cached data until the first "
            "check completes."
        )
        return

    state = status.get(
        "state",
        "unknown",
    )

    message = status.get(
        "message",
        "",
    )

    completed_raw = status.get(
        "completed_at_utc"
    )

    completed = None

    if completed_raw:
        try:
            completed = pd.Timestamp(
                completed_raw
            )

            if completed.tzinfo is None:
                completed = (
                    completed.tz_localize(
                        "UTC"
                    )
                )
            else:
                completed = (
                    completed.tz_convert(
                        "UTC"
                    )
                )

        except (
            ValueError,
            TypeError,
        ):
            completed = None

    if state == "refreshing":
        st.info(
            "Refreshing live grid data in the "
            "background. The dashboard is "
            "temporarily showing the latest "
            "cached values."
        )
        return

    if state in {
        "degraded",
        "failed",
    }:
        st.warning(
            message
            or (
                "Live refresh is unavailable; "
                "serving cached values."
            )
        )

        source_refresh = status.get(
            "source_refresh",
            {},
        )

        prediction = status.get(
            "prediction",
            {},
        )

        errors = []

        for (
            source_name,
            result,
        ) in source_refresh.items():
            if result.get(
                "error"
            ):
                errors.append(
                    f"{source_name}: "
                    f"{result['error']}"
                )

        if prediction.get(
            "error"
        ):
            errors.append(
                "Prediction: "
                f"{prediction['error']}"
            )

        if errors:
            with st.expander(
                "Refresh details"
            ):
                for error in errors:
                    st.caption(
                        error
                    )

        return

    if completed is not None:
        local = completed.tz_convert(
            "Europe/London"
        )

        st.caption(
            "● Live data checked "
            f"{local.strftime('%d %b · %H:%M %Z')}"
        )

    else:
        st.caption(
            "● Live data refresh active"
        )

def calculate_margin_percentile(
    predicted_drm_mw: float,
    history: pd.Series,
) -> float:
    clean = pd.to_numeric(
        history,
        errors="coerce",
    ).dropna()

    if clean.empty:
        return 50.0

    return float(
        (
            clean
            < predicted_drm_mw
        ).mean()
        * 100
    )


def describe_margin_percentile(
    percentile: float,
) -> str:
    if percentile <= 10:
        return "historically tight"

    if percentile <= 25:
        return "below the typical historical range"

    if percentile <= 75:
        return "around the typical historical range"

    return "high relative to historical margins"


def render_forecast_hero(
    forecast: dict | None,
    margin: pd.DataFrame,
    margin_history: pd.Series,
) -> None:
    st.markdown(
        "## 24-hour-ahead forecast"
    )

    if (
        forecast is None
        or margin.empty
    ):
        st.info(
            "A saved forecast is not currently available."
        )
        return

    predicted = float(
        forecast[
            "predicted_drm_mw"
        ]
    )

    target = pd.Timestamp(
        forecast[
            "target_time_utc"
        ]
    )

    if target.tzinfo is None:
        target = (
            target.tz_localize(
                "UTC"
            )
        )

    latest = float(
        margin.iloc[-1][
            "derated_margin_mw"
        ]
    )

    change = (
        predicted
        - latest
    )

    percentile = (
        calculate_margin_percentile(
            predicted,
            margin_history,
        )
    )

    description = (
        describe_margin_percentile(
            percentile
        )
    )

    headline, bridge = (
        st.columns(
            [1.15, 1]
        )
    )

    with headline:
        st.metric(
            "Predicted de-rated margin",
            f"{predicted / 1000:.1f} GW",
            delta=(
                f"{change / 1000:+.1f} GW "
                "vs latest"
            ),
        )

        local_target = (
            target.tz_convert(
                "Europe/London"
            )
        )

        st.markdown(
            f"**Forecast for "
            f"{local_target.strftime('%d %b %Y · %H:%M %Z')}**"
        )

        st.caption(
            f"This forecast is higher than "
            f"{percentile:.0f}% of historical DRM observations "
            f"and is {description}."
        )

    with bridge:
        st.altair_chart(
            build_drm_change_bridge(
                forecast
            ),
            width="stretch",
        )

    forecast_chart = (
        build_forecast_graphs(
            recent_margin=margin,
            forecast=forecast,
        )[
            "history_and_forecast"
        ]
    )

    st.altair_chart(
        forecast_chart,
        width="stretch",
    )

    st.caption(
        "Solid line = recent published DRM · "
        "dashed boundary / point = the model's "
        "single prediction exactly 24 hours ahead."
    )


def render_grid_context(
    margin: pd.DataFrame,
    demand: pd.DataFrame,
    generation: pd.DataFrame,
) -> None:
    st.markdown(
        "## Current grid context"
    )

    if (
        margin.empty
        or demand.empty
    ):
        st.info(
            "Current grid context is unavailable."
        )
        return

    latest_margin = (
        margin.iloc[-1]
    )

    latest_demand = (
        demand.dropna(
            subset=[
                "demand_mw"
            ]
        ).iloc[-1]
    )

    total_generation = None

    if not generation.empty:
        latest_generation = (
            generation.iloc[-1]
        )

        positive = (
            latest_generation[
                latest_generation > 0
            ]
        )

        total_generation = (
            positive.sum()
            / 1000
        )

    curr_drm, curr_demand, track_gen, upload_date = st.columns([1, 1, 1, 1.5])

    curr_drm.metric(
        "Current DRM",
        (
            f"{latest_margin['derated_margin_mw'] / 1000:.1f} "
            "GW"
        ),
    )

    curr_demand.metric(
        "Current demand",
        (
            f"{latest_demand['demand_mw'] / 1000:.1f} "
            "GW"
        ),
    )

    track_gen.metric(
        "Tracked generation",
        (
            f"{total_generation:.1f} GW"
            if total_generation is not None
            else "—"
        ),
    )

    latest_time = pd.Timestamp(
        latest_margin[
            "event_time_utc"
        ]
    )

    upload_date.metric(
        "Data updated",
        latest_time.strftime(
            "%d %b · %H:%M UTC"
        ),
    )

    age = (
        pd.Timestamp.now(
            tz="UTC"
        )
        - latest_time
    )

    if age > pd.Timedelta(
        minutes=90
    ):
        st.warning(
            "The local dataset is stale. "
            "The dashboard is serving the latest cached values."
        )


def render_recent_grid_history(
    margin: pd.DataFrame,
    demand: pd.DataFrame,
) -> None:
    st.markdown(
        "## Recent grid history"
    )

    left, right = st.columns(2)

    with left:
        margin_chart = (
            build_margin_graphs(
                margin
            )[
                "line"
            ]
        )

        st.altair_chart(
            margin_chart,
            width="stretch",
        )

    with right:
        st.altair_chart(
            build_demand_settlement_bars(
                demand
            ),
            width="stretch",
        )

        st.caption(
            "Amber bars are display-only linear estimates "
            "for internal missing settlement periods. "
            "They are never written back into the model data."
        )


def render_demand_context(
    demand_history: pd.DataFrame,
) -> None:
    st.markdown(
        "### Demand vs a typical day"
    )

    try:
        chart = (
            build_typical_day_demand_dashboard(
                demand_history
            )
        )
    except ValueError as exc:
        st.info(
            str(exc)
        )
        return

    st.altair_chart(
        chart,
        width="stretch",
    )

    st.caption(
        "The current in-progress profile is shown alongside the "
        "latest full-day profile, historical median, and interquartile "
        "range for each half-hour settlement period."
    )


def render_generation_section(
    generation: pd.DataFrame,
) -> None:
    st.markdown(
        "## Generation"
    )

    if generation.empty:
        st.info(
            "Generation data is unavailable."
        )
        return

    # mix, movement = (
    #     st.columns(
    #         [2, 1]
    #     )
    # )

# with mix:
    st.altair_chart(
        build_generation_doughnut_dashboard(
            generation
        ),
        width="stretch",
    )

    st.caption(
        "Small positive contributors are grouped into Other. "
        "Negative interconnector / storage flows are not represented "
        "as doughnut slices."
    )

# with movement:
    st.altair_chart(
        build_generation_change_dashboard(
            generation,
            lookback_hours=4,
        ),
        width="stretch",
    )

    st.caption(
        "Direction is shown by which side of zero the bar reaches; "
        "colour intensity represents movement strength."
    )


def render_model_performance(
    metrics: dict,
    predictions: pd.DataFrame,
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
        (
            f"{metrics['mae_improvement_pct']:.2f}%"
        ),
    )

    if predictions.empty:
        st.caption(
            "Final holdout · Ridge Regression · "
            "alpha=350 · 24-hour horizon"
        )
        return

    left, right = (
        st.columns(2)
    )

    with left:
        residuals = (
            build_validation_graphs(
                predictions
            )[
                "residuals"
            ]
        )

        st.altair_chart(
            residuals,
            width="stretch",
        )

        st.caption(
            "Residuals show when the model predicted DRM "
            "too high or too low over time."
        )

    with right:
        try:
            comparison = (
                build_model_vs_persistence_vertical(
                    predictions
                )
            )

            st.altair_chart(
                comparison,
                width="stretch",
            )
        except ValueError as exc:
            st.info(
                str(exc)
            )

        st.caption(
            "Lower MAE is better. The y-axis is intentionally "
            "focused on the observed error range so the improvement "
            "is legible; exact values are labelled."
        )

    st.caption(
        "Final holdout · Ridge Regression · "
        "alpha=350 · 24-hour forecast horizon"
    )
