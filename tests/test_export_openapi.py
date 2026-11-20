import json

from backend import export_openapi
from backend.export_openapi import OPENAPI_PATH, main, render_schema


def test_committed_schema_is_up_to_date():
    # If this fails, run: python -m backend.export_openapi
    assert OPENAPI_PATH.read_text(encoding="utf-8") == render_schema()


def test_schema_lists_every_endpoint():
    paths = json.loads(render_schema())["paths"]

    assert set(paths) == {
        "/api/health",
        "/api/status",
        "/api/forecast/hero",
        "/api/grid/now",
        "/api/history/margin",
        "/api/history/demand",
        "/api/demand/typical-day",
        "/api/generation/live",
        "/api/generation/change",
        "/api/interconnectors/live",
        "/api/model/metrics",
        "/api/model/validation",
    }


def test_main_writes_the_schema(tmp_path):
    output = tmp_path / "openapi.json"

    assert main(["--output", str(output)]) == 0
    assert output.read_bytes() == render_schema().encode("utf-8")


def test_check_passes_when_up_to_date(tmp_path, capsys):
    output = tmp_path / "openapi.json"
    main(["--output", str(output)])

    assert main(["--check", "--output", str(output)]) == 0
    assert "up to date" in capsys.readouterr().out


def test_check_accepts_windows_line_endings(tmp_path):
    output = tmp_path / "openapi.json"
    output.write_bytes(render_schema().replace("\n", "\r\n").encode("utf-8"))

    assert main(["--check", "--output", str(output)]) == 0


def test_check_fails_when_stale_or_missing(tmp_path, capsys):
    output = tmp_path / "openapi.json"

    assert main(["--check", "--output", str(output)]) == 1

    output.write_text("{}\n", encoding="utf-8")
    assert main(["--check", "--output", str(output)]) == 1
    assert "python -m backend.export_openapi" in capsys.readouterr().err
    # --check never writes.
    assert output.read_text(encoding="utf-8") == "{}\n"


def test_default_output_is_backend_openapi_json():
    from pathlib import Path

    assert OPENAPI_PATH == Path(export_openapi.__file__).resolve().parent / "openapi.json"
    assert OPENAPI_PATH.parent.name == "backend"
