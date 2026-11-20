import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app
from core import config, queries
from core.views.generation import generation_change_view, generation_mix_view
from core.views.interconnectors import INTERCONNECTOR_GROUPS


@pytest.fixture
def client():
    return TestClient(create_app())


@pytest.fixture
def db(grid_db, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", grid_db)
    return grid_db


# --- /api/generation/live ------------------------------------------------------


def test_generation_live(db, client):
    view = generation_mix_view(queries.load_live_generation_mix(db_path=db), minimum_share=0.0)

    body = client.get("/api/generation/live").json()

    assert body["state"] == "ok"
    assert body["as_of_utc"] == "2026-09-24T23:55:00Z"
    assert body["total_gw"] == pytest.approx(view.total_gw)
    assert body["embedded_is_actual"] is True
    assert [s["fuel_type"] for s in body["slices"]] == view.mix["fuel_type"].tolist()
    assert [s["generation_gw"] for s in body["slices"]] == pytest.approx(
        view.mix["generation_gw"].tolist()
    )
    assert sum(s["share"] for s in body["slices"]) == pytest.approx(1.0)
    # Largest first, and minimum_share=0 keeps small sources (OTHER is FUELINST's own).
    sizes = [s["generation_gw"] for s in body["slices"]]
    assert sizes == sorted(sizes, reverse=True)


def test_generation_live_embedded_forecast_and_missing(db, client):
    with sqlite3.connect(db) as conn:
        conn.execute("DELETE FROM neso_demand_update WHERE forecast_actual_indicator = 'A'")
    assert client.get("/api/generation/live").json()["embedded_is_actual"] is False

    with sqlite3.connect(db) as conn:
        conn.execute("DELETE FROM neso_demand_update")
    # The API caches the mix for 45 seconds; drop it to see the change.
    client.app.state.loaders.clear()
    assert client.get("/api/generation/live").json()["embedded_is_actual"] is None


def test_generation_live_without_positive_output_is_insufficient(db, client):
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE elexon_generation_fuelinst SET generation_mw = 0")
        conn.execute("DELETE FROM neso_demand_update")

    assert client.get("/api/generation/live").json() == {
        "state": "insufficient",
        "message": "No generation mix available.",
    }


# --- /api/generation/change ----------------------------------------------------


def test_generation_change(db, client):
    view = generation_change_view(
        queries.load_recent_generation(7, db_path=db), lookback_hours=4, top_n=8
    )

    body = client.get("/api/generation/change").json()

    assert body["state"] == "ok"
    assert body["as_of_utc"] == body["latest_time_utc"] == "2026-09-24T23:30:00Z"
    assert body["earlier_time_utc"] == "2026-09-24T19:30:00Z"
    assert len(body["movements"]) == 8
    assert [m["fuel_type"] for m in body["movements"]] == view.movement["fuel_type"].tolist()
    assert [m["delta_gw"] for m in body["movements"]] == pytest.approx(
        view.movement["delta_gw"].tolist()
    )
    assert body["movements"][0]["movement_strength"] == 1.0
    assert set(body["movements"][0]) == {"fuel_type", "delta_gw", "movement_strength"}


def test_generation_change_needs_four_hours_of_history(db, client):
    with sqlite3.connect(db) as conn:
        conn.execute(
            "DELETE FROM elexon_generation_fuelhh WHERE event_time_utc < ?",
            ("2026-09-24T22:00:00+00:00",),
        )

    assert client.get("/api/generation/change").json() == {
        "state": "insufficient",
        "message": "Not enough generation history for movement chart.",
    }


# --- /api/interconnectors/live -------------------------------------------------


def test_interconnectors_live(db, client):
    body = client.get("/api/interconnectors/live").json()

    assert body["state"] == "ok"
    assert body["as_of_utc"] == "2026-09-24T23:55:00Z"
    assert [f["country"] for f in body["flows"]] == list(INTERCONNECTOR_GROUPS)
    flows = {f["country"]: f for f in body["flows"]}
    assert flows["France"] == {"country": "France", "flow_gw": 1.5, "direction": "Import"}
    assert flows["Belgium"]["direction"] == "Idle"
    assert body["net_flow_gw"] == pytest.approx(sum(f["flow_gw"] for f in body["flows"]))


def test_interconnector_export(db, client):
    with sqlite3.connect(db) as conn:
        conn.execute(
            "UPDATE elexon_generation_fuelinst SET generation_mw = -900"
            " WHERE fuel_type = 'INTNSL'"
        )

    flows = {f["country"]: f for f in client.get("/api/interconnectors/live").json()["flows"]}

    assert flows["Norway"]["flow_gw"] == pytest.approx(-0.9)
    assert flows["Norway"]["direction"] == "Export"


# --- Empty database ------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("/api/generation/live", "Live generation data is unavailable."),
        ("/api/generation/change", "Generation data is unavailable."),
        ("/api/interconnectors/live", "No current interconnector data."),
    ],
)
def test_empty_database_is_unavailable(empty_grid_db, client, monkeypatch, path, message):
    monkeypatch.setattr(config, "DB_PATH", empty_grid_db)

    assert client.get(path).json() == {"state": "unavailable", "message": message}
