"""Tests for the API's ETag / 304 Not Modified middleware."""

import pytest
from fastapi.testclient import TestClient

from backend.api.etag import etag_for, matches
from backend.api.main import create_app
from core import config

WEB_ORIGIN = "http://localhost:5000"


@pytest.fixture
def client(grid_db, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", grid_db)
    return TestClient(create_app())


# --- Matching ------------------------------------------------------------------


def test_etag_is_weak_and_depends_on_the_body():
    assert etag_for(b"a").startswith('W/"')
    assert etag_for(b"a") == etag_for(b"a")
    assert etag_for(b"a") != etag_for(b"b")


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ('W/"abc"', True),
        ('"abc"', True),  # weak comparison ignores W/
        ('W/"xyz", W/"abc"', True),
        ("*", True),
        ('W/"xyz"', False),
        ("", False),
        ('W/"ab"', False),
    ],
)
def test_matches(header, expected):
    assert matches(header, 'W/"abc"') is expected


# --- Middleware ------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    ["/api/status", "/api/grid/now", "/api/history/margin", "/api/health"],
)
def test_successful_gets_have_an_etag_matching_the_body(client, path):
    response = client.get(path)

    assert response.status_code == 200
    assert response.headers["etag"] == etag_for(response.content)


def test_matching_if_none_match_returns_304_without_a_body(client):
    first = client.get("/api/grid/now")

    second = client.get("/api/grid/now", headers={"If-None-Match": first.headers["etag"]})

    assert second.status_code == 304
    assert second.content == b""
    assert second.headers["etag"] == first.headers["etag"]
    assert "content-type" not in second.headers
    assert second.headers.get("content-length", "0") == "0"


def test_different_if_none_match_returns_the_full_response(client):
    first = client.get("/api/grid/now")

    response = client.get("/api/grid/now", headers={"If-None-Match": 'W/"stale"'})

    assert response.status_code == 200
    assert response.json() == first.json()


def test_query_parameters_give_different_etags(client):
    week = client.get("/api/history/margin", params={"days": 7})
    day = client.get("/api/history/margin", params={"days": 1})

    assert week.headers["etag"] != day.headers["etag"]


def test_errors_have_no_etag(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "missing.db")
    client = TestClient(create_app())

    unavailable = client.get("/api/grid/now", headers={"If-None-Match": "*"})
    invalid = client.get("/api/history/margin", params={"days": 0})

    assert unavailable.status_code == 503
    assert "etag" not in unavailable.headers
    assert invalid.status_code == 422
    assert "etag" not in invalid.headers


def test_routes_outside_the_api_have_no_etag(client):
    assert "etag" not in client.get("/openapi.json").headers


def test_etag_is_the_same_with_and_without_gzip(client):
    gzipped = client.get("/api/history/margin", headers={"Accept-Encoding": "gzip"})
    plain = client.get("/api/history/margin", headers={"Accept-Encoding": "identity"})

    assert gzipped.headers["content-encoding"] == "gzip"
    assert "content-encoding" not in plain.headers
    assert gzipped.headers["etag"] == plain.headers["etag"]

    not_modified = client.get(
        "/api/history/margin",
        headers={"Accept-Encoding": "gzip", "If-None-Match": plain.headers["etag"]},
    )
    assert not_modified.status_code == 304


# --- CORS ------------------------------------------------------------------------


@pytest.fixture
def web_client(grid_db, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", grid_db)
    return TestClient(create_app([WEB_ORIGIN]))


def test_browsers_may_read_the_etag(web_client):
    response = web_client.get("/api/grid/now", headers={"Origin": WEB_ORIGIN})

    assert "etag" in response.headers["access-control-expose-headers"].lower()


def test_browsers_may_send_if_none_match(web_client):
    preflight = web_client.options(
        "/api/grid/now",
        headers={
            "Origin": WEB_ORIGIN,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "if-none-match",
        },
    )

    assert preflight.status_code == 200
    assert "if-none-match" in preflight.headers["access-control-allow-headers"].lower()


def test_304_keeps_cors_headers(web_client):
    etag = web_client.get("/api/grid/now", headers={"Origin": WEB_ORIGIN}).headers["etag"]

    response = web_client.get(
        "/api/grid/now",
        headers={"Origin": WEB_ORIGIN, "If-None-Match": etag},
    )

    assert response.status_code == 304
    assert response.headers["access-control-allow-origin"] == WEB_ORIGIN


# --- Cache-Control ---------------------------------------------------------------


@pytest.mark.parametrize("path", ["/api/status", "/api/grid/now", "/api/model/metrics"])
def test_successful_responses_must_revalidate(client, path):
    assert client.get(path).headers["cache-control"] == "no-cache"


def test_304_keeps_cache_control(client):
    etag = client.get("/api/grid/now").headers["etag"]

    response = client.get("/api/grid/now", headers={"If-None-Match": etag})

    assert response.status_code == 304
    assert response.headers["cache-control"] == "no-cache"


def test_errors_are_never_stored(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "missing.db")
    client = TestClient(create_app())

    assert client.get("/api/grid/now").headers["cache-control"] == "no-store"
    assert client.get("/api/history/margin", params={"days": 0}).headers["cache-control"] == "no-store"
    assert client.get("/api/nope").headers["cache-control"] == "no-store"


def test_no_max_age_anywhere(client):
    for path in ["/api/status", "/api/grid/now", "/api/history/demand"]:
        assert "max-age" not in client.get(path).headers["cache-control"]


def test_routes_outside_the_api_have_no_cache_control(client):
    assert "cache-control" not in client.get("/openapi.json").headers
