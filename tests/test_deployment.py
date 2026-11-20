"""Tests for core.deployment, using an in-memory zip instead of the network."""

import io
import tempfile
import zipfile
from pathlib import Path

import pytest
import requests

from core import deployment
from core.deployment import BUNDLE_URL_ENV, ensure_deployment_data

URL = "https://example.invalid/bundle.zip"


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        for name, content in files.items():
            bundle.writestr(name, content)
    return buffer.getvalue()


class _FakeResponse:
    def __init__(self, content: bytes, status: int = 200):
        self.content = content
        self.status = status

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise requests.HTTPError(f"{self.status} error")


@pytest.fixture
def project(tmp_path):
    """A fake repo root, with the database path inside it."""
    root = tmp_path / "repo"
    root.mkdir()
    return root, root / "data" / "grid.db"


@pytest.fixture
def downloads(monkeypatch):
    """Replace requests.get; record each URL requested."""
    requested = []

    def serve(content: bytes, status: int = 200):
        def fake_get(url, timeout):
            requested.append(url)
            return _FakeResponse(content, status)

        monkeypatch.setattr(deployment.requests, "get", fake_get)

    return requested, serve


@pytest.fixture(autouse=True)
def no_bundle_env(monkeypatch):
    monkeypatch.delenv(BUNDLE_URL_ENV, raising=False)


def test_does_nothing_when_database_exists(project, downloads):
    root, db = project
    db.parent.mkdir()
    db.write_bytes(b"existing")
    requested, serve = downloads
    serve(b"unused")

    assert ensure_deployment_data(URL, db_path=db, project_root=root) is False
    assert requested == []
    assert db.read_bytes() == b"existing"


def test_downloads_and_extracts_bundle(project, downloads):
    root, db = project
    requested, serve = downloads
    serve(_zip_bytes({
        "data/grid.db": b"sqlite",
        "data/processed/latest_forecast.json": b"{}",
    }))

    assert ensure_deployment_data(URL, db_path=db, project_root=root) is True
    assert requested == [URL]
    assert db.read_bytes() == b"sqlite"
    assert (root / "data" / "processed" / "latest_forecast.json").is_file()


def test_uses_environment_variable_when_no_url_given(project, downloads, monkeypatch):
    root, db = project
    requested, serve = downloads
    serve(_zip_bytes({"data/grid.db": b"sqlite"}))
    monkeypatch.setenv(BUNDLE_URL_ENV, "https://example.invalid/from-env.zip")

    ensure_deployment_data(db_path=db, project_root=root)

    assert requested == ["https://example.invalid/from-env.zip"]


def test_requires_a_url_when_database_missing(project):
    root, db = project

    with pytest.raises(RuntimeError, match=BUNDLE_URL_ENV):
        ensure_deployment_data(db_path=db, project_root=root)


def test_bundle_without_database_reports_what_it_found(project, downloads):
    root, db = project
    _, serve = downloads
    serve(_zip_bytes({"wrong/place/grid.db": b"sqlite"}))

    with pytest.raises(RuntimeError, match="database was not found") as error:
        ensure_deployment_data(URL, db_path=db, project_root=root)

    assert str(Path("wrong") / "place" / "grid.db") in str(error.value)


def test_http_errors_propagate(project, downloads):
    root, db = project
    _, serve = downloads
    serve(b"", status=404)

    with pytest.raises(requests.HTTPError):
        ensure_deployment_data(URL, db_path=db, project_root=root)

    assert not db.exists()


def test_temporary_zip_is_removed_even_if_extraction_fails(project, downloads, monkeypatch):
    root, db = project
    _, serve = downloads
    serve(b"not a zip file")

    created = []
    real_named_temporary_file = tempfile.NamedTemporaryFile

    def tracking(*args, **kwargs):
        handle = real_named_temporary_file(*args, **kwargs)
        created.append(Path(handle.name))
        return handle

    monkeypatch.setattr(deployment.tempfile, "NamedTemporaryFile", tracking)

    with pytest.raises(zipfile.BadZipFile):
        ensure_deployment_data(URL, db_path=db, project_root=root)

    assert len(created) == 1
    assert not created[0].exists()


def test_dashboard_wrapper_treats_missing_secrets_file_as_no_url(monkeypatch, tmp_path):
    from dashboard import bootstrap

    # Run from a folder with no .streamlit/secrets.toml.
    monkeypatch.chdir(tmp_path)

    assert bootstrap._secret_bundle_url() is None
