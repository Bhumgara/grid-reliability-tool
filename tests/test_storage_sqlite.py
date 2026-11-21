"""
Parity tests: SQLiteStore returns (and writes) exactly what the existing
functions in core.queries, core.db, pipelines.build_dataset and
pipelines.refresh do, against the fixture database.

Once those functions delegate to the store (the next commits), these become
plain SQLiteStore tests.
"""

import sqlite3
from datetime import date, datetime, timezone

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal, assert_series_equal

from core import db, queries
from core.storage import DatabaseUnavailableError, GridStore, SQLiteStore
from pipelines import build_dataset, refresh

TIME = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)


@pytest.fixture
def store(grid_db):
    return SQLiteStore(grid_db)


def _times_to_utc(df: pd.DataFrame) -> pd.DataFrame:
    """Old FUELINST loaders return event times as strings; the store parses them."""
    out = df.copy()
    out["event_time_utc"] = pd.to_datetime(out["event_time_utc"], utc=True)
    return out


def test_satisfies_the_interface(store):
    assert isinstance(store, GridStore)


# --- Dashboard and API reads -----------------------------------------------------


@pytest.mark.parametrize("days", [1, 7])
@pytest.mark.parametrize(
    ("method", "loader"),
    [
        ("recent_margin", queries.load_recent_margin),
        ("recent_demand", queries.load_recent_demand),
        ("recent_generation", queries.load_recent_generation),
    ],
)
def test_recent_reads_match_core_queries(store, grid_db, method, loader, days):
    assert_frame_equal(getattr(store, method)(days), loader(days, db_path=grid_db))


def test_live_generation_mix_matches(store, grid_db):
    expected = _times_to_utc(queries.load_live_generation_mix(db_path=grid_db))

    assert_frame_equal(store.live_generation_mix(), expected)


def test_live_generation_mix_without_neso(store, grid_db):
    with sqlite3.connect(grid_db) as conn:
        conn.execute("DELETE FROM neso_demand_update")
    expected = _times_to_utc(queries.load_live_generation_mix(db_path=grid_db))

    result = store.live_generation_mix()

    assert_frame_equal(result, expected)
    assert result["embedded_data_status"].isna().all()


def test_live_interconnectors_match(store, grid_db):
    expected = _times_to_utc(queries.load_live_interconnectors(db_path=grid_db))

    assert_frame_equal(store.live_interconnectors(), expected)


def test_margin_history_matches(store, grid_db):
    assert_series_equal(store.margin_history(), queries.load_margin_history(db_path=grid_db))


def test_times_are_utc(store):
    for frame in [store.recent_margin(7), store.live_generation_mix(), store.live_interconnectors()]:
        assert str(frame["event_time_utc"].dt.tz) == "UTC"
    assert str(store.recent_generation(7).index.tz) == "UTC"


@pytest.mark.parametrize(
    "method",
    ["recent_margin", "recent_demand", "recent_generation"],
)
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


@pytest.mark.parametrize(
    ("method", "loader"),
    [
        ("model_targets", build_dataset.load_targets),
        ("model_demand", build_dataset.load_demand),
        ("model_margin_history", build_dataset.load_margin_history),
    ],
)
def test_model_inputs_match_build_dataset(store, grid_db, method, loader):
    with sqlite3.connect(grid_db) as conn:
        expected = loader(conn)

    assert_frame_equal(getattr(store, method)(), expected)


def test_model_fuel_matches_build_dataset(store, grid_db):
    with sqlite3.connect(grid_db) as conn:
        expected = build_dataset.load_fuelhh(conn)

    assert_frame_equal(store.model_fuel(build_dataset.FUEL_TYPES), expected)


# --- Freshness and counts --------------------------------------------------------


@pytest.mark.parametrize(
    "dataset",
    ["elexon_margin_lolpdrm", "elexon_demand_indo", "elexon_generation_fuelhh",
     "elexon_generation_fuelinst", "neso_generation_mix", "neso_demand_update"],
)
def test_latest_times_match_refresh(store, grid_db, dataset):
    with sqlite3.connect(grid_db) as conn:
        expected = (
            refresh.max_timestamp(conn, dataset, ("event_time_utc", "interval_start_utc", "start_time_utc")),
            refresh.max_timestamp(
                conn, dataset,
                ("published_at_utc", "event_time_utc", "interval_start_utc", "start_time_utc"),
            ),
        )

    assert store.latest_times(dataset) == expected


def test_latest_times_when_missing_or_empty(tmp_path, empty_grid_db):
    assert SQLiteStore(tmp_path / "missing.db").latest_times("elexon_demand_indo") == (None, None)
    assert SQLiteStore(empty_grid_db).latest_times("elexon_demand_indo") == (None, None)
    assert SQLiteStore(empty_grid_db).latest_times("model_dataset") == (None, None)


@pytest.mark.parametrize(
    ("dataset", "count_function"),
    [
        ("elexon_margin_lolpdrm", "count_margin_lolpdrm_rows"),
        ("elexon_demand_indo", "count_demand_indo_rows"),
        ("elexon_generation_fuelhh", "count_generation_fuelhh_rows"),
        ("elexon_generation_fuelinst", "count_generation_fuelinst_rows"),
        ("neso_generation_mix", "count_neso_generation_mix_rows"),
        ("neso_demand_update", "count_neso_demand_update_rows"),
    ],
)
def test_row_counts_match_core_db(store, grid_db, monkeypatch, dataset, count_function):
    monkeypatch.setattr(db, "DB_PATH", grid_db)

    assert store.row_count(dataset) == getattr(db, count_function)()


def test_target_row_count_matches_core_db(store, grid_db, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", grid_db)

    assert store.target_row_count() == db.count_target_rows()


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
        "event_time_utc": TIME, "published_at_utc": TIME, "forecast_horizon_hours": 1,
        "settlement_date": date(2026, 11, 20), "settlement_period": 21,
        "derated_margin_mw": 5000.0, "loss_of_load_probability": 0.001, "source": "elexon",
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
        "interval_start_utc": TIME, "interval_end_utc": TIME,
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

TABLES = {
    "margin_lolpdrm": "elexon_margin_lolpdrm",
    "demand_indo": "elexon_demand_indo",
    "generation_fuelhh": "elexon_generation_fuelhh",
    "generation_fuelinst": "elexon_generation_fuelinst",
    "neso_generation_mix": "neso_generation_mix",
    "neso_demand_update": "neso_demand_update",
}


def _table(path, table) -> pd.DataFrame:
    with sqlite3.connect(path) as conn:
        return pd.read_sql_query(f'SELECT * FROM "{table}" ORDER BY 1', conn)


@pytest.mark.parametrize("kind", list(ROWS))
def test_upserts_write_what_core_db_writes(tmp_path, monkeypatch, kind):
    old_path, new_path = tmp_path / "old.db", tmp_path / "new.db"
    monkeypatch.setattr(db, "DB_PATH", old_path)
    db.initialise_database()
    getattr(db, f"upsert_{kind}_rows")(ROWS[kind])

    store = SQLiteStore(new_path)
    store.initialise()
    getattr(store, f"upsert_{kind}")(ROWS[kind])

    assert_frame_equal(_table(new_path, TABLES[kind]), _table(old_path, TABLES[kind]))
    assert len(_table(new_path, TABLES[kind])) == 1


def test_upserting_the_same_key_replaces_the_row(tmp_path):
    store = SQLiteStore(tmp_path / "grid.db")
    store.initialise()

    store.upsert_demand_indo(ROWS["demand_indo"])
    store.upsert_demand_indo([{**ROWS["demand_indo"][0], "demand_mw": 31000.0}])

    table = _table(tmp_path / "grid.db", "elexon_demand_indo")
    assert table["demand_mw"].tolist() == [31000.0]


def test_initialise_creates_the_file_and_is_repeatable(tmp_path):
    path = tmp_path / "new" / "folder" / "grid.db"
    store = SQLiteStore(path)

    store.initialise()
    store.initialise()

    assert path.is_file()
    assert store.row_count("elexon_demand_indo") == 0


def test_save_model_dataset_matches_build_dataset(tmp_path, monkeypatch):
    dataset = pd.DataFrame({
        "target_time_utc": pd.to_datetime(["2026-11-20T10:00Z", "2026-11-20T10:30Z"], utc=True),
        "forecast_origin_utc": pd.to_datetime(["2026-11-19T10:00Z", None], utc=True),
        "target_drm_mw": [5000.0, 5100.0],
    })
    old_path, new_path = tmp_path / "old.db", tmp_path / "new.db"
    monkeypatch.setattr(build_dataset, "DB_PATH", old_path)
    build_dataset.save_dataset_to_db(dataset)

    SQLiteStore(new_path).save_model_dataset(dataset)
    SQLiteStore(new_path).save_model_dataset(dataset)  # replaces, doesn't append

    assert_frame_equal(_table(new_path, "model_dataset"), _table(old_path, "model_dataset"))
    assert len(_table(new_path, "model_dataset")) == 2
    with sqlite3.connect(new_path) as conn:
        indexes = {row[1] for row in conn.execute("PRAGMA index_list('model_dataset')")}
    assert "idx_model_dataset_target_time" in indexes


def test_failed_write_rolls_back(tmp_path):
    store = SQLiteStore(tmp_path / "grid.db")
    store.initialise()
    good = ROWS["demand_indo"][0]
    bad = {**good, "event_time_utc": TIME.replace(hour=11), "demand_mw": None}  # NOT NULL

    with pytest.raises(sqlite3.IntegrityError):
        store.upsert_demand_indo([good, bad])

    assert store.row_count("elexon_demand_indo") == 0
