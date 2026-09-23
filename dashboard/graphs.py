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
