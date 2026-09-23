import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from core.config import DB_PATH

from model.features import (
    add_calendar_features,
    add_drm_lag_features,
    build_demand_features,
    build_fuel_features,
    build_margin_features,
)

from pipelines.helper import (
    merge_asof_forecast_origin,
    report_dataset_diagnostics,
)


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

def load_margin_history(
    conn: sqlite3.Connection,
) -> pd.DataFrame:
    query = """
        SELECT
            event_time_utc,
            published_at_utc,
            forecast_horizon_hours,
            derated_margin_mw
        FROM elexon_margin_lolpdrm
        WHERE forecast_horizon_hours = 1
          AND derated_margin_mw IS NOT NULL
        ORDER BY published_at_utc;
    """

    df = pd.read_sql_query(
        query,
        conn,
    )

    df["event_time_utc"] = pd.to_datetime(
        df["event_time_utc"],
        utc=True,
    )

    df["published_at_utc"] = pd.to_datetime(
        df["published_at_utc"],
        utc=True,
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


def validate_dataset(
    df: pd.DataFrame,
) -> None:
    if df["target_time_utc"].duplicated().any():
        raise ValueError(
            "Duplicate target timestamps found."
        )

    publication_columns = [
        "baseline_published_at_utc",
        "drm_48h_published_at_utc",
        "drm_168h_published_at_utc",
        "demand_published_at_utc",
        "fuel_published_at_utc",
        "margin_published_at_utc",
    ]

    for column in publication_columns:
        available = df[column].notna()

        leaked = (
            df.loc[available, column]
            > df.loc[
                available,
                "forecast_origin_utc",
            ]
        )

        if leaked.any():
            raise ValueError(
                "Feature leakage detected "
                f"in {column}."
            )

    # Demand and FUELHH represent historical
    # observations, so their event itself must not
    # occur after the forecast origin.
    event_columns = [
        "demand_event_time_utc",
        "fuel_event_time_utc",
    ]

    for column in event_columns:
        available = df[column].notna()

        future_event = (
            df.loc[available, column]
            > df.loc[
                available,
                "forecast_origin_utc",
            ]
        )

        if future_event.any():
            raise ValueError(
                f"Future event used in {column}."
            )

def save_dataset_to_db(df: pd.DataFrame) -> None:
    db_df = df.copy()

    # SQLite has no native timezone-aware datetime type,
    # so store datetimes consistently as ISO-8601 strings.
    datetime_columns = [
        column
        for column in db_df.columns
        if pd.api.types.is_datetime64_any_dtype(db_df[column])
    ]

    for column in datetime_columns:
        db_df[column] = db_df[column].apply(
            lambda value: (
                value.isoformat()
                if pd.notna(value)
                else None
            )
        )

    with sqlite3.connect(str(DB_PATH)) as conn:
        db_df.to_sql(
            "model_dataset",
            conn,
            if_exists="replace",
            index=False,
        )

        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
                idx_model_dataset_target_time
            ON model_dataset (target_time_utc);
            """
        )

def build_model_dataset() -> pd.DataFrame:
    with sqlite3.connect(str(DB_PATH)) as conn:
        targets = load_targets(conn)
        demand = load_demand(conn)
        fuel = load_fuelhh(conn)
        margin = load_margin_history(conn)

    df = targets.copy()

    # Fixed 24-hour-ahead prediction.
    df["forecast_origin_utc"] = (
        df["target_time_utc"]
        - pd.Timedelta(hours=24)
    )

    # Known from the target timestamp itself.
    df = add_calendar_features(df)

    # 24-hour persistence benchmark.
    df = add_baseline(
        df,
        targets,
    )

    # Exact historical DRM look-backs.
    df = add_drm_lag_features(
        df,
        targets,
    )

    # Build temporal features independently
    # on the underlying source series.
    demand_features = build_demand_features(
        demand,
        window=10,
    )

    fuel_features = build_fuel_features(
        fuel,
        window=10,
    )

    margin_features = build_margin_features(
        margin,
        window=10,
    )

    # Attach only feature snapshots that were
    # available by each forecast origin.
    df = merge_asof_forecast_origin(
        df,
        demand_features,
        "demand_published_at_utc",
    )

    df = merge_asof_forecast_origin(
        df,
        fuel_features,
        "fuel_published_at_utc",
    )

    df = merge_asof_forecast_origin(
        df,
        margin_features,
        "margin_published_at_utc",
    )

    report_dataset_diagnostics(df)
    validate_dataset(df)

    df = df.sort_values(
        "target_time_utc"
    ).reset_index(drop=True)

    save_dataset_to_db(df)

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print()
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

    print(
        "Margin history coverage:",
        f"{df['margin_published_at_utc'].notna().mean():.2%}",
    )

    print(
        "Saved to database table: model_dataset"
    )

    print(
        f"Saved to {OUTPUT_PATH}"
    )

    return df



if __name__ == "__main__":
    build_model_dataset()
