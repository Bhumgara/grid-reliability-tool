import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from core.config import DB_PATH


TARGET_SQL_PATH = Path("sql/datasets/build_model_dataset.sql")
OUTPUT_PATH = Path("data/processed/model_dataset.csv")

FUEL_TYPES = [
    "WIND",
    "CCGT",
    "NUCLEAR",
    "BIOMASS",
]


def load_targets(conn: sqlite3.Connection) -> pd.DataFrame:
    query = TARGET_SQL_PATH.read_text()

    df = pd.read_sql_query(query, conn)

    df["target_time_utc"] = pd.to_datetime(
        df["target_time_utc"],
        utc=True,
    )
    df["target_published_at_utc"] = pd.to_datetime(
        df["target_published_at_utc"],
        utc=True,
    )

    return df


def load_demand(conn: sqlite3.Connection) -> pd.DataFrame:
    query = """
        SELECT
            event_time_utc,
            published_at_utc,
            demand_mw
        FROM elexon_demand_indo
        WHERE demand_mw IS NOT NULL
        ORDER BY published_at_utc;
    """

    df = pd.read_sql_query(query, conn)

    df["event_time_utc"] = pd.to_datetime(
        df["event_time_utc"],
        utc=True,
    )
    df["published_at_utc"] = pd.to_datetime(
        df["published_at_utc"],
        utc=True,
    )

    return df.rename(
        columns={
            "event_time_utc": "demand_event_time_utc",
            "published_at_utc": "demand_published_at_utc",
        }
    )


def load_fuelhh(conn: sqlite3.Connection) -> pd.DataFrame:
    placeholders = ",".join("?" for _ in FUEL_TYPES)

    query = f"""
        SELECT
            event_time_utc,
            published_at_utc,
            fuel_type,
            generation_mw
        FROM elexon_generation_fuelhh
        WHERE fuel_type IN ({placeholders})
        ORDER BY published_at_utc;
    """

    df = pd.read_sql_query(
        query,
        conn,
        params=FUEL_TYPES,
    )

    df["event_time_utc"] = pd.to_datetime(
        df["event_time_utc"],
        utc=True,
    )
    df["published_at_utc"] = pd.to_datetime(
        df["published_at_utc"],
        utc=True,
    )

    wide = (
        df.pivot_table(
            index=[
                "event_time_utc",
                "published_at_utc",
            ],
            columns="fuel_type",
            values="generation_mw",
            aggfunc="last",
        )
        .reset_index()
    )

    wide.columns.name = None

    wide = wide.rename(
        columns={
            "event_time_utc": "fuel_event_time_utc",
            "published_at_utc": "fuel_published_at_utc",
            "WIND": "wind_mw",
            "CCGT": "ccgt_mw",
            "NUCLEAR": "nuclear_mw",
            "BIOMASS": "biomass_mw",
        }
    )

    return wide


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


def add_baseline(
    df: pd.DataFrame,
    targets: pd.DataFrame,
) -> pd.DataFrame:
    previous = targets[
        [
            "target_time_utc",
            "target_published_at_utc",
            "target_drm_mw",
        ]
    ].rename(
        columns={
            "target_time_utc": "baseline_time_utc",
            "target_published_at_utc":
                "baseline_published_at_utc",
            "target_drm_mw":
                "baseline_drm_yesterday_mw",
        }
    )

    result = df.merge(
        previous,
        how="left",
        left_on="forecast_origin_utc",
        right_on="baseline_time_utc",
    )

    unavailable = (
        result["baseline_published_at_utc"].notna()
        & (
            result["baseline_published_at_utc"]
            > result["forecast_origin_utc"]
        )
    )

    result.loc[
        unavailable,
        "baseline_drm_yesterday_mw",
    ] = np.nan

    result.loc[
        unavailable,
        "baseline_time_utc",
    ] = pd.NaT

    result.loc[
        unavailable,
        "baseline_published_at_utc",
    ] = pd.NaT

    return result


def add_latest_demand(
    df: pd.DataFrame,
    demand: pd.DataFrame,
) -> pd.DataFrame:
    return pd.merge_asof(
        df.sort_values("forecast_origin_utc"),
        demand.sort_values("demand_published_at_utc"),
        left_on="forecast_origin_utc",
        right_on="demand_published_at_utc",
        direction="backward",
        allow_exact_matches=True,
    )


def add_latest_generation(
    df: pd.DataFrame,
    fuel: pd.DataFrame,
) -> pd.DataFrame:
    return pd.merge_asof(
        df.sort_values("forecast_origin_utc"),
        fuel.sort_values("fuel_published_at_utc"),
        left_on="forecast_origin_utc",
        right_on="fuel_published_at_utc",
        direction="backward",
        allow_exact_matches=True,
    )


def validate_dataset(df: pd.DataFrame) -> None:
    if df["target_time_utc"].duplicated().any():
        raise ValueError(
            "Duplicate target timestamps found."
        )

    publication_columns = [
        "baseline_published_at_utc",
        "demand_published_at_utc",
        "fuel_published_at_utc",
    ]

    for column in publication_columns:
        available = df[column].notna()

        leaked = (
            df.loc[available, column]
            > df.loc[available, "forecast_origin_utc"]
        )

        if leaked.any():
            raise ValueError(
                f"Feature leakage detected in {column}."
            )

    event_columns = [
        "demand_event_time_utc",
        "fuel_event_time_utc",
    ]

    for column in event_columns:
        available = df[column].notna()

        future_event = (
            df.loc[available, column]
            > df.loc[available, "forecast_origin_utc"]
        )

        if future_event.any():
            raise ValueError(
                f"Future event used in {column}."
            )


def build_model_dataset() -> pd.DataFrame:
    with sqlite3.connect(str(DB_PATH)) as conn:
        targets = load_targets(conn)
        demand = load_demand(conn)
        fuel = load_fuelhh(conn)

    df = targets.copy()

    # Fixed 24-hour-ahead prediction:
    # forecast origin O = target T - 24 hours.
    df["forecast_origin_utc"] = (
        df["target_time_utc"]
        - pd.Timedelta(hours=24)
    )

    df = add_calendar_features(df)

    df = add_baseline(
        df,
        targets,
    )

    df = add_latest_demand(
        df,
        demand,
    )

    df = add_latest_generation(
        df,
        fuel,
    )

    bad_baseline = df[
        df["baseline_published_at_utc"].notna()
        & (
            df["baseline_published_at_utc"]
            > df["forecast_origin_utc"]
        )
    ]

    print("Unsafe baseline rows:", len(bad_baseline))

    print(
        bad_baseline[
            [
                "target_time_utc",
                "forecast_origin_utc",
                "baseline_time_utc",
                "baseline_published_at_utc",
                "baseline_drm_yesterday_mw",
            ]
        ].head(20)
    )

    validate_dataset(df)

    df = df.sort_values(
        "target_time_utc"
    ).reset_index(drop=True)

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print(f"Dataset rows: {len(df):,}")
    print(
        "Target range:",
        df["target_time_utc"].min(),
        "->",
        df["target_time_utc"].max(),
    )

    print(
        "Baseline coverage:",
        f"{df['baseline_drm_yesterday_mw'].notna().mean():.2%}",
    )

    print(
        "Demand coverage:",
        f"{df['demand_mw'].notna().mean():.2%}",
    )

    print(
        "FUELHH coverage:",
        f"{df['fuel_published_at_utc'].notna().mean():.2%}",
    )

    print(f"Saved to {OUTPUT_PATH}")

    return df


if __name__ == "__main__":
    build_model_dataset()