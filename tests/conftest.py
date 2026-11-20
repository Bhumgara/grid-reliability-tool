import sqlite3

import pytest

from tests.fixtures.grid_db import SCHEMA_PATH, build_grid_db


@pytest.fixture
def grid_db(tmp_path):
    """Path to a freshly built fixture database (see tests/fixtures/grid_db.py)."""
    return build_grid_db(tmp_path / "grid.db")


@pytest.fixture
def empty_grid_db(tmp_path):
    """Path to a database with the real schema and no rows."""
    path = tmp_path / "empty.db"
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    finally:
        conn.close()
    return path
