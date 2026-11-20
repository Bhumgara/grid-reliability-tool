"""
Export the API's OpenAPI schema to backend/openapi.json.

The Flutter client's Dart models are generated from this file, so it is
committed and kept in step with the code. From the repo root:

    python -m backend.export_openapi           # write the file
    python -m backend.export_openapi --check   # exit 1 if it is out of date

A test also fails when the committed file is out of date.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backend.api.main import create_app

OPENAPI_PATH = Path(__file__).resolve().parent / "openapi.json"


def render_schema() -> str:
    """The schema as stable, readable JSON with a trailing newline."""
    schema = create_app(cors_origins=[]).openapi()
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="don't write; exit 1 if the file is missing or out of date",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OPENAPI_PATH,
        help=f"where to write the schema (default: {OPENAPI_PATH})",
    )
    args = parser.parse_args(argv)

    schema = render_schema()

    if args.check:
        current = args.output.read_text(encoding="utf-8") if args.output.exists() else None
        if current != schema:
            print(
                f"{args.output} is out of date. "
                "Run: python -m backend.export_openapi",
                file=sys.stderr,
            )
            return 1
        print(f"{args.output} is up to date.")
        return 0

    args.output.write_text(schema, encoding="utf-8", newline="\n")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
