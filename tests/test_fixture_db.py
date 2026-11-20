"""Checks that the fixture database matches what the loaders expect."""

import sqlite3

from tests.fixtures.grid_db import (
    DEFAULT_DAYS,
    FIXTURE_END,
    FUEL_BASE_MW,
    FUELINST_LATEST,
)


def _scalar(path, query, params=()):
    with sqlite3.connect(path) as conn:
        return conn.execute(query, params).fetchone()[0]


def test_row_counts(grid_db):
    periods = DEFAULT_DAYS * 48

    assert _scalar(grid_db, "SELECT COUNT(*) FROM elexon_demand_indo") == periods
    assert _scalar(
        grid_db,
        "SELECT COUNT(*) FROM elexon_margin_lolpdrm WHERE forecast_horizon_hours = 1",
    ) == periods
    assert _scalar(
        grid_db, "SELECT COUNT(*) FROM elexon_generation_fuelhh"
    ) == periods * len(FUEL_BASE_MW)


def test_timestamps_use_ingestion_format(grid_db):
    latest = _scalar(grid_db, "SELECT MAX(event_time_utc) FROM elexon_demand_indo")

    assert latest == FIXTURE_END.isoformat()
    assert latest.endswith("+00:00")


def test_margin_has_one_null_per_horizon(grid_db):
    assert _scalar(
        grid_db,
        "SELECT COUNT(*) FROM elexon_margin_lolpdrm "
        "WHERE derated_margin_mw IS NULL AND forecast_horizon_hours = 1",
    ) == 1


def test_latest_fuelinst_snapshot_has_actual_and_forecast_neso(grid_db):
    latest = _scalar(
        grid_db, "SELECT MAX(event_time_utc) FROM elexon_generation_fuelinst"
    )
    assert latest == FUELINST_LATEST.isoformat()

    with sqlite3.connect(grid_db) as conn:
        indicators = {
            row[0]
            for row in conn.execute(
                "SELECT n.forecast_actual_indicator "
                "FROM neso_demand_update n "
                "JOIN elexon_generation_fuelinst f "
                "ON f.settlement_date = n.settlement_date "
                "AND f.settlement_period = n.settlement_period "
                "WHERE f.event_time_utc = ?",
                (latest,),
            )
        }

    assert indicators == {"A", "F"}
