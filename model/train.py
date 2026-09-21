import sqlite3

import pandas as pd
from sklearn.ensemble import (
    GradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error
from xgboost import XGBRegressor

from core.config import DB_PATH


VALIDATION_START = pd.Timestamp("2025-10-01T00:00:00Z")
TEST_START = pd.Timestamp("2026-01-01T00:00:00Z")

FEATURE_COLUMNS = [
    "baseline_drm_yesterday_mw",
    "demand_mw",
    "wind_mw",
    "ccgt_mw",
    "nuclear_mw",
    "biomass_mw",
    "target_hour_sin",
    "target_hour_cos",
    "target_dow_sin",
    "target_dow_cos",
    "target_month_sin",
    "target_month_cos",
]

TARGET_COLUMN = "target_drm_mw"
BASELINE_COLUMN = "baseline_drm_yesterday_mw"


def load_model_dataset() -> pd.DataFrame:
    with sqlite3.connect(str(DB_PATH)) as conn:
        df = pd.read_sql_query(
            """
            SELECT *
            FROM model_dataset
            ORDER BY target_time_utc;
            """,
            conn,
        )

    df["target_time_utc"] = pd.to_datetime(
        df["target_time_utc"],
        utc=True,
    )

    return df


def prepare_model_data(
    df: pd.DataFrame,
) -> pd.DataFrame:
    return df.dropna(
        subset=FEATURE_COLUMNS + [TARGET_COLUMN]
    ).copy()


def chronological_split(
    df: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    train = df[
        df["target_time_utc"] < VALIDATION_START
    ].copy()

    validation = df[
        (df["target_time_utc"] >= VALIDATION_START)
        & (df["target_time_utc"] < TEST_START)
    ].copy()

    test = df[
        df["target_time_utc"] >= TEST_START
    ].copy()

    return train, validation, test


def evaluate(
    y_true,
    y_pred,
) -> dict[str, float]:
    mae = mean_absolute_error(
        y_true,
        y_pred,
    )

    rmse = mean_squared_error(
        y_true,
        y_pred,
    ) ** 0.5

    return {
        "mae_mw": mae,
        "rmse_mw": rmse,
    }


def build_models() -> dict:
    return {
        "Linear Regression": LinearRegression(),

        "Random Forest": RandomForestRegressor(
            random_state=42,
            n_jobs=-1,
        ),

        "Gradient Boosting": GradientBoostingRegressor(
            random_state=42,
        ),

        "XGBoost": XGBRegressor(
            random_state=42,
            n_jobs=-1,
            objective="reg:squarederror",
        ),
    }


def main() -> None:
    df = load_model_dataset()
    model_df = prepare_model_data(df)

    print(
        "Usable model range:",
        model_df["target_time_utc"].min(),
        "->",
        model_df["target_time_utc"].max(),
    )

    train, validation, test = chronological_split(
        model_df
    )

    print(f"Train rows: {len(train):,}")
    print(f"Validation rows: {len(validation):,}")
    print(f"Locked test rows: {len(test):,}")

    X_train = train[FEATURE_COLUMNS]
    y_train = train[TARGET_COLUMN]

    X_validation = validation[FEATURE_COLUMNS]
    y_validation = validation[TARGET_COLUMN]

    # Persistence baseline evaluated on exactly the
    # same validation rows as every ML model.
    baseline_predictions = validation[
        BASELINE_COLUMN
    ]

    baseline_metrics = evaluate(
        y_validation,
        baseline_predictions,
    )

    results = [
        {
            "model": "Persistence Baseline",
            **baseline_metrics,
        }
    ]

    models = build_models()

    for name, model in models.items():
        print(f"Training {name}...")

        model.fit(
            X_train,
            y_train,
        )

        predictions = model.predict(
            X_validation
        )

        metrics = evaluate(
            y_validation,
            predictions,
        )

        results.append(
            {
                "model": name,
                **metrics,
            }
        )

    results_df = pd.DataFrame(results)

    baseline_mae = baseline_metrics["mae_mw"]

    results_df["mae_improvement_pct"] = (
        (
            baseline_mae
            - results_df["mae_mw"]
        )
        / baseline_mae
        * 100
    )

    print()
    print("Validation results")
    print(
        results_df.to_string(
            index=False,
            formatters={
                "mae_mw": lambda x: f"{x:,.2f}",
                "rmse_mw": lambda x: f"{x:,.2f}",
                "mae_improvement_pct":
                    lambda x: f"{x:+.2f}%",
            },
        )
    )


if __name__ == "__main__":
    main()