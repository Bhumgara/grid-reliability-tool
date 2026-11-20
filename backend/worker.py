"""
Standalone refresh worker: keeps the live data and forecast up to date.

The same loop as the Streamlit thread in dashboard/bootstrap.py, as its own
process, so the API (which only reads) can run without the dashboard. Each
check calls pipelines.refresh.refresh_live_data(), which only fetches data
that is stale. From the repo root:

    python -m backend.worker          # loop until stopped
    python -m backend.worker --once   # one check, then exit

Before the first check, it downloads the deployment bundle if the database
is missing (core.deployment, using DEPLOYMENT_BUNDLE_URL). If that fails, the
worker exits with code 1 rather than refreshing without data.

The loop stops cleanly on Ctrl+C or SIGTERM (what container hosts send on
shutdown), finishing any refresh in progress first.

``--once`` is for hosts that run the worker on a schedule instead of keeping
it running (cron, or Cloud Scheduler triggering a Cloud Run job). Its exit
code tells the scheduler whether the check worked: 0 if it did (including
"degraded", where cached data remains usable), 1 if it raised or the refresh
state is "failed".
"""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading
from collections.abc import Callable

from core import config, deployment

logger = logging.getLogger("backend.worker")


def _default_refresh() -> dict:
    # Imported here so importing this module (e.g. in tests) doesn't load
    # the ingestion and model code.
    from pipelines.refresh import refresh_live_data

    return refresh_live_data()


def prepare_data(
    ensure_data: Callable[[], bool] = deployment.ensure_deployment_data,
) -> bool:
    """
    Make sure the database exists before the first refresh.

    Returns False (after logging why) if it is missing and could not be
    downloaded, e.g. no bundle URL is set or the download failed.
    """
    try:
        downloaded = ensure_data()
    except Exception:
        logger.exception("Could not set up the deployment data")
        return False

    if downloaded:
        logger.info("Downloaded the deployment bundle")
    return True


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


def exit_code(status: dict | None) -> int:
    """Exit code for ``--once``: 1 if the check raised or failed, else 0."""
    if status is None or status.get("state") == "failed":
        return 1
    return 0


def main(
    argv: list[str] | None = None,
    refresh: Callable[[], dict] = _default_refresh,
    ensure_data: Callable[[], bool] = deployment.ensure_deployment_data,
) -> int:
    parser = argparse.ArgumentParser(description="Keep the live grid data up to date.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="run one refresh check and exit (for cron or scheduled jobs)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if not prepare_data(ensure_data):
        return 1

    if args.once:
        return exit_code(refresh_once(refresh))

    stop = threading.Event()
    _stop_on_signals(stop)
    run_forever(stop, refresh=refresh)
    return 0


if __name__ == "__main__":
    sys.exit(main())
