"""
The pipelines read and write through a GridStore: the model dataset build,
the 24-hour prediction, refresh freshness checks and the core.db wrappers
used by ingestion. Runs against the fixture database; output files go to
tmp_path.
"""

import json
from datetime import timedelta

import pandas as pd
import pytest

from core import db
from core.storage import SQLiteStore
from pipelines import build_dataset, predict, refresh
from tests.test_storage_sqlite import ROWS, TIME


@pytest.fixture
def store(grid_db):
    return SQLiteStore(grid_db)


@pytest.fixture(autouse=True)
def outputs_in_tmp(tmp_path, monkeypatch):
    """Keep the CSV and forecast files out of the real data folder."""
    monkeypatch.setattr("core.config.MODEL_DATASET_PATH", tmp_path / "model_dataset.csv")
    monkeypatch.setattr("core.config.FORECAST_PATH", tmp_path / "latest_forecast.json")


def test_build_model_dataset_saves_to_the_store(store, tmp_path):
    df = build_dataset.build_model_dataset(store)

    assert len(df) > 0
    assert store.row_count("model_dataset") == len(df)
    assert (tmp_path / "model_dataset.csv").is_file()


def test_load_model_inputs_comes_from_the_store(store):
    targets, demand, fuel, margin = build_dataset.load_model_inputs(store)

    assert targets.equals(store.model_targets())
    assert demand.equals(store.model_demand())
    assert fuel.equals(store.model_fuel(build_dataset.FUEL_TYPES))
    assert margin.equals(store.model_margin_history())


def test_run_prediction_reads_from_the_store(store, tmp_path):
    forecast = predict.run_prediction(store)

    latest = store.recent_margin(1)
    assert pd.Timestamp(forecast["forecast_origin_utc"]) == latest["event_time_utc"].iloc[-1]
    assert forecast["latest_drm_mw"] == pytest.approx(latest["derated_margin_mw"].iloc[-1])
    assert json.loads((tmp_path / "latest_forecast.json").read_text())["target_time_utc"] == (
        forecast["target_time_utc"]
    )


def test_run_prediction_without_a_database_raises(tmp_path):
    with pytest.raises(Exception, match="Database not found"):
        predict.run_prediction(SQLiteStore(tmp_path / "missing.db"))


NOW = pd.Timestamp("2026-09-25T00:10:00Z")


def test_source_state_uses_the_store(store):
    states = {spec.name: refresh.source_state(spec, now=NOW, store=store) for spec in refresh.SOURCES}

    demand = states["Demand"]
    assert demand["latest_event_utc"] == "2026-09-24T23:30:00+00:00"
    assert demand["latest_freshness_utc"] == "2026-09-25T00:00:00+00:00"
    assert demand["age_minutes"] == 10.0
    assert demand["stale"] is False

    # The fixture publishes margins an hour early, so they're 100 minutes old.
    assert states["LOLPDRM"]["age_minutes"] == 100.0
    assert states["LOLPDRM"]["stale"] is True

    # No NESO generation mix rows in the fixture.
    assert states["NESO generation mix"]["latest_event_utc"] is None
    assert states["NESO generation mix"]["stale"] is True


def test_source_state_with_a_missing_database(tmp_path):
    state = refresh.source_state(refresh.SOURCES[0], now=NOW, store=SQLiteStore(tmp_path / "x.db"))

    assert state == {
        "name": "LOLPDRM",
        "required": True,
        "latest_event_utc": None,
        "latest_freshness_utc": None,
        "age_minutes": None,
        "stale": True,
    }
    assert not (tmp_path / "x.db").exists()


def test_source_state_defaults_to_the_configured_database(grid_db, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", grid_db)

    state = refresh.source_state(refresh.SOURCES[1], now=NOW)

    assert state["latest_event_utc"] == "2026-09-24T23:30:00+00:00"


def test_core_db_wrappers_write_to_the_configured_database(tmp_path, monkeypatch):
    path = tmp_path / "grid.db"
    monkeypatch.setattr("core.config.DB_PATH", path)

    db.initialise_database()
    # Different counts per table, so a wrapper counting the wrong table fails.
    later = {**ROWS["demand_indo"][0], "event_time_utc": TIME + timedelta(minutes=30)}
    db.upsert_demand_indo_rows([*ROWS["demand_indo"], later])
    db.upsert_margin_lolpdrm_rows(ROWS["margin_lolpdrm"])

    assert db.count_demand_indo_rows() == 2
    assert db.count_margin_lolpdrm_rows() == 1
    assert db.count_target_rows() == 1
    assert db.count_generation_fuelhh_rows() == 0
    assert SQLiteStore(path).recent_demand(1)["demand_mw"].tolist() == [30000.0, 30000.0]
