import pandas as pd
import pytest

from core.margin import (
    calculate_margin_percentile,
    describe_margin_percentile,
)


def test_percentile_is_share_of_history_below_forecast():
    history = pd.Series([1000, 2000, 3000, 4000])

    assert calculate_margin_percentile(2500, history) == 50.0
    assert calculate_margin_percentile(500, history) == 0.0
    assert calculate_margin_percentile(5000, history) == 100.0


def test_percentile_ignores_non_numeric_and_missing_values():
    history = pd.Series([1000, "bad", None, 3000])

    assert calculate_margin_percentile(2000, history) == 50.0


def test_percentile_defaults_to_50_without_history():
    assert calculate_margin_percentile(2000, pd.Series([], dtype=float)) == 50.0


@pytest.mark.parametrize(
    ("percentile", "label"),
    [
        (0, "historically tight"),
        (10, "historically tight"),
        (10.1, "below the typical historical range"),
        (25, "below the typical historical range"),
        (75, "around the typical historical range"),
        (75.1, "high relative to historical margins"),
    ],
)
def test_describe_margin_percentile_thresholds(percentile, label):
    assert describe_margin_percentile(percentile) == label
