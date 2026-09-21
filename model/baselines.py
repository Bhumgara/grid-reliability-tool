import sqlite3

import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

from core.config import DB_PATH


TEST_START = pd.Timestamp(
    "2026-01-01T00:00:00Z"
)


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

    datetime_columns = [
        "target_time_utc",
        "forecast_origin_utc",
    ]

    for column in datetime_columns:
        df[column] = pd.to_datetime(
            df[column],
            utc=True,
        )

    return df


def chronological_split(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    train = df[
        df["target_time_utc"] < TEST_START
    ].copy()

    test = df[
        df["target_time_utc"] >= TEST_START
    ].copy()

    return train, test


def evaluate_persistence_baseline(
    test: pd.DataFrame,
) -> dict[str, float]:
    baseline = test.dropna(
        subset=[
            "target_drm_mw",
            "baseline_drm_yesterday_mw",
        ]
    )

    y_true = baseline["target_drm_mw"]
    y_pred = baseline["baseline_drm_yesterday_mw"]

    mae = mean_absolute_error(
        y_true,
        y_pred,
    )

    rmse = mean_squared_error(
        y_true,
        y_pred,
    ) ** 0.5

    return {
        "rows": len(baseline),
        "mae_mw": mae,
        "rmse_mw": rmse,
    }


def main() -> None:
    df = load_model_dataset()

    train, test = chronological_split(df)

    metrics = evaluate_persistence_baseline(test)

    print(
        "Train:",
        train["target_time_utc"].min(),
        "->",
        train["target_time_utc"].max(),
    )

    print(
        "Test:",
        test["target_time_utc"].min(),
        "->",
        test["target_time_utc"].max(),
    )

    print(f"Train rows: {len(train):,}")
    print(f"Test rows: {len(test):,}")

    print()
    print("24-hour persistence baseline")
    print(f"Evaluation rows: {metrics['rows']:,}")
    print(f"MAE:  {metrics['mae_mw']:,.2f} MW")
    print(f"RMSE: {metrics['rmse_mw']:,.2f} MW")
