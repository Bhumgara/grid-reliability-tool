"""
End-to-end polling: the client checks /api/status, then revalidates data
with If-None-Match, while the worker refreshes underneath.

Uses the real middleware, cached loaders (with a fake clock) and the worker's
completion record; only the refresh itself is faked.
"""

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend import worker
from backend.api.loaders import LIVE_TTL_SECONDS, SLOW_TTL_SECONDS, Loaders
from backend.api.main import create_app
from core import config
from tests.test_views_model import METRICS

FIRST_REFRESH = datetime(2026, 9, 25, 0, 0, tzinfo=timezone.utc)


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class PollingClient:
    """Keeps each endpoint's ETag and body, like the Flutter data layer (4.1/4.2)."""

    def __init__(self, client: TestClient):
        self.client = client
        self.etags: dict[str, str] = {}
        self.bodies: dict[str, dict] = {}

    def get(self, path: str):
        headers = {}
        if path in self.etags:
            headers["If-None-Match"] = self.etags[path]

        response = self.client.get(path, headers=headers)

        if response.status_code == 200:
            self.etags[path] = response.headers["etag"]
            self.bodies[path] = response.json()
        return response

    def last_refresh(self) -> str | None:
        return self.bodies["/api/status"]["last_refresh_completed_utc"]


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def setup(grid_db, tmp_path, monkeypatch, clock):
    monkeypatch.setattr(config, "DB_PATH", grid_db)
    monkeypatch.setattr(config, "STATUS_PATH", tmp_path / "refresh_status.json")
    monkeypatch.setattr(config, "LAST_REFRESH_PATH", tmp_path / "last_refresh.json")
    monkeypatch.setattr(config, "METRICS_PATH", tmp_path / "metrics.json")
    (tmp_path / "metrics.json").write_text(json.dumps(METRICS), encoding="utf-8")

    app = create_app()
    app.state.loaders = Loaders(clock=clock)

    worker.refresh_once(lambda: {"state": "fresh"}, now=lambda: FIRST_REFRESH)

    return PollingClient(TestClient(app)), grid_db, tmp_path


def _worker_check(db=None, *, at, new_margin_mw=None):
    """One worker check at ``at``; optionally change the latest margin in the database."""

    def refresh():
        if new_margin_mw is not None:
            with sqlite3.connect(db) as conn:
                conn.execute(
                    "UPDATE elexon_margin_lolpdrm SET derated_margin_mw = ? "
                    "WHERE event_time_utc = (SELECT MAX(event_time_utc) FROM elexon_margin_lolpdrm)",
                    (new_margin_mw,),
                )
        return {"state": "fresh"}

    worker.refresh_once(refresh, now=lambda: at)


def test_unchanged_data_is_304(setup):
    poller, _, _ = setup

    assert poller.get("/api/status").status_code == 200
    assert poller.get("/api/grid/now").status_code == 200

    assert poller.get("/api/status").status_code == 304
    assert poller.get("/api/grid/now").status_code == 304
    assert poller.last_refresh() == "2026-09-25T00:00:00Z"


def test_refresh_that_changes_data_gives_200_and_a_new_etag(setup, clock):
    poller, db, _ = setup
    poller.get("/api/status")
    poller.get("/api/grid/now")
    old_etag = poller.etags["/api/grid/now"]
    old_refresh = poller.last_refresh()

    _worker_check(db, at=FIRST_REFRESH + timedelta(minutes=5), new_margin_mw=1234.0)
    clock.now += LIVE_TTL_SECONDS

    status = poller.get("/api/status")
    assert status.status_code == 200
    assert poller.last_refresh() == "2026-09-25T00:05:00Z" > old_refresh

    data = poller.get("/api/grid/now")
    assert data.status_code == 200
    assert data.headers["etag"] != old_etag
    assert poller.bodies["/api/grid/now"]["drm_gw"] == pytest.approx(1.234)


def test_data_stays_cached_on_the_server_until_its_ttl(setup, clock):
    poller, db, _ = setup
    poller.get("/api/grid/now")

    _worker_check(db, at=FIRST_REFRESH + timedelta(minutes=5), new_margin_mw=1234.0)
    clock.now += LIVE_TTL_SECONDS - 1

    # Still within the API's 45 s cache: same content, so still 304.
    assert poller.get("/api/grid/now").status_code == 304

    clock.now += 1
    assert poller.get("/api/grid/now").status_code == 200


def test_refresh_without_data_changes_keeps_data_304(setup, clock):
    poller, _, _ = setup
    poller.get("/api/status")
    poller.get("/api/grid/now")

    _worker_check(at=FIRST_REFRESH + timedelta(minutes=5))
    clock.now += LIVE_TTL_SECONDS

    # Status moves on, so the client asks for the data, but it costs only a 304.
    assert poller.get("/api/status").status_code == 200
    assert poller.last_refresh() == "2026-09-25T00:05:00Z"
    assert poller.get("/api/grid/now").status_code == 304


def test_retrain_without_a_refresh_changes_the_metrics_etag(setup, clock):
    poller, _, tmp_path = setup
    poller.get("/api/status")
    poller.get("/api/model/metrics")

    retrained = {**METRICS, "model_mae_mw": 3000.0, "mae_improvement_pct": 26.8}
    (tmp_path / "metrics.json").write_text(json.dumps(retrained), encoding="utf-8")
    clock.now += SLOW_TTL_SECONDS

    # No new refresh...
    assert poller.get("/api/status").status_code == 304
    # ...but the content hash still notices the new model.
    response = poller.get("/api/model/metrics")
    assert response.status_code == 200
    assert poller.bodies["/api/model/metrics"]["model_mae_gw"] == pytest.approx(3.0)


def test_status_etag_changes_mid_refresh_but_last_refresh_does_not(setup, clock):
    poller, _, tmp_path = setup
    poller.get("/api/status")

    # pipelines.refresh writes this while a refresh runs.
    (tmp_path / "refresh_status.json").write_text(
        json.dumps({"state": "refreshing", "started_at_utc": "2026-09-25T00:05:00+00:00"}),
        encoding="utf-8",
    )
    clock.now += LIVE_TTL_SECONDS

    response = poller.get("/api/status")

    # The status body changed, but the time clients compare stayed put, so a
    # well-behaved client doesn't refetch data yet.
    assert response.status_code == 200
    assert poller.bodies["/api/status"]["refresh_state"] == "refreshing"
    assert poller.last_refresh() == "2026-09-25T00:00:00Z"
