import sqlite3
from pathlib import Path

from core.config import DB_PATH


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def initialise_database():
    schema = Path("sql/schema.sql").read_text(encoding="utf-8")

    with get_connection() as conn:
        conn.executescript(schema)


def upsert_margin_lolpdrm_rows(rows):
    query = Path(
        "sql/ingestion/upsert_elexon_margin_lolpdrm.sql"
    ).read_text(encoding="utf-8")

    values = [
        (
            row["event_time_utc"].isoformat(),
            row["published_at_utc"].isoformat(),
            row["forecast_horizon_hours"],
            row["settlement_date"].isoformat(),
            row["settlement_period"],
            row["derated_margin_mw"],
            row["loss_of_load_probability"],
            row["source"],
        )
        for row in rows
    ]

    with get_connection() as conn:
        conn.executemany(query, values)


def upsert_demand_indo_rows(rows):
    query = Path(
        "sql/ingestion/upsert_elexon_demand_indo.sql"
    ).read_text(encoding="utf-8")

    values = [
        (
            row["event_time_utc"].isoformat(),
            row["published_at_utc"].isoformat(),
            row["settlement_date"].isoformat(),
            row["settlement_period"],
            row["demand_mw"],
            row["source"],
        )
        for row in rows
    ]

    with get_connection() as conn:
        conn.executemany(query, values)

def upsert_neso_generation_mix_rows(rows):
    query = Path(
        "sql/ingestion/upsert_neso_generation_mix.sql"
    ).read_text(encoding="utf-8")

    values = [
        (
            row["interval_start_utc"].isoformat(),
            row["interval_end_utc"].isoformat(),
            row["biomass_pct"],
            row["coal_pct"],
            row["imports_pct"],
            row["gas_pct"],
            row["nuclear_pct"],
            row["other_pct"],
            row["hydro_pct"],
            row["solar_pct"],
            row["wind_pct"],
            row["source"],
        )
        for row in rows
    ]

    with get_connection() as conn:
        conn.executemany(query, values)


def count_margin_lolpdrm_rows():
    with get_connection() as conn:
        result = conn.execute(
            "SELECT COUNT(*) FROM elexon_margin_lolpdrm"
        ).fetchone()

    return result[0]


def count_demand_indo_rows():
            "SELECT COUNT(*) FROM elexon_demand_indo"
    with get_connection() as conn:
        return conn.execute(
        ).fetchone()[0]


def count_target_rows():
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT COUNT(*)
            FROM elexon_margin
            WHERE forecast_horizon_hours = 1
            """
        ).fetchone()[0]

def count_neso_generation_mix_rows():
    with get_connection() as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM neso_generation_mix"
        ).fetchone()[0]