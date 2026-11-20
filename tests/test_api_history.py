import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app
from core import config, queries
from core.views.demand import demand_settlement_view
from tests.fixtures.grid_db import DEFAULT_DAYS, FIXTURE_END


@pytest.fixture
def client():
    return TestClient(create_app())


@pytest.fixture
def use_db(monkeypatch):
    def use(path):
        monkeypatch.setattr(config, "DB_PATH", path)

    return use


def test_margin_history_defaults_to_seven_days(grid_db, use_db, client):
    use_db(grid_db)
    margin = queries.load_recent_margin(7, db_path=grid_db)

    body = client.get("/api/history/margin").json()

    assert body["state"] == "ok"
    assert len(body["points"]) == len(margin)
    assert body["points"][-1] == {
        "time_utc": "2026-09-24T23:30:00Z",
        "drm_gw": pytest.approx(margin.iloc[-1]["derated_margin_mw"] / 1000),
    }
    assert body["as_of_utc"] == "2026-09-24T23:30:00Z"
    times = [point["time_utc"] for point in body["points"]]
    assert times == sorted(times)


def test_margin_history_days_parameter(grid_db, use_db, client):
    use_db(grid_db)

    body = client.get("/api/history/margin", params={"days": 1}).json()

    assert len(body["points"]) == 48


def test_demand_history_marks_estimated_gaps(grid_db, use_db, client):
    # Remove two internal half-hours; they come back as estimates.
    gap = [
        (FIXTURE_END.replace(hour=12, minute=0)).isoformat(),
        (FIXTURE_END.replace(hour=12, minute=30)).isoformat(),
    ]
    with sqlite3.connect(grid_db) as conn:
        conn.executemany(
            "DELETE FROM elexon_demand_indo WHERE event_time_utc = ?",
            [(time,) for time in gap],
        )
    use_db(grid_db)
    expected = demand_settlement_view(queries.load_recent_demand(7, db_path=grid_db))

    body = client.get("/api/history/demand").json()

    assert body["state"] == "ok"
    assert len(body["points"]) == len(expected)
    estimated = [point["time_utc"] for point in body["points"] if point["estimated"]]
    assert estimated == ["2026-09-24T12:00:00Z", "2026-09-24T12:30:00Z"]
    assert [point["demand_gw"] for point in body["points"]] == pytest.approx(
        expected["demand_gw"].tolist()
    )
    assert body["as_of_utc"] == "2026-09-24T23:30:00Z"


@pytest.mark.parametrize("path", ["/api/history/margin", "/api/history/demand"])
@pytest.mark.parametrize("days", [0, -1, 91, "week"])
def test_days_out_of_range_is_rejected(grid_db, use_db, client, path, days):
    use_db(grid_db)

    assert client.get(path, params={"days": days}).status_code == 422


@pytest.mark.parametrize("path", ["/api/history/margin", "/api/history/demand"])
def test_longest_window_is_allowed(grid_db, use_db, client, path):
    use_db(grid_db)

    body = client.get(path, params={"days": 90}).json()

    # The fixture holds DEFAULT_DAYS of data.
    assert body["state"] == "ok"
    assert len(body["points"]) >= DEFAULT_DAYS * 48 - 1


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("/api/history/margin", "Margin history is unavailable."),
        ("/api/history/demand", "Demand history is unavailable."),
    ],
)
def test_empty_database_is_unavailable(empty_grid_db, use_db, client, path, message):
    use_db(empty_grid_db)

    assert client.get(path).json() == {"state": "unavailable", "message": message}
