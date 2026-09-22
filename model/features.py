import numpy as np
import pandas as pd


def add_calendar_features(
    df: pd.DataFrame,
) -> pd.DataFrame:
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

    mean_column = f"demand_mean_{window}"
    delta_column = f"demand_delta_{window}"

    df[mean_column] = (
        df["demand_mw"]
        .rolling(
            window=window,
            min_periods=window,
        )
        .mean()
    )

    df[delta_column] = (
        df["demand_mw"]
        - df[mean_column]
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
        value_column = f"{fuel_name}_mw"
        mean_column = (
            f"{fuel_name}_mean_{window}"
        )
        delta_column = (
            f"{fuel_name}_delta_{window}"
        )

        df[mean_column] = (
            df[value_column]
            .rolling(
                window=window,
                min_periods=window,
            )
            .mean()
        )

        df[delta_column] = (
            df[value_column]
            - df[mean_column]
        )

    return df


def build_margin_features(
    margin: pd.DataFrame,
    window: int = 10,
) -> pd.DataFrame:
    df = margin.copy()

    # Use the same 1-hour DRM series as the
    # historical modelling target.
    if "forecast_horizon_hours" in df.columns:
        df = df[
            df["forecast_horizon_hours"] == 1
        ].copy()

    df = df.sort_values(
        "published_at_utc"
    ).copy()

    df = df.rename(
        columns={
            "event_time_utc":
                "margin_event_time_utc",
            "published_at_utc":
                "margin_published_at_utc",
            "derated_margin_mw":
                "latest_drm_mw",
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


def add_drm_lag_features(
    df: pd.DataFrame,
    targets: pd.DataFrame,
) -> pd.DataFrame:
    result = df.copy()

    history = targets[
        [
            "target_time_utc",
            "target_published_at_utc",
            "target_drm_mw",
        ]
    ].copy()

    for hours in [48, 168]:
        lagged = history.copy()

        # Shift historical target timestamps forward,
        # allowing them to join to the target for which
        # they represent a lag.
        lagged["target_time_utc"] = (
            lagged["target_time_utc"]
            + pd.Timedelta(hours=hours)
        )

        value_column = (
            f"drm_{hours}h_ago_mw"
        )

        published_column = (
            f"drm_{hours}h_published_at_utc"
        )

        lagged = lagged.rename(
            columns={
                "target_drm_mw":
                    value_column,
                "target_published_at_utc":
                    published_column,
            }
        )

        lagged = lagged[
            [
                "target_time_utc",
                value_column,
                published_column,
            ]
        ]

        result = result.merge(
            lagged,
            how="left",
            on="target_time_utc",
            validate="one_to_one",
        )

        # Defensive leakage check: even a historical
        # lag may only be used if it had been published
        # by this row's forecast origin.
        unavailable = (
            result[published_column].notna()
            & (
                result[published_column]
                > result["forecast_origin_utc"]
            )
        )

        result.loc[
            unavailable,
            value_column,
        ] = np.nan

        result.loc[
            unavailable,
            published_column,
        ] = pd.NaT

    return result