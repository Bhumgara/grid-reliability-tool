"""
First-run data setup for deployments.

A fresh deployment has no database. It downloads a zip bundle containing
``data/grid.db`` (and any other data files). Entries under ``data/`` go into
the data folder (the database's folder, ``core.config.DATA_DIR`` by default,
which ``GRID_DATA_DIR`` can move, e.g. to a container volume); anything else
goes into the repo root. Used by the Streamlit dashboard and the refresh
worker.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path
from zipfile import ZipFile

import requests

from core import config

logger = logging.getLogger(__name__)

# Environment variable holding the bundle URL when none is passed in.
BUNDLE_URL_ENV = "DEPLOYMENT_BUNDLE_URL"

DOWNLOAD_TIMEOUT_SECONDS = 120

# Top-level folder in the bundle whose contents belong in the data folder.
BUNDLE_DATA_PREFIX = "data"


def _move_tree(source: Path, target: Path) -> None:
    """Move every file under ``source`` to the same place under ``target``, replacing files."""
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue

        destination = target / path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)

        try:
            os.replace(path, destination)
        except OSError:
            # Different drive or filesystem (e.g. a mounted volume): copy instead.
            shutil.copy2(path, destination)


def _install_bundle(zip_path: Path, data_dir: Path, project_root: Path) -> None:
    """Extract the bundle: ``data/...`` into ``data_dir``, the rest into ``project_root``."""
    with tempfile.TemporaryDirectory() as staging_name:
        staging = Path(staging_name)

        with ZipFile(zip_path) as bundle:
            logger.info("Extracting %s", bundle.namelist())
            # extractall drops absolute paths and ".." parts, so nothing can
            # land outside the staging folder.
            bundle.extractall(staging)

        for entry in sorted(staging.iterdir()):
            if entry.name == BUNDLE_DATA_PREFIX and entry.is_dir():
                _move_tree(entry, data_dir)
            elif entry.is_dir():
                _move_tree(entry, project_root / entry.name)
            else:
                project_root.mkdir(parents=True, exist_ok=True)
                os.replace(entry, project_root / entry.name)


def ensure_deployment_data(
    bundle_url: str | None = None,
    *,
    db_path: Path | None = None,
    project_root: Path | None = None,
) -> bool:
    """
    Download and extract the deployment bundle if the database is missing.

    ``bundle_url`` defaults to the ``DEPLOYMENT_BUNDLE_URL`` environment
    variable. ``db_path`` and ``project_root`` default to ``core.config``. The
    bundle's ``data/`` entries go into ``db_path``'s folder.

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

    data_dir = db_path.parent

    try:
        _install_bundle(zip_path, data_dir, project_root)
    finally:
        zip_path.unlink(missing_ok=True)

    if not db_path.exists():
        candidates = {*project_root.rglob(db_path.name), *data_dir.rglob(db_path.name)}
        found = ", ".join(sorted(str(path) for path in candidates))
        raise RuntimeError(
            "Deployment bundle downloaded but the database was not found. "
            f"Expected: {db_path}. Found: {found or 'none'}"
        )

    logger.info("Deployment data ready at %s", db_path)
    return True
