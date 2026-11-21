"""Tests for choosing the storage backends with environment variables."""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from core import config, db, queries
from core.storage import (
    LocalFileStore,
    SQLiteStore,
    UnknownBackendError,
    check_backends,
    get_file_store,
    get_grid_store,
)
from core.storage import backends
from core.storage.backends import DATABASE_BACKEND_ENV, FILE_BACKEND_ENV
from pipelines import predict, refresh
from tests.test_storage_interface import CompleteStore


@pytest.fixture(autouse=True)
def no_backend_env(monkeypatch):
    monkeypatch.delenv(DATABASE_BACKEND_ENV, raising=False)
    monkeypatch.delenv(FILE_BACKEND_ENV, raising=False)


# --- Choosing --------------------------------------------------------------------


def test_defaults_are_sqlite_and_local_files():
    assert isinstance(get_grid_store(), SQLiteStore)
    assert isinstance(get_file_store(), LocalFileStore)
    assert check_backends() == {"database": "sqlite", "files": "local"}


@pytest.mark.parametrize("value", ["", "  ", "sqlite", "SQLite", " sqlite "])
def test_database_backend_names_are_forgiving(monkeypatch, value):
    monkeypatch.setenv(DATABASE_BACKEND_ENV, value)

    assert backends.database_backend() == "sqlite"


@pytest.mark.parametrize("value", ["", "local", "LOCAL"])
def test_file_backend_names_are_forgiving(monkeypatch, value):
    monkeypatch.setenv(FILE_BACKEND_ENV, value)

    assert backends.file_backend() == "local"


@pytest.mark.parametrize(
    ("env", "getter"),
    [(DATABASE_BACKEND_ENV, get_grid_store), (FILE_BACKEND_ENV, get_file_store)],
)
def test_unknown_backend_is_an_error_listing_the_choices(monkeypatch, env, getter):
    monkeypatch.setenv(env, "postgress")

    with pytest.raises(UnknownBackendError, match=f"{env}='postgress'.*Choose one of"):
        getter()
    with pytest.raises(UnknownBackendError):
        check_backends()


def test_setting_is_read_on_each_call(monkeypatch):
    assert backends.database_backend() == "sqlite"

    monkeypatch.setenv(DATABASE_BACKEND_ENV, "nope")

    with pytest.raises(UnknownBackendError):
        backends.database_backend()


# --- Everything follows the setting -------------------------------------------------


class FakeGridStore(CompleteStore):
    """Every GridStore method, returning canned data."""

    def recent_margin(self, days):
        return pd.DataFrame({
            "event_time_utc": pd.to_datetime(["2026-11-20T10:00Z"]),
            "derated_margin_mw": [1234.0],
        })

    def row_count(self, dataset):
        return 42

    def latest_times(self, dataset):
        return (pd.Timestamp("2026-11-20T10:00Z"), pd.Timestamp("2026-11-20T10:05Z"))


class FakeFileStore:
    def __init__(self):
        self.saved = {}

    def read_json(self, key):
        return self.saved.get(key)

    def write_json(self, key, payload):
        self.saved[key] = payload

    def read_csv(self, key):
        return None

    def write_csv(self, key, frame):
        self.saved[key] = frame

    def location(self, key):
        return f"fake://{key}"


@pytest.fixture
def fake_backends(monkeypatch):
    files = FakeFileStore()
    monkeypatch.setitem(backends.DATABASE_BACKENDS, "fake", FakeGridStore)
    monkeypatch.setitem(backends.FILE_BACKENDS, "fake", lambda: files)
    monkeypatch.setenv(DATABASE_BACKEND_ENV, "fake")
    monkeypatch.setenv(FILE_BACKEND_ENV, "fake")
    return files


def test_queries_use_the_configured_database(fake_backends):
    assert queries.load_recent_margin(7)["derated_margin_mw"].tolist() == [1234.0]


def test_explicit_db_path_still_means_that_sqlite_file(fake_backends, grid_db):
    assert len(queries.load_recent_margin(1, db_path=grid_db)) == 48


def test_core_db_wrappers_use_the_configured_database(fake_backends):
    assert db.count_demand_indo_rows() == 42


def test_refresh_freshness_uses_the_configured_database(fake_backends):
    state = refresh.source_state(refresh.SOURCES[1], now=pd.Timestamp("2026-11-20T10:10Z"))

    assert state["latest_freshness_utc"] == "2026-11-20T10:05:00+00:00"
    assert state["age_minutes"] == 5.0


def test_files_use_the_configured_file_store(fake_backends, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "STATUS_PATH", tmp_path / "status.json")

    refresh.write_status({"state": "fresh"})
    predict.save_forecast({"predicted_drm_mw": 1.0})

    assert fake_backends.saved == {
        "refresh_status": {"state": "fresh"},
        "forecast": {"predicted_drm_mw": 1.0},
    }
    assert queries.load_refresh_status() == {"state": "fresh"}
    assert not (tmp_path / "status.json").exists()


def test_api_serves_from_the_configured_backends(fake_backends):
    from backend.api.main import create_app

    body = TestClient(create_app()).get("/api/history/margin").json()

    assert body["points"] == [{"time_utc": "2026-11-20T10:00:00Z", "drm_gw": 1.234}]


# --- Start-up checks -----------------------------------------------------------------


def test_api_refuses_to_start_with_an_unknown_backend(monkeypatch):
    from backend.api.main import create_app

    monkeypatch.setenv(DATABASE_BACKEND_ENV, "postgress")

    with pytest.raises(UnknownBackendError):
        create_app()


def test_worker_exits_1_with_an_unknown_backend(monkeypatch, caplog):
    from backend import worker

    monkeypatch.setenv(FILE_BACKEND_ENV, "gcs")

    code = worker.main(
        ["--once"],
        ensure_data=lambda: pytest.fail("set up data with a bad backend"),
        refresh=lambda: pytest.fail("refreshed with a bad backend"),
    )

    assert code == 1
    assert "GRID_FILE_BACKEND='gcs'" in caplog.text


def test_env_example_documents_both_settings():
    text = (config.PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")

    assert f"{DATABASE_BACKEND_ENV}=sqlite" in text
    assert f"{FILE_BACKEND_ENV}=local" in text
