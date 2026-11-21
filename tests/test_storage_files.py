"""Tests for the file store and the code that now reads and writes through it."""

import json
import typing

import pandas as pd
import pytest

from core import config, queries
from core.storage import FileKey, FileStore, LocalFileStore, get_file_store
from core.storage.files import _CONFIG_PATHS
from pipelines import predict, refresh

KEYS = typing.get_args(FileKey)


@pytest.fixture
def files_in_tmp(tmp_path, monkeypatch):
    """Point every file key's core.config path into tmp_path."""
    for key, attribute in _CONFIG_PATHS.items():
        monkeypatch.setattr(config, attribute, tmp_path / "processed" / f"{key}.data")
    return tmp_path / "processed"


# --- LocalFileStore -----------------------------------------------------------------


def test_satisfies_the_interface():
    assert isinstance(LocalFileStore(), FileStore)
    assert isinstance(get_file_store(), FileStore)


def test_every_key_has_a_config_path():
    assert set(_CONFIG_PATHS) == set(KEYS)
    for attribute in _CONFIG_PATHS.values():
        assert hasattr(config, attribute)


def test_default_paths_follow_core_config():
    files = LocalFileStore()

    assert files.path("forecast") == config.FORECAST_PATH
    assert files.path("refresh_status") == config.STATUS_PATH
    assert files.path("last_refresh") == config.LAST_REFRESH_PATH
    assert files.path("validation_predictions") == config.VALIDATION_PATH
    assert files.path("model_dataset") == config.MODEL_DATASET_PATH
    assert files.location("forecast") == str(config.FORECAST_PATH)


def test_paths_are_looked_up_on_each_call(tmp_path, monkeypatch):
    files = LocalFileStore()
    monkeypatch.setattr(config, "STATUS_PATH", tmp_path / "status.json")

    assert files.path("refresh_status") == tmp_path / "status.json"


def test_explicit_paths_override_config(tmp_path):
    files = LocalFileStore({"forecast": tmp_path / "f.json"})

    assert files.path("forecast") == tmp_path / "f.json"
    assert files.path("refresh_status") == config.STATUS_PATH


def test_unknown_key_is_an_error():
    with pytest.raises(KeyError, match="nope"):
        LocalFileStore().path("nope")


def test_json_round_trip(files_in_tmp):
    files = LocalFileStore()

    files.write_json("forecast", {"predicted_drm_mw": 4200.0, "nested": {"a": [1, 2]}})

    assert files.read_json("forecast") == {"predicted_drm_mw": 4200.0, "nested": {"a": [1, 2]}}
    # Creates the folder; leaves no temporary file behind.
    assert sorted(p.name for p in files_in_tmp.iterdir()) == ["forecast.data"]


def test_csv_round_trip(files_in_tmp):
    files = LocalFileStore()
    frame = pd.DataFrame({"target_time_utc": ["2026-11-20T10:00:00+00:00"], "error_mw": [12.5]})

    files.write_csv("validation_predictions", frame)

    pd.testing.assert_frame_equal(files.read_csv("validation_predictions"), frame)


def test_writes_replace_the_whole_file(files_in_tmp):
    files = LocalFileStore()

    files.write_json("refresh_status", {"state": "refreshing", "extra": 1})
    files.write_json("refresh_status", {"state": "fresh"})

    assert files.read_json("refresh_status") == {"state": "fresh"}


@pytest.mark.parametrize(
    "content",
    [None, "", '{"state": "fre', "\xff\xfe not utf-8"],
    ids=["missing", "empty", "half-written", "not-utf8"],
)
def test_unreadable_json_is_none(files_in_tmp, content):
    if content is not None:
        files_in_tmp.mkdir(parents=True, exist_ok=True)
        (files_in_tmp / "forecast.data").write_bytes(content.encode("latin-1"))

    assert LocalFileStore().read_json("forecast") is None


@pytest.mark.parametrize("content", [None, "", '"unclosed\n1,2'], ids=["missing", "empty", "broken"])
def test_unreadable_csv_is_none(files_in_tmp, content):
    if content is not None:
        files_in_tmp.mkdir(parents=True, exist_ok=True)
        (files_in_tmp / "test_predictions.data").write_text(content, encoding="utf-8")

    assert LocalFileStore().read_csv("test_predictions") is None


# --- Callers ------------------------------------------------------------------------


def test_refresh_status_round_trip_follows_config(files_in_tmp):
    # pipelines.refresh used to copy STATUS_PATH at import, ignoring later changes.
    refresh.write_status({"state": "fresh", "message": "ok"})

    assert refresh.read_status() == {"state": "fresh", "message": "ok"}
    assert queries.load_refresh_status() == {"state": "fresh", "message": "ok"}
    assert (files_in_tmp / "refresh_status.data").is_file()


def test_read_status_is_empty_when_missing_or_not_a_dict(files_in_tmp):
    assert refresh.read_status() == {}

    LocalFileStore().write_json("refresh_status", ["not", "a", "dict"])
    assert refresh.read_status() == {}


def test_saved_forecast_is_what_the_api_reads(files_in_tmp):
    forecast = {"generated_at_utc": "2026-11-20T10:00:00", "predicted_drm_mw": 4200.0}

    predict.save_forecast(forecast)

    assert queries.load_latest_forecast() == forecast
    assert refresh.forecast_generated_at() == pd.Timestamp("2026-11-20T10:00:00Z")


@pytest.mark.parametrize(
    "payload",
    [None, {}, {"generated_at_utc": None}, {"generated_at_utc": "soon"}, ["list"]],
)
def test_forecast_generated_at_handles_missing_and_bad_values(files_in_tmp, payload):
    if payload is not None:
        LocalFileStore().write_json("forecast", payload)

    assert refresh.forecast_generated_at() is None


def test_worker_record_is_what_the_api_reads(files_in_tmp):
    from datetime import datetime, timezone

    from backend import worker

    worker.record_refresh_completed(datetime(2026, 11, 20, 10, 1, tzinfo=timezone.utc))

    assert queries.load_last_refresh_completed() == pd.Timestamp("2026-11-20T10:01:00Z")


def test_validation_predictions_fall_back_to_test(files_in_tmp):
    test = pd.DataFrame({"target_time_utc": ["2026-11-20T10:00:00+00:00"], "error_mw": [1.0]})
    LocalFileStore().write_csv("test_predictions", test)

    df = queries.load_validation_predictions()

    assert df["error_mw"].tolist() == [1.0]
    assert str(df["target_time_utc"].dt.tz) == "UTC"

    LocalFileStore().write_csv("validation_predictions", test.assign(error_mw=2.0))
    assert queries.load_validation_predictions()["error_mw"].tolist() == [2.0]


def test_validation_predictions_empty_when_neither_exists(files_in_tmp):
    assert queries.load_validation_predictions().empty


def test_explicit_paths_still_work_for_loaders(tmp_path):
    path = tmp_path / "somewhere" / "forecast.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"predicted_drm_mw": 1.0}), encoding="utf-8")

    assert queries.load_latest_forecast(path) == {"predicted_drm_mw": 1.0}


def test_metrics_are_read_from_artifacts_not_the_file_store():
    # artifacts/ ships with the code; it isn't a FileStore key.
    assert "metrics" not in KEYS
    assert queries.load_model_metrics()["model"] == "Ridge Regression"
