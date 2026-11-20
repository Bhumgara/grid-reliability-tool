"""Smoke tests: the test setup works and the core package is importable."""

from pathlib import Path


def test_core_package_imports():
    import core.config
    import core.db  # noqa: F401

    assert core.config.DB_PATH == Path("data/grid.db")


def test_schema_file_present():
    assert Path("sql/schema.sql").is_file()
