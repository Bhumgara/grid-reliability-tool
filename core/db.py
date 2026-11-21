"""
Ingestion writes and row counts, used by pipelines.ingest.

Thin wrappers around the storage backend (``core.storage``; SQLite today),
kept so the ingestion code reads the same. The SQL lives in
``core/storage/sqlite.py``.
"""

from core.storage import SQLiteStore


def _store() -> SQLiteStore:
    # Reads core.config.DB_PATH on each call.
    return SQLiteStore()


def initialise_database():
    _store().initialise()


def upsert_margin_lolpdrm_rows(rows):
    _store().upsert_margin_lolpdrm(rows)


def upsert_demand_indo_rows(rows):
    _store().upsert_demand_indo(rows)


def upsert_generation_fuelhh_rows(rows):
    _store().upsert_generation_fuelhh(rows)


def upsert_generation_fuelinst_rows(rows):
    _store().upsert_generation_fuelinst(rows)


def upsert_neso_generation_mix_rows(rows):
    _store().upsert_neso_generation_mix(rows)


def upsert_neso_demand_update_rows(rows):
    _store().upsert_neso_demand_update(rows)


def count_margin_lolpdrm_rows():
    return _store().row_count("elexon_margin_lolpdrm")


def count_demand_indo_rows():
    return _store().row_count("elexon_demand_indo")


def count_generation_fuelhh_rows():
    return _store().row_count("elexon_generation_fuelhh")


def count_generation_fuelinst_rows():
    return _store().row_count("elexon_generation_fuelinst")


def count_target_rows():
    return _store().target_row_count()


def count_neso_generation_mix_rows():
    return _store().row_count("neso_generation_mix")


def count_neso_demand_update_rows():
    return _store().row_count("neso_demand_update")
