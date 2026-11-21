"""
Choosing the storage backends.

    GRID_DATABASE_BACKEND   the GridStore (default "sqlite")
    GRID_FILE_BACKEND       the FileStore (default "local")

Read when a store is requested, not at import. Add a backend by
implementing the interface and registering it in DATABASE_BACKENDS or
FILE_BACKENDS.
"""

from __future__ import annotations

import os
from collections.abc import Callable

from core.storage.base import GridStore
from core.storage.files import FileStore, LocalFileStore
from core.storage.sqlite import SQLiteStore

DATABASE_BACKEND_ENV = "GRID_DATABASE_BACKEND"
FILE_BACKEND_ENV = "GRID_FILE_BACKEND"

DEFAULT_DATABASE_BACKEND = "sqlite"
DEFAULT_FILE_BACKEND = "local"

# Backend name -> a function that builds it from the environment and core.config.
DATABASE_BACKENDS: dict[str, Callable[[], GridStore]] = {
    "sqlite": SQLiteStore,
}
FILE_BACKENDS: dict[str, Callable[[], FileStore]] = {
    "local": LocalFileStore,
}


class UnknownBackendError(ValueError):
    """A backend environment variable names a backend that doesn't exist."""


def _chosen(env: str, backends: dict, default: str) -> str:
    name = os.environ.get(env, "").strip().lower() or default

    if name not in backends:
        raise UnknownBackendError(
            f"{env}={name!r} is not a known backend. "
            f"Choose one of: {', '.join(sorted(backends))}."
        )

    return name


def database_backend() -> str:
    """The configured GridStore backend name."""
    return _chosen(DATABASE_BACKEND_ENV, DATABASE_BACKENDS, DEFAULT_DATABASE_BACKEND)


def file_backend() -> str:
    """The configured FileStore backend name."""
    return _chosen(FILE_BACKEND_ENV, FILE_BACKENDS, DEFAULT_FILE_BACKEND)


def get_grid_store() -> GridStore:
    """The database store the app uses, chosen by GRID_DATABASE_BACKEND."""
    return DATABASE_BACKENDS[database_backend()]()


def get_file_store() -> FileStore:
    """The file store the app uses, chosen by GRID_FILE_BACKEND."""
    return FILE_BACKENDS[file_backend()]()


def check_backends() -> dict[str, str]:
    """
    Validate both settings and return the chosen names. Call at start-up so a
    typo fails immediately rather than on the first request.
    """
    return {"database": database_backend(), "files": file_backend()}
