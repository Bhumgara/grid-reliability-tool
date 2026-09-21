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

from datetime import datetime, timezone


def parse_backfill_datetime(value: str, field_name: str) -> datetime:
    try:
        dt = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise ValueError(
            f"Invalid {field_name}: {value!r}. "
            "Use a valid ISO-8601 UTC datetime, "
            "for example '2026-09-01T00:00Z'."
        ) from exc

    if dt.tzinfo is None:
        raise ValueError(
            f"{field_name} must include a timezone. "
            "Use UTC, e.g. '2026-09-01T00:00Z'."
        )

    return dt.astimezone(timezone.utc)

def validate_backfill_range(
    from_dt: str,
    to_dt: str,
) -> tuple[datetime, datetime]:
    start = parse_backfill_datetime(
        from_dt,
        "from_dt",
    )
    end = parse_backfill_datetime(
        to_dt,
        "to_dt",
    )

    if start >= end:
        raise ValueError(
            f"from_dt must be earlier than to_dt. "
            f"Received {from_dt!r} -> {to_dt!r}."
        )

    return start, end

def ingest_lolpdrm(from_dt: str, to_dt: str):
    start, end = validate_backfill_range(
        from_dt,
        to_dt,
    )

    raw = fetch_lolpdrm(start, end)

    rows = normalise_elexon_lolpdrm(raw["data"])

    save_raw(raw, f"lolpdrm_{start}_{end}.json")

    initialise_database()
    upsert_margin_lolpdrm_rows(rows)

    print(f"LOLPDRM Fetched: {len(rows)}")
    print(f"LOLPDRM rows total: {count_margin_lolpdrm_rows()}")
    print(f"Target rows: {count_target_rows()}")

def ingest_indo(from_dt: str, to_dt: str):
    start, end = validate_backfill_range(
            from_dt,
            to_dt,
        )
    
    raw = fetch_indo(start, end)

    safe_from = start.replace(":", "-")
    safe_to = end.replace(":", "-")

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
    start, end = validate_backfill_range(
            from_dt,
            to_dt,
        )
    
    raw = fetch_fuelhh(start, end)

    safe_from = start.replace(":", "-")
    safe_to = end.replace(":", "-")

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
    start, end = validate_backfill_range(
            from_dt,
            to_dt,
        )
    
    raw = fetch_generation_mix(start, end)

    safe_from = start.replace(":", "-")
    safe_to = end.replace(":", "-")

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
    start_dt, end_dt = validate_backfill_range(
            from_dt,
            to_dt,
        )

    start = datetime.fromisoformat(
        start_dt.replace("Z", "+00:00")
    )
    end = datetime.fromisoformat(
        end_dt.replace("Z", "+00:00")
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
    start_dt, end_dt = validate_backfill_range(
                from_dt,
                to_dt,
            )

    start = datetime.fromisoformat(
        start_dt.replace("Z", "+00:00")
    )
    end = datetime.fromisoformat(
        end_dt.replace("Z", "+00:00")
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

def backfill_fuelhh(
    from_dt: str,
    to_dt: str,
):
    start_dt, end_dt = validate_backfill_range(
                from_dt,
                to_dt,
            )
    
    start = datetime.fromisoformat(
        start_dt.replace("Z", "+00:00")
    )
    end = datetime.fromisoformat(
        end_dt.replace("Z", "+00:00")
    )

    current = start

    while current < end:
        chunk_end = min(
            current + timedelta(days=1),
            end,
        )

        chunk_from = current.isoformat().replace(
            "+00:00", "Z"
        )
        chunk_to = chunk_end.isoformat().replace(
            "+00:00", "Z"
        )

        print(
            f"Ingesting FUELHH "
            f"{chunk_from} -> {chunk_to}"
        )

        ingest_fuelhh(
            chunk_from,
            chunk_to,
        )

        current = chunk_end

def backfill_neso_generation_mix(
    from_dt: str,
    to_dt: str,
):
    start_dt, end_dt = validate_backfill_range(
                from_dt,
                to_dt,
            )
    
    start = datetime.fromisoformat(
        start_dt.replace("Z", "+00:00")
    )
    end = datetime.fromisoformat(
        end_dt.replace("Z", "+00:00")
    )

    current = start

    while current < end:
        chunk_end = min(
            current + timedelta(days=1),
            end,
        )

        chunk_from = current.isoformat().replace(
            "+00:00", "Z"
        )
        chunk_to = chunk_end.isoformat().replace(
            "+00:00", "Z"
        )

        print(
            f"Ingesting NESO generation mix "
            f"{chunk_from} -> {chunk_to}"
        )

        ingest_neso_generation_mix(
            chunk_from,
            chunk_to,
        )

        current = chunk_end

if __name__ == "__main__":
    backfill_lolpdrm(
        from_dt="2026-09-01T00:00Z",
        to_dt="2026-09-21T00:00Z",
    )

    backfill_indo(
        from_dt="2026-09-01T00:00Z",
        to_dt="2026-09-21T00:00Z",
    )

    backfill_neso_generation_mix(
        from_dt="2026-09-01T00:00Z",
        to_dt="2026-09-21T00:00Z",
    )

    backfill_fuelhh(
        from_dt="2026-09-01T00:00Z",
        to_dt="2026-09-21T00:00Z",
    )