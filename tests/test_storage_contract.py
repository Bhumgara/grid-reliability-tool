"""
Contract tests: behaviour every storage backend must have.

These use only the GridStore and FileStore methods (no SQL, no paths), so a
new backend passes them by adding a factory to GRID_STORES or FILE_STORES.
A guard test fails if a backend is registered in core/storage/backends.py
without one. Each test runs once per backend.
"""

from __future__ import annotations

import typing
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest

from core.storage import (
    DatabaseUnavailableError,
    Dataset,
    FileKey,
    FileStore,
    GridStore,
    LocalFileStore,
    SQLiteStore,
)
from core.storage import backends
from core.storage.files import _CONFIG_PATHS

# Backend name -> a function that returns a new store (not yet initialised)
# using only the private tmp_path it is given.
GRID_STORES: dict[str, Callable] = {
    "sqlite": lambda tmp: SQLiteStore(tmp / "grid.db"),
}
FILE_STORES: dict[str, Callable] = {
    "local": lambda tmp: LocalFileStore(
        {key: tmp / "files" / f"{key}.out" for key in _CONFIG_PATHS}
    ),
}

END = datetime(2026, 11, 20, 23, 30, tzinfo=timezone.utc)
HALF_HOUR = timedelta(minutes=30)


def test_every_registered_backend_has_contract_tests():
    assert set(backends.DATABASE_BACKENDS) == set(GRID_STORES)
    assert set(backends.FILE_BACKENDS) == set(FILE_STORES)


@pytest.fixture(params=sorted(GRID_STORES))
def missing(request, tmp_path) -> GridStore:
    """A store that hasn't been created yet."""
    return GRID_STORES[request.param](tmp_path)


@pytest.fixture
def store(missing) -> GridStore:
    """A created, empty store."""
    missing.initialise()
    return missing


@pytest.fixture(params=sorted(FILE_STORES))
def files(request, tmp_path) -> FileStore:
    return FILE_STORES[request.param](tmp_path)


# --- Row builders: normalised records, as core.normalise produces -----------------


def _times(count: int, end: datetime = END) -> list[datetime]:
    return [end - HALF_HOUR * (count - 1 - i) for i in range(count)]


def _settlement(t: datetime) -> tuple[date, int]:
    return t.date(), t.hour * 2 + t.minute // 30 + 1


def margin_rows(times, horizon=1, margin=lambda i: 5000.0 + i):
    rows = []
    for i, t in enumerate(times):
        day, period = _settlement(t)
        rows.append({
            "event_time_utc": t, "published_at_utc": t - timedelta(hours=horizon),
            "forecast_horizon_hours": horizon, "settlement_date": day,
            "settlement_period": period, "derated_margin_mw": margin(i),
            "loss_of_load_probability": 0.001, "source": "elexon",
        })
    return rows


def demand_rows(times, demand=lambda i: 30000.0 + i):
    rows = []
    for i, t in enumerate(times):
        day, period = _settlement(t)
        rows.append({
            "event_time_utc": t, "published_at_utc": t + HALF_HOUR,
            "settlement_date": day, "settlement_period": period,
            "demand_mw": demand(i), "source": "elexon",
        })
    return rows


def generation_rows(times, outputs: dict[str, float], source="elexon"):
    rows = []
    for t in times:
        day, period = _settlement(t)
        for fuel, mw in outputs.items():
            rows.append({
                "event_time_utc": t, "published_at_utc": t + HALF_HOUR,
                "settlement_date": day, "settlement_period": period,
                "fuel_type": fuel, "generation_mw": mw, "source": source,
            })
    return rows


def neso_demand_rows(t: datetime, actual=(1200.0, 300.0), forecast=(999.0, 999.0)):
    day, period = _settlement(t)
    rows = []
    for indicator, values in (("A", actual), ("F", forecast)):
        if values is not None:
            rows.append({
                "settlement_date": day.isoformat(), "settlement_period": period,
                "forecast_actual_indicator": indicator,
                "embedded_wind_mw": values[0], "embedded_solar_mw": values[1],
                "pump_storage_pumping_mw": 0.0, "source": "neso_demand_update",
            })
    return rows


def _assert_utc(values):
    assert str(pd.Series(values).dt.tz) == "UTC"


# --- A store that doesn't exist yet --------------------------------------------------


@pytest.mark.parametrize(
    "read",
    [
        lambda s: s.recent_margin(7), lambda s: s.recent_demand(7),
        lambda s: s.recent_generation(7), lambda s: s.live_generation_mix(),
        lambda s: s.live_interconnectors(), lambda s: s.margin_history(),
        lambda s: s.model_targets(), lambda s: s.model_demand(),
        lambda s: s.model_fuel(["WIND"]), lambda s: s.model_margin_history(),
    ],
)
def test_reads_from_a_missing_store_raise(missing, read):
    with pytest.raises(DatabaseUnavailableError):
        read(missing)


def test_freshness_and_counts_of_a_missing_store_are_empty(missing):
    assert missing.latest_times("elexon_demand_indo") == (None, None)
    assert missing.row_count("elexon_demand_indo") == 0
    assert missing.target_row_count() == 0


def test_initialise_is_repeatable(missing):
    missing.initialise()
    missing.initialise()

    assert missing.row_count("elexon_margin_lolpdrm") == 0


# --- An empty store ------------------------------------------------------------------


def test_reads_from_an_empty_store_are_empty(store):
    for frame in [
        store.recent_margin(7), store.recent_demand(7), store.recent_generation(7),
        store.live_generation_mix(), store.live_interconnectors(), store.margin_history(),
        store.model_targets(), store.model_demand(), store.model_margin_history(),
    ]:
        assert len(frame) == 0


@pytest.mark.parametrize("dataset", typing.get_args(Dataset))
def test_empty_datasets_have_no_times_or_rows(store, dataset):
    assert store.latest_times(dataset) == (None, None)
    assert store.row_count(dataset) == 0


# --- Margin ----------------------------------------------------------------------------


def test_recent_margin_is_the_latest_one_hour_ahead_values(store):
    times = _times(3 * 48)
    store.upsert_margin_lolpdrm(margin_rows(times))
    store.upsert_margin_lolpdrm(margin_rows(times, horizon=8, margin=lambda i: -1.0))

    df = store.recent_margin(1)

    assert list(df.columns) == ["event_time_utc", "derated_margin_mw"]
    _assert_utc(df["event_time_utc"])
    assert df["event_time_utc"].tolist() == [pd.Timestamp(t) for t in times[-48:]]
    assert df["derated_margin_mw"].tolist() == [5000.0 + i for i in range(96, 144)]


def test_null_margins_are_left_out_but_counted_as_targets(store):
    times = _times(4)
    store.upsert_margin_lolpdrm(margin_rows(times, margin=lambda i: None if i == 1 else 1.0 * i))

    assert len(store.recent_margin(7)) == 3
    # The interface doesn't promise an order for the history values.
    assert sorted(store.margin_history().tolist()) == [0.0, 2.0, 3.0]
    assert store.target_row_count() == 4
    assert store.row_count("elexon_margin_lolpdrm") == 4


def test_margin_model_inputs(store):
    times = _times(5)
    store.upsert_margin_lolpdrm(margin_rows(times))
    store.upsert_margin_lolpdrm(margin_rows(times, horizon=8))

    targets = store.model_targets()
    history = store.model_margin_history()

    assert list(targets.columns) == [
        "target_time_utc", "target_published_at_utc", "settlement_date",
        "settlement_period", "target_drm_mw",
    ]
    assert targets["target_time_utc"].tolist() == [pd.Timestamp(t) for t in times]
    _assert_utc(targets["target_published_at_utc"])
    assert len(history) == 5
    assert (history["forecast_horizon_hours"] == 1).all()
    assert history["published_at_utc"].is_monotonic_increasing


def test_upserting_a_margin_key_replaces_it(store):
    (t,) = _times(1)
    store.upsert_margin_lolpdrm(margin_rows([t], margin=lambda i: 100.0))
    store.upsert_margin_lolpdrm(margin_rows([t], margin=lambda i: 200.0))

    assert store.recent_margin(1)["derated_margin_mw"].tolist() == [200.0]
    assert store.row_count("elexon_margin_lolpdrm") == 1


# --- Demand ----------------------------------------------------------------------------


def test_recent_demand_and_model_demand(store):
    times = _times(60)
    store.upsert_demand_indo(demand_rows(times))

    recent = store.recent_demand(1)
    model = store.model_demand()

    assert list(recent.columns) == ["event_time_utc", "demand_mw"]
    assert recent["event_time_utc"].tolist() == [pd.Timestamp(t) for t in times[-48:]]
    assert list(model.columns) == ["demand_event_time_utc", "demand_published_at_utc", "demand_mw"]
    assert len(model) == 60
    _assert_utc(model["demand_published_at_utc"])


def test_upserting_a_demand_key_replaces_it(store):
    rows = demand_rows(_times(1))
    store.upsert_demand_indo(rows)
    store.upsert_demand_indo([{**rows[0], "demand_mw": 1.0}])

    assert store.recent_demand(1)["demand_mw"].tolist() == [1.0]


# --- Half-hourly generation (FUELHH) ----------------------------------------------------


def test_recent_generation_is_wide_and_windowed_from_the_latest_period(store):
    times = _times(3 * 48)
    store.upsert_generation_fuelhh(generation_rows(times, {"WIND": 8000.0, "CCGT": 9000.0}))

    df = store.recent_generation(1)

    assert set(df.columns) == {"WIND", "CCGT"}
    assert str(df.index.tz) == "UTC"
    assert df.index[-1] == pd.Timestamp(END)
    assert df.index[0] == pd.Timestamp(END) - pd.Timedelta(days=1)
    assert (df["WIND"] == 8000.0).all()


def test_model_fuel_keeps_only_requested_fuels_with_model_names(store):
    times = _times(3)
    store.upsert_generation_fuelhh(
        generation_rows(times, {"WIND": 8000.0, "CCGT": 9000.0, "COAL": 5.0})
    )

    df = store.model_fuel(["WIND", "CCGT"])

    assert set(df.columns) == {"fuel_event_time_utc", "fuel_published_at_utc", "ccgt_mw", "wind_mw"}
    assert len(df) == 3
    _assert_utc(df["fuel_event_time_utc"])


# --- Live generation (FUELINST + NESO) -------------------------------------------------

LIVE = {"CCGT": 9000.0, "OCGT": 50.0, "WIND": 8000.0, "NUCLEAR": 4500.0,
        "INTFR": 1500.0, "INTNSL": -700.0}


@pytest.fixture
def live(store):
    latest, earlier = END, END - timedelta(minutes=5)
    store.upsert_generation_fuelinst(
        generation_rows([earlier], {fuel: mw * 0.5 for fuel, mw in LIVE.items()}, "elexon_fuelinst")
    )
    store.upsert_generation_fuelinst(generation_rows([latest], LIVE, "elexon_fuelinst"))
    return store, latest


def test_live_mix_uses_the_latest_snapshot_and_neso_actuals(live):
    store, latest = live
    store.upsert_neso_demand_update(neso_demand_rows(latest))

    df = store.live_generation_mix().set_index("fuel_type")

    assert set(df.index) == {"CCGT", "COAL", "OIL", "NUCLEAR", "BIOMASS",
                             "NPSHYD", "OTHER", "WIND", "SOLAR"}
    assert (df["event_time_utc"] == pd.Timestamp(latest)).all()
    _assert_utc(df["event_time_utc"])
    assert df.loc["CCGT", "generation_mw"] == 9050.0  # OCGT merged in
    assert df.loc["WIND", "generation_mw"] == 8000.0 + 1200.0
    assert df.loc["SOLAR", "generation_mw"] == 300.0
    assert df.loc["COAL", "generation_mw"] == 0.0
    assert (df["embedded_data_status"] == "A").all()


def test_live_mix_falls_back_to_neso_forecast_then_nothing(live):
    store, latest = live
    store.upsert_neso_demand_update(neso_demand_rows(latest, actual=None))

    forecast = store.live_generation_mix().set_index("fuel_type")
    assert forecast.loc["WIND", "generation_mw"] == 8000.0 + 999.0
    assert (forecast["embedded_data_status"] == "F").all()


def test_live_mix_without_neso(live):
    store, _ = live

    df = store.live_generation_mix().set_index("fuel_type")

    assert df.loc["WIND", "generation_mw"] == 8000.0
    assert df.loc["SOLAR", "generation_mw"] == 0.0
    assert df["embedded_data_status"].isna().all()


def test_live_interconnectors_are_the_latest_int_flows(live):
    store, latest = live

    df = store.live_interconnectors()

    assert list(df.columns) == ["event_time_utc", "fuel_type", "generation_mw"]
    flows = dict(zip(df["fuel_type"], df["generation_mw"]))
    assert flows == {"INTFR": 1500.0, "INTNSL": -700.0}
    assert (df["event_time_utc"] == pd.Timestamp(latest)).all()


# --- Freshness ---------------------------------------------------------------------------


def test_latest_times_are_the_latest_event_and_publication(store):
    times = _times(4)
    store.upsert_demand_indo(demand_rows(times))

    event, freshness = store.latest_times("elexon_demand_indo")

    assert event == pd.Timestamp(END)
    assert freshness == pd.Timestamp(END + HALF_HOUR)
    assert str(event.tz) == str(freshness.tz) == "UTC"


def test_latest_times_fall_back_to_the_interval_start(store):
    start = END - HALF_HOUR
    store.upsert_neso_generation_mix([{
        "interval_start_utc": start, "interval_end_utc": END,
        "biomass_pct": 5.0, "coal_pct": 0.0, "imports_pct": 10.0, "gas_pct": 30.0,
        "nuclear_pct": 15.0, "other_pct": 1.0, "hydro_pct": 1.0, "solar_pct": 8.0,
        "wind_pct": 30.0, "source": "neso_carbon_intensity",
    }])

    assert store.latest_times("neso_generation_mix") == (pd.Timestamp(start), pd.Timestamp(start))
    assert store.row_count("neso_generation_mix") == 1


# --- Model dataset -----------------------------------------------------------------------


def test_saving_the_model_dataset_replaces_it(store):
    dataset = pd.DataFrame({
        "target_time_utc": pd.to_datetime(["2026-11-20T10:00Z", "2026-11-20T10:30Z"], utc=True),
        "target_drm_mw": [5000.0, 5100.0],
    })

    store.save_model_dataset(dataset)
    store.save_model_dataset(dataset.iloc[:1])

    assert store.row_count("model_dataset") == 1


# --- File stores -----------------------------------------------------------------------

FILE_KEYS = typing.get_args(FileKey)


def test_file_store_satisfies_the_interface(files):
    assert isinstance(files, FileStore)


@pytest.mark.parametrize("key", FILE_KEYS)
def test_missing_files_read_as_none(files, key):
    assert files.read_json(key) is None
    assert files.read_csv(key) is None


@pytest.mark.parametrize("key", FILE_KEYS)
def test_json_round_trip_and_replace(files, key):
    files.write_json(key, {"a": 1, "nested": {"b": [1.5, None, "x"]}})
    assert files.read_json(key) == {"a": 1, "nested": {"b": [1.5, None, "x"]}}

    files.write_json(key, {"a": 2})
    assert files.read_json(key) == {"a": 2}


@pytest.mark.parametrize("key", ["validation_predictions", "test_predictions", "model_dataset"])
def test_csv_round_trip_and_replace(files, key):
    frame = pd.DataFrame({"target_time_utc": ["2026-11-20T10:00:00+00:00"], "error_mw": [1.5]})
    files.write_csv(key, frame)
    pd.testing.assert_frame_equal(files.read_csv(key), frame)

    files.write_csv(key, frame.assign(error_mw=2.5))
    assert files.read_csv(key)["error_mw"].tolist() == [2.5]


def test_keys_are_independent(files):
    files.write_json("forecast", {"which": "forecast"})
    files.write_json("refresh_status", {"which": "status"})

    assert files.read_json("forecast") == {"which": "forecast"}
    assert files.read_json("refresh_status") == {"which": "status"}


def test_location_names_where_a_key_lives(files):
    assert isinstance(files.location("forecast"), str)
    assert files.location("forecast") != files.location("refresh_status")
