"""Tests for the API's cached loaders."""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.api.loaders import (
    FORECAST_TTL_SECONDS,
    LIVE_TTL_SECONDS,
    SLOW_TTL_SECONDS,
    STATUS_TTL_SECONDS,
    Loaders,
)
from backend.api.main import create_app
from core import queries
from core.queries import DatabaseUnavailableError


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def calls(monkeypatch):
    """Replace core.queries.load_recent_margin with a counting fake."""
    made = []

    def fake(days=7):
        made.append(days)
        return pd.DataFrame({
            "event_time_utc": pd.to_datetime(["2026-11-20T10:00Z"]),
            "derated_margin_mw": [float(len(made))],
        })

    monkeypatch.setattr(queries, "load_recent_margin", fake)
    return made


def test_ttls_match_the_dashboard():
    assert (LIVE_TTL_SECONDS, FORECAST_TTL_SECONDS, STATUS_TTL_SECONDS) == (45, 15, 5)
    assert SLOW_TTL_SECONDS == 3600


def test_value_is_cached_until_the_ttl_passes(calls, clock):
    loaders = Loaders(clock=clock)

    first = loaders.load_recent_margin(7)
    clock.now += LIVE_TTL_SECONDS - 1
    second = loaders.load_recent_margin(7)

    assert calls == [7]
    assert first.equals(second)

    clock.now += 1
    third = loaders.load_recent_margin(7)

    assert calls == [7, 7]
    assert third["derated_margin_mw"].iloc[0] == 2.0


def test_arguments_are_cached_separately(calls, clock):
    loaders = Loaders(clock=clock)

    loaders.load_recent_margin(7)
    loaders.load_recent_margin(1)
    loaders.load_recent_margin(7)

    assert calls == [7, 1]


def test_callers_get_copies(calls, clock):
    loaders = Loaders(clock=clock)

    # Change both a freshly loaded value and one served from the cache.
    for _ in range(2):
        value = loaders.load_recent_margin(7)
        value.loc[0, "derated_margin_mw"] = -1.0

    assert loaders.load_recent_margin(7)["derated_margin_mw"].iloc[0] == 1.0
    assert calls == [7]


def test_disabled_cache_always_loads(calls):
    loaders = Loaders(enabled=False)

    loaders.load_recent_margin(7)
    loaders.load_recent_margin(7)

    assert calls == [7, 7]


def test_clear_drops_cached_values(calls, clock):
    loaders = Loaders(clock=clock)

    loaders.load_recent_margin(7)
    loaders.clear()
    loaders.load_recent_margin(7)

    assert calls == [7, 7]


def test_errors_are_not_cached(monkeypatch, clock):
    attempts = []

    def flaky(days=7):
        attempts.append(days)
        if len(attempts) == 1:
            raise DatabaseUnavailableError("not yet")
        return pd.DataFrame({"derated_margin_mw": [1.0]})

    monkeypatch.setattr(queries, "load_recent_margin", flaky)
    loaders = Loaders(clock=clock)

    with pytest.raises(DatabaseUnavailableError):
        loaders.load_recent_margin(7)

    assert len(loaders.load_recent_margin(7)) == 1
    assert attempts == [7, 7]


@pytest.mark.parametrize(
    ("method", "loader", "ttl"),
    [
        ("load_recent_margin", "load_recent_margin", LIVE_TTL_SECONDS),
        ("load_recent_demand", "load_recent_demand", LIVE_TTL_SECONDS),
        ("load_recent_generation", "load_recent_generation", LIVE_TTL_SECONDS),
        ("load_live_generation_mix", "load_live_generation_mix", LIVE_TTL_SECONDS),
        ("load_live_interconnectors", "load_live_interconnectors", LIVE_TTL_SECONDS),
        ("load_latest_forecast", "load_latest_forecast", FORECAST_TTL_SECONDS),
        ("load_refresh_status", "load_refresh_status", STATUS_TTL_SECONDS),
        ("load_last_refresh_completed", "load_last_refresh_completed", STATUS_TTL_SECONDS),
        ("load_margin_history", "load_margin_history", SLOW_TTL_SECONDS),
        ("load_model_metrics", "load_model_metrics", SLOW_TTL_SECONDS),
        ("load_validation_predictions", "load_validation_predictions", SLOW_TTL_SECONDS),
    ],
)
def test_each_loader_uses_its_ttl(monkeypatch, clock, method, loader, ttl):
    made = []
    monkeypatch.setattr(queries, loader, lambda *args: made.append(args) or {"n": len(made)})
    loaders = Loaders(clock=clock)

    getattr(loaders, method)()
    clock.now += ttl - 0.5
    getattr(loaders, method)()
    assert len(made) == 1

    clock.now += 0.5
    getattr(loaders, method)()
    assert len(made) == 2


def test_each_app_has_its_own_cache(calls):
    first, second = create_app(), create_app()

    TestClient(first).get("/api/history/margin")
    TestClient(second).get("/api/history/margin")
    TestClient(first).get("/api/history/margin")

    assert first.state.loaders is not second.state.loaders
    assert calls == [7, 7]


def test_create_app_can_turn_the_cache_off(calls):
    client = TestClient(create_app(cache=False))

    client.get("/api/history/margin")
    client.get("/api/history/margin")

    assert calls == [7, 7]
    assert client.app.state.loaders.enabled is False


def test_routes_use_the_cache(grid_db, monkeypatch):
    monkeypatch.setattr("core.config.DB_PATH", grid_db)
    client = TestClient(create_app())
    loads = []
    real = queries.load_recent_demand
    monkeypatch.setattr(queries, "load_recent_demand", lambda *a: loads.append(a) or real(*a))

    for _ in range(3):
        assert client.get("/api/grid/now").json()["state"] == "ok"

    assert loads == [(7,)]
