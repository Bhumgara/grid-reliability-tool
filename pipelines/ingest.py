from core.api.elexon import (
    fetch_lolpdrm,
    fetch_indo,
    fetch_fuelhh,
    save_raw,
)

from core.api.neso import (
    fetch_generation_mix,
    save_raw_neso,
)

from core.normalise import (
    normalise_elexon_lolpdrm,
    normalise_elexon_indo,
    normalise_elexon_fuelhh,
    normalise_neso_generation_mix,
)

from core.db import (
    count_margin_lolpdrm_rows,
    count_demand_indo_rows,
    count_target_rows,
    count_generation_fuelhh_rows,
    count_neso_generation_mix_rows,
    initialise_database,
    upsert_margin_lolpdrm_rows,
    upsert_demand_indo_rows,
    upsert_generation_fuelhh_rows,
    upsert_neso_generation_mix_rows,
)

from datetime import datetime, timedelta

def ingest_lolpdrm(from_dt: str, to_dt: str):
    raw = fetch_lolpdrm(from_dt, to_dt)

    rows = normalise_elexon_lolpdrm(raw["data"])

    save_raw(raw, f"lolpdrm_{from_dt}_{to_dt}.json")

    initialise_database()
    upsert_margin_lolpdrm_rows(rows)

    print(f"LOLPDRM Fetched: {len(rows)}")
    print(f"LOLPDRM rows total: {count_margin_lolpdrm_rows()}")
    print(f"Target rows: {count_target_rows()}")

def ingest_indo(from_dt: str, to_dt: str):
    raw = fetch_indo(from_dt, to_dt)

    safe_from = from_dt.replace(":", "-")
    safe_to = to_dt.replace(":", "-")

    save_raw(
        raw,
        f"indo_demand_{safe_from}_{safe_to}.json",
    )

    rows = normalise_elexon_indo(raw["data"])

    print(f"INDO fetched: {len(rows)}")

    initialise_database()
    upsert_demand_indo_rows(rows)

    print(
        f"INDO rows in database: "
        f"{count_demand_indo_rows()}"
    )

def ingest_fuelhh(from_dt: str, to_dt: str):
    raw = fetch_fuelhh(from_dt, to_dt)

    safe_from = from_dt.replace(":", "-")
    safe_to = to_dt.replace(":", "-")

    save_raw(
        raw,
        f"fuelhh_{safe_from}_{safe_to}.json",
    )

    rows = normalise_elexon_fuelhh(
        raw["data"]
    )

    print(
        f"FUELHH generation rows fetched: {len(rows)}"
    )

    initialise_database()
    upsert_generation_fuelhh_rows(rows)

    print(
        "FUELHH rows in database: "
        f"{count_generation_fuelhh_rows()}"
    )

def ingest_neso_generation_mix(
    from_dt: str,
    to_dt: str,
):
    raw = fetch_generation_mix(from_dt, to_dt)

    safe_from = from_dt.replace(":", "-")
    safe_to = to_dt.replace(":", "-")

    save_raw_neso(
        raw,
        f"generation_mix_{safe_from}_{safe_to}.json",
    )

    rows = normalise_neso_generation_mix(
        raw["data"]
    )

    print(
        f"NESO generation mix fetched: {len(rows)}"
    )

    initialise_database()

    upsert_neso_generation_mix_rows(rows)

    print(
        "NESO generation mix rows in database: "
        f"{count_neso_generation_mix_rows()}"
    )


def backfill_lolpdrm(from_dt: str, to_dt: str):
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

        ingest_lolpdrm(chunk_from, chunk_to)

        # Boundary overlap is okay because your upsert
        # prevents duplicate rows.
        current = chunk_end

def backfill_indo(from_dt: str, to_dt: str):
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

        ingest_indo(chunk_from, chunk_to)

        # Boundary overlap is okay because your upsert
        # prevents duplicate rows.
        current = chunk_end

if __name__ == "__main__":
    ingest_neso_generation_mix(
        "2026-09-01T00:00Z",
        "2026-09-02T00:00Z",
    )