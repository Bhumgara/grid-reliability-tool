"""
De-rated margin context: how a forecast compares with historical margins.
"""

import pandas as pd


def calculate_margin_percentile(
    predicted_drm_mw: float,
    history: pd.Series,
) -> float:
    """
    Percentage of historical margins below ``predicted_drm_mw`` (0-100).

    Non-numeric and missing values are ignored. Returns 50.0 when there is
    no usable history.
    """
    clean = pd.to_numeric(
        history,
        errors="coerce",
    ).dropna()

    if clean.empty:
        return 50.0

    return float(
        (
            clean
            < predicted_drm_mw
        ).mean()
        * 100
    )


def describe_margin_percentile(
    percentile: float,
) -> str:
    """Plain-English label for a margin percentile."""
    if percentile <= 10:
        return "historically tight"

    if percentile <= 25:
        return "below the typical historical range"

    if percentile <= 75:
        return "around the typical historical range"

    return "high relative to historical margins"
