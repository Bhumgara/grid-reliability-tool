import numpy as np
import pandas as pd

from core.storage import GridStore, get_file_store, get_grid_store

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


FUEL_TYPES = [
    "WIND",
    "CCGT",
    "NUCLEAR",
    "BIOMASS",
]


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

def load_model_inputs(
    store: GridStore,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """``(targets, demand, fuel, margin)`` from the store, as the model expects."""
    return (
        store.model_targets(),
        store.model_demand(),
        store.model_fuel(FUEL_TYPES),
        store.model_margin_history(),
    )


def build_model_dataset(store: GridStore | None = None) -> pd.DataFrame:
    """Build the modelling dataset; ``store`` defaults to the configured backend."""
    store = store or get_grid_store()
    targets, demand, fuel, margin = load_model_inputs(store)

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

    store.save_model_dataset(df)

    files = get_file_store()
    files.write_csv("model_dataset", df)

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
        f"Saved to {files.location('model_dataset')}"
    )

    return df


if __name__ == "__main__":
    build_model_dataset()
