from core.api.elexon import fetch_drm, save_raw
from core.db import (
    count_margin_rows,
    initialise_database,
    upsert_margin_rows,
    count_target_rows,
)
from core.normalise import normalise_elexon_drm

from datetime import datetime, timedelta

def ingest_drm(from_dt: str, to_dt: str):
    raw = fetch_drm(from_dt, to_dt)

    rows = normalise_elexon_drm(raw["data"])

    save_raw(raw, f"drm_{from_dt}_{to_dt}.json")

    initialise_database()
    upsert_margin_rows(rows)

    print(f"Fetched: {len(rows)}")
    print(f"Database total: {count_margin_rows()}")
    print(f"Target rows: {count_target_rows()}")

def backfill_drm(from_dt: str, to_dt: str):
    start = datetime.fromisoformat(
        from_dt.replace("Z", "+00:00")
    )
    end = datetime.fromisoformat(
        to_dt.replace("Z", "+00:00")
    )

    current = start

    while current < end:
        chunk_end = min(
            current + timedelta(days=7),
            end,
        )

        chunk_from = current.isoformat().replace("+00:00", "Z")
        chunk_to = chunk_end.isoformat().replace("+00:00", "Z")

        print(f"Ingesting {chunk_from} -> {chunk_to}")

        ingest_drm(chunk_from, chunk_to)

        # Boundary overlap is okay because your upsert
        # prevents duplicate rows.
        current = chunk_end


if __name__ == "__main__":
    ingest_drm(
        "2026-09-01T00:00Z",
        "2026-09-08T00:00Z",
    )

    backfill_drm(
        "2026-01-01T00:00Z",
        "2026-09-16T00:00Z",
    )