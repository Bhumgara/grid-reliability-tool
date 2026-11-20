"""
Build a small, deterministic SQLite database for tests.

The tables come from the real sql/schema.sql, and values are stored in the
same formats the ingestion code writes (see core/db.py):

- timestamps: ISO 8601 with offset, e.g. "2026-09-24T23:30:00+00:00"
- settlement dates: "YYYY-MM-DD"

Settlement periods are derived from UTC for simplicity (period 1 = 00:00 UTC).
Real periods follow UK local time, so do not test BST/GMT edge cases with this.

The data deliberately includes the cases the dashboard loaders filter on:
non-1h forecast horizons, NULL margins, interconnector fuel types, an older
FUELINST snapshot, and both actual ('A') and forecast ('F') NESO rows.
"""

from __future__ import annotations

import math
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA_PATH = Path("sql/schema.sql")

# Last half-hour in the fixture. Fixed so tests are reproducible.
FIXTURE_END = datetime(2026, 9, 24, 23, 30, tzinfo=timezone.utc)
DEFAULT_DAYS = 14

HALF_HOUR = timedelta(minutes=30)

# FUELHH / FUELINST fuel types with a base output in MW.
FUEL_BASE_MW = {
    "CCGT": 9000.0,
    "OCGT": 50.0,
    "COAL": 0.0,
    "OIL": 0.0,
    "NUCLEAR": 4500.0,
    "BIOMASS": 1800.0,
    "NPSHYD": 300.0,
    "WIND": 8000.0,
    "PS": 200.0,
    "OTHER": 150.0,
    "INTFR": 1500.0,
    "INTNED": 800.0,
    "INTNSL": 1200.0,
}

# Two FUELINST snapshots: the loaders must pick the latest one.
FUELINST_LATEST = FIXTURE_END + timedelta(minutes=25)
FUELINST_PREVIOUS = FIXTURE_END + timedelta(minutes=20)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _settlement(value: datetime) -> tuple[str, int]:
    period = value.hour * 2 + value.minute // 30 + 1
    return value.date().isoformat(), period


def _daily_shape(value: datetime) -> float:
    """0..1 curve peaking around 18:00 UTC, lowest around 06:00."""
    hours = value.hour + value.minute / 60
    return 0.5 + 0.5 * math.sin((hours - 12) / 24 * 2 * math.pi)


def _half_hours(days: int) -> list[datetime]:
    count = days * 48
    start = FIXTURE_END - HALF_HOUR * (count - 1)
    return [start + HALF_HOUR * i for i in range(count)]


def build_grid_db(
    path: Path,
    days: int = DEFAULT_DAYS,
) -> Path:
    """Create the database at ``path`` and return the path."""
    times = _half_hours(days)

    with sqlite3.connect(path) as conn:
        conn.executescript(
            SCHEMA_PATH.read_text(encoding="utf-8")
        )
        _insert_margin(conn, times)
        _insert_demand(conn, times)
        _insert_fuelhh(conn, times)
        _insert_fuelinst(conn)
        _insert_neso_demand_update(conn)

    conn.close()
    return path


def _insert_margin(conn: sqlite3.Connection, times: list[datetime]) -> None:
    rows = []

    for i, t in enumerate(times):
        date, period = _settlement(t)
        published = _iso(t - timedelta(hours=1))

        # Comfortable overnight, tighter at the evening peak.
        margin = 6000.0 - 3000.0 * _daily_shape(t)

        # One NULL margin to exercise "IS NOT NULL" filters.
        if i == len(times) // 2:
            margin = None

        for horizon in (1, 8):
            rows.append(
                (
                    _iso(t), published, horizon, date, period,
                    margin, 0.0001, "elexon",
                )
            )

    conn.executemany(
        "INSERT INTO elexon_margin_lolpdrm VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )


def _insert_demand(conn: sqlite3.Connection, times: list[datetime]) -> None:
    rows = []

    for t in times:
        date, period = _settlement(t)
        demand = 22000.0 + 12000.0 * _daily_shape(t)
        rows.append(
            (_iso(t), _iso(t + HALF_HOUR), date, period, demand, "elexon")
        )

    conn.executemany(
        "INSERT INTO elexon_demand_indo VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )


def _insert_fuelhh(conn: sqlite3.Connection, times: list[datetime]) -> None:
    rows = []

    for t in times:
        date, period = _settlement(t)
        shape = _daily_shape(t)

        for fuel, base in FUEL_BASE_MW.items():
            # Gas follows demand; everything else stays flat.
            mw = base * (0.6 + 0.8 * shape) if fuel == "CCGT" else base
            rows.append(
                (
                    _iso(t), _iso(t + HALF_HOUR), date, period,
                    fuel, mw, "elexon",
                )
            )

    conn.executemany(
        "INSERT INTO elexon_generation_fuelhh VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )


def _insert_fuelinst(conn: sqlite3.Connection) -> None:
    rows = []

    for snapshot, scale in (
        (FUELINST_PREVIOUS, 0.9),
        (FUELINST_LATEST, 1.0),
    ):
        date, period = _settlement(snapshot)

        for fuel, base in FUEL_BASE_MW.items():
            rows.append(
                (
                    _iso(snapshot), _iso(snapshot), date, period,
                    fuel, base * scale, "elexon_fuelinst",
                )
            )

    conn.executemany(
        "INSERT INTO elexon_generation_fuelinst VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )


def _insert_neso_demand_update(conn: sqlite3.Connection) -> None:
    date, period = _settlement(FUELINST_LATEST)

    # Loaders prefer the actual ('A') row over the forecast ('F') row.
    rows = [
        (date, period, "A", 1200.0, 0.0, 0.0, "neso_demand_update"),
        (date, period, "F", 999.0, 999.0, 0.0, "neso_demand_update"),
    ]

    conn.executemany(
        "INSERT INTO neso_demand_update ("
        "settlement_date, settlement_period, forecast_actual_indicator, "
        "embedded_wind_mw, embedded_solar_mw, pump_storage_pumping_mw, "
        "source) VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
