"""Altair chart builders for the UK Energy Reliability Tool.

This module only builds chart objects. It does not load data, call Streamlit,
or display anything. Each public builder returns multiple chart variants so a
separate swiper/A-B testing UI can score them later.
"""

from __future__ import annotations

from typing import Any

import altair as alt
import pandas as pd

ChartSet = dict[str, Any]


def _datetime(df: pd.DataFrame, column: str) -> pd.DataFrame:
    out = df.copy()
    out[column] = pd.to_datetime(out[column], utc=True)
    return out


def _series_gw(
    df: pd.DataFrame,
    time_col: str,
    value_col: str,
    output_col: str,
) -> pd.DataFrame:
    out = _datetime(df[[time_col, value_col]].dropna(), time_col)
    out[output_col] = out[value_col] / 1000
    return out


def _time_x(column: str = "event_time_utc") -> alt.X:
    return alt.X(f"{column}:T", title=None, axis=alt.Axis(labelAngle=0))


def build_forecast_graphs(
    recent_margin: pd.DataFrame,
    forecast: dict,
) -> ChartSet:
    """Five views of the single 24-hour-ahead DRM prediction."""
    history = _series_gw(
        recent_margin,
        "event_time_utc",
        "derated_margin_mw",
        "drm_gw",
    )

    target = pd.Timestamp(forecast["target_time_utc"])
    predicted = float(forecast["predicted_drm_mw"]) / 1000
    latest = float(forecast["latest_drm_mw"]) / 1000

    point = pd.DataFrame(
        {"event_time_utc": [target], "drm_gw": [predicted]}
    )

    history_line = (
        alt.Chart(history)
        .mark_line(strokeWidth=2)
        .encode(
            x=_time_x(),
            y=alt.Y("drm_gw:Q", title="DRM (GW)", scale=alt.Scale(zero=False)),
            tooltip=[
                alt.Tooltip("event_time_utc:T", title="Time"),
                alt.Tooltip("drm_gw:Q", title="DRM", format=".1f"),
            ],
        )
    )

    forecast_dot = (
        alt.Chart(point)
        .mark_point(filled=True, size=200)
        .encode(
            x="event_time_utc:T",
            y="drm_gw:Q",
            tooltip=[
                alt.Tooltip("event_time_utc:T", title="Forecast target"),
                alt.Tooltip("drm_gw:Q", title="Predicted DRM", format=".1f"),
            ],
        )
    )

    target_rule = (
        alt.Chart(pd.DataFrame({"event_time_utc": [target]}))
        .mark_rule(strokeDash=[5, 5])
        .encode(x="event_time_utc:T")
    )

    history_and_forecast = (
        history_line + target_rule + forecast_dot
    ).properties(title="Recent DRM + 24h forecast", height=320)

    compare = pd.DataFrame(
        {
            "state": ["Latest published", "24h forecast"],
            "drm_gw": [latest, predicted],
        }
    )

    comparison_bars = (
        alt.Chart(compare)
        .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6)
        .encode(
            x=alt.X("state:N", title=None),
            y=alt.Y("drm_gw:Q", title="DRM (GW)"),
            tooltip=["state:N", alt.Tooltip("drm_gw:Q", format=".1f")],
        )
        .properties(title="Latest vs forecast", height=320)
    )

    lollipop = (
        alt.Chart(compare)
        .mark_rule()
        .encode(
            x=alt.X("state:N", title=None),
            y=alt.Y("drm_gw:Q", title="DRM (GW)"),
            y2=alt.value(0),
        )
        + alt.Chart(compare)
        .mark_point(filled=True, size=220)
        .encode(
            x="state:N",
            y="drm_gw:Q",
            tooltip=["state:N", alt.Tooltip("drm_gw:Q", format=".1f")],
        )
    ).properties(title="Current-to-forecast change", height=320)

    histogram = (
        alt.Chart(history)
        .mark_bar()
        .encode(
            x=alt.X("drm_gw:Q", bin=alt.Bin(maxbins=30), title="DRM (GW)"),
            y=alt.Y("count():Q", title="Frequency"),
        )
    )
    forecast_rule = (
        alt.Chart(pd.DataFrame({"drm_gw": [predicted]}))
        .mark_rule(strokeWidth=3)
        .encode(
            x="drm_gw:Q",
            tooltip=[alt.Tooltip("drm_gw:Q", title="Forecast", format=".1f")],
        )
    )
    distribution = (histogram + forecast_rule).properties(
        title="Forecast in recent DRM distribution", height=320
    )

    history_points = (
        alt.Chart(history)
        .mark_circle(size=38, opacity=0.6)
        .encode(
            x=_time_x(),
            y=alt.Y("drm_gw:Q", title="DRM (GW)", scale=alt.Scale(zero=False)),
            tooltip=["event_time_utc:T", alt.Tooltip("drm_gw:Q", format=".1f")],
        )
    )
    observations_and_forecast = (
        history_points + target_rule + forecast_dot
    ).properties(title="Observed DRM + forecast point", height=320)

    return {
        "history_and_forecast": history_and_forecast,
        "comparison_bars": comparison_bars,
        "lollipop": lollipop,
        "distribution": distribution,
        "observations_and_forecast": observations_and_forecast,
    }


def _build_single_series_graphs(
    df: pd.DataFrame,
    value_col: str,
    output_col: str,
    label: str,
) -> ChartSet:
    data = _series_gw(df, "event_time_utc", value_col, output_col)

    line = (
        alt.Chart(data)
        .mark_line(strokeWidth=2)
        .encode(
            x=_time_x(),
            y=alt.Y(f"{output_col}:Q", title=f"{label} (GW)", scale=alt.Scale(zero=False)),
            tooltip=["event_time_utc:T", alt.Tooltip(f"{output_col}:Q", format=".1f")],
        )
        .properties(title=f"{label} — line", height=300)
    )

    area = (
        alt.Chart(data)
        .mark_area(opacity=0.55)
        .encode(
            x=_time_x(),
            y=alt.Y(f"{output_col}:Q", title=f"{label} (GW)", scale=alt.Scale(zero=False)),
            tooltip=["event_time_utc:T", alt.Tooltip(f"{output_col}:Q", format=".1f")],
        )
        .properties(title=f"{label} — area", height=300)
    )

    bars = (
        alt.Chart(data)
        .mark_bar()
        .encode(
            x=_time_x(),
            y=alt.Y(f"{output_col}:Q", title=f"{label} (GW)"),
            tooltip=["event_time_utc:T", alt.Tooltip(f"{output_col}:Q", format=".1f")],
        )
        .properties(title=f"{label} — settlement bars", height=300)
    )

    points = (
        alt.Chart(data)
        .mark_circle(size=42, opacity=0.65)
        .encode(
            x=_time_x(),
            y=alt.Y(f"{output_col}:Q", title=f"{label} (GW)", scale=alt.Scale(zero=False)),
            tooltip=["event_time_utc:T", alt.Tooltip(f"{output_col}:Q", format=".1f")],
        )
        .properties(title=f"{label} — observations", height=300)
    )

    heat = data.copy()
    local = heat["event_time_utc"].dt.tz_convert("Europe/London")
    heat["date"] = local.dt.strftime("%d %b")
    heat["hour"] = local.dt.hour + local.dt.minute / 60

    heatmap = (
        alt.Chart(heat)
        .mark_rect()
        .encode(
            x=alt.X("hour:O", title="Hour of day"),
            y=alt.Y("date:O", title=None),
            color=alt.Color(f"{output_col}:Q", title=f"{label} (GW)"),
            tooltip=[
                "date:N",
                alt.Tooltip("hour:Q", title="Hour"),
                alt.Tooltip(f"{output_col}:Q", title=label, format=".1f"),
            ],
        )
        .properties(title=f"{label} — day/hour heatmap", height=300)
    )

    return {
        "line": line,
        "area": area,
        "bars": bars,
        "points": points,
        "heatmap": heatmap,
    }


def build_margin_graphs(margin: pd.DataFrame) -> ChartSet:
    """Five alternatives for recent de-rated margin."""
    return _build_single_series_graphs(
        margin,
        "derated_margin_mw",
        "drm_gw",
        "De-rated margin",
    )


def build_demand_graphs(demand: pd.DataFrame) -> ChartSet:
    """Five alternatives for recent electricity demand."""
    return _build_single_series_graphs(
        demand,
        "demand_mw",
        "demand_gw",
        "Demand",
    )


def build_generation_graphs(generation: pd.DataFrame) -> ChartSet:
    """Alternatives for generation by fuel.

    Expected input: event_time_utc index (or column), fuel columns, MW values.

    The pie and doughnut variants use the latest available generation snapshot,
    mirroring the current-mix style used by live grid dashboards.
    """
    wide = generation.copy()

    if "event_time_utc" not in wide.columns:
        wide = wide.reset_index()

    wide["event_time_utc"] = pd.to_datetime(
        wide["event_time_utc"],
        utc=True,
    )

    fuels = [
        column
        for column in wide.columns
        if column != "event_time_utc"
    ]

    long = wide.melt(
        id_vars="event_time_utc",
        value_vars=fuels,
        var_name="fuel_type",
        value_name="generation_mw",
    )

    long = long.dropna(
        subset=["generation_mw"]
    )

    long["generation_gw"] = (
        long["generation_mw"] / 1000
    )

    multi_line = (
        alt.Chart(long)
        .mark_line(strokeWidth=2)
        .encode(
            x=_time_x(),
            y=alt.Y(
                "generation_gw:Q",
                title="Generation (GW)",
            ),
            color=alt.Color(
                "fuel_type:N",
                title="Fuel",
            ),
            tooltip=[
                "event_time_utc:T",
                "fuel_type:N",
                alt.Tooltip(
                    "generation_gw:Q",
                    title="Generation",
                    format=".1f",
                ),
            ],
        )
        .properties(
            title="Generation — multi-line",
            height=320,
        )
    )

    stacked_area = (
        alt.Chart(long)
        .mark_area()
        .encode(
            x=_time_x(),
            y=alt.Y(
                "generation_gw:Q",
                title="Generation (GW)",
                stack="zero",
            ),
            color=alt.Color(
                "fuel_type:N",
                title="Fuel",
            ),
            tooltip=[
                "event_time_utc:T",
                "fuel_type:N",
                alt.Tooltip(
                    "generation_gw:Q",
                    title="Generation",
                    format=".1f",
                ),
            ],
        )
        .properties(
            title="Generation — stacked area",
            height=320,
        )
    )

    hourly = (
        long
        .set_index("event_time_utc")
        .groupby("fuel_type")[
            "generation_gw"
        ]
        .resample("2h")
        .mean()
        .reset_index()
    )

    stacked_bars = (
        alt.Chart(hourly)
        .mark_bar()
        .encode(
            x=_time_x(),
            y=alt.Y(
                "generation_gw:Q",
                title="Generation (GW)",
                stack="zero",
            ),
            color=alt.Color(
                "fuel_type:N",
                title="Fuel",
            ),
            tooltip=[
                "event_time_utc:T",
                "fuel_type:N",
                alt.Tooltip(
                    "generation_gw:Q",
                    title="Generation",
                    format=".1f",
                ),
            ],
        )
        .properties(
            title="Generation — stacked bars",
            height=320,
        )
    )

    shares = long.copy()

    total = shares.groupby(
        "event_time_utc"
    )["generation_gw"].transform(
        "sum"
    )

    shares["share"] = (
        shares["generation_gw"]
        / total
    )

    normalized_area = (
        alt.Chart(shares)
        .mark_area()
        .encode(
            x=_time_x(),
            y=alt.Y(
                "share:Q",
                title="Share",
                stack="normalize",
                axis=alt.Axis(format="%"),
            ),
            color=alt.Color(
                "fuel_type:N",
                title="Fuel",
            ),
            tooltip=[
                "event_time_utc:T",
                "fuel_type:N",
                alt.Tooltip(
                    "share:Q",
                    title="Share",
                    format=".1%",
                ),
            ],
        )
        .properties(
            title="Generation — proportional mix",
            height=320,
        )
    )

    small_multiples = (
        alt.Chart(long)
        .mark_area(opacity=0.7)
        .encode(
            x=_time_x(),
            y=alt.Y(
                "generation_gw:Q",
                title="Generation (GW)",
            ),
        )
        .properties(
            width=180,
            height=110,
        )
        .facet(
            facet=alt.Facet(
                "fuel_type:N",
                title=None,
            ),
            columns=2,
        )
        .properties(
            title="Generation — small multiples"
        )
    )

    # Latest timestamp only: these are point-in-time mix charts rather than
    # summaries across the whole seven-day window.
    latest_time = wide["event_time_utc"].max()

    latest_mix = (
        long[
            long["event_time_utc"]
            == latest_time
        ][
            [
                "fuel_type",
                "generation_gw",
            ]
        ]
        .groupby(
            "fuel_type",
            as_index=False,
        )["generation_gw"]
        .sum()
    )

    latest_total = latest_mix[
        "generation_gw"
    ].sum()

    if latest_total > 0:
        latest_mix["share"] = (
            latest_mix["generation_gw"]
            / latest_total
        )
    else:
        latest_mix["share"] = 0.0

    latest_mix = latest_mix.sort_values(
        "generation_gw",
        ascending=False,
    )

    latest_local = latest_time.tz_convert(
        "Europe/London"
    )

    snapshot_title = (
        "Latest generation mix — "
        f"{latest_local.strftime('%d %b · %H:%M %Z')}"
    )

    pie = (
        alt.Chart(latest_mix)
        .mark_arc(
            outerRadius=125,
        )
        .encode(
            theta=alt.Theta(
                "generation_gw:Q",
                stack=True,
            ),
            color=alt.Color(
                "fuel_type:N",
                title="Fuel",
                sort=latest_mix[
                    "fuel_type"
                ].tolist(),
            ),
            order=alt.Order(
                "generation_gw:Q",
                sort="descending",
            ),
            tooltip=[
                alt.Tooltip(
                    "fuel_type:N",
                    title="Fuel",
                ),
                alt.Tooltip(
                    "generation_gw:Q",
                    title="Generation (GW)",
                    format=".2f",
                ),
                alt.Tooltip(
                    "share:Q",
                    title="Share",
                    format=".1%",
                ),
            ],
        )
        .properties(
            title=snapshot_title,
            height=320,
        )
    )

    doughnut = (
        alt.Chart(latest_mix)
        .mark_arc(
            innerRadius=65,
            outerRadius=125,
        )
        .encode(
            theta=alt.Theta(
                "generation_gw:Q",
                stack=True,
            ),
            color=alt.Color(
                "fuel_type:N",
                title="Fuel",
                sort=latest_mix[
                    "fuel_type"
                ].tolist(),
            ),
            order=alt.Order(
                "generation_gw:Q",
                sort="descending",
            ),
            tooltip=[
                alt.Tooltip(
                    "fuel_type:N",
                    title="Fuel",
                ),
                alt.Tooltip(
                    "generation_gw:Q",
                    title="Generation (GW)",
                    format=".2f",
                ),
                alt.Tooltip(
                    "share:Q",
                    title="Share",
                    format=".1%",
                ),
            ],
        )
        .properties(
            title=snapshot_title,
            height=320,
        )
    )

    return {
        "multi_line": multi_line,
        "stacked_area": stacked_area,
        "stacked_bars": stacked_bars,
        "normalized_area": normalized_area,
        "small_multiples": small_multiples,
        "pie_latest_mix": pie,
        "doughnut_latest_mix": doughnut,
    }


def build_validation_graphs(predictions: pd.DataFrame) -> ChartSet:
    """Five alternatives for final/validation prediction diagnostics.

    Expected columns:
      target_time_utc, target_drm_mw, predicted_drm_mw,
      error_mw, absolute_error_mw
    """
    data = predictions.copy()
    data["target_time_utc"] = pd.to_datetime(data["target_time_utc"], utc=True)
    data["actual_gw"] = data["target_drm_mw"] / 1000
    data["predicted_gw"] = data["predicted_drm_mw"] / 1000
    data["error_gw"] = data["error_mw"] / 1000
    data["absolute_error_gw"] = data["absolute_error_mw"] / 1000

    temporal = data.melt(
        id_vars="target_time_utc",
        value_vars=["actual_gw", "predicted_gw"],
        var_name="series",
        value_name="drm_gw",
    )

    time_comparison = (
        alt.Chart(temporal)
        .mark_line(strokeWidth=1.5)
        .encode(
            x=alt.X("target_time_utc:T", title=None),
            y=alt.Y("drm_gw:Q", title="DRM (GW)"),
            color=alt.Color("series:N", title=None),
        )
        .properties(title="Actual vs predicted over time", height=320)
    )

    parity = (
        alt.Chart(data)
        .mark_circle(size=40, opacity=0.45)
        .encode(
            x=alt.X("actual_gw:Q", title="Actual DRM (GW)"),
            y=alt.Y("predicted_gw:Q", title="Predicted DRM (GW)"),
            tooltip=[
                alt.Tooltip("actual_gw:Q", format=".1f"),
                alt.Tooltip("predicted_gw:Q", format=".1f"),
            ],
        )
        .properties(title="Actual vs predicted", height=320)
    )

    residuals = (
        alt.Chart(data)
        .mark_bar()
        .encode(
            x=alt.X("target_time_utc:T", title=None),
            y=alt.Y("error_gw:Q", title="Prediction error (GW)"),
            tooltip=[
                "target_time_utc:T",
                alt.Tooltip("error_gw:Q", format="+.1f"),
            ],
        )
        .properties(title="Residuals over time", height=320)
    )

    error_histogram = (
        alt.Chart(data)
        .mark_bar()
        .encode(
            x=alt.X("absolute_error_gw:Q", bin=alt.Bin(maxbins=35), title="Absolute error (GW)"),
            y=alt.Y("count():Q", title="Observations"),
        )
        .properties(title="Absolute error distribution", height=320)
    )

    bands = data.copy()
    bands["actual_band"] = pd.qcut(
        bands["actual_gw"], q=10, duplicates="drop"
    ).astype(str)
    error_by_band = (
        alt.Chart(bands)
        .mark_bar()
        .encode(
            x=alt.X("actual_band:N", title="Actual DRM decile", sort=None, axis=alt.Axis(labelAngle=-45)),
            y=alt.Y("mean(absolute_error_gw):Q", title="Mean absolute error (GW)"),
            tooltip=[
                "actual_band:N",
                alt.Tooltip("mean(absolute_error_gw):Q", title="MAE", format=".2f"),
            ],
        )
        .properties(title="Error by actual DRM band", height=320)
    )

    return {
        "time_comparison": time_comparison,
        "parity": parity,
        "residuals": residuals,
        "error_histogram": error_histogram,
        "error_by_band": error_by_band,
    }


# ============================================================
# Experimental / concept charts
# ============================================================

def _require_columns(
    df: pd.DataFrame,
    columns: list[str],
    context: str,
) -> None:
    missing = [
        column
        for column in columns
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"{context} requires columns: {missing}"
        )


def _latest_generation_snapshot(
    generation: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Timestamp]:
    """
    Return the latest generation snapshot in long form.

    Output columns:
        fuel_type
        generation_gw
        share
    """
    wide = generation.copy()

    if "event_time_utc" not in wide.columns:
        wide = wide.reset_index()

    _require_columns(
        wide,
        ["event_time_utc"],
        "Generation snapshot",
    )

    wide["event_time_utc"] = pd.to_datetime(
        wide["event_time_utc"],
        utc=True,
    )

    latest_time = wide[
        "event_time_utc"
    ].max()

    latest = wide[
        wide["event_time_utc"]
        == latest_time
    ].copy()

    fuels = [
        column
        for column in latest.columns
        if column != "event_time_utc"
    ]

    mix = latest.melt(
        id_vars="event_time_utc",
        value_vars=fuels,
        var_name="fuel_type",
        value_name="generation_mw",
    )

    mix = (
        mix.dropna(
            subset=["generation_mw"]
        )
        .groupby(
            "fuel_type",
            as_index=False,
        )["generation_mw"]
        .sum()
    )

    mix = mix[
        mix["generation_mw"] >= 0
    ].copy()

    mix["generation_gw"] = (
        mix["generation_mw"]
        / 1000
    )

    total = mix[
        "generation_gw"
    ].sum()

    if total > 0:
        mix["share"] = (
            mix["generation_gw"]
            / total
        )
    else:
        mix["share"] = 0.0

    mix = mix.sort_values(
        "generation_gw",
        ascending=False,
    )

    return mix, latest_time


def _percentile(
    value: float,
    history: pd.Series,
) -> float:
    clean = pd.to_numeric(
        history,
        errors="coerce",
    ).dropna()

    if clean.empty:
        raise ValueError(
            "Cannot calculate percentile from "
            "an empty historical series."
        )

    return float(
        (clean <= value).mean()
        * 100
    )


def _percentile_band_chart(
    percentile: float,
    value_gw: float,
    title: str,
    value_label: str,
) -> alt.TopLevelMixin:
    bands = pd.DataFrame(
        {
            "row": [
                "Historical position"
            ] * 4,
            "band": [
                "Lowest 10%",
                "10–25%",
                "25–75%",
                "Highest 25%",
            ],
            "start": [
                0,
                10,
                25,
                75,
            ],
            "end": [
                10,
                25,
                75,
                100,
            ],
        }
    )

    marker = pd.DataFrame(
        {
            "row": [
                "Historical position"
            ],
            "percentile": [
                percentile
            ],
            "label": [
                (
                    f"{value_label}: "
                    f"{value_gw:.1f} GW · "
                    f"{percentile:.0f}th percentile"
                )
            ],
        }
    )

    band_chart = (
        alt.Chart(bands)
        .mark_bar(
            size=42,
        )
        .encode(
            x=alt.X(
                "start:Q",
                title="Historical percentile",
                scale=alt.Scale(
                    domain=[0, 100]
                ),
            ),
            x2="end:Q",
            y=alt.Y(
                "row:N",
                title=None,
                axis=None,
            ),
            color=alt.Color(
                "band:N",
                title="Historical band",
            ),
            tooltip=[
                "band:N",
            ],
        )
    )

    marker_rule = (
        alt.Chart(marker)
        .mark_rule(
            strokeWidth=4,
        )
        .encode(
            x="percentile:Q",
            tooltip=[
                alt.Tooltip(
                    "label:N",
                    title=None,
                )
            ],
        )
    )

    marker_point = (
        alt.Chart(marker)
        .mark_point(
            filled=True,
            size=170,
        )
        .encode(
            x="percentile:Q",
            y="row:N",
            tooltip=[
                alt.Tooltip(
                    "label:N",
                    title=None,
                )
            ],
        )
    )

    return (
        band_chart
        + marker_rule
        + marker_point
    ).properties(
        title=title,
        height=120,
    )


# ------------------------------------------------------------
# 1. Forecast historical position
# ------------------------------------------------------------

def build_forecast_percentile_graph(
    forecast: dict,
    margin_history: pd.DataFrame | pd.Series,
) -> alt.TopLevelMixin:
    """
    Place the 24-hour DRM forecast within its historical distribution.

    margin_history can be:
      - a Series of DRM values in MW; or
      - a DataFrame containing derated_margin_mw.
    """
    predicted_mw = float(
        forecast["predicted_drm_mw"]
    )

    if isinstance(
        margin_history,
        pd.DataFrame,
    ):
        _require_columns(
            margin_history,
            ["derated_margin_mw"],
            "Forecast percentile",
        )

        history = margin_history[
            "derated_margin_mw"
        ]
    else:
        history = margin_history

    percentile = _percentile(
        predicted_mw,
        history,
    )

    return _percentile_band_chart(
        percentile=percentile,
        value_gw=predicted_mw / 1000,
        title=(
            "Where the 24-hour forecast "
            "sits historically"
        ),
        value_label="Forecast DRM",
    )


# ------------------------------------------------------------
# 2. DRM change bridge
# ------------------------------------------------------------

def build_drm_change_bridge(
    forecast: dict,
) -> alt.TopLevelMixin:
    """
    Compare the latest known DRM with the 24-hour-ahead prediction.
    """
    latest = (
        float(
            forecast["latest_drm_mw"]
        )
        / 1000
    )

    predicted = (
        float(
            forecast["predicted_drm_mw"]
        )
        / 1000
    )

    delta = predicted - latest

    points = pd.DataFrame(
        {
            "state": [
                "Current",
                "24h forecast",
            ],
            "drm_gw": [
                latest,
                predicted,
            ],
            "label": [
                f"{latest:.1f} GW",
                f"{predicted:.1f} GW",
            ],
        }
    )

    bridge = pd.DataFrame(
        {
            "row": [
                "DRM"
            ],
            "start": [
                latest
            ],
            "end": [
                predicted
            ],
            "delta": [
                delta
            ],
        }
    )

    connector = (
        alt.Chart(bridge)
        .mark_rule(
            strokeWidth=5,
        )
        .encode(
            x=alt.X(
                "start:Q",
                title="De-rated margin (GW)",
                scale=alt.Scale(
                    zero=False
                ),
            ),
            x2="end:Q",
            y=alt.Y(
                "row:N",
                title=None,
                axis=None,
            ),
            tooltip=[
                alt.Tooltip(
                    "delta:Q",
                    title="Change (GW)",
                    format="+.1f",
                )
            ],
        )
    )

    point_chart = (
        alt.Chart(points)
        .mark_point(
            filled=True,
            size=230,
        )
        .encode(
            x="drm_gw:Q",
            y=alt.value(30),
            shape=alt.Shape(
                "state:N",
                title=None,
            ),
            tooltip=[
                "state:N",
                alt.Tooltip(
                    "drm_gw:Q",
                    title="DRM (GW)",
                    format=".1f",
                ),
            ],
        )
    )

    labels = (
        alt.Chart(points)
        .mark_text(
            dy=-24,
            fontWeight="bold",
        )
        .encode(
            x="drm_gw:Q",
            y=alt.value(30),
            text="label:N",
        )
    )

    return (
        connector
        + point_chart
        + labels
    ).properties(
        title=(
            "Current DRM to "
            "24-hour forecast"
        ),
        height=120,
    )


# ------------------------------------------------------------
# 3. Typical-day demand profile
# ------------------------------------------------------------

def build_typical_day_demand_graph(
    demand_history: pd.DataFrame,
) -> alt.TopLevelMixin:
    """
    Compare the latest local day's demand profile with the historical
    median and interquartile range for each half-hour slot.

    For a strong comparison, pass substantially more than seven days
    of demand history.
    """
    _require_columns(
        demand_history,
        [
            "event_time_utc",
            "demand_mw",
        ],
        "Typical-day demand",
    )

    data = demand_history[
        [
            "event_time_utc",
            "demand_mw",
        ]
    ].dropna().copy()

    data[
        "event_time_utc"
    ] = pd.to_datetime(
        data["event_time_utc"],
        utc=True,
    )

    local = data[
        "event_time_utc"
    ].dt.tz_convert(
        "Europe/London"
    )

    data["local_date"] = (
        local.dt.date
    )

    data["settlement_slot"] = (
        local.dt.hour * 2
        + local.dt.minute // 30
        + 1
    )

    data["demand_gw"] = (
        data["demand_mw"]
        / 1000
    )

    latest_date = data[
        "local_date"
    ].max()

    reference = data[
        data["local_date"]
        < latest_date
    ]

    if reference.empty:
        raise ValueError(
            "Typical-day demand needs at least "
            "one earlier local day for comparison."
        )

    typical = (
        reference.groupby(
            "settlement_slot"
        )["demand_gw"]
        .agg(
            q25=lambda x: x.quantile(
                0.25
            ),
            median="median",
            q75=lambda x: x.quantile(
                0.75
            ),
        )
        .reset_index()
    )

    current = data[
        data["local_date"]
        == latest_date
    ][
        [
            "settlement_slot",
            "demand_gw",
        ]
    ]

    band = (
        alt.Chart(typical)
        .mark_area(
            opacity=0.25,
        )
        .encode(
            x=alt.X(
                "settlement_slot:Q",
                title="Settlement period",
                scale=alt.Scale(
                    domain=[1, 48]
                ),
            ),
            y=alt.Y(
                "q25:Q",
                title="Demand (GW)",
                scale=alt.Scale(
                    zero=False
                ),
            ),
            y2="q75:Q",
        )
    )

    median_line = (
        alt.Chart(typical)
        .mark_line(
            strokeDash=[5, 4],
            strokeWidth=2,
        )
        .encode(
            x="settlement_slot:Q",
            y="median:Q",
            tooltip=[
                alt.Tooltip(
                    "settlement_slot:Q",
                    title="Settlement period",
                ),
                alt.Tooltip(
                    "median:Q",
                    title="Typical demand",
                    format=".1f",
                ),
            ],
        )
    )

    current_line = (
        alt.Chart(current)
        .mark_line(
            strokeWidth=3,
        )
        .encode(
            x="settlement_slot:Q",
            y="demand_gw:Q",
            tooltip=[
                alt.Tooltip(
                    "settlement_slot:Q",
                    title="Settlement period",
                ),
                alt.Tooltip(
                    "demand_gw:Q",
                    title="Latest-day demand",
                    format=".1f",
                ),
            ],
        )
    )

    return (
        band
        + median_line
        + current_line
    ).properties(
        title=(
            "Latest demand profile "
            "vs a typical day"
        ),
        height=320,
    )


# ------------------------------------------------------------
# 4. Demand percentile for current settlement period
# ------------------------------------------------------------

def build_current_demand_percentile_graph(
    demand_history: pd.DataFrame,
) -> alt.TopLevelMixin:
    """
    Show how the latest demand observation compares with historical
    observations from the same local half-hour slot.
    """
    _require_columns(
        demand_history,
        [
            "event_time_utc",
            "demand_mw",
        ],
        "Demand percentile",
    )

    data = demand_history[
        [
            "event_time_utc",
            "demand_mw",
        ]
    ].dropna().copy()

    data[
        "event_time_utc"
    ] = pd.to_datetime(
        data["event_time_utc"],
        utc=True,
    )

    data = data.sort_values(
        "event_time_utc"
    )

    local = data[
        "event_time_utc"
    ].dt.tz_convert(
        "Europe/London"
    )

    data["settlement_slot"] = (
        local.dt.hour * 2
        + local.dt.minute // 30
        + 1
    )

    latest = data.iloc[-1]

    comparable = data[
        data["settlement_slot"]
        == latest[
            "settlement_slot"
        ]
    ]

    percentile = _percentile(
        float(
            latest["demand_mw"]
        ),
        comparable[
            "demand_mw"
        ],
    )

    return _percentile_band_chart(
        percentile=percentile,
        value_gw=(
            float(
                latest["demand_mw"]
            )
            / 1000
        ),
        title=(
            "Current demand relative "
            "to this time of day"
        ),
        value_label="Demand",
    )


# ------------------------------------------------------------
# 5. Generation mix doughnut + centre statistic
# ------------------------------------------------------------

def build_generation_doughnut_summary(
    generation: pd.DataFrame,
) -> alt.TopLevelMixin:
    """
    Latest generation mix with total tracked generation in the centre.
    """
    mix, latest_time = (
        _latest_generation_snapshot(
            generation
        )
    )

    total_gw = mix[
        "generation_gw"
    ].sum()

    doughnut = (
        alt.Chart(mix)
        .mark_arc(
            innerRadius=78,
            outerRadius=135,
        )
        .encode(
            theta=alt.Theta(
                "generation_gw:Q"
            ),
            color=alt.Color(
                "fuel_type:N",
                title="Fuel",
            ),
            order=alt.Order(
                "generation_gw:Q",
                sort="descending",
            ),
            tooltip=[
                alt.Tooltip(
                    "fuel_type:N",
                    title="Fuel",
                ),
                alt.Tooltip(
                    "generation_gw:Q",
                    title="Generation (GW)",
                    format=".2f",
                ),
                alt.Tooltip(
                    "share:Q",
                    title="Share",
                    format=".1%",
                ),
            ],
        )
    )

    total_text = (
        alt.Chart(
            pd.DataFrame(
                {
                    "label": [
                        f"{total_gw:.1f} GW"
                    ]
                }
            )
        )
        .mark_text(
            fontSize=25,
            fontWeight="bold",
            dy=-7,
        )
        .encode(
            text="label:N"
        )
    )

    caption = (
        alt.Chart(
            pd.DataFrame(
                {
                    "label": [
                        "tracked generation"
                    ]
                }
            )
        )
        .mark_text(
            fontSize=12,
            dy=18,
        )
        .encode(
            text="label:N"
        )
    )

    local_time = latest_time.tz_convert(
        "Europe/London"
    )

    return (
        doughnut
        + total_text
        + caption
    ).properties(
        title=(
            "Latest generation mix — "
            f"{local_time.strftime('%d %b · %H:%M %Z')}"
        ),
        height=340,
    )


# ------------------------------------------------------------
# 6. Latest generation ranking
# ------------------------------------------------------------

def build_generation_ranking_graph(
    generation: pd.DataFrame,
) -> alt.TopLevelMixin:
    """
    Rank the latest available generation sources by output.
    """
    mix, latest_time = (
        _latest_generation_snapshot(
            generation
        )
    )

    bars = (
        alt.Chart(mix)
        .mark_bar(
            cornerRadiusEnd=4,
        )
        .encode(
            x=alt.X(
                "generation_gw:Q",
                title="Generation (GW)",
            ),
            y=alt.Y(
                "fuel_type:N",
                title=None,
                sort="-x",
            ),
            tooltip=[
                "fuel_type:N",
                alt.Tooltip(
                    "generation_gw:Q",
                    title="Generation (GW)",
                    format=".2f",
                ),
                alt.Tooltip(
                    "share:Q",
                    title="Share",
                    format=".1%",
                ),
            ],
        )
    )

    labels = (
        alt.Chart(mix)
        .mark_text(
            align="left",
            dx=5,
        )
        .encode(
            x="generation_gw:Q",
            y=alt.Y(
                "fuel_type:N",
                sort="-x",
            ),
            text=alt.Text(
                "generation_gw:Q",
                format=".1f",
            ),
        )
    )

    local_time = latest_time.tz_convert(
        "Europe/London"
    )

    return (
        bars
        + labels
    ).properties(
        title=(
            "Generation ranking — "
            f"{local_time.strftime('%d %b · %H:%M %Z')}"
        ),
        height=300,
    )


# ------------------------------------------------------------
# 7. Fuel movement
# ------------------------------------------------------------

def build_generation_change_graph(
    generation: pd.DataFrame,
    lookback_hours: int = 4,
) -> alt.TopLevelMixin:
    """
    Show which tracked fuel types changed most over the lookback window.
    """
    wide = generation.copy()

    if "event_time_utc" not in wide.columns:
        wide = wide.reset_index()

    _require_columns(
        wide,
        ["event_time_utc"],
        "Generation movement",
    )

    wide[
        "event_time_utc"
    ] = pd.to_datetime(
        wide["event_time_utc"],
        utc=True,
    )

    wide = wide.sort_values(
        "event_time_utc"
    )

    latest_time = wide[
        "event_time_utc"
    ].max()

    comparison_time = (
        latest_time
        - pd.Timedelta(
            hours=lookback_hours
        )
    )

    earlier = wide[
        wide["event_time_utc"]
        <= comparison_time
    ]

    if earlier.empty:
        raise ValueError(
            "Generation movement does not "
            "have enough history for the "
            f"{lookback_hours}-hour lookback."
        )

    latest_row = wide.iloc[-1]
    earlier_row = earlier.iloc[-1]

    fuels = [
        column
        for column in wide.columns
        if column != "event_time_utc"
    ]

    rows = []

    for fuel in fuels:
        if (
            pd.isna(
                latest_row[fuel]
            )
            or pd.isna(
                earlier_row[fuel]
            )
        ):
            continue

        delta_gw = (
            float(
                latest_row[fuel]
            )
            - float(
                earlier_row[fuel]
            )
        ) / 1000

        rows.append(
            {
                "fuel_type": fuel,
                "delta_gw": delta_gw,
                "direction": (
                    "Increased"
                    if delta_gw > 0
                    else (
                        "Decreased"
                        if delta_gw < 0
                        else "Unchanged"
                    )
                ),
            }
        )

    movement = pd.DataFrame(
        rows
    )

    movement[
        "absolute_change"
    ] = movement[
        "delta_gw"
    ].abs()

    movement = movement.sort_values(
        "absolute_change",
        ascending=False,
    )

    zero = (
        alt.Chart(
            pd.DataFrame(
                {"zero": [0]}
            )
        )
        .mark_rule()
        .encode(
            x="zero:Q"
        )
    )

    bars = (
        alt.Chart(movement)
        .mark_bar()
        .encode(
            x=alt.X(
                "delta_gw:Q",
                title=(
                    f"Change over "
                    f"{lookback_hours}h (GW)"
                ),
            ),
            y=alt.Y(
                "fuel_type:N",
                title=None,
                sort="-x",
            ),
            color=alt.Color(
                "direction:N",
                title=None,
            ),
            tooltip=[
                "fuel_type:N",
                alt.Tooltip(
                    "delta_gw:Q",
                    title="Change (GW)",
                    format="+.2f",
                ),
            ],
        )
    )

    return (
        bars
        + zero
    ).properties(
        title=(
            "Which generation sources "
            "are moving?"
        ),
        height=300,
    )


# ------------------------------------------------------------
# 8. Demand vs DRM relationship
# ------------------------------------------------------------

def build_margin_demand_scatter(
    margin: pd.DataFrame,
    demand: pd.DataFrame,
) -> alt.TopLevelMixin:
    """
    Historical relationship between demand and DRM using matching
    half-hour event timestamps.
    """
    _require_columns(
        margin,
        [
            "event_time_utc",
            "derated_margin_mw",
        ],
        "Margin-demand scatter",
    )

    _require_columns(
        demand,
        [
            "event_time_utc",
            "demand_mw",
        ],
        "Margin-demand scatter",
    )

    margin_data = margin[
        [
            "event_time_utc",
            "derated_margin_mw",
        ]
    ].copy()

    demand_data = demand[
        [
            "event_time_utc",
            "demand_mw",
        ]
    ].copy()

    margin_data[
        "event_time_utc"
    ] = pd.to_datetime(
        margin_data["event_time_utc"],
        utc=True,
    )

    demand_data[
        "event_time_utc"
    ] = pd.to_datetime(
        demand_data["event_time_utc"],
        utc=True,
    )

    data = margin_data.merge(
        demand_data,
        on="event_time_utc",
        how="inner",
    ).dropna()

    data["drm_gw"] = (
        data["derated_margin_mw"]
        / 1000
    )

    data["demand_gw"] = (
        data["demand_mw"]
        / 1000
    )

    points = (
        alt.Chart(data)
        .mark_circle(
            opacity=0.35,
            size=45,
        )
        .encode(
            x=alt.X(
                "demand_gw:Q",
                title="Demand (GW)",
            ),
            y=alt.Y(
                "drm_gw:Q",
                title="De-rated margin (GW)",
            ),
            tooltip=[
                alt.Tooltip(
                    "event_time_utc:T",
                    title="Time",
                ),
                alt.Tooltip(
                    "demand_gw:Q",
                    title="Demand",
                    format=".1f",
                ),
                alt.Tooltip(
                    "drm_gw:Q",
                    title="DRM",
                    format=".1f",
                ),
            ],
        )
    )

    if data.empty:
        return points.properties(
            title="Demand vs de-rated margin",
            height=320,
        )

    latest = data.tail(1)

    latest_point = (
        alt.Chart(latest)
        .mark_point(
            filled=True,
            size=230,
        )
        .encode(
            x="demand_gw:Q",
            y="drm_gw:Q",
            tooltip=[
                alt.Tooltip(
                    "event_time_utc:T",
                    title="Latest matching point",
                ),
                alt.Tooltip(
                    "demand_gw:Q",
                    title="Demand",
                    format=".1f",
                ),
                alt.Tooltip(
                    "drm_gw:Q",
                    title="DRM",
                    format=".1f",
                ),
            ],
        )
    )

    return (
        points
        + latest_point
    ).properties(
        title="Demand vs de-rated margin",
        height=320,
    )


# ------------------------------------------------------------
# 9. Forecast error direction
# ------------------------------------------------------------

def build_error_direction_graph(
    predictions: pd.DataFrame,
) -> alt.TopLevelMixin:
    """
    Summarise how often the model predicts above or below the actual DRM.

    Assumes error_mw = predicted - actual.
    """
    _require_columns(
        predictions,
        ["error_mw"],
        "Error direction",
    )

    data = predictions[
        ["error_mw"]
    ].dropna().copy()

    data["direction"] = data[
        "error_mw"
    ].map(
        lambda value: (
            "Predicted too high"
            if value > 0
            else (
                "Predicted too low"
                if value < 0
                else "Exact"
            )
        )
    )

    summary = (
        data.groupby(
            "direction",
            as_index=False,
        )
        .agg(
            count=(
                "error_mw",
                "size",
            ),
            mean_error_mw=(
                "error_mw",
                "mean",
            ),
        )
    )

    summary["signed_count"] = (
        summary.apply(
            lambda row: (
                -row["count"]
                if row["direction"]
                == "Predicted too low"
                else row["count"]
            ),
            axis=1,
        )
    )

    summary["mean_error_gw"] = (
        summary[
            "mean_error_mw"
        ]
        / 1000
    )

    zero = (
        alt.Chart(
            pd.DataFrame(
                {"zero": [0]}
            )
        )
        .mark_rule()
        .encode(
            x="zero:Q"
        )
    )

    bars = (
        alt.Chart(summary)
        .mark_bar()
        .encode(
            x=alt.X(
                "signed_count:Q",
                title=(
                    "Observations "
                    "(left = predicted too low)"
                ),
            ),
            y=alt.Y(
                "direction:N",
                title=None,
            ),
            color=alt.Color(
                "direction:N",
                title=None,
            ),
            tooltip=[
                "direction:N",
                alt.Tooltip(
                    "count:Q",
                    title="Observations",
                    format=",.0f",
                ),
                alt.Tooltip(
                    "mean_error_gw:Q",
                    title="Mean error (GW)",
                    format="+.2f",
                ),
            ],
        )
    )

    return (
        bars
        + zero
    ).properties(
        title=(
            "Does the model tend to "
            "predict high or low?"
        ),
        height=220,
    )


# ------------------------------------------------------------
# 10. Model vs persistence
# ------------------------------------------------------------

def _find_baseline_column(
    predictions: pd.DataFrame,
) -> str:
    candidates = [
        "baseline_drm_yesterday_mw",
        "baseline_prediction_mw",
        "persistence_drm_mw",
        "baseline_drm_mw",
    ]

    for column in candidates:
        if column in predictions.columns:
            return column

    raise ValueError(
        "Model-vs-persistence chart needs a "
        "baseline prediction column. Expected "
        f"one of: {candidates}"
    )


def build_model_vs_persistence_graph(
    predictions: pd.DataFrame,
    baseline_col: str | None = None,
) -> alt.TopLevelMixin:
    """
    Dumbbell comparison of model and persistence MAE overall and for
    the lowest 10% of actual DRM observations.
    """
    _require_columns(
        predictions,
        [
            "target_drm_mw",
            "predicted_drm_mw",
        ],
        "Model-vs-persistence",
    )

    if baseline_col is None:
        baseline_col = (
            _find_baseline_column(
                predictions
            )
        )

    _require_columns(
        predictions,
        [baseline_col],
        "Model-vs-persistence",
    )

    data = predictions[
        [
            "target_drm_mw",
            "predicted_drm_mw",
            baseline_col,
        ]
    ].dropna().copy()

    data["model_abs_error_mw"] = (
        data["predicted_drm_mw"]
        - data["target_drm_mw"]
    ).abs()

    data["baseline_abs_error_mw"] = (
        data[baseline_col]
        - data["target_drm_mw"]
    ).abs()

    threshold = data[
        "target_drm_mw"
    ].quantile(
        0.10
    )

    segments = [
        (
            "Overall",
            data,
        ),
        (
            "Lowest 10% DRM",
            data[
                data[
                    "target_drm_mw"
                ]
                <= threshold
            ],
        ),
    ]

    rows = []

    for label, segment in segments:
        if segment.empty:
            continue

        rows.append(
            {
                "segment": label,
                "model_mae_gw": (
                    segment[
                        "model_abs_error_mw"
                    ].mean()
                    / 1000
                ),
                "baseline_mae_gw": (
                    segment[
                        "baseline_abs_error_mw"
                    ].mean()
                    / 1000
                ),
            }
        )

    compare = pd.DataFrame(
        rows
    )

    connector = (
        alt.Chart(compare)
        .mark_rule(
            strokeWidth=4,
        )
        .encode(
            x=alt.X(
                "model_mae_gw:Q",
                title="Mean absolute error (GW)",
            ),
            x2="baseline_mae_gw:Q",
            y=alt.Y(
                "segment:N",
                title=None,
                sort=[
                    "Overall",
                    "Lowest 10% DRM",
                ],
            ),
        )
    )

    points = compare.melt(
        id_vars="segment",
        value_vars=[
            "model_mae_gw",
            "baseline_mae_gw",
        ],
        var_name="method",
        value_name="mae_gw",
    )

    points["method"] = (
        points["method"]
        .map(
            {
                "model_mae_gw":
                    "Ridge",
                "baseline_mae_gw":
                    "Persistence",
            }
        )
    )

    dots = (
        alt.Chart(points)
        .mark_point(
            filled=True,
            size=190,
        )
        .encode(
            x="mae_gw:Q",
            y=alt.Y(
                "segment:N",
                sort=[
                    "Overall",
                    "Lowest 10% DRM",
                ],
            ),
            shape=alt.Shape(
                "method:N",
                title=None,
            ),
            tooltip=[
                "segment:N",
                "method:N",
                alt.Tooltip(
                    "mae_gw:Q",
                    title="MAE (GW)",
                    format=".2f",
                ),
            ],
        )
    )

    return (
        connector
        + dots
    ).properties(
        title=(
            "Ridge vs persistence "
            "forecast error"
        ),
        height=180,
    )


# ------------------------------------------------------------
# Future concept: multi-horizon confidence fan
# ------------------------------------------------------------

def build_confidence_fan_graph(
    future_predictions: pd.DataFrame,
    recent_margin: pd.DataFrame | None = None,
) -> alt.TopLevelMixin:
    """
    Build a multi-horizon DRM prediction fan.

    IMPORTANT:
    This visual should only be used once the forecasting pipeline
    produces multiple future horizons AND calibrated prediction
    intervals. It must not fabricate uncertainty around the existing
    single T+24h Ridge prediction.

    Required future_predictions columns:
        target_time_utc
        predicted_drm_mw
        lower_50_mw
        upper_50_mw
        lower_80_mw
        upper_80_mw
        lower_95_mw
        upper_95_mw
    """
    required = [
        "target_time_utc",
        "predicted_drm_mw",
        "lower_50_mw",
        "upper_50_mw",
        "lower_80_mw",
        "upper_80_mw",
        "lower_95_mw",
        "upper_95_mw",
    ]

    _require_columns(
        future_predictions,
        required,
        "Confidence fan",
    )

    future = future_predictions[
        required
    ].dropna().copy()

    future[
        "target_time_utc"
    ] = pd.to_datetime(
        future["target_time_utc"],
        utc=True,
    )

    for column in required[1:]:
        future[
            column.replace(
                "_mw",
                "_gw",
            )
        ] = (
            future[column]
            / 1000
        )

    band_95 = (
        alt.Chart(future)
        .mark_area(
            opacity=0.12,
        )
        .encode(
            x=alt.X(
                "target_time_utc:T",
                title=None,
            ),
            y=alt.Y(
                "lower_95_gw:Q",
                title="De-rated margin (GW)",
                scale=alt.Scale(
                    zero=False
                ),
            ),
            y2="upper_95_gw:Q",
            tooltip=[
                alt.Tooltip(
                    "target_time_utc:T",
                    title="Target",
                ),
                alt.Tooltip(
                    "lower_95_gw:Q",
                    title="95% lower",
                    format=".1f",
                ),
                alt.Tooltip(
                    "upper_95_gw:Q",
                    title="95% upper",
                    format=".1f",
                ),
            ],
        )
    )

    band_80 = (
        alt.Chart(future)
        .mark_area(
            opacity=0.20,
        )
        .encode(
            x="target_time_utc:T",
            y="lower_80_gw:Q",
            y2="upper_80_gw:Q",
        )
    )

    band_50 = (
        alt.Chart(future)
        .mark_area(
            opacity=0.32,
        )
        .encode(
            x="target_time_utc:T",
            y="lower_50_gw:Q",
            y2="upper_50_gw:Q",
        )
    )

    prediction_line = (
        alt.Chart(future)
        .mark_line(
            strokeWidth=3,
        )
        .encode(
            x="target_time_utc:T",
            y="predicted_drm_gw:Q",
            tooltip=[
                alt.Tooltip(
                    "target_time_utc:T",
                    title="Target",
                ),
                alt.Tooltip(
                    "predicted_drm_gw:Q",
                    title="Predicted DRM",
                    format=".1f",
                ),
            ],
        )
    )

    chart = (
        band_95
        + band_80
        + band_50
        + prediction_line
    )

    if (
        recent_margin is not None
        and not recent_margin.empty
    ):
        _require_columns(
            recent_margin,
            [
                "event_time_utc",
                "derated_margin_mw",
            ],
            "Confidence fan history",
        )

        history = _series_gw(
            recent_margin,
            "event_time_utc",
            "derated_margin_mw",
            "drm_gw",
        )

        history_line = (
            alt.Chart(history)
            .mark_line(
                strokeWidth=2,
            )
            .encode(
                x="event_time_utc:T",
                y="drm_gw:Q",
                tooltip=[
                    alt.Tooltip(
                        "event_time_utc:T",
                        title="Observed time",
                    ),
                    alt.Tooltip(
                        "drm_gw:Q",
                        title="Observed DRM",
                        format=".1f",
                    ),
                ],
            )
        )

        transition_time = future[
            "target_time_utc"
        ].min()

        transition = (
            alt.Chart(
                pd.DataFrame(
                    {
                        "transition": [
                            transition_time
                        ]
                    }
                )
            )
            .mark_rule(
                strokeDash=[5, 5],
            )
            .encode(
                x="transition:T"
            )
        )

        chart = (
            history_line
            + transition
            + chart
        )

    return chart.properties(
        title=(
            "Observed DRM transitioning "
            "into multi-horizon forecast uncertainty"
        ),
        height=340,
    )


def build_concept_graphs(
    forecast: dict,
    margin_history: pd.DataFrame,
    demand_history: pd.DataFrame,
    generation: pd.DataFrame,
    predictions: pd.DataFrame,
    confidence_fan_data: pd.DataFrame | None = None,
) -> ChartSet:
    """
    Convenience builder for the ten experimental concepts.

    Confidence fan is included only when future multi-horizon
    prediction-interval data is supplied.
    """
    charts: ChartSet = {
        "forecast_percentile":
            build_forecast_percentile_graph(
                forecast,
                margin_history,
            ),

        "drm_change_bridge":
            build_drm_change_bridge(
                forecast
            ),

        "typical_day_demand":
            build_typical_day_demand_graph(
                demand_history
            ),

        "current_demand_percentile":
            build_current_demand_percentile_graph(
                demand_history
            ),

        "generation_doughnut_summary":
            build_generation_doughnut_summary(
                generation
            ),

        "generation_ranking":
            build_generation_ranking_graph(
                generation
            ),

        "generation_change":
            build_generation_change_graph(
                generation
            ),

        "margin_demand_scatter":
            build_margin_demand_scatter(
                margin_history,
                demand_history,
            ),

        "error_direction":
            build_error_direction_graph(
                predictions
            ),

        "model_vs_persistence":
            build_model_vs_persistence_graph(
                predictions
            ),
    }

    if confidence_fan_data is not None:
        charts["confidence_fan"] = (
            build_confidence_fan_graph(
                confidence_fan_data,
                recent_margin=margin_history,
            )
        )

    return charts


# ============================================================
# Dashboard-selected chart implementations
# ============================================================

FUEL_COLOURS = {
    "WIND": "#4E79A7",
    "CCGT": "#E15759",
    "NUCLEAR": "#F1CE63",
    "BIOMASS": "#59A14F",
    "NPSHYD": "#76B7B2",
    "PS": "#B07AA1",
    "OCGT": "#FF9DA7",
    "OIL": "#9C755F",
    "COAL": "#79706E",
    "OTHER": "#BAB0AC",
    "INTELEC": "#86BCB6",
    "INTEW": "#8CD17D",
    "INTFR": "#499894",
    "INTGRNL": "#D4A6C8",
    "INTIFA2": "#FABFD2",
    "INTIRL": "#B6992D",
    "INTNED": "#D37295",
    "INTNEM": "#A0CBE8",
    "INTNSL": "#FFBE7D",
    "INTVKL": "#8F7C6E",
}


def _fuel_scale(values: pd.Series) -> alt.Scale:
    domain = [
        value
        for value in values.dropna().unique().tolist()
    ]

    colours = [
        FUEL_COLOURS.get(
            value,
            "#A7A7A7",
        )
        for value in domain
    ]

    return alt.Scale(
        domain=domain,
        range=colours,
    )


def build_demand_settlement_bars(
    demand: pd.DataFrame,
) -> alt.TopLevelMixin:
    """
    Settlement-period demand bars.

    Internal missing half-hours are linearly interpolated for display only
    and explicitly labelled Estimated. Leading/trailing gaps remain blank.
    Nothing is written back to the source data.
    """
    _require_columns(
        demand,
        [
            "event_time_utc",
            "demand_mw",
        ],
        "Demand settlement bars",
    )

    data = demand[
        [
            "event_time_utc",
            "demand_mw",
        ]
    ].copy()

    data["event_time_utc"] = pd.to_datetime(
        data["event_time_utc"],
        utc=True,
    )

    data = (
        data.sort_values(
            "event_time_utc"
        )
        .drop_duplicates(
            "event_time_utc",
            keep="last",
        )
        .set_index(
            "event_time_utc"
        )
    )

    if data.empty:
        return (
            alt.Chart(
                pd.DataFrame(
                    {
                        "message": [
                            "No demand data"
                        ]
                    }
                )
            )
            .mark_text()
            .encode(
                text="message:N"
            )
            .properties(
                height=300
            )
        )

    complete_index = pd.date_range(
        start=data.index.min(),
        end=data.index.max(),
        freq="30min",
        tz="UTC",
    )

    data = data.reindex(
        complete_index
    )

    data.index.name = (
        "event_time_utc"
    )

    data["data_type"] = (
        data["demand_mw"]
        .notna()
        .map(
            {
                True: "Observed",
                False: "Estimated",
            }
        )
    )

    data["display_demand_mw"] = (
        data["demand_mw"]
        .interpolate(
            method="time",
            limit_area="inside",
        )
    )

    data = (
        data.reset_index()
        .dropna(
            subset=[
                "display_demand_mw"
            ]
        )
    )

    data["demand_gw"] = (
        data["display_demand_mw"]
        / 1000
    )

    return (
        alt.Chart(data)
        .mark_bar(
            size=5,
        )
        .encode(
            x=alt.X(
                "event_time_utc:T",
                title=None,
                axis=alt.Axis(
                    labelAngle=0,
                ),
            ),
            y=alt.Y(
                "demand_gw:Q",
                title="Demand (GW)",
                scale=alt.Scale(
                    zero=False,
                ),
            ),
            color=alt.Color(
                "data_type:N",
                title="Data",
                scale=alt.Scale(
                    domain=[
                        "Observed",
                        "Estimated",
                    ],
                    range=[
                        "#4E79A7",
                        "#F2A541",
                    ],
                ),
            ),
            tooltip=[
                alt.Tooltip(
                    "event_time_utc:T",
                    title="Settlement period",
                ),
                alt.Tooltip(
                    "demand_gw:Q",
                    title="Demand",
                    format=".1f",
                ),
                alt.Tooltip(
                    "data_type:N",
                    title="Data",
                ),
            ],
        )
        .properties(
            title=(
                "Electricity demand by "
                "settlement period"
            ),
            height=300,
        )
    )


def build_generation_doughnut_dashboard(
    generation: pd.DataFrame,
    minimum_share: float = 0.025,
) -> alt.TopLevelMixin:
    """
    Current generation mix with:
      - small categories grouped into Other,
      - semantic fuel colours,
      - total positive tracked generation in the centre,
      - outside text labels for readable major contributors.
    """
    mix, latest_time = (
        _latest_generation_snapshot(
            generation
        )
    )

    if mix.empty:
        raise ValueError(
            "No generation mix available."
        )

    small = (
        mix["share"]
        < minimum_share
    )

    if small.any():
        other_gw = mix.loc[
            small,
            "generation_gw",
        ].sum()

        mix = mix.loc[
            ~small
        ].copy()

        if other_gw > 0:
            mix = pd.concat(
                [
                    mix,
                    pd.DataFrame(
                        {
                            "fuel_type": [
                                "OTHER"
                            ],
                            "generation_gw": [
                                other_gw
                            ],
                        }
                    ),
                ],
                ignore_index=True,
            )

    mix = (
        mix.groupby(
            "fuel_type",
            as_index=False,
        )["generation_gw"]
        .sum()
    )

    total_gw = mix[
        "generation_gw"
    ].sum()

    mix["share"] = (
        mix["generation_gw"]
        / total_gw
    )

    mix = mix.sort_values(
        "generation_gw",
        ascending=False,
    ).reset_index(
        drop=True
    )

    mix["label"] = (
        mix["fuel_type"]
        + " · "
        + (
            mix["share"]
            * 100
        ).round(0).astype(int).astype(str)
        + "%"
    )

    scale = _fuel_scale(
        mix["fuel_type"]
    )

    doughnut = (
        alt.Chart(mix)
        .mark_arc(
            innerRadius=78,
            outerRadius=130,
            stroke="white",
            strokeWidth=1,
        )
        .encode(
            theta=alt.Theta(
                "generation_gw:Q",
            ),
            color=alt.Color(
                "fuel_type:N",
                title="Fuel",
                scale=scale,
                sort=(
                    mix[
                        "fuel_type"
                    ].tolist()
                ),
            ),
            order=alt.Order(
                "generation_gw:Q",
                sort="descending",
            ),
            tooltip=[
                alt.Tooltip(
                    "fuel_type:N",
                    title="Fuel",
                ),
                alt.Tooltip(
                    "generation_gw:Q",
                    title="Generation",
                    format=".2f",
                ),
                alt.Tooltip(
                    "share:Q",
                    title="Share",
                    format=".1%",
                ),
            ],
        )
    )

    outside_labels = (
        alt.Chart(mix)
        .mark_text(
            radius=158,
            fontSize=11,
        )
        .encode(
            theta=alt.Theta(
                "generation_gw:Q",
                stack=True,
            ),
            text="label:N",
            color=alt.Color(
                "fuel_type:N",
                scale=scale,
                legend=None,
            ),
        )
    )

    centre = (
        alt.Chart(
            pd.DataFrame(
                {
                    "value": [
                        f"{total_gw:.1f} GW"
                    ],
                    "caption": [
                        "tracked output"
                    ],
                }
            )
        )
        .mark_text(
            fontSize=24,
            fontWeight="bold",
            dy=-8,
        )
        .encode(
            text="value:N"
        )
    )

    centre_caption = (
        alt.Chart(
            pd.DataFrame(
                {
                    "caption": [
                        "tracked output"
                    ]
                }
            )
        )
        .mark_text(
            fontSize=11,
            dy=18,
        )
        .encode(
            text="caption:N"
        )
    )

    local_time = (
        latest_time.tz_convert(
            "Europe/London"
        )
    )

    return (
        doughnut
        + outside_labels
        + centre
        + centre_caption
    ).properties(
        title=(
            "Current generation mix · "
            f"{local_time.strftime('%d %b · %H:%M %Z')}"
        ),
        height=360,
    )


def build_generation_change_dashboard(
    generation: pd.DataFrame,
    lookback_hours: int = 4,
    top_n: int = 8,
) -> alt.TopLevelMixin:
    """
    Biggest generation movements over the lookback period.

    Direction is already encoded by the zero baseline, so colour is used
    for movement strength rather than increase/decrease.
    """
    wide = generation.copy()

    if "event_time_utc" not in wide.columns:
        wide = wide.reset_index()

    _require_columns(
        wide,
        ["event_time_utc"],
        "Generation movement",
    )

    wide["event_time_utc"] = pd.to_datetime(
        wide["event_time_utc"],
        utc=True,
    )

    wide = wide.sort_values(
        "event_time_utc"
    )

    latest_time = wide[
        "event_time_utc"
    ].max()

    earlier = wide[
        wide["event_time_utc"]
        <= (
            latest_time
            - pd.Timedelta(
                hours=lookback_hours
            )
        )
    ]

    if earlier.empty:
        raise ValueError(
            "Not enough generation history "
            "for movement chart."
        )

    latest_row = wide.iloc[-1]
    earlier_row = earlier.iloc[-1]

    rows = []

    for fuel in [
        column
        for column in wide.columns
        if column
        != "event_time_utc"
    ]:
        latest_value = (
            latest_row[fuel]
        )

        earlier_value = (
            earlier_row[fuel]
        )

        if (
            pd.isna(latest_value)
            or pd.isna(
                earlier_value
            )
        ):
            continue

        delta_gw = (
            float(latest_value)
            - float(earlier_value)
        ) / 1000

        rows.append(
            {
                "fuel_type": fuel,
                "delta_gw": delta_gw,
                "absolute_change": abs(
                    delta_gw
                ),
            }
        )

    movement = (
        pd.DataFrame(rows)
        .sort_values(
            "absolute_change",
            ascending=False,
        )
        .head(top_n)
    )

    if movement.empty:
        raise ValueError(
            "No generation movements available."
        )

    max_change = (
        movement[
            "absolute_change"
        ].max()
    )

    movement["movement_strength"] = (
        movement[
            "absolute_change"
        ]
        / max_change
        if max_change
        else 0
    )

    zero = (
        alt.Chart(
            pd.DataFrame(
                {
                    "zero": [0]
                }
            )
        )
        .mark_rule(
            strokeWidth=1,
        )
        .encode(
            x="zero:Q"
        )
    )

    bars = (
        alt.Chart(movement)
        .mark_bar()
        .encode(
            x=alt.X(
                "delta_gw:Q",
                title=(
                    f"Change over "
                    f"{lookback_hours} hours (GW)"
                ),
            ),
            y=alt.Y(
                "fuel_type:N",
                title=None,
                sort="-x",
            ),
            color=alt.Color(
                "movement_strength:Q",
                title="Movement strength",
                scale=alt.Scale(
                    scheme="oranges",
                ),
            ),
            tooltip=[
                alt.Tooltip(
                    "fuel_type:N",
                    title="Fuel",
                ),
                alt.Tooltip(
                    "delta_gw:Q",
                    title="Change",
                    format="+.2f",
                ),
            ],
        )
    )

    return (
        bars
        + zero
    ).properties(
        title=(
            "Biggest generation movements"
        ),
        height=330,
    )


def build_model_vs_persistence_vertical(
    predictions: pd.DataFrame,
    baseline_col: str | None = None,
) -> alt.TopLevelMixin:
    """
    Vertical comparison requested during concept review.

    Starts the y-axis close to the observed MAE range instead of at zero so
    the model improvement is visually legible. Exact values remain in labels.
    """
    _require_columns(
        predictions,
        [
            "target_drm_mw",
            "predicted_drm_mw",
        ],
        "Model-vs-persistence",
    )

    if baseline_col is None:
        baseline_col = (
            _find_baseline_column(
                predictions
            )
        )

    _require_columns(
        predictions,
        [baseline_col],
        "Model-vs-persistence",
    )

    data = predictions[
        [
            "target_drm_mw",
            "predicted_drm_mw",
            baseline_col,
        ]
    ].dropna().copy()

    data["model_abs_error_mw"] = (
        data["predicted_drm_mw"]
        - data["target_drm_mw"]
    ).abs()

    data["baseline_abs_error_mw"] = (
        data[baseline_col]
        - data["target_drm_mw"]
    ).abs()

    threshold = (
        data[
            "target_drm_mw"
        ].quantile(
            0.10
        )
    )

    rows = []

    for label, segment in [
        (
            "Overall",
            data,
        ),
        (
            "Lowest 10% DRM",
            data[
                data[
                    "target_drm_mw"
                ]
                <= threshold
            ],
        ),
    ]:
        if segment.empty:
            continue

        rows.extend(
            [
                {
                    "segment": label,
                    "method": "Persistence",
                    "mae_gw": (
                        segment[
                            "baseline_abs_error_mw"
                        ].mean()
                        / 1000
                    ),
                },
                {
                    "segment": label,
                    "method": "Ridge",
                    "mae_gw": (
                        segment[
                            "model_abs_error_mw"
                        ].mean()
                        / 1000
                    ),
                },
            ]
        )

    compare = pd.DataFrame(
        rows
    )

    minimum = float(
        compare["mae_gw"].min()
    )

    maximum = float(
        compare["mae_gw"].max()
    )

    padding = max(
        (
            maximum
            - minimum
        )
        * 0.35,
        0.35,
    )

    lower_bound = max(
        0,
        minimum - padding,
    )

    upper_bound = (
        maximum
        + padding
    )

    lines = (
        alt.Chart(compare)
        .mark_line(
            strokeWidth=4,
        )
        .encode(
            x=alt.X(
                "segment:N",
                title=None,
                sort=[
                    "Overall",
                    "Lowest 10% DRM",
                ],
            ),
            y=alt.Y(
                "mae_gw:Q",
                title="Mean absolute error (GW)",
                scale=alt.Scale(
                    domain=[
                        lower_bound,
                        upper_bound,
                    ],
                    zero=False,
                ),
            ),
            detail="method:N",
            color=alt.Color(
                "method:N",
                title=None,
            ),
        )
    )

    points = (
        alt.Chart(compare)
        .mark_point(
            filled=True,
            size=180,
        )
        .encode(
            x=alt.X(
                "segment:N",
                sort=[
                    "Overall",
                    "Lowest 10% DRM",
                ],
            ),
            y="mae_gw:Q",
            color=alt.Color(
                "method:N",
                title=None,
            ),
            tooltip=[
                "segment:N",
                "method:N",
                alt.Tooltip(
                    "mae_gw:Q",
                    title="MAE",
                    format=".2f",
                ),
            ],
        )
    )

    labels = (
        alt.Chart(compare)
        .mark_text(
            dy=-14,
            fontSize=12,
        )
        .encode(
            x=alt.X(
                "segment:N",
                sort=[
                    "Overall",
                    "Lowest 10% DRM",
                ],
            ),
            y="mae_gw:Q",
            text=alt.Text(
                "mae_gw:Q",
                format=".2f",
            ),
            color=alt.Color(
                "method:N",
                legend=None,
            ),
        )
    )

    return (
        lines
        + points
        + labels
    ).properties(
        title=(
            "Ridge vs persistence · lower is better"
        ),
        height=300,
    )


def build_typical_day_demand_dashboard(
    demand_history: pd.DataFrame,
) -> alt.TopLevelMixin:
    """
    Dashboard version of the typical-day concept.

    The legend explicitly distinguishes the latest profile from the
    historical median, while a light IQR band shows the typical range.
    """
    _require_columns(
        demand_history,
        [
            "event_time_utc",
            "demand_mw",
        ],
        "Typical-day demand",
    )

    data = demand_history[
        [
            "event_time_utc",
            "demand_mw",
        ]
    ].dropna().copy()

    data["event_time_utc"] = pd.to_datetime(
        data["event_time_utc"],
        utc=True,
    )

    local = data[
        "event_time_utc"
    ].dt.tz_convert(
        "Europe/London"
    )

    data["local_date"] = (
        local.dt.date
    )

    data["settlement_slot"] = (
        local.dt.hour * 2
        + local.dt.minute // 30
        + 1
    )

    data["demand_gw"] = (
        data["demand_mw"]
        / 1000
    )

    latest_date = data[
        "local_date"
    ].max()

    reference = data[
        data["local_date"]
        < latest_date
    ]

    if reference.empty:
        raise ValueError(
            "Typical-day demand needs at least "
            "one earlier local day for comparison."
        )

    typical = (
        reference.groupby(
            "settlement_slot"
        )["demand_gw"]
        .agg(
            q25=lambda values: (
                values.quantile(
                    0.25
                )
            ),
            median="median",
            q75=lambda values: (
                values.quantile(
                    0.75
                )
            ),
        )
        .reset_index()
    )

    latest = data[
        data["local_date"]
        == latest_date
    ][
        [
            "settlement_slot",
            "demand_gw",
        ]
    ].copy()

    line_data = pd.concat(
        [
            typical[
                [
                    "settlement_slot",
                    "median",
                ]
            ].rename(
                columns={
                    "median":
                        "demand_gw"
                }
            ).assign(
                series=(
                    "Historical median"
                )
            ),

            latest.assign(
                series=(
                    "Latest profile"
                )
            ),
        ],
        ignore_index=True,
    )

    band = (
        alt.Chart(typical)
        .mark_area(
            opacity=0.18,
            color="#9E9E9E",
        )
        .encode(
            x=alt.X(
                "settlement_slot:Q",
                title="Settlement period",
                scale=alt.Scale(
                    domain=[
                        1,
                        48,
                    ]
                ),
            ),
            y=alt.Y(
                "q25:Q",
                title="Demand (GW)",
                scale=alt.Scale(
                    zero=False,
                ),
            ),
            y2="q75:Q",
            tooltip=[
                alt.Tooltip(
                    "settlement_slot:Q",
                    title="Settlement period",
                ),
                alt.Tooltip(
                    "q25:Q",
                    title="25th percentile",
                    format=".1f",
                ),
                alt.Tooltip(
                    "q75:Q",
                    title="75th percentile",
                    format=".1f",
                ),
            ],
        )
    )

    lines = (
        alt.Chart(line_data)
        .mark_line(
            strokeWidth=3,
        )
        .encode(
            x=alt.X(
                "settlement_slot:Q",
                title="Settlement period",
            ),
            y=alt.Y(
                "demand_gw:Q",
                title="Demand (GW)",
            ),
            color=alt.Color(
                "series:N",
                title=None,
                scale=alt.Scale(
                    domain=[
                        "Latest profile",
                        "Historical median",
                    ],
                    range=[
                        "#4E79A7",
                        "#666666",
                    ],
                ),
            ),
            strokeDash=alt.StrokeDash(
                "series:N",
                title=None,
                scale=alt.Scale(
                    domain=[
                        "Latest profile",
                        "Historical median",
                    ],
                    range=[
                        [1, 0],
                        [6, 4],
                    ],
                ),
            ),
            tooltip=[
                "series:N",
                alt.Tooltip(
                    "settlement_slot:Q",
                    title="Settlement period",
                ),
                alt.Tooltip(
                    "demand_gw:Q",
                    title="Demand",
                    format=".1f",
                ),
            ],
        )
    )

    return (
        band
        + lines
    ).properties(
        title=(
            "Latest demand profile "
            "vs historical typical range"
        ),
        height=320,
    )

