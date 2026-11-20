"""Smoke tests: the test setup works and the core package is importable."""

from pathlib import Path

import pytest


def test_core_package_imports():
    import core.config
    import core.db  # noqa: F401

    assert core.config.DB_PATH == core.config.PROJECT_ROOT / "data" / "grid.db"


def test_project_root_is_the_repo_root():
    from core.config import PROJECT_ROOT

    assert (PROJECT_ROOT / "core" / "config.py").is_file()
    assert (PROJECT_ROOT / "sql" / "schema.sql").is_file()


@pytest.mark.parametrize(
    "name",
    [
        "DB_PATH",
        "METRICS_PATH",
        "FORECAST_PATH",
        "STATUS_PATH",
        "VALIDATION_PATH",
        "TEST_PATH",
    ],
)
def test_config_paths_are_absolute_inside_the_repo(name):
    import core.config

    path = getattr(core.config, name)

    assert path.is_absolute()
    assert path.is_relative_to(core.config.PROJECT_ROOT)


def test_dashboard_bootstrap_shares_config_paths():
    import core.config
    from dashboard import bootstrap

    assert bootstrap.DB_PATH is core.config.DB_PATH


def test_refresh_loop_sleeps_for_shared_interval(monkeypatch):
    import core.config
    from dashboard import bootstrap

    class StopLoop(Exception):
        pass

    slept = []

    def fake_sleep(seconds):
        slept.append(seconds)
        raise StopLoop

    monkeypatch.setattr(bootstrap, "refresh_live_data", lambda: None)
    monkeypatch.setattr(bootstrap.time, "sleep", fake_sleep)

    with pytest.raises(StopLoop):
        bootstrap._refresh_loop()

    assert slept == [core.config.REFRESH_CHECK_SECONDS]
    assert core.config.REFRESH_CHECK_SECONDS == 150


def test_schema_file_present():
    assert Path("sql/schema.sql").is_file()
