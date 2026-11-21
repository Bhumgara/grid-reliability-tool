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


# --- Data folder outside the repo (GRID_DATA_DIR) --------------------------------


def test_data_entries_go_to_the_database_folder(tmp_path, downloads):
    root = tmp_path / "repo"
    root.mkdir()
    volume = tmp_path / "volume"
    db = volume / "grid.db"
    _, serve = downloads
    serve(_zip_bytes({
        "data/grid.db": b"sqlite",
        "data/processed/latest_forecast.json": b"{}",
        "data/raw/elexon/x.json": b"[]",
        "README.txt": b"top-level file",
        "extras/notes.md": b"top-level folder",
    }))

    assert ensure_deployment_data(URL, db_path=db, project_root=root) is True

    assert db.read_bytes() == b"sqlite"
    assert (volume / "processed" / "latest_forecast.json").read_bytes() == b"{}"
    assert (volume / "raw" / "elexon" / "x.json").read_bytes() == b"[]"
    assert not (root / "data").exists()
    # Entries outside data/ still go to the repo root.
    assert (root / "README.txt").read_bytes() == b"top-level file"
    assert (root / "extras" / "notes.md").read_bytes() == b"top-level folder"


def test_existing_data_files_are_replaced(tmp_path, downloads):
    root = tmp_path / "repo"
    volume = tmp_path / "volume"
    (volume / "processed").mkdir(parents=True)
    (volume / "processed" / "latest_forecast.json").write_bytes(b"old")
    _, serve = downloads
    serve(_zip_bytes({
        "data/grid.db": b"sqlite",
        "data/processed/latest_forecast.json": b"new",
    }))

    ensure_deployment_data(URL, db_path=volume / "grid.db", project_root=root)

    assert (volume / "processed" / "latest_forecast.json").read_bytes() == b"new"


def test_copies_when_files_cannot_be_moved(tmp_path, downloads, monkeypatch):
    # A mounted volume on another filesystem can't take os.replace.
    root = tmp_path / "repo"
    volume = tmp_path / "volume"
    _, serve = downloads
    serve(_zip_bytes({"data/grid.db": b"sqlite"}))

    def cross_device(source, destination):
        raise OSError("Invalid cross-device link")

    monkeypatch.setattr(deployment.os, "replace", cross_device)

    ensure_deployment_data(URL, db_path=volume / "grid.db", project_root=root)

    assert (volume / "grid.db").read_bytes() == b"sqlite"


def test_bundle_entries_cannot_escape(tmp_path, downloads):
    root = tmp_path / "sandbox" / "repo"
    root.mkdir(parents=True)
    volume = tmp_path / "sandbox" / "volume"
    _, serve = downloads
    serve(_zip_bytes({
        "data/grid.db": b"sqlite",
        "../escaped.txt": b"bad",
        "data/../../escaped2.txt": b"bad",
    }))

    ensure_deployment_data(URL, db_path=volume / "grid.db", project_root=root)

    assert not (tmp_path / "escaped.txt").exists()
    assert not (tmp_path / "sandbox" / "escaped.txt").exists()
    assert not (tmp_path / "escaped2.txt").exists()
    assert not (tmp_path / "sandbox" / "escaped2.txt").exists()
    written = {p for p in tmp_path.rglob("*") if p.is_file()}
    assert all(root in p.parents or volume in p.parents for p in written)
