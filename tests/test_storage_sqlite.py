"""
Tests for SQLiteStore against the fixture database (tests/fixtures/grid_db.py).

Expected values come from the fixture's constants or from SQL run directly on
the file, not from the store's own queries. (Backend-independent behaviour
gets its own contract tests later in TODO.md 2.6.)
"""

import sqlite3
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest

from core.storage import DatabaseUnavailableError, GridStore, SQLiteStore
from pipelines.build_dataset import FUEL_TYPES
from tests.fixtures.grid_db import (
    DEFAULT_DAYS,
    FIXTURE_END,
    FUEL_BASE_MW,
    FUELINST_LATEST,
)

END = pd.Timestamp(FIXTURE_END)
LATEST_SNAPSHOT = pd.Timestamp(FUELINST_LATEST)
HALF_HOUR = pd.Timedelta(minutes=30)
TIME = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)


@pytest.fixture
def store(grid_db):
    return SQLiteStore(grid_db)


def _sql(path, query, params=()):
    with sqlite3.connect(path) as conn:
        return conn.execute(query, params).fetchall()


def _scalar(path, query, params=()):
    return _sql(path, query, params)[0][0]


def _assert_half_hourly_to_end(times: pd.Series, count: int):
    times = pd.Series(times).reset_index(drop=True)
    assert len(times) == count
    assert str(times.dt.tz) == "UTC"
    assert times.iloc[-1] == END
    assert times.is_monotonic_increasing


def test_satisfies_the_interface(store):
    assert isinstance(store, GridStore)


# --- Dashboard and API reads -----------------------------------------------------


@pytest.mark.parametrize("days", [1, 7])
def test_recent_margin(store, grid_db, days):
    df = store.recent_margin(days)

    assert list(df.columns) == ["event_time_utc", "derated_margin_mw"]
    # The fixture's NULL margin sits mid-history, outside these windows.
    _assert_half_hourly_to_end(df["event_time_utc"], days * 48)
    assert df["derated_margin_mw"].notna().all()
    # Values are the 1-hour-ahead rows, not the 8-hour ones.
    expected_last = _scalar(
        grid_db,
        "SELECT derated_margin_mw FROM elexon_margin_lolpdrm "
        "WHERE forecast_horizon_hours = 1 AND event_time_utc = ?",
        (FIXTURE_END.isoformat(),),
    )
    assert df["derated_margin_mw"].iloc[-1] == expected_last


@pytest.mark.parametrize("days", [1, 7])
def test_recent_demand(store, grid_db, days):
    df = store.recent_demand(days)

    assert list(df.columns) == ["event_time_utc", "demand_mw"]
    _assert_half_hourly_to_end(df["event_time_utc"], days * 48)
    assert df["demand_mw"].iloc[-1] == _scalar(
        grid_db,
        "SELECT demand_mw FROM elexon_demand_indo WHERE event_time_utc = ?",
        (FIXTURE_END.isoformat(),),
    )


def test_recent_generation(store, grid_db):
    df = store.recent_generation(7)

    assert set(df.columns) == set(FUEL_BASE_MW)
    assert str(df.index.tz) == "UTC"
    assert df.index[-1] == END
    assert df.index[0] == END - pd.Timedelta(days=7)
    assert df.loc[END, "WIND"] == FUEL_BASE_MW["WIND"]
    assert df.loc[END, "CCGT"] == _scalar(
        grid_db,
        "SELECT generation_mw FROM elexon_generation_fuelhh "
        "WHERE fuel_type = 'CCGT' AND event_time_utc = ?",
        (FIXTURE_END.isoformat(),),
    )


def test_live_generation_mix(store):
    df = store.live_generation_mix().set_index("fuel_type")

    assert set(df.index) == {
        "CCGT", "COAL", "OIL", "NUCLEAR", "BIOMASS", "NPSHYD", "OTHER", "WIND", "SOLAR",
    }
    assert (df["event_time_utc"] == LATEST_SNAPSHOT).all()
    # Latest snapshot only; OCGT merges into CCGT; NESO actual ('A') wind is added.
    assert df.loc["CCGT", "generation_mw"] == FUEL_BASE_MW["CCGT"] + FUEL_BASE_MW["OCGT"]
    assert df.loc["WIND", "generation_mw"] == FUEL_BASE_MW["WIND"] + 1200.0
    assert df.loc["SOLAR", "generation_mw"] == 0.0
    assert (df["embedded_data_status"] == "A").all()


def test_live_generation_mix_falls_back_to_neso_forecast(store, grid_db):
    with sqlite3.connect(grid_db) as conn:
        conn.execute("DELETE FROM neso_demand_update WHERE forecast_actual_indicator = 'A'")

    df = store.live_generation_mix().set_index("fuel_type")

    assert df.loc["WIND", "generation_mw"] == FUEL_BASE_MW["WIND"] + 999.0
    assert df.loc["SOLAR", "generation_mw"] == 999.0
    assert (df["embedded_data_status"] == "F").all()


def test_live_generation_mix_without_neso(store, grid_db):
    with sqlite3.connect(grid_db) as conn:
        conn.execute("DELETE FROM neso_demand_update")

    df = store.live_generation_mix().set_index("fuel_type")

    assert df.loc["WIND", "generation_mw"] == FUEL_BASE_MW["WIND"]
    assert df["embedded_data_status"].isna().all()


def test_live_interconnectors(store):
    df = store.live_interconnectors()

    assert list(df.columns) == ["event_time_utc", "fuel_type", "generation_mw"]
    assert df["fuel_type"].tolist() == ["INTFR", "INTNED", "INTNSL"]
    assert df["generation_mw"].tolist() == [FUEL_BASE_MW[f] for f in ["INTFR", "INTNED", "INTNSL"]]
    assert (df["event_time_utc"] == LATEST_SNAPSHOT).all()


def test_margin_history(store):
    history = store.margin_history()

    # Every 1-hour-ahead row except the fixture's one NULL.
    assert len(history) == DEFAULT_DAYS * 48 - 1
    assert history.notna().all()


@pytest.mark.parametrize("method", ["recent_margin", "recent_demand", "recent_generation"])
def test_recent_reads_on_empty_db(empty_grid_db, method):
    assert getattr(SQLiteStore(empty_grid_db), method)(7).empty


@pytest.mark.parametrize(
    "method",
    ["live_generation_mix", "live_interconnectors", "margin_history",
     "model_targets", "model_demand", "model_margin_history"],
)
def test_other_reads_on_empty_db(empty_grid_db, method):
    assert len(getattr(SQLiteStore(empty_grid_db), method)()) == 0


@pytest.mark.parametrize(
    "call",
    [
        lambda s: s.recent_margin(7),
        lambda s: s.live_generation_mix(),
        lambda s: s.margin_history(),
        lambda s: s.model_targets(),
        lambda s: s.model_fuel(["WIND"]),
    ],
)
def test_missing_database_raises_and_is_not_created(tmp_path, call):
    missing = tmp_path / "grid.db"

    with pytest.raises(DatabaseUnavailableError):
        call(SQLiteStore(missing))

    assert not missing.exists()


def test_reads_are_read_only(store):
    with store._read() as conn:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute("DELETE FROM elexon_demand_indo")


def test_default_path_is_read_from_config_on_each_call(grid_db, monkeypatch):
    store = SQLiteStore()
    monkeypatch.setattr("core.config.DB_PATH", grid_db)

    assert store.db_path == grid_db.resolve()
    assert len(store.recent_margin(1)) == 48


# --- Model inputs ----------------------------------------------------------------


def test_model_targets(store):
    df = store.model_targets()

    assert list(df.columns) == [
        "target_time_utc", "target_published_at_utc", "settlement_date",
        "settlement_period", "target_drm_mw",
    ]
    _assert_half_hourly_to_end(df["target_time_utc"], DEFAULT_DAYS * 48 - 1)
    # The fixture publishes each margin an hour before its event.
    assert (df["target_time_utc"] - df["target_published_at_utc"] == pd.Timedelta(hours=1)).all()


def test_model_demand(store):
    df = store.model_demand()

    assert list(df.columns) == ["demand_event_time_utc", "demand_published_at_utc", "demand_mw"]
    assert len(df) == DEFAULT_DAYS * 48
    assert str(df["demand_event_time_utc"].dt.tz) == "UTC"
    assert df["demand_published_at_utc"].is_monotonic_increasing


def test_model_fuel(store):
    df = store.model_fuel(FUEL_TYPES)

    assert list(df.columns) == [
        "fuel_event_time_utc", "fuel_published_at_utc",
        "biomass_mw", "ccgt_mw", "nuclear_mw", "wind_mw",
    ]
    assert len(df) == DEFAULT_DAYS * 48
    assert (df["wind_mw"] == FUEL_BASE_MW["WIND"]).all()
    assert str(df["fuel_event_time_utc"].dt.tz) == "UTC"


def test_model_fuel_only_requested_types(store):
    df = store.model_fuel(["WIND"])

    assert list(df.columns) == ["fuel_event_time_utc", "fuel_published_at_utc", "wind_mw"]


def test_model_margin_history(store):
    df = store.model_margin_history()

    assert list(df.columns) == [
        "event_time_utc", "published_at_utc", "forecast_horizon_hours", "derated_margin_mw",
    ]
    assert len(df) == DEFAULT_DAYS * 48 - 1
    assert (df["forecast_horizon_hours"] == 1).all()
    assert df["published_at_utc"].is_monotonic_increasing


# --- Freshness and counts --------------------------------------------------------


@pytest.mark.parametrize(
    ("dataset", "event_column", "freshness_column"),
    [
        ("elexon_margin_lolpdrm", "event_time_utc", "published_at_utc"),
        ("elexon_demand_indo", "event_time_utc", "published_at_utc"),
        ("elexon_generation_fuelhh", "event_time_utc", "published_at_utc"),
        ("elexon_generation_fuelinst", "event_time_utc", "published_at_utc"),
    ],
)
def test_latest_times(store, grid_db, dataset, event_column, freshness_column):
    expected = tuple(
        pd.Timestamp(_scalar(grid_db, f'SELECT MAX("{column}") FROM "{dataset}"'))
        for column in (event_column, freshness_column)
    )

    assert store.latest_times(dataset) == expected
    assert all(str(time.tz) == "UTC" for time in store.latest_times(dataset))


def test_latest_times_for_neso_generation_mix_use_interval_start(tmp_path):
    store = SQLiteStore(tmp_path / "grid.db")
    store.initialise()
    store.upsert_neso_generation_mix(ROWS["neso_generation_mix"])

    # No publication time, so freshness falls back to the interval start.
    assert store.latest_times("neso_generation_mix") == (pd.Timestamp(TIME), pd.Timestamp(TIME))


def test_latest_times_when_missing_empty_or_without_time_columns(tmp_path, grid_db, empty_grid_db):
    assert SQLiteStore(tmp_path / "missing.db").latest_times("elexon_demand_indo") == (None, None)
    assert SQLiteStore(empty_grid_db).latest_times("elexon_demand_indo") == (None, None)
    assert SQLiteStore(empty_grid_db).latest_times("model_dataset") == (None, None)
    # neso_demand_update keys on settlement date and period, not a timestamp.
    assert SQLiteStore(grid_db).latest_times("neso_demand_update") == (None, None)


@pytest.mark.parametrize(
    "dataset",
    ["elexon_margin_lolpdrm", "elexon_demand_indo", "elexon_generation_fuelhh",
     "elexon_generation_fuelinst", "neso_generation_mix", "neso_demand_update"],
)
def test_row_count(store, grid_db, dataset):
    assert store.row_count(dataset) == _scalar(grid_db, f'SELECT COUNT(*) FROM "{dataset}"')


def test_target_row_count(store):
    # Both 1-hour-ahead rows and the NULL one count; 8-hour ones don't.
    assert store.target_row_count() == DEFAULT_DAYS * 48


def test_counts_when_missing_or_without_tables(tmp_path):
    missing = SQLiteStore(tmp_path / "missing.db")
    bare_path = tmp_path / "bare.db"
    sqlite3.connect(bare_path).close()
    bare = SQLiteStore(bare_path)

    for store in (missing, bare):
        assert store.row_count("elexon_demand_indo") == 0
        assert store.row_count("model_dataset") == 0
        assert store.target_row_count() == 0


# --- Writes ------------------------------------------------------------------------

ROWS = {
    "margin_lolpdrm": [{
        "event_time_utc": TIME, "published_at_utc": TIME - timedelta(hours=1),
        "forecast_horizon_hours": 1, "settlement_date": date(2026, 11, 20),
        "settlement_period": 21, "derated_margin_mw": 5000.0,
        "loss_of_load_probability": 0.001, "source": "elexon",
    }],
    "demand_indo": [{
        "event_time_utc": TIME, "published_at_utc": TIME,
        "settlement_date": date(2026, 11, 20), "settlement_period": 21,
        "demand_mw": 30000.0, "source": "elexon",
    }],
    "generation_fuelhh": [{
        "event_time_utc": TIME, "published_at_utc": TIME,
        "settlement_date": date(2026, 11, 20), "settlement_period": 21,
        "fuel_type": "WIND", "generation_mw": 8000.0, "source": "elexon",
    }],
    "generation_fuelinst": [{
        "event_time_utc": TIME, "published_at_utc": TIME,
        "settlement_date": date(2026, 11, 20), "settlement_period": 21,
        "fuel_type": "INTFR", "generation_mw": 1500.0, "source": "elexon_fuelinst",
    }],
    "neso_generation_mix": [{
        "interval_start_utc": TIME, "interval_end_utc": TIME + timedelta(minutes=30),
        "biomass_pct": 5.0, "coal_pct": 0.0, "imports_pct": 10.0, "gas_pct": 30.0,
        "nuclear_pct": 15.0, "other_pct": 1.0, "hydro_pct": 1.0, "solar_pct": 8.0,
        "wind_pct": 30.0, "source": "neso_carbon_intensity",
    }],
    "neso_demand_update": [{
        "settlement_date": "2026-11-20", "settlement_period": 21,
        "forecast_actual_indicator": "A", "embedded_wind_mw": 1200.0,
        "embedded_solar_mw": 300.0, "pump_storage_pumping_mw": 0.0,
        "source": "neso_demand_update",
    }],
}

# What each row looks like in SQLite: datetimes and dates as ISO strings.
STORED = {
    "margin_lolpdrm": ("elexon_margin_lolpdrm", {
        "event_time_utc": "2026-11-20T10:00:00+00:00",
        "published_at_utc": "2026-11-20T09:00:00+00:00",
        "forecast_horizon_hours": 1, "settlement_date": "2026-11-20",
        "settlement_period": 21, "derated_margin_mw": 5000.0,
        "loss_of_load_probability": 0.001, "source": "elexon",
    }),
    "demand_indo": ("elexon_demand_indo", {
        "event_time_utc": "2026-11-20T10:00:00+00:00",
        "published_at_utc": "2026-11-20T10:00:00+00:00",
        "settlement_date": "2026-11-20", "settlement_period": 21,
        "demand_mw": 30000.0, "source": "elexon",
    }),
    "generation_fuelhh": ("elexon_generation_fuelhh", {
        "event_time_utc": "2026-11-20T10:00:00+00:00", "fuel_type": "WIND",
        "settlement_date": "2026-11-20", "generation_mw": 8000.0,
    }),
    "generation_fuelinst": ("elexon_generation_fuelinst", {
        "event_time_utc": "2026-11-20T10:00:00+00:00", "fuel_type": "INTFR",
        "generation_mw": 1500.0, "source": "elexon_fuelinst",
    }),
    "neso_generation_mix": ("neso_generation_mix", {
        "interval_start_utc": "2026-11-20T10:00:00+00:00",
        "interval_end_utc": "2026-11-20T10:30:00+00:00",
        "gas_pct": 30.0, "wind_pct": 30.0, "source": "neso_carbon_intensity",
    }),
    "neso_demand_update": ("neso_demand_update", {
        "settlement_date": "2026-11-20", "settlement_period": 21,
        "forecast_actual_indicator": "A", "embedded_wind_mw": 1200.0,
        "embedded_solar_mw": 300.0, "pump_storage_pumping_mw": 0.0,
    }),
}


def _rows(path, table) -> list[dict]:
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(f'SELECT * FROM "{table}"')]


@pytest.fixture
def new_store(tmp_path):
    store = SQLiteStore(tmp_path / "grid.db")
    store.initialise()
    return store


@pytest.mark.parametrize("kind", list(ROWS))
def test_upserts_store_rows_as_iso_strings(new_store, kind):
    table, expected = STORED[kind]

    getattr(new_store, f"upsert_{kind}")(ROWS[kind])

    (row,) = _rows(new_store.db_path, table)
    assert {key: row[key] for key in expected} == expected


def test_upserting_the_same_key_replaces_the_row(new_store):
    new_store.upsert_demand_indo(ROWS["demand_indo"])
    new_store.upsert_demand_indo([{**ROWS["demand_indo"][0], "demand_mw": 31000.0}])

    assert [row["demand_mw"] for row in _rows(new_store.db_path, "elexon_demand_indo")] == [31000.0]


def test_upserts_read_back_through_the_store(new_store):
    new_store.upsert_margin_lolpdrm(ROWS["margin_lolpdrm"])

    df = new_store.recent_margin(1)

    assert df["event_time_utc"].tolist() == [pd.Timestamp(TIME)]
    assert df["derated_margin_mw"].tolist() == [5000.0]


def test_initialise_creates_the_file_and_is_repeatable(tmp_path):
    path = tmp_path / "new" / "folder" / "grid.db"
    store = SQLiteStore(path)

    store.initialise()
    store.initialise()

    assert path.is_file()
    assert store.row_count("elexon_demand_indo") == 0


def test_save_model_dataset(tmp_path):
    dataset = pd.DataFrame({
        "target_time_utc": pd.to_datetime(["2026-11-20T10:00Z", "2026-11-20T10:30Z"], utc=True),
        "forecast_origin_utc": pd.to_datetime(["2026-11-19T10:00Z", None], utc=True),
        "target_drm_mw": [5000.0, 5100.0],
    })
    store = SQLiteStore(tmp_path / "grid.db")

    store.save_model_dataset(dataset)
    store.save_model_dataset(dataset)  # replaces, doesn't append

    assert _rows(store.db_path, "model_dataset") == [
        {"target_time_utc": "2026-11-20T10:00:00+00:00",
         "forecast_origin_utc": "2026-11-19T10:00:00+00:00", "target_drm_mw": 5000.0},
        {"target_time_utc": "2026-11-20T10:30:00+00:00",
         "forecast_origin_utc": None, "target_drm_mw": 5100.0},
    ]
    indexes = {row[1] for row in _sql(store.db_path, "PRAGMA index_list('model_dataset')")}
    assert "idx_model_dataset_target_time" in indexes


def test_failed_write_rolls_back(new_store):
    good = ROWS["demand_indo"][0]
    bad = {**good, "event_time_utc": TIME.replace(hour=11), "demand_mw": None}  # NOT NULL

    with pytest.raises(sqlite3.IntegrityError):
        new_store.upsert_demand_indo([good, bad])

    assert new_store.row_count("elexon_demand_indo") == 0
