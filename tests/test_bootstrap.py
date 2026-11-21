"""Tests for the dashboard's refresh-thread flag (no real thread is started)."""

import pytest

from dashboard import bootstrap
from dashboard.bootstrap import REFRESH_THREAD_ENV


class FakeThread:
    started = []

    def __init__(self, target, daemon, name):
        self.target = target
        self.daemon = daemon
        self.name = name

    def start(self):
        FakeThread.started.append(self)


@pytest.fixture(autouse=True)
def fresh_worker_cache(monkeypatch):
    """Clear Streamlit's cached thread and replace threading.Thread."""
    monkeypatch.delenv(REFRESH_THREAD_ENV, raising=False)
    monkeypatch.setattr(bootstrap.threading, "Thread", FakeThread)
    FakeThread.started = []
    bootstrap.start_background_worker.clear()
    yield
    bootstrap.start_background_worker.clear()


@pytest.mark.parametrize("value", [None, "", "1", "true", "yes", "on", "anything"])
def test_thread_is_on_unless_turned_off(monkeypatch, value):
    if value is not None:
        monkeypatch.setenv(REFRESH_THREAD_ENV, value)

    assert bootstrap.refresh_thread_enabled() is True


@pytest.mark.parametrize("value", ["0", "false", "no", "off", "FALSE", " Off "])
def test_thread_can_be_turned_off(monkeypatch, value):
    monkeypatch.setenv(REFRESH_THREAD_ENV, value)

    assert bootstrap.refresh_thread_enabled() is False


def test_start_background_worker_starts_one_daemon_thread():
    first = bootstrap.start_background_worker()
    second = bootstrap.start_background_worker()

    assert FakeThread.started == [first]
    assert second is first
    assert first.daemon is True
    assert first.name == "grid-live-refresh"
    assert first.target is bootstrap._refresh_loop


def test_start_background_worker_does_nothing_when_off(monkeypatch, capsys):
    monkeypatch.setenv(REFRESH_THREAD_ENV, "0")

    assert bootstrap.start_background_worker() is None
    assert FakeThread.started == []
    assert "Dashboard refresh thread off" in capsys.readouterr().out


def test_env_example_documents_the_flag():
    from core.config import PROJECT_ROOT

    assert f"{REFRESH_THREAD_ENV}=" in (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
