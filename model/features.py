import numpy as np
import pandas as pd


def add_calendar_features(df: pd.DataFrame) -> pd.DataFrame:
    local_time = df["target_time_utc"].dt.tz_convert(
        "Europe/London"
    )

    minute_of_day = (
        local_time.dt.hour * 60
        + local_time.dt.minute
    )

    df["target_hour_sin"] = np.sin(
        2 * np.pi * minute_of_day / (24 * 60)
    )
    df["target_hour_cos"] = np.cos(
        2 * np.pi * minute_of_day / (24 * 60)
    )

    day_of_week = local_time.dt.dayofweek

    df["target_dow_sin"] = np.sin(
        2 * np.pi * day_of_week / 7
    )
    df["target_dow_cos"] = np.cos(
        2 * np.pi * day_of_week / 7
    )

    month = local_time.dt.month - 1

    df["target_month_sin"] = np.sin(
        2 * np.pi * month / 12
    )
    df["target_month_cos"] = np.cos(
        2 * np.pi * month / 12
    )

    return df

def build_demand_features(
    demand: pd.DataFrame,
    window: int = 10,
) -> pd.DataFrame:
    df = demand.sort_values(
        "demand_published_at_utc"
    ).copy()

    df["demand_mean_10"] = (
        df["demand_mw"]
        .rolling(
            window=window,
            min_periods=window,
        )
        .mean()
    )

    df["demand_delta_10"] = (
        df["demand_mw"]
        - df["demand_mean_10"]
    )

    return df

def build_fuel_features(
    fuel: pd.DataFrame,
    window: int = 10,
) -> pd.DataFrame:
    df = fuel.sort_values(
        "fuel_published_at_utc"
    ).copy()

    for fuel_name in [
        "wind",
        "ccgt",
        "nuclear",
        "biomass",
    ]:
        value_col = f"{fuel_name}_mw"
        mean_col = f"{fuel_name}_mean_10"
        delta_col = f"{fuel_name}_delta_10"

        df[mean_col] = (
            df[value_col]
            .rolling(
                window=window,
                min_periods=window,
            )
            .mean()
        )

        df[delta_col] = (
            df[value_col]
            - df[mean_col]
        )

    return df

def build_margin_features(
    margin: pd.DataFrame,
    window: int = 10,
) -> pd.DataFrame:
    df = margin.copy()

    # Historical DRM features should use the same 1-hour
    # horizon series that we use as the modelling target.
    if "forecast_horizon_hours" in df.columns:
        df = df[
            df["forecast_horizon_hours"] == 1
        ].copy()

    df = df.sort_values(
        "published_at_utc"
    ).copy()

    df = df.rename(
        columns={
            "event_time_utc": "margin_event_time_utc",
            "published_at_utc": "margin_published_at_utc",
            "derated_margin_mw": "latest_drm_mw",
        }
    )

    mean_column = f"drm_mean_{window}"
    delta_column = f"drm_delta_{window}"

    df[mean_column] = (
        df["latest_drm_mw"]
        .rolling(
            window=window,
            min_periods=window,
        )
        .mean()
    )

    df[delta_column] = (
        df["latest_drm_mw"]
        - df[mean_column]
    )

    return df[
        [
            "margin_event_time_utc",
            "margin_published_at_utc",
            "latest_drm_mw",
            mean_column,
            delta_column,
        ]
    ]
