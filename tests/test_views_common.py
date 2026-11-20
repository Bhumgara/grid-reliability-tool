import pandas as pd
import pytest

from core.views.common import require_columns, series_gw, to_utc


def test_to_utc_parses_without_changing_input():
    df = pd.DataFrame({"t": ["2026-09-24T12:00:00+01:00"]})

    out = to_utc(df, "t")

    assert out["t"].iloc[0] == pd.Timestamp("2026-09-24T11:00:00Z")
    assert df["t"].iloc[0] == "2026-09-24T12:00:00+01:00"


def test_series_gw_converts_and_drops_missing():
    df = pd.DataFrame(
        {
            "t": ["2026-09-24T00:00:00+00:00", "2026-09-24T00:30:00+00:00"],
            "mw": [1500.0, None],
            "other": [1, 2],
        }
    )

    out = series_gw(df, "t", "mw", "gw")

    assert list(out.columns) == ["t", "mw", "gw"]
    assert out["gw"].tolist() == [1.5]
    assert str(out["t"].dt.tz) == "UTC"


def test_require_columns_names_missing_columns():
    df = pd.DataFrame({"a": [1]})

    require_columns(df, ["a"], "Thing")

    with pytest.raises(ValueError, match=r"Thing requires columns: \['b'\]"):
        require_columns(df, ["a", "b"], "Thing")
