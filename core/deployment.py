"""
First-run data setup for deployments.

A fresh deployment has no database. It downloads a zip bundle containing
``data/grid.db`` (and any other data files) and extracts it into the repo root.
Used by the Streamlit dashboard today and by the API and refresh worker later.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from zipfile import ZipFile

import requests

from core import config

logger = logging.getLogger(__name__)

# Environment variable holding the bundle URL when none is passed in.
BUNDLE_URL_ENV = "DEPLOYMENT_BUNDLE_URL"

DOWNLOAD_TIMEOUT_SECONDS = 120


def ensure_deployment_data(
    bundle_url: str | None = None,
    *,
    db_path: Path | None = None,
    project_root: Path | None = None,
) -> bool:
    """
    Download and extract the deployment bundle if the database is missing.

    ``bundle_url`` defaults to the ``DEPLOYMENT_BUNDLE_URL`` environment
    variable. ``db_path`` and ``project_root`` default to ``core.config``.

    Returns True if the bundle was downloaded, False if the database already
    existed. Raises RuntimeError if no URL is configured, or if the bundle did
    not contain the database.
    """
    db_path = db_path or config.DB_PATH
    project_root = project_root or config.PROJECT_ROOT

    if db_path.exists():
        return False

    url = bundle_url or os.environ.get(BUNDLE_URL_ENV)

    if not url:
        raise RuntimeError(
            "Database is missing and no deployment bundle URL is configured. "
            f"Pass bundle_url or set {BUNDLE_URL_ENV}."
        )

    logger.info("Database missing at %s; downloading deployment bundle", db_path)

    response = requests.get(url, timeout=DOWNLOAD_TIMEOUT_SECONDS)
    response.raise_for_status()

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp.write(response.content)
        zip_path = Path(tmp.name)

    try:
        with ZipFile(zip_path) as bundle:
            logger.info("Extracting %s into %s", bundle.namelist(), project_root)
            bundle.extractall(project_root)
    finally:
        zip_path.unlink(missing_ok=True)

    if not db_path.exists():
        found = ", ".join(str(path) for path in project_root.rglob(db_path.name))
        raise RuntimeError(
            "Deployment bundle downloaded but the database was not found. "
            f"Expected: {db_path}. Found: {found or 'none'}"
        )

    logger.info("Deployment data ready at %s", db_path)
    return True
