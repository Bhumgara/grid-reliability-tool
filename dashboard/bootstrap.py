"""
Streamlit bootstrap for the live refresh worker.

The daemon refreshes immediately when the app process starts, then checks
periodically. pipelines.refresh decides whether anything is stale enough to
fetch, so ordinary Streamlit reruns never trigger API calls directly.

Only one refresher should run against the database. When the standalone
worker (``python -m backend.worker``) is running, set
``GRID_DASHBOARD_REFRESH=0`` so the dashboard doesn't start its own thread.
"""

from __future__ import annotations

import os
import threading
import time

import streamlit as st

from core import deployment
from core.config import DB_PATH, REFRESH_CHECK_SECONDS
from pipelines.refresh import refresh_live_data


# Environment flag for the dashboard's refresh thread. On unless set to one of
# OFF_VALUES (any case), so the deployed dashboard keeps refreshing by default.
REFRESH_THREAD_ENV = "GRID_DASHBOARD_REFRESH"
OFF_VALUES = {"0", "false", "no", "off"}


def refresh_thread_enabled() -> bool:
    """False if ``GRID_DASHBOARD_REFRESH`` turns the dashboard's thread off."""
    value = os.environ.get(REFRESH_THREAD_ENV, "")
    return value.strip().lower() not in OFF_VALUES


def _secret_bundle_url() -> str | None:
    """The bundle URL from Streamlit secrets, or None if there is no secrets file."""
    try:
        return st.secrets.get("deployment_bundle_url")
    except FileNotFoundError:
        return None


def ensure_deployment_data() -> None:
    """
    Download the deployment bundle on first run (see core.deployment).

    The URL comes from the ``deployment_bundle_url`` Streamlit secret, falling
    back to the DEPLOYMENT_BUNDLE_URL environment variable. Secrets are only
    read when the database is missing.
    """
    if DB_PATH.exists():
        return

    deployment.ensure_deployment_data(bundle_url=_secret_bundle_url())


def _refresh_loop() -> None:
    while True:
        try:
            refresh_live_data()
        except Exception as exc:
            print(
                "[live-refresh] "
                f"{type(exc).__name__}: {exc}"
            )

        time.sleep(REFRESH_CHECK_SECONDS)


@st.cache_resource(show_spinner=False)
def start_background_worker() -> threading.Thread | None:
    """
    Start the refresh thread once per server process, unless
    ``GRID_DASHBOARD_REFRESH`` turns it off (returns None then).
    """
    if not refresh_thread_enabled():
        print(
            "[live-refresh] Dashboard refresh thread off "
            f"({REFRESH_THREAD_ENV}); expecting backend.worker to refresh."
        )
        return None

    worker = threading.Thread(
        target=_refresh_loop,
        daemon=True,
        name="grid-live-refresh",
    )
    worker.start()
    return worker
