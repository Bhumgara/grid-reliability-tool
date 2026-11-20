"""Tests for the FastAPI app: health endpoint and CORS settings."""

import pytest
from fastapi.testclient import TestClient

from backend.api.main import CORS_ORIGINS_ENV, cors_origins_from_env, create_app

WEB_ORIGIN = "http://localhost:5000"


@pytest.fixture(autouse=True)
def no_cors_env(monkeypatch):
    monkeypatch.delenv(CORS_ORIGINS_ENV, raising=False)


def _preflight(client: TestClient, method: str = "GET", origin: str = WEB_ORIGIN):
    return client.options(
        "/api/health",
        headers={"Origin": origin, "Access-Control-Request-Method": method},
    )


def test_health_returns_ok():
    response = TestClient(create_app()).get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_routes_are_under_api_prefix():
    assert TestClient(create_app()).get("/health").status_code == 404


def test_create_app_returns_a_new_app_each_time():
    assert create_app() is not create_app()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", []),
        (" , ", []),
        (WEB_ORIGIN, [WEB_ORIGIN]),
        (
            " http://localhost:5000/ , ,https://grid.example.com",
            [WEB_ORIGIN, "https://grid.example.com"],
        ),
    ],
)
def test_cors_origins_from_env_cleans_the_list(monkeypatch, raw, expected):
    monkeypatch.setenv(CORS_ORIGINS_ENV, raw)

    assert cors_origins_from_env() == expected


def test_cors_origins_from_env_is_empty_when_unset():
    assert cors_origins_from_env() == []


def test_no_cors_headers_when_unset():
    client = TestClient(create_app())

    response = client.get("/api/health", headers={"Origin": WEB_ORIGIN})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
    assert _preflight(client).status_code == 405


def test_allowed_origin_gets_cors_headers(monkeypatch):
    monkeypatch.setenv(CORS_ORIGINS_ENV, WEB_ORIGIN)
    client = TestClient(create_app())

    response = client.get("/api/health", headers={"Origin": WEB_ORIGIN})
    preflight = _preflight(client)

    assert response.headers["access-control-allow-origin"] == WEB_ORIGIN
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == WEB_ORIGIN


def test_other_origins_get_no_cors_headers():
    client = TestClient(create_app([WEB_ORIGIN]))

    response = client.get("/api/health", headers={"Origin": "https://other.example"})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
    assert _preflight(client, origin="https://other.example").status_code == 400


def test_only_get_is_allowed_cross_origin():
    client = TestClient(create_app([WEB_ORIGIN]))

    assert _preflight(client, method="POST").status_code == 400


def test_explicit_origins_override_the_environment(monkeypatch):
    monkeypatch.setenv(CORS_ORIGINS_ENV, WEB_ORIGIN)
    client = TestClient(create_app(cors_origins=[]))

    response = client.get("/api/health", headers={"Origin": WEB_ORIGIN})

    assert "access-control-allow-origin" not in response.headers


def test_missing_database_returns_503_empty_state(tmp_path, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", tmp_path / "grid.db")
    monkeypatch.setattr("core.config.FORECAST_PATH", tmp_path / "forecast.json")
    (tmp_path / "forecast.json").write_text('{"predicted_drm_mw": 1}', encoding="utf-8")
    client = TestClient(create_app([WEB_ORIGIN]))

    response = client.get("/api/forecast/hero", headers={"Origin": WEB_ORIGIN})

    assert response.status_code == 503
    assert response.json() == {
        "state": "unavailable",
        "message": "Grid data is not available yet. Try again shortly.",
    }
    # The web build can still read the body.
    assert response.headers["access-control-allow-origin"] == WEB_ORIGIN
    # The request did not create an empty database.
    assert not (tmp_path / "grid.db").exists()
