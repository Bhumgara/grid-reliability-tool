import json

import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app
from core import config, queries
from core.margin import calculate_margin_percentile
from tests.test_views_forecast import HERO_FORECAST


@pytest.fixture
def forecast_path(tmp_path, monkeypatch):
    """Point the forecast loader at a temporary file (not created)."""
    path = tmp_path / "latest_forecast.json"
    monkeypatch.setattr(config, "FORECAST_PATH", path)
    return path


@pytest.fixture
def client():
    return TestClient(create_app())


def _use_db(monkeypatch, path):
    monkeypatch.setattr(config, "DB_PATH", path)


def test_forecast_hero(grid_db, forecast_path, client, monkeypatch):
    _use_db(monkeypatch, grid_db)
    forecast_path.write_text(json.dumps(HERO_FORECAST), encoding="utf-8")

    response = client.get("/api/forecast/hero")
    body = response.json()

    margin = queries.load_recent_margin(7, db_path=grid_db)
    latest_gw = margin.iloc[-1]["derated_margin_mw"] / 1000
    history = queries.load_margin_history(db_path=grid_db)

    assert response.status_code == 200
    assert body["state"] == "ok"
    assert body["as_of_utc"] == "2026-09-25T00:05:00Z"
    assert body["generated_at_utc"] == "2026-09-25T00:05:00Z"
    assert body["target_time_utc"] == "2026-09-25T23:30:00Z"
    assert body["forecast_origin_utc"] == "2026-09-24T23:30:00Z"
    assert body["latest_time_utc"] == "2026-09-24T23:30:00Z"
    assert body["predicted_drm_gw"] == pytest.approx(4.2)
    assert body["latest_drm_gw"] == pytest.approx(latest_gw)
    assert body["percentile"] == pytest.approx(
        calculate_margin_percentile(4200.0, history)
    )
    assert isinstance(body["percentile_description"], str)
    assert set(body["bridge"]) == {
        "current_drm_gw", "predicted_drm_gw", "change_gw",
        "direction", "axis_min_gw", "axis_max_gw",
    }
    assert body["bridge"]["current_drm_gw"] == pytest.approx(latest_gw)
    assert body["bridge"]["direction"] == ("up" if 4.2 > latest_gw else "down")


def test_no_saved_forecast_is_unavailable(grid_db, forecast_path, client, monkeypatch):
    _use_db(monkeypatch, grid_db)

    assert client.get("/api/forecast/hero").json() == {
        "state": "unavailable",
        "message": "A saved forecast is not currently available.",
    }


def test_no_recent_margin_is_unavailable(empty_grid_db, forecast_path, client, monkeypatch):
    _use_db(monkeypatch, empty_grid_db)
    forecast_path.write_text(json.dumps(HERO_FORECAST), encoding="utf-8")

    assert client.get("/api/forecast/hero").json()["state"] == "unavailable"


def test_incomplete_forecast_is_insufficient(grid_db, forecast_path, client, monkeypatch):
    _use_db(monkeypatch, grid_db)
    forecast_path.write_text(json.dumps({"predicted_drm_mw": 4200.0}), encoding="utf-8")

    assert client.get("/api/forecast/hero").json() == {
        "state": "insufficient",
        "message": "The saved forecast is incomplete.",
    }


def test_forecast_hero_is_in_openapi_schema(client):
    schema = client.get("/openapi.json").json()
    responses = schema["paths"]["/api/forecast/hero"]["get"]["responses"]
    options = responses["200"]["content"]["application/json"]["schema"]["anyOf"]

    assert {option["$ref"] for option in options} == {
        "#/components/schemas/ForecastHeroResponse",
        "#/components/schemas/EmptyState",
    }
