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

from pathlib import Path
from zipfile import ZipFile
import tempfile

import requests


# dashboard/bootstrap.py -> dashboard -> repo root
PROJECT_ROOT = Path(__file__).resolve().parents[1]

DB_PATH = PROJECT_ROOT / "data" / "grid.db"


def ensure_deployment_data() -> None:
    if DB_PATH.exists():
        return

    url = st.secrets.get("deployment_bundle_url")

    if not url:
        raise RuntimeError(
            "Database is missing and "
            "'deployment_bundle_url' is not configured."
        )

    with tempfile.NamedTemporaryFile(
        suffix=".zip",
        delete=False,
    ) as tmp:
        response = requests.get(
            url,
            timeout=120,
        )
        response.raise_for_status()

        tmp.write(response.content)
        zip_path = Path(tmp.name)

    with ZipFile(zip_path) as bundle:
        print("ZIP contents:", bundle.namelist())
        bundle.extractall(PROJECT_ROOT)

    zip_path.unlink(missing_ok=True)

    print("Project root:", PROJECT_ROOT)
    print("Expected DB:", DB_PATH)
    print("DB exists:", DB_PATH.exists())

    print(
        "Extracted data files:",
        [str(p) for p in PROJECT_ROOT.rglob("grid.db")]
    )

    if not DB_PATH.exists():
        raise RuntimeError(
            f"Deployment bundle downloaded but database was not found. "
            f"Expected: {DB_PATH}"
        )


CHECK_EVERY_SECONDS = 150


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
