import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app
from core import config, queries
from core.views.grid_now import grid_now_view


@pytest.fixture
def client():
    return TestClient(create_app())


def test_grid_now(grid_db, client, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", grid_db)
    view = grid_now_view(
        queries.load_recent_margin(7, db_path=grid_db),
        queries.load_recent_demand(7, db_path=grid_db),
        queries.load_recent_generation(7, db_path=grid_db),
    )

    response = client.get("/api/grid/now")

    assert response.status_code == 200
    assert response.json() == {
        "state": "ok",
        "as_of_utc": "2026-09-24T23:30:00Z",
        "drm_gw": pytest.approx(view.drm_gw),
        "drm_time_utc": "2026-09-24T23:30:00Z",
        "demand_gw": pytest.approx(view.demand_gw),
        "demand_time_utc": "2026-09-24T23:30:00Z",
        "tracked_generation_gw": pytest.approx(view.tracked_generation_gw),
        "generation_time_utc": "2026-09-24T23:30:00Z",
        "stale_after_utc": "2026-09-25T01:00:00Z",
    }


def test_empty_database_is_unavailable(empty_grid_db, client, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", empty_grid_db)

    assert client.get("/api/grid/now").json() == {
        "state": "unavailable",
        "message": "Current grid context is unavailable.",
    }

