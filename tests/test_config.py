"""
Tests for GRID_DATA_DIR in core.config.

core.config reads the variable once, at import, so each case imports it in a
fresh Python process.
"""

import json
import os
import subprocess
import sys

import pytest

from core.config import PROJECT_ROOT

PATHS = ["DATA_DIR", "RAW_DIR", "PROCESSED_DIR", "DB_PATH", "STATUS_PATH",
         "LAST_REFRESH_PATH", "FORECAST_PATH", "ELEXON_RAW_DIR", "ARTIFACTS_DIR",
         "MODEL_PATH", "SQL_DIR"]


def _config_paths(data_dir: str | None, cwd=PROJECT_ROOT) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k != "GRID_DATA_DIR"}
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    if data_dir is not None:
        env["GRID_DATA_DIR"] = data_dir

    script = (
        "import json, core.config as c; "
        f"print(json.dumps({{name: str(getattr(c, name)) for name in {PATHS!r}}}))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=cwd, env=env, capture_output=True, text=True, check=True,
        stdin=subprocess.DEVNULL,
    )
    return json.loads(result.stdout)


@pytest.mark.parametrize("value", [None, "", "   "])
def test_default_data_dir_is_in_the_repo(value):
    paths = _config_paths(value)

    assert paths["DATA_DIR"] == str(PROJECT_ROOT / "data")
    assert paths["DB_PATH"] == str(PROJECT_ROOT / "data" / "grid.db")


def test_grid_data_dir_moves_every_data_path(tmp_path):
    volume = tmp_path / "volume"

    paths = _config_paths(str(volume))

    assert paths["DATA_DIR"] == str(volume)
    assert paths["DB_PATH"] == str(volume / "grid.db")
    assert paths["RAW_DIR"] == str(volume / "raw")
    assert paths["ELEXON_RAW_DIR"] == str(volume / "raw" / "elexon")
    assert paths["PROCESSED_DIR"] == str(volume / "processed")
    assert paths["STATUS_PATH"] == str(volume / "processed" / "refresh_status.json")
    assert paths["LAST_REFRESH_PATH"] == str(volume / "processed" / "last_refresh.json")
    assert paths["FORECAST_PATH"] == str(volume / "processed" / "latest_forecast.json")


def test_code_paths_stay_in_the_repo(tmp_path):
    paths = _config_paths(str(tmp_path / "volume"))

    # Committed files (model, SQL) ship with the code, not the data volume.
    assert paths["ARTIFACTS_DIR"] == str(PROJECT_ROOT / "artifacts")
    assert paths["MODEL_PATH"] == str(PROJECT_ROOT / "artifacts" / "ridge_drm_24h.joblib")
    assert paths["SQL_DIR"] == str(PROJECT_ROOT / "sql")


def test_relative_grid_data_dir_is_taken_from_the_current_directory(tmp_path):
    paths = _config_paths("my-data", cwd=tmp_path)

    assert paths["DATA_DIR"] == str((tmp_path / "my-data").resolve())


def test_env_example_documents_grid_data_dir():
    assert "GRID_DATA_DIR=" in (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
