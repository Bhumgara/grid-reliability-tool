"""
Standalone refresh worker: keeps the live data and forecast up to date.

The same loop as the Streamlit thread in dashboard/bootstrap.py, as its own
process, so the API (which only reads) can run without the dashboard. Each
check calls pipelines.refresh.refresh_live_data(), which only fetches data
that is stale. From the repo root:

    python -m backend.worker

Stops cleanly on Ctrl+C or SIGTERM (what container hosts send on shutdown),
finishing any refresh in progress first.
"""

from __future__ import annotations

import logging
import signal
import sys
import threading
from collections.abc import Callable

from core import config

logger = logging.getLogger("backend.worker")


def _default_refresh() -> dict:
    # Imported here so importing this module (e.g. in tests) doesn't load
    # the ingestion and model code.
    from pipelines.refresh import refresh_live_data

    return refresh_live_data()


def refresh_once(refresh: Callable[[], dict] = _default_refresh) -> dict | None:
    """
    Run one refresh check and log the outcome.

    Returns the status from ``refresh``, or None if it raised; errors are
    logged, not raised, so one failed check doesn't stop the worker.
    """
    try:
        status = refresh()
    except Exception:
        logger.exception("Refresh check failed")
        return None

    logger.info(
        "Refresh check: %s. %s",
        status.get("state", "unknown"),
        status.get("message", ""),
    )
    return status


def run_forever(
    stop: threading.Event,
    refresh: Callable[[], dict] = _default_refresh,
    interval_seconds: float | None = None,
) -> None:
    """
    Check immediately, then every ``interval_seconds`` until ``stop`` is set.

    ``interval_seconds`` defaults to ``core.config.REFRESH_CHECK_SECONDS``.
    """
    if interval_seconds is None:
        interval_seconds = config.REFRESH_CHECK_SECONDS

    logger.info("Refresh worker started; checking every %s seconds", interval_seconds)

    while not stop.is_set():
        refresh_once(refresh)
        # Returns early when stop is set, so shutdown doesn't wait out the interval.
        stop.wait(interval_seconds)

    logger.info("Refresh worker stopped")


def _stop_on_signals(stop: threading.Event) -> None:
    def handle(signum, frame):
        logger.info("Received %s; stopping after the current check", signal.Signals(signum).name)
        stop.set()

    signal.signal(signal.SIGINT, handle)
    signal.signal(signal.SIGTERM, handle)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    stop = threading.Event()
    _stop_on_signals(stop)
    run_forever(stop)
    return 0


if __name__ == "__main__":
    sys.exit(main())
