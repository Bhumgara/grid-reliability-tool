import pytest

from tests.fixtures.grid_db import build_grid_db


@pytest.fixture
def grid_db(tmp_path):
    """Path to a freshly built fixture database (see tests/fixtures/grid_db.py)."""
    return build_grid_db(tmp_path / "grid.db")
