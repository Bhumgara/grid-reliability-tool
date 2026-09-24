"""
Streamlit bootstrap for the live refresh worker.

The daemon refreshes immediately when the app process starts, then checks
periodically. pipelines.refresh decides whether anything is stale enough to
fetch, so ordinary Streamlit reruns never trigger API calls directly.
"""

from __future__ import annotations

import threading
import time

import streamlit as st

from pipelines.refresh import refresh_live_data


CHECK_EVERY_SECONDS = 15 * 60


def _refresh_loop() -> None:
    while True:
        try:
            refresh_live_data()
        except Exception as exc:
            print(
                "[live-refresh] "
                f"{type(exc).__name__}: {exc}"
            )

        time.sleep(CHECK_EVERY_SECONDS)


@st.cache_resource(show_spinner=False)
def start_background_worker() -> threading.Thread:
    worker = threading.Thread(
        target=_refresh_loop,
        daemon=True,
        name="grid-live-refresh",
    )
    worker.start()
    return worker
