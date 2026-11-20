import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app
from core import config, queries
from core.views.demand import typical_day_view
from tests.fixtures.grid_db import FIXTURE_END, build_grid_db


@pytest.fixture
def client():
    return TestClient(create_app())


@pytest.fixture
def grid_db_90d(tmp_path, monkeypatch):
    db = build_grid_db(tmp_path / "grid90.db", days=90)
    monkeypatch.setattr(config, "DB_PATH", db)
    return db


def test_typical_day(grid_db_90d, client):
    # The fixture repeats the same day; add a trend (+100 MW a day) so the
    # quartiles differ and the result depends on using all 90 days.
    with sqlite3.connect(grid_db_90d) as conn:
        conn.execute(
            "UPDATE elexon_demand_indo SET demand_mw = demand_mw"
            " + 100 * (julianday(event_time_utc) - julianday('2026-06-01'))"
        )
    view = typical_day_view(queries.load_recent_demand(90, db_path=grid_db_90d))

    response = client.get("/api/demand/typical-day")
    body = response.json()

    assert response.status_code == 200
    assert body["state"] == "ok"
    assert body["as_of_utc"] == "2026-09-24T23:30:00Z"
    # Fixture ends 23:30 UTC on 24 Sep = 00:30 BST on 25 Sep.
    assert body["current_date"] == "2026-09-25"
    assert body["latest_full_date"] == "2026-09-24"
    assert [point["slot"] for point in body["current"]] == [1, 2]
    assert len(body["latest_full"]) == 48

    assert [slot["slot"] for slot in body["typical"]] == list(range(1, 49))
    first = body["typical"][0]
    assert set(first) == {"slot", "q25_gw", "median_gw", "q75_gw"}
    assert [slot["median_gw"] for slot in body["typical"]] == pytest.approx(
        view.typical["median"].tolist()
    )
    assert [slot["q25_gw"] for slot in body["typical"]] == pytest.approx(
        view.typical["q25"].tolist()
    )
    assert [slot["q75_gw"] for slot in body["typical"]] == pytest.approx(
        view.typical["q75"].tolist()
    )
    assert all(s["q25_gw"] < s["median_gw"] < s["q75_gw"] for s in body["typical"])
    assert [p["demand_gw"] for p in body["latest_full"]] == pytest.approx(
        view.latest_full["demand_gw"].tolist()
    )


def test_one_local_day_is_insufficient(grid_db_90d, client):
    # Keep only the two half-hours of the latest local day.
    with sqlite3.connect(grid_db_90d) as conn:
        conn.execute(
            "DELETE FROM elexon_demand_indo WHERE event_time_utc < ?",
            ((FIXTURE_END.replace(hour=23, minute=0)).isoformat(),),
        )

    assert client.get("/api/demand/typical-day").json() == {
        "state": "insufficient",
        "message": (
            "Typical-day demand needs at least one earlier local day for comparison."
        ),
    }


def test_empty_database_is_unavailable(empty_grid_db, client, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", empty_grid_db)

    assert client.get("/api/demand/typical-day").json() == {
        "state": "unavailable",
        "message": "Demand history is unavailable.",
    }
