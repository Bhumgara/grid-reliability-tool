"""Small helpers shared by the view functions."""

import pandas as pd


def to_utc(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Copy of ``df`` with ``column`` parsed as UTC datetimes."""
    out = df.copy()
    out[column] = pd.to_datetime(out[column], utc=True)
    return out


def timestamp_utc_or_none(raw) -> pd.Timestamp | None:
    """
    Parse one timestamp as UTC (naive times are taken as UTC).

    Returns None if ``raw`` is empty or not a valid time, for fields read from
    files the refresh worker may be rewriting.
    """
    if raw is None or raw == "":
        return None

    try:
        ts = pd.Timestamp(raw)
    except (ValueError, TypeError, OverflowError):
        return None

    if ts is pd.NaT:
        return None

    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def series_gw(
    df: pd.DataFrame,
    time_col: str,
    value_col: str,
    output_col: str,
) -> pd.DataFrame:
    """
    Time series with ``value_col`` (MW) converted to GW in ``output_col``.

    Keeps only the time and value columns (plus the new GW column), drops rows
    with missing values, and parses the time column as UTC.
    """
    out = to_utc(df[[time_col, value_col]].dropna(), time_col)
    out[output_col] = out[value_col] / 1000
    return out


def require_columns(
    df: pd.DataFrame,
    columns: list[str],
    context: str,
) -> None:
    """Raise ValueError naming any of ``columns`` missing from ``df``."""
    missing = [
        column
        for column in columns
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"{context} requires columns: {missing}"
        )
