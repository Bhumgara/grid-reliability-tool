"""
The file-store interface: the JSON and CSV outputs the pipelines write and
the dashboard and API read, named by key rather than by path.

Today these are files in ``data/processed/`` (``LocalFileStore``). The same
keys could map to objects in a bucket (e.g. Cloud Storage) by implementing
``FileStore``; see TODO.md 2.6.

Not included: ``artifacts/`` (the trained model and its metrics). They are
part of the code release, shipped in the container image, not data output.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

import pandas as pd

from core import config

FileKey = Literal[
    "forecast",                # latest 24-hour forecast (pipelines.predict)
    "refresh_status",          # live refresh status (pipelines.refresh)
    "last_refresh",            # worker's last completed check (backend.worker)
    "validation_predictions",  # model validation results (model/evaluate.py)
    "test_predictions",        # model test results (model/evaluate.py)
    "model_dataset",           # modelling dataset (pipelines.build_dataset)
]

# The core.config path for each key, looked up on each call so GRID_DATA_DIR
# and tests that patch core.config are respected.
_CONFIG_PATHS: dict[str, str] = {
    "forecast": "FORECAST_PATH",
    "refresh_status": "STATUS_PATH",
    "last_refresh": "LAST_REFRESH_PATH",
    "validation_predictions": "VALIDATION_PATH",
    "test_predictions": "TEST_PATH",
    "model_dataset": "MODEL_DATASET_PATH",
}


@runtime_checkable
class FileStore(Protocol):
    """
    JSON and CSV outputs by key.

    Reads return None when the file is missing, unreadable or half-written
    (writers may be replacing it). Writes replace the whole file, so readers
    see either the old or the new version, never part of one.
    """

    def read_json(self, key: FileKey) -> dict | None: ...

    def write_json(self, key: FileKey, payload: dict) -> None: ...

    def read_csv(self, key: FileKey) -> pd.DataFrame | None: ...

    def write_csv(self, key: FileKey, frame: pd.DataFrame) -> None: ...

    def location(self, key: FileKey) -> str:
        """Where ``key`` is stored, for log messages (a path or URL)."""
        ...


class LocalFileStore:
    """
    ``FileStore`` backed by local files, at the ``core.config`` paths.

    ``paths`` overrides the path for particular keys (used by tests and the
    loaders' explicit ``path`` arguments).
    """

    def __init__(self, paths: dict[str, Path] | None = None) -> None:
        self._paths = dict(paths or {})

    def path(self, key: FileKey) -> Path:
        if key in self._paths:
            return Path(self._paths[key])
        if key not in _CONFIG_PATHS:
            raise KeyError(f"Unknown file key: {key!r}")
        return Path(getattr(config, _CONFIG_PATHS[key]))

    def location(self, key: FileKey) -> str:
        return str(self.path(key))

    def _replace(self, key: FileKey, text: str) -> None:
        path = self.path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(text, encoding="utf-8", newline="\n")
        temporary.replace(path)

    def read_json(self, key: FileKey) -> dict | None:
        path = self.path(key)
        try:
            with path.open(encoding="utf-8") as file:
                return json.load(file)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return None

    def write_json(self, key: FileKey, payload: dict) -> None:
        self._replace(key, json.dumps(payload, indent=2) + "\n")

    def read_csv(self, key: FileKey) -> pd.DataFrame | None:
        path = self.path(key)
        if not path.is_file():
            return None
        try:
            return pd.read_csv(path)
        except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeDecodeError):
            return None

    def write_csv(self, key: FileKey, frame: pd.DataFrame) -> None:
        buffer = io.StringIO()
        frame.to_csv(buffer, index=False)
        self._replace(key, buffer.getvalue())
