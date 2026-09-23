from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
)


OUTPUT_DIR = Path("data/processed")


def evaluate_predictions(
    y_true,
    y_pred,
) -> dict[str, float]:
    return {
        "mae_mw": mean_absolute_error(
            y_true,
            y_pred,
        ),
        "rmse_mw": mean_squared_error(
            y_true,
            y_pred,
        ) ** 0.5,
    }


def inspect_validation_errors(
    validation: pd.DataFrame,
    predictions,
) -> pd.DataFrame:
    results = validation[
        [
            "target_time_utc",
            "target_drm_mw",
            "baseline_drm_yesterday_mw",
        ]
    ].copy()

    results["predicted_drm_mw"] = predictions

    results["error_mw"] = (
        results["predicted_drm_mw"]
        - results["target_drm_mw"]
    )

    results["absolute_error_mw"] = (
        results["error_mw"].abs()
    )

    print()
    print("Validation error inspection")

    print(
        f"Mean error / bias: "
        f"{results['error_mw'].mean():,.2f} MW"
    )

    print(
        f"Median absolute error: "
        f"{results['absolute_error_mw'].median():,.2f} MW"
    )

    print(
        f"90th percentile absolute error: "
        f"{results['absolute_error_mw'].quantile(0.90):,.2f} MW"
    )

    print(
        f"95th percentile absolute error: "
        f"{results['absolute_error_mw'].quantile(0.95):,.2f} MW"
    )

    inspect_tight_periods(results)
    print_worst_errors(results)

    save_validation_predictions(results)
    save_validation_plot(results)

    return results


def inspect_tight_periods(
    results: pd.DataFrame,
) -> None:
    # Use the lowest 10% of actual DRM values rather
    # than inventing an arbitrary operational threshold.
    threshold = results[
        "target_drm_mw"
    ].quantile(0.10)

    tight = results[
        results["target_drm_mw"] <= threshold
    ].copy()

    metrics = evaluate_predictions(
        tight["target_drm_mw"],
        tight["predicted_drm_mw"],
    )

    baseline_metrics = evaluate_predictions(
        tight["target_drm_mw"],
        tight["baseline_drm_yesterday_mw"],
    )

    print()
    print("Lowest 10% DRM periods")

    print(
        f"DRM threshold: "
        f"{threshold:,.2f} MW"
    )

    print(
        f"Rows: {len(tight):,}"
    )

    print(
        f"Model MAE: "
        f"{metrics['mae_mw']:,.2f} MW"
    )

    print(
        f"Baseline MAE: "
        f"{baseline_metrics['mae_mw']:,.2f} MW"
    )

    print(
        f"Model RMSE: "
        f"{metrics['rmse_mw']:,.2f} MW"
    )


def print_worst_errors(
    results: pd.DataFrame,
) -> None:
    worst = (
        results
        .nlargest(
            10,
            "absolute_error_mw",
        )
        [
            [
                "target_time_utc",
                "target_drm_mw",
                "predicted_drm_mw",
                "error_mw",
                "absolute_error_mw",
            ]
        ]
    )

    print()
    print("10 largest validation errors")

    print(
        worst.to_string(
            index=False,
            formatters={
                "target_drm_mw":
                    lambda x: f"{x:,.2f}",
                "predicted_drm_mw":
                    lambda x: f"{x:,.2f}",
                "error_mw":
                    lambda x: f"{x:+,.2f}",
                "absolute_error_mw":
                    lambda x: f"{x:,.2f}",
            },
        )
    )


def save_validation_predictions(
    results: pd.DataFrame,
) -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = (
        OUTPUT_DIR
        / "validation_predictions.csv"
    )

    results.to_csv(
        path,
        index=False,
    )

    print()
    print(f"Saved validation predictions to {path}")


def save_validation_plot(
    results: pd.DataFrame,
) -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = (
        OUTPUT_DIR
        / "validation_forecast_vs_actual.png"
    )

    plt.figure(
        figsize=(14, 6)
    )

    plt.plot(
        results["target_time_utc"],
        results["target_drm_mw"],
        label="Actual DRM",
    )

    plt.plot(
        results["target_time_utc"],
        results["predicted_drm_mw"],
        label="Predicted DRM",
    )

    plt.xlabel("Target time")
    plt.ylabel("De-rated Margin (MW)")
    plt.title(
        "Validation: predicted vs actual DRM"
    )

    plt.legend()
    plt.tight_layout()

    plt.savefig(
        path,
        dpi=150,
    )

    plt.close()

    print(
        f"Saved validation plot to {path}"
    )