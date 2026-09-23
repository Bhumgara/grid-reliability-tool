import json
from pathlib import Path

import joblib
import pandas as pd

from model.evaluate import evaluate_predictions
from model.train import (
    BASELINE_COLUMN,
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    TEST_START,
    build_model,
    load_model_dataset,
    prepare_model_data,
)


ARTIFACT_DIR = Path("artifacts")
OUTPUT_DIR = Path("data/processed")


def build_final_split(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    development = df[
        df["target_time_utc"] < TEST_START
    ].copy()

    test = df[
        df["target_time_utc"] >= TEST_START
    ].copy()

    return development, test


def build_test_predictions(
    test: pd.DataFrame,
    predictions,
) -> pd.DataFrame:
    results = test[
        [
            "target_time_utc",
            TARGET_COLUMN,
            BASELINE_COLUMN,
        ]
    ].copy()

    results["predicted_drm_mw"] = predictions

    results["error_mw"] = (
        results["predicted_drm_mw"]
        - results[TARGET_COLUMN]
    )

    results["absolute_error_mw"] = (
        results["error_mw"].abs()
    )

    return results


def main() -> None:
    df = load_model_dataset()
    model_df = prepare_model_data(df)

    development, test = build_final_split(
        model_df
    )

    print(
        "Development range:",
        development["target_time_utc"].min(),
        "->",
        development["target_time_utc"].max(),
    )

    print(
        "Locked test range:",
        test["target_time_utc"].min(),
        "->",
        test["target_time_utc"].max(),
    )

    print(
        f"Development rows: {len(development):,}"
    )

    print(
        f"Locked test rows: {len(test):,}"
    )

    X_development = development[
        FEATURE_COLUMNS
    ]

    y_development = development[
        TARGET_COLUMN
    ]

    X_test = test[
        FEATURE_COLUMNS
    ]

    y_test = test[
        TARGET_COLUMN
    ]

    baseline_predictions = test[
        BASELINE_COLUMN
    ]

    # Frozen model configuration.
    model = build_model()

    print()
    print(
        "Training final Ridge Regression "
        "(alpha=350)..."
    )

    model.fit(
        X_development,
        y_development,
    )

    predictions = model.predict(
        X_test
    )

    model_metrics = evaluate_predictions(
        y_test,
        predictions,
    )

    baseline_metrics = evaluate_predictions(
        y_test,
        baseline_predictions,
    )

    mae_improvement_pct = (
        (
            baseline_metrics["mae_mw"]
            - model_metrics["mae_mw"]
        )
        / baseline_metrics["mae_mw"]
        * 100
    )

    print()
    print("Final locked-test results")

    print(
        f"Persistence MAE: "
        f"{baseline_metrics['mae_mw']:,.2f} MW"
    )

    print(
        f"Persistence RMSE: "
        f"{baseline_metrics['rmse_mw']:,.2f} MW"
    )

    print(
        f"Ridge MAE: "
        f"{model_metrics['mae_mw']:,.2f} MW"
    )

    print(
        f"Ridge RMSE: "
        f"{model_metrics['rmse_mw']:,.2f} MW"
    )

    print(
        f"MAE improvement vs persistence: "
        f"{mae_improvement_pct:+.2f}%"
    )

    ARTIFACT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    joblib.dump(
        model,
        ARTIFACT_DIR / "ridge_drm_24h.joblib",
    )

    predictions_df = build_test_predictions(
        test,
        predictions,
    )

    predictions_df.to_csv(
        OUTPUT_DIR / "test_predictions.csv",
        index=False,
    )

    metrics = {
        "model": "Ridge Regression",
        "alpha": 350.0,
        "forecast_horizon_hours": 24,
        "development_start":
            development["target_time_utc"]
            .min()
            .isoformat(),
        "development_end":
            development["target_time_utc"]
            .max()
            .isoformat(),
        "test_start":
            test["target_time_utc"]
            .min()
            .isoformat(),
        "test_end":
            test["target_time_utc"]
            .max()
            .isoformat(),
        "development_rows":
            len(development),
        "test_rows":
            len(test),
        "model_mae_mw":
            model_metrics["mae_mw"],
        "model_rmse_mw":
            model_metrics["rmse_mw"],
        "baseline_mae_mw":
            baseline_metrics["mae_mw"],
        "baseline_rmse_mw":
            baseline_metrics["rmse_mw"],
        "mae_improvement_pct":
            mae_improvement_pct,
    }

    with (
        ARTIFACT_DIR / "metrics.json"
    ).open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            metrics,
            file,
            indent=2,
        )

    with (
        ARTIFACT_DIR / "feature_columns.json"
    ).open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            FEATURE_COLUMNS,
            file,
            indent=2,
        )

    print()
    print(
        "Saved model to "
        "artifacts/ridge_drm_24h.joblib"
    )

    print(
        "Saved metrics to "
        "artifacts/metrics.json"
    )

    print(
        "Saved test predictions to "
        "data/processed/test_predictions.csv"
    )


if __name__ == "__main__":
    main()