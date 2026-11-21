"""Tests for core.queries against the fixture database and fixture files."""

import json
import sqlite3
from datetime import timedelta

import pandas as pd
import pytest

from core import queries
from tests.fixtures.grid_db import (
    DEFAULT_DAYS,
    FIXTURE_END,
    FUEL_BASE_MW,
    FUELINST_LATEST,
)

WEEK = 7 * 48
INTERCONNECTORS = sorted(f for f in FUEL_BASE_MW if f.startswith("INT"))


def _assert_sorted_utc(df: pd.DataFrame) -> None:
    times = df["event_time_utc"]
    assert str(times.dt.tz) == "UTC"
    assert times.is_monotonic_increasing


# --- Database loaders -------------------------------------------------------


def test_recent_margin_returns_latest_week_of_1h_horizon(grid_db):
    df = queries.load_recent_margin(7, db_path=grid_db)

    assert list(df.columns) == ["event_time_utc", "derated_margin_mw"]
    assert len(df) == WEEK
    assert df["derated_margin_mw"].notna().all()
    assert df["event_time_utc"].iloc[-1] == FIXTURE_END
    _assert_sorted_utc(df)


def test_recent_demand_returns_latest_week(grid_db):
    df = queries.load_recent_demand(7, db_path=grid_db)

    assert list(df.columns) == ["event_time_utc", "demand_mw"]
    assert len(df) == WEEK
    assert df["event_time_utc"].iloc[-1] == FIXTURE_END
    _assert_sorted_utc(df)


def test_recent_generation_is_wide_by_fuel(grid_db):
    df = queries.load_recent_generation(7, db_path=grid_db)

    assert set(df.columns) == set(FUEL_BASE_MW)
    assert df.index.max() == FIXTURE_END
    assert df.index.min() == FIXTURE_END - timedelta(days=7)
    assert df.index.is_monotonic_increasing
    # Current behaviour: the cutoff is inclusive, so 7 days gives 7 * 48 + 1.
    assert len(df) == WEEK + 1


def test_live_generation_mix_combines_fuelinst_and_neso(grid_db):
    df = queries.load_live_generation_mix(db_path=grid_db)
    mix = df.set_index("fuel_type")["generation_mw"]

    assert list(mix.index) == [
        "CCGT", "COAL", "OIL", "NUCLEAR", "BIOMASS",
        "NPSHYD", "OTHER", "WIND", "SOLAR",
    ]
    assert mix["CCGT"] == FUEL_BASE_MW["CCGT"] + FUEL_BASE_MW["OCGT"]
    # NESO actual ('A') row is used, not the forecast ('F') row.
    assert mix["WIND"] == FUEL_BASE_MW["WIND"] + 1200.0
    assert mix["SOLAR"] == 0.0
    assert (df["embedded_data_status"] == "A").all()
    assert (df["event_time_utc"] == FUELINST_LATEST.isoformat()).all()


def test_live_generation_mix_without_neso_row(grid_db):
    conn = sqlite3.connect(grid_db)
    try:
        conn.execute("DELETE FROM neso_demand_update")
        conn.commit()
    finally:
        conn.close()

    df = queries.load_live_generation_mix(db_path=grid_db)
    mix = df.set_index("fuel_type")["generation_mw"]

    assert mix["WIND"] == FUEL_BASE_MW["WIND"]
    assert mix["SOLAR"] == 0.0
    assert df["embedded_data_status"].isna().all()


def test_live_interconnectors_from_latest_snapshot(grid_db):
    df = queries.load_live_interconnectors(db_path=grid_db)

    assert list(df["fuel_type"]) == INTERCONNECTORS
    assert (df["event_time_utc"] == FUELINST_LATEST.isoformat()).all()
    assert list(df["generation_mw"]) == [FUEL_BASE_MW[f] for f in INTERCONNECTORS]


def test_margin_history_excludes_nulls_and_other_horizons(grid_db):
    history = queries.load_margin_history(db_path=grid_db)

    # One NULL margin is dropped; horizon-8 rows are excluded.
    assert len(history) == DEFAULT_DAYS * 48 - 1
    assert history.notna().all()


DATABASE_LOADERS = [
    queries.load_recent_margin,
    queries.load_recent_demand,
    queries.load_recent_generation,
    queries.load_live_generation_mix,
    queries.load_live_interconnectors,
    queries.load_margin_history,
]


@pytest.mark.parametrize("loader", DATABASE_LOADERS)
def test_database_loaders_return_empty_on_empty_db(loader, empty_grid_db):
    assert len(loader(db_path=empty_grid_db)) == 0


def test_loaders_default_to_config_db_path(grid_db, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", grid_db)

    assert len(queries.load_recent_demand(7)) == WEEK


@pytest.mark.parametrize("loader", DATABASE_LOADERS)
def test_missing_database_raises_and_is_not_created(loader, tmp_path):
    missing = tmp_path / "grid.db"

    with pytest.raises(queries.DatabaseUnavailableError, match="Database not found"):
        loader(db_path=missing)

    assert not missing.exists()


def test_database_is_opened_read_only(grid_db):
    with queries._connect(grid_db) as conn:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute("DELETE FROM elexon_demand_indo")

    assert len(queries.load_recent_demand(7, db_path=grid_db)) == WEEK


def test_database_path_with_spaces(grid_db, tmp_path):
    spaced = tmp_path / "folder with spaces" / "grid #1.db"
    spaced.parent.mkdir()
    spaced.write_bytes(grid_db.read_bytes())

    assert len(queries.load_recent_demand(7, db_path=spaced)) == WEEK


# --- File loaders -----------------------------------------------------------


def test_file_loaders_when_files_missing(tmp_path):
    missing = tmp_path / "missing"

    assert queries.load_model_metrics(missing) == {}
    assert queries.load_latest_forecast(missing) is None
    assert queries.load_refresh_status(missing) == {}
    assert queries.load_validation_predictions(missing, missing).empty


def test_json_loaders_read_valid_files(tmp_path):
    metrics = tmp_path / "metrics.json"
    forecast = tmp_path / "forecast.json"
    status = tmp_path / "status.json"
    metrics.write_text(json.dumps({"mae": 1.5}))
    forecast.write_text(json.dumps({"predicted_drm_mw": 4200}))
    status.write_text(json.dumps({"ok": True}))

    assert queries.load_model_metrics(metrics) == {"mae": 1.5}
    assert queries.load_latest_forecast(forecast) == {"predicted_drm_mw": 4200}
    assert queries.load_refresh_status(status) == {"ok": True}


def test_live_json_loaders_tolerate_half_written_files(tmp_path):
    partial = tmp_path / "partial.json"
    partial.write_text('{"predicted_drm_mw": 42')

    assert queries.load_latest_forecast(partial) is None
    assert queries.load_refresh_status(partial) == {}


def test_validation_predictions_prefers_validation_then_test(tmp_path):
    validation = tmp_path / "validation.csv"
    test = tmp_path / "test.csv"
    test.write_text("target_time_utc,actual\n2026-01-01T00:00:00+00:00,9\n")

    fallback = queries.load_validation_predictions(validation, test)
    assert fallback["actual"].tolist() == [9]

    validation.write_text("target_time_utc,actual\n2026-09-24T00:00:00+00:00,1\n")

    df = queries.load_validation_predictions(validation, test)
    assert df["actual"].tolist() == [1]
    assert str(df["target_time_utc"].dt.tz) == "UTC"


# --- Last refresh completed ---------------------------------------------------


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ('{"last_refresh_completed_utc": "2026-11-20T10:01:30+00:00"}', pd.Timestamp("2026-11-20T10:01:30Z")),
        ('{"last_refresh_completed_utc": "2026-11-20T11:01:30+01:00"}', pd.Timestamp("2026-11-20T10:01:30Z")),
        ('{"last_refresh_completed_utc": "2026-11-20T10:01:30"}', pd.Timestamp("2026-11-20T10:01:30Z")),
        ('{"last_refresh_completed_utc": "soon"}', None),
        ('{"last_refresh_completed_utc": null}', None),
        ("{}", None),
        ("[1, 2]", None),
        ('{"last_refresh_comp', None),
    ],
    ids=["utc", "offset", "naive", "bad-time", "null", "no-key", "not-a-dict", "half-written"],
)
def test_load_last_refresh_completed(tmp_path, content, expected):
    path = tmp_path / "last_refresh.json"
    path.write_text(content, encoding="utf-8")

    result = queries.load_last_refresh_completed(path)

    assert result == expected
    if expected is not None:
        assert str(result.tz) == "UTC"


def test_last_refresh_completed_missing_file(tmp_path):
    assert queries.load_last_refresh_completed(tmp_path / "missing.json") is None


def test_last_refresh_completed_defaults_to_config_path(tmp_path, monkeypatch):
    path = tmp_path / "last_refresh.json"
    path.write_text('{"last_refresh_completed_utc": "2026-11-20T10:00:00Z"}', encoding="utf-8")
    monkeypatch.setattr("core.config.LAST_REFRESH_PATH", path)

    assert queries.load_last_refresh_completed() == pd.Timestamp("2026-11-20T10:00:00Z")
