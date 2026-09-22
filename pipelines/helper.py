import pandas as pd


def merge_asof_forecast_origin(
    df: pd.DataFrame,
    features: pd.DataFrame,
    published_column: str,
) -> pd.DataFrame:
    return pd.merge_asof(
        df.sort_values("forecast_origin_utc"),
        features.sort_values(published_column),
        left_on="forecast_origin_utc",
        right_on=published_column,
        direction="backward",
        allow_exact_matches=True,
    )

def report_dataset_diagnostics(df: pd.DataFrame) -> None:
    unsafe_baseline = (
        df["baseline_published_at_utc"].notna()
        & (
            df["baseline_published_at_utc"]
            > df["forecast_origin_utc"]
        )
    )

    print(
        "Unsafe baseline rows:",
        int(unsafe_baseline.sum()),
    )