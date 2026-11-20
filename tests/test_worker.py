"""Tests for the standalone refresh worker, with a fake refresh (no network)."""

import logging
import signal
import threading

import pytest

from backend import worker
from core import config


class StoppingRefresh:
    """Fake refresh that records calls and sets ``stop`` after ``limit`` of them."""

    def __init__(self, stop: threading.Event, limit: int, fail_on=()):
        self.stop = stop
        self.limit = limit
        self.fail_on = set(fail_on)
        self.calls = 0

    def __call__(self) -> dict:
        self.calls += 1
        if self.calls >= self.limit:
            self.stop.set()
        if self.calls in self.fail_on:
            raise RuntimeError(f"boom {self.calls}")
        return {"state": "fresh", "message": "ok"}


def test_refresh_once_logs_the_state(caplog):
    caplog.set_level(logging.INFO, logger="backend.worker")

    status = worker.refresh_once(lambda: {"state": "degraded", "message": "late"})

    assert status == {"state": "degraded", "message": "late"}
    assert "Refresh check: degraded. late" in caplog.text


def test_refresh_once_logs_and_swallows_errors(caplog):
    def broken():
        raise RuntimeError("API down")

    assert worker.refresh_once(broken) is None
    assert "Refresh check failed" in caplog.text
    assert "API down" in caplog.text


def test_run_forever_checks_immediately_then_on_each_interval():
    stop = threading.Event()
    refresh = StoppingRefresh(stop, limit=3)

    worker.run_forever(stop, refresh=refresh, interval_seconds=0)

    assert refresh.calls == 3


def test_run_forever_keeps_going_after_a_failed_check():
    stop = threading.Event()
    refresh = StoppingRefresh(stop, limit=3, fail_on={1, 2})

    worker.run_forever(stop, refresh=refresh, interval_seconds=0)

    assert refresh.calls == 3


def test_run_forever_does_nothing_when_already_stopped():
    stop = threading.Event()
    stop.set()
    refresh = StoppingRefresh(stop, limit=99)

    worker.run_forever(stop, refresh=refresh, interval_seconds=0)

    assert refresh.calls == 0


def test_run_forever_uses_the_shared_interval_by_default(monkeypatch):
    waits = []

    class RecordingEvent(threading.Event):
        def wait(self, timeout=None):
            waits.append(timeout)
            self.set()
            return True

    stop = RecordingEvent()

    worker.run_forever(stop, refresh=lambda: {})

    assert waits == [config.REFRESH_CHECK_SECONDS]


def test_stop_interrupts_the_wait():
    stop = threading.Event()
    calls = []
    thread = threading.Thread(
        target=worker.run_forever,
        kwargs={"stop": stop, "refresh": lambda: calls.append(1) or {}, "interval_seconds": 60},
    )

    thread.start()
    stop.set()
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert len(calls) <= 1


def test_default_refresh_calls_the_pipeline(monkeypatch):
    import pipelines.refresh

    monkeypatch.setattr(pipelines.refresh, "refresh_live_data", lambda: {"state": "fresh"})

    assert worker._default_refresh() == {"state": "fresh"}


@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
def test_signals_set_the_stop_event(monkeypatch, signum):
    handlers = {}
    monkeypatch.setattr(worker.signal, "signal", lambda sig, handler: handlers.update({sig: handler}))
    stop = threading.Event()

    worker._stop_on_signals(stop)
    handlers[signum](signum, None)

    assert stop.is_set()


# --- --once and main() ---------------------------------------------------------


def _data_ready() -> bool:
    """Stand-in for ensure_deployment_data when the database already exists."""
    return False


@pytest.mark.parametrize(
    ("status", "code"),
    [
        ({"state": "fresh"}, 0),
        ({"state": "degraded"}, 0),
        ({"state": "refreshing"}, 0),
        ({}, 0),
        ({"state": "failed"}, 1),
        (None, 1),
    ],
)
def test_exit_code(status, code):
    assert worker.exit_code(status) == code


def test_once_runs_one_check_and_exits(monkeypatch):
    calls = []
    monkeypatch.setattr(worker, "run_forever", lambda *a, **k: pytest.fail("looped"))

    code = worker.main(["--once"], ensure_data=_data_ready, refresh=lambda: calls.append(1) or {"state": "fresh"})

    assert code == 0
    assert calls == [1]


@pytest.mark.parametrize("refresh_result", ["raise", "failed"])
def test_once_exits_1_when_the_check_fails(refresh_result):
    def refresh():
        if refresh_result == "raise":
            raise RuntimeError("API down")
        return {"state": "failed", "message": "Live refresh failed"}

    assert worker.main(["--once"], ensure_data=_data_ready, refresh=refresh) == 1


def test_main_without_once_runs_the_loop(monkeypatch):
    ran = {}

    def fake_run_forever(stop, refresh):
        ran["refresh"] = refresh

    monkeypatch.setattr(worker, "run_forever", fake_run_forever)
    monkeypatch.setattr(worker, "_stop_on_signals", lambda stop: None)

    def refresh():
        return {}

    assert worker.main([], refresh=refresh, ensure_data=_data_ready) == 0
    assert ran["refresh"] is refresh


def test_unknown_argument_is_rejected():
    with pytest.raises(SystemExit) as error:
        worker.main(["--twice"])

    assert error.value.code == 2


# --- Deployment data -----------------------------------------------------------


def test_prepare_data_when_database_exists(caplog):
    caplog.set_level(logging.INFO, logger="backend.worker")

    assert worker.prepare_data(lambda: False) is True
    assert "Downloaded" not in caplog.text


def test_prepare_data_logs_a_download(caplog):
    caplog.set_level(logging.INFO, logger="backend.worker")

    assert worker.prepare_data(lambda: True) is True
    assert "Downloaded the deployment bundle" in caplog.text


def test_prepare_data_reports_failure(caplog):
    def no_url():
        raise RuntimeError("no deployment bundle URL is configured")

    assert worker.prepare_data(no_url) is False
    assert "Could not set up the deployment data" in caplog.text
    assert "no deployment bundle URL" in caplog.text


@pytest.mark.parametrize("args", [[], ["--once"]])
def test_data_is_prepared_before_the_first_check(monkeypatch, args):
    order = []
    monkeypatch.setattr(worker, "_stop_on_signals", lambda stop: None)
    monkeypatch.setattr(
        worker, "run_forever", lambda stop, refresh: order.append("loop")
    )

    worker.main(
        args,
        ensure_data=lambda: order.append("data") or False,
        refresh=lambda: order.append("check") or {"state": "fresh"},
    )

    assert order[0] == "data"
    assert order[1] == ("check" if args else "loop")


@pytest.mark.parametrize("args", [[], ["--once"]])
def test_no_data_means_exit_1_without_refreshing(monkeypatch, args):
    monkeypatch.setattr(worker, "run_forever", lambda *a, **k: pytest.fail("looped"))

    def no_data():
        raise RuntimeError("download failed")

    code = worker.main(
        args,
        ensure_data=no_data,
        refresh=lambda: pytest.fail("refreshed without data"),
    )

    assert code == 1


def test_default_data_step_is_core_deployment():
    import inspect

    from core import deployment

    default = inspect.signature(worker.main).parameters["ensure_data"].default
    assert default is deployment.ensure_deployment_data
