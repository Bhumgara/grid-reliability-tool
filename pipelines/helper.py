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


def report_dataset_diagnostics(
    df: pd.DataFrame,
) -> None:
    publication_columns = {
        "baseline":
            "baseline_published_at_utc",
        "DRM 48h lag":
            "drm_48h_published_at_utc",
        "DRM 168h lag":
            "drm_168h_published_at_utc",
        "demand":
            "demand_published_at_utc",
        "FUELHH":
            "fuel_published_at_utc",
        "margin":
            "margin_published_at_utc",
    }

    print()
    print("Dataset diagnostics")

    for label, column in publication_columns.items():
        if column not in df.columns:
            continue

        available = df[column].notna()

        unsafe = (
            available
            & (
                df[column]
                > df["forecast_origin_utc"]
            )
        )

        print(
            f"{label}: "
            f"coverage={available.mean():.2%}, "
            f"unsafe={int(unsafe.sum()):,}"
        )

    duplicate_targets = (
        df["target_time_utc"]
        .duplicated()
        .sum()
    )

    print(
        "Duplicate targets:",
        f"{duplicate_targets:,}",
    )
