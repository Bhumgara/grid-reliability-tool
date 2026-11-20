import json

import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app
from core import config
from tests.test_views_status import DEGRADED


@pytest.fixture
def status_path(tmp_path, monkeypatch):
    """Point the status loader at a temporary file (not created)."""
    path = tmp_path / "refresh_status.json"
    monkeypatch.setattr(config, "STATUS_PATH", path)
    return path


@pytest.fixture
def client():
    return TestClient(create_app())


def test_status_before_first_refresh(status_path, client):
    response = client.get("/api/status")

    assert response.status_code == 200
    assert response.json() == {
        "state": "ok",
        "as_of_utc": None,
        "refresh_state": "starting",
        "message": (
            "Live refresh worker is starting; "
            "showing cached data until the first check completes."
        ),
        "started_at_utc": None,
        "completed_at_utc": None,
        "forecast_generated_at_utc": None,
        "sources": [],
        "errors": [],
    }


def test_status_from_file(status_path, client):
    status_path.write_text(json.dumps(DEGRADED), encoding="utf-8")

    body = client.get("/api/status").json()

    assert body["state"] == "ok"
    assert body["refresh_state"] == "degraded"
    assert body["as_of_utc"] == "2026-11-20T10:01:30Z"
    assert body["completed_at_utc"] == "2026-11-20T10:01:30Z"
    assert body["started_at_utc"] == "2026-11-20T10:00:00Z"
    assert body["sources"][0] == {
        "name": "LOLPDRM",
        "required": True,
        "latest_event_utc": "2026-11-20T09:30:00Z",
        "age_minutes": 26.5,
        "stale": False,
    }
    assert body["errors"] == [
        "NESO generation mix: HTTPError: 503 error",
        "Prediction: ValueError: no rows",
    ]


def test_half_written_file_reads_as_starting(status_path, client):
    status_path.write_text('{"state": "fre', encoding="utf-8")

    assert client.get("/api/status").json()["refresh_state"] == "starting"


def test_status_is_in_openapi_schema(client):
    schema = client.get("/openapi.json").json()

    assert "/api/status" in schema["paths"]
    assert "StatusResponse" in schema["components"]["schemas"]
