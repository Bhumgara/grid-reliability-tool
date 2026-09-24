import json
import sqlite3
from pathlib import Path

import joblib
import pandas as pd

from core.config import DB_PATH
from model.features import (
    add_calendar_features,
    add_drm_lag_features,
    build_demand_features,
    build_fuel_features,
    build_margin_features,
)
from pipelines.build_dataset import (
    add_baseline,
    load_demand,
    load_fuelhh,
    load_margin_history,
    load_targets,
)
from pipelines.helper import (
    merge_asof_forecast_origin,
)


MODEL_PATH = Path(
    "artifacts/ridge_drm_24h.joblib"
)

FEATURE_COLUMNS_PATH = Path(
    "artifacts/feature_columns.json"
)

OUTPUT_PATH = Path(
    "data/processed/latest_forecast.json"
)

FORECAST_HORIZON_HOURS = 24


def load_feature_columns() -> list[str]:
    if not FEATURE_COLUMNS_PATH.exists():
        raise FileNotFoundError(
            f"Feature manifest not found: "
            f"{FEATURE_COLUMNS_PATH}"
        )

    with FEATURE_COLUMNS_PATH.open(
        encoding="utf-8",
    ) as file:
        return json.load(file)


def load_saved_model():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Saved model not found: {MODEL_PATH}"
        )

    return joblib.load(
        MODEL_PATH
    )


def choose_forecast_origin(
    targets: pd.DataFrame,
) -> pd.Timestamp:
    """
    Choose the latest half-hourly DRM timestamp that:

    1. is not in the future; and
    2. had already been published by that timestamp.

    This ensures the 24-hour persistence feature is
    genuinely available at the selected forecast origin.
    """

    now = pd.Timestamp.now(
        tz="UTC"
    ).floor("30min")

    candidates = targets[
        (
            targets["target_time_utc"]
            <= now
        )
        & (
            targets["target_published_at_utc"]
            <= targets["target_time_utc"]
        )
    ].copy()

    if candidates.empty:
        raise ValueError(
            "No valid forecast origin is available "
            "from the stored DRM history."
        )

    return candidates[
        "target_time_utc"
    ].max()


def build_prediction_row(
    targets: pd.DataFrame,
    demand: pd.DataFrame,
    fuel: pd.DataFrame,
    margin: pd.DataFrame,
    forecast_origin: pd.Timestamp,
) -> pd.DataFrame:
    target_time = (
        forecast_origin
        + pd.Timedelta(
            hours=FORECAST_HORIZON_HOURS
        )
    )

    df = pd.DataFrame(
        {
            "target_time_utc": [
                target_time
            ],
            "forecast_origin_utc": [
                forecast_origin
            ],
        }
    )

    # Target-time calendar features.
    df = add_calendar_features(
        df
    )

    # Exact 24-hour DRM persistence feature.
    df = add_baseline(
        df,
        targets,
    )

    # Exact historical DRM lags.
    df = add_drm_lag_features(
        df,
        targets,
    )

    # Source-level rolling and delta features.
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

    # Only attach source information that had been
    # published by the forecast origin.
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

    return df


def validate_prediction_row(
    df: pd.DataFrame,
    feature_columns: list[str],
) -> None:
    missing_columns = [
        column
        for column in feature_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            "Prediction row is missing required "
            f"features: {missing_columns}"
        )

    null_features = [
        column
        for column in feature_columns
        if df[column].isna().any()
    ]

    if null_features:
        raise ValueError(
            "Prediction row contains unavailable "
            f"features: {null_features}"
        )

    publication_columns = [
        "baseline_published_at_utc",
        "drm_48h_published_at_utc",
        "drm_168h_published_at_utc",
        "demand_published_at_utc",
        "fuel_published_at_utc",
        "margin_published_at_utc",
    ]

    forecast_origin = df[
        "forecast_origin_utc"
    ].iloc[0]

    for column in publication_columns:
        if column not in df.columns:
            continue

        published_at = df[
            column
        ].iloc[0]

        if (
            pd.notna(published_at)
            and published_at > forecast_origin
        ):
            raise ValueError(
                "Prediction leakage detected: "
                f"{column}={published_at} "
                f"is after forecast origin "
                f"{forecast_origin}."
            )


def timestamp_to_iso(
    value,
) -> str | None:
    if pd.isna(value):
        return None

    return pd.Timestamp(
        value
    ).isoformat()


def build_forecast_payload(
    df: pd.DataFrame,
    predicted_drm_mw: float,
) -> dict:
    row = df.iloc[0]

    return {
        "model": "Ridge Regression",
        "alpha": 350.0,
        "forecast_horizon_hours":
            FORECAST_HORIZON_HOURS,

        "generated_at_utc":
            pd.Timestamp.now(
                tz="UTC"
            ).isoformat(),

        "forecast_origin_utc":
            timestamp_to_iso(
                row["forecast_origin_utc"]
            ),

        "target_time_utc":
            timestamp_to_iso(
                row["target_time_utc"]
            ),

        "predicted_drm_mw":
            predicted_drm_mw,

        "latest_drm_mw":
            float(
                row["latest_drm_mw"]
            ),

        "demand_mw":
            float(
                row["demand_mw"]
            ),

        "source_publications": {
            "baseline":
                timestamp_to_iso(
                    row[
                        "baseline_published_at_utc"
                    ]
                ),

            "demand":
                timestamp_to_iso(
                    row[
                        "demand_published_at_utc"
                    ]
                ),

            "fuel":
                timestamp_to_iso(
                    row[
                        "fuel_published_at_utc"
                    ]
                ),

            "margin":
                timestamp_to_iso(
                    row[
                        "margin_published_at_utc"
                    ]
                ),
        },
    }


def save_forecast(
    forecast: dict,
) -> None:
    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Write atomically so Streamlit never reads a
    # partially written JSON file.
    temporary_path = OUTPUT_PATH.with_suffix(
        ".tmp"
    )

    with temporary_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            forecast,
            file,
            indent=2,
        )

    temporary_path.replace(
        OUTPUT_PATH
    )


def run_prediction() -> dict:
    feature_columns = (
        load_feature_columns()
    )

    model = load_saved_model()

    with sqlite3.connect(
        str(DB_PATH)
    ) as conn:
        targets = load_targets(
            conn
        )

        demand = load_demand(
            conn
        )

        fuel = load_fuelhh(
            conn
        )

        margin = load_margin_history(
            conn
        )

    forecast_origin = (
        choose_forecast_origin(
            targets
        )
    )

    prediction_row = (
        build_prediction_row(
            targets=targets,
            demand=demand,
            fuel=fuel,
            margin=margin,
            forecast_origin=forecast_origin,
        )
    )

    validate_prediction_row(
        prediction_row,
        feature_columns,
    )

    X = prediction_row[
        feature_columns
    ]

    predicted_drm_mw = float(
        model.predict(X)[0]
    )

    forecast = build_forecast_payload(
        prediction_row,
        predicted_drm_mw,
    )

    save_forecast(
        forecast
    )

    print()
    print("24-hour DRM forecast")
    print(
        "Forecast origin:",
        forecast[
            "forecast_origin_utc"
        ],
    )
    print(
        "Target time:",
        forecast[
            "target_time_utc"
        ],
    )
    print(
        "Predicted DRM:",
        f"{predicted_drm_mw:,.2f} MW",
    )
    print(
        "Latest known DRM:",
        f"{forecast['latest_drm_mw']:,.2f} MW",
    )
    print(
        f"Saved to {OUTPUT_PATH}"
    )

    return forecast


def main() -> None:
    run_prediction()


if __name__ == "__main__":
    main()