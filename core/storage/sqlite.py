"""
SQLite implementation of ``GridStore`` (``data/grid.db``).

The SQL here is the SQL ``core.queries``, ``core.db``, ``pipelines.build_dataset``
and ``pipelines.refresh`` run today; tests check each method returns the same
data. Reads open the database read-only, so a missing file raises
``DatabaseUnavailableError`` instead of creating an empty one. Writes open it
read-write, creating the file and folder if needed.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path

import pandas as pd

from core import config
from core.storage.base import Dataset, DatabaseUnavailableError, Row

# Columns used for each dataset's latest data time and latest publication time,
# first match wins (as pipelines.refresh.max_timestamp).
_EVENT_COLUMNS = ("event_time_utc", "interval_start_utc", "start_time_utc")
_FRESHNESS_COLUMNS = ("published_at_utc", *_EVENT_COLUMNS)


def _utc(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values, utc=True)


def _utc_scalar(value) -> pd.Timestamp | None:
    if value is None:
        return None
    ts = pd.Timestamp(value)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def _iso(value) -> str:
    return value.isoformat()


class SQLiteStore:
    """
    ``GridStore`` backed by one SQLite file.

    ``db_path`` defaults to ``core.config.DB_PATH``, read on each call, so
    tests (and ``GRID_DATA_DIR``) can point it elsewhere.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path

    @property
    def db_path(self) -> Path:
        return Path(self._db_path or config.DB_PATH).resolve()

    # --- Connections ----------------------------------------------------------

    @contextmanager
    def _read(self) -> Iterator[sqlite3.Connection]:
        path = self.db_path

        if not path.is_file():
            raise DatabaseUnavailableError(f"Database not found: {path}")

        conn = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=10)
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        path = self.db_path
        path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(path, timeout=10)
        try:
            with conn:  # commits, or rolls back on error
                yield conn
        finally:
            conn.close()

    # --- Set-up ---------------------------------------------------------------

    def initialise(self) -> None:
        schema = config.SCHEMA_PATH.read_text(encoding="utf-8")
        with self._write() as conn:
            conn.executescript(schema)

    # --- Dashboard and API reads ------------------------------------------------

    @staticmethod
    def _sorted_by_time(df: pd.DataFrame) -> pd.DataFrame:
        df["event_time_utc"] = _utc(df["event_time_utc"])
        return df.sort_values("event_time_utc").reset_index(drop=True)

    def recent_margin(self, days: int) -> pd.DataFrame:
        with self._read() as conn:
            df = pd.read_sql_query(
                """
                SELECT event_time_utc, derated_margin_mw
                FROM elexon_margin_lolpdrm
                WHERE forecast_horizon_hours = 1
                  AND derated_margin_mw IS NOT NULL
                ORDER BY event_time_utc DESC
                LIMIT ?;
                """,
                conn,
                params=(days * 48,),
            )
        return df if df.empty else self._sorted_by_time(df)

    def recent_demand(self, days: int) -> pd.DataFrame:
        with self._read() as conn:
            df = pd.read_sql_query(
                """
                SELECT event_time_utc, demand_mw
                FROM elexon_demand_indo
                ORDER BY event_time_utc DESC
                LIMIT ?;
                """,
                conn,
                params=(days * 48,),
            )
        return df if df.empty else self._sorted_by_time(df)

    def recent_generation(self, days: int) -> pd.DataFrame:
        with self._read() as conn:
            latest = _utc_scalar(
                conn.execute(
                    "SELECT MAX(event_time_utc) FROM elexon_generation_fuelhh;"
                ).fetchone()[0]
            )

            if latest is None:
                return pd.DataFrame()

            cutoff = latest - pd.Timedelta(days=days)

            df = pd.read_sql_query(
                """
                SELECT event_time_utc, fuel_type, generation_mw
                FROM elexon_generation_fuelhh
                WHERE event_time_utc >= ?
                ORDER BY event_time_utc;
                """,
                conn,
                params=(cutoff.isoformat(),),
            )

        if df.empty:
            return df

        df["event_time_utc"] = _utc(df["event_time_utc"])

        return df.pivot_table(
            index="event_time_utc",
            columns="fuel_type",
            values="generation_mw",
            aggfunc="sum",
        ).sort_index()

    def _latest_fuelinst(self, conn: sqlite3.Connection, where: str = "") -> pd.DataFrame:
        return pd.read_sql_query(
            f"""
            SELECT event_time_utc, settlement_date, settlement_period,
                   fuel_type, generation_mw
            FROM elexon_generation_fuelinst
            WHERE event_time_utc = (
                SELECT MAX(event_time_utc) FROM elexon_generation_fuelinst
            )
            {where}
            ORDER BY fuel_type
            """,
            conn,
        )

    def live_generation_mix(self) -> pd.DataFrame:
        with self._read() as conn:
            latest = self._latest_fuelinst(conn)

            if latest.empty:
                return pd.DataFrame()

            neso = pd.read_sql_query(
                """
                SELECT embedded_wind_mw, embedded_solar_mw, forecast_actual_indicator
                FROM neso_demand_update
                WHERE settlement_date = ?
                  AND settlement_period = ?
                ORDER BY CASE WHEN forecast_actual_indicator = 'A' THEN 0 ELSE 1 END
                LIMIT 1
                """,
                conn,
                params=(
                    latest["settlement_date"].iloc[0],
                    int(latest["settlement_period"].iloc[0]),
                ),
            )

        fuelinst = latest.set_index("fuel_type")["generation_mw"].to_dict()

        if neso.empty:
            indicator, embedded_wind, embedded_solar = None, 0.0, 0.0
        else:
            indicator = neso["forecast_actual_indicator"].iloc[0]
            embedded_wind = float(neso["embedded_wind_mw"].fillna(0.0).iloc[0])
            embedded_solar = float(neso["embedded_solar_mw"].fillna(0.0).iloc[0])

        # Gas types merge into CCGT; embedded wind adds to WIND; SOLAR is NESO's.
        mix = {
            "CCGT": fuelinst.get("CCGT", 0.0) + fuelinst.get("OCGT", 0.0),
            "COAL": fuelinst.get("COAL", 0.0),
            "OIL": fuelinst.get("OIL", 0.0),
            "NUCLEAR": fuelinst.get("NUCLEAR", 0.0),
            "BIOMASS": fuelinst.get("BIOMASS", 0.0),
            "NPSHYD": fuelinst.get("NPSHYD", 0.0),
            "OTHER": fuelinst.get("OTHER", 0.0),
            "WIND": fuelinst.get("WIND", 0.0) + embedded_wind,
            "SOLAR": embedded_solar,
        }
        event_time = _utc_scalar(latest["event_time_utc"].iloc[0])

        return pd.DataFrame(
            [
                {
                    "event_time_utc": event_time,
                    "fuel_type": fuel,
                    "generation_mw": mw,
                    "embedded_data_status": indicator,
                }
                for fuel, mw in mix.items()
            ]
        )

    def live_interconnectors(self) -> pd.DataFrame:
        with self._read() as conn:
            df = self._latest_fuelinst(conn, where="AND fuel_type LIKE 'INT%'")

        df = df[["event_time_utc", "fuel_type", "generation_mw"]].copy()
        if not df.empty:
            df["event_time_utc"] = _utc(df["event_time_utc"])
        return df.reset_index(drop=True)

    def margin_history(self) -> pd.Series:
        with self._read() as conn:
            df = pd.read_sql_query(
                """
                SELECT derated_margin_mw
                FROM elexon_margin_lolpdrm
                WHERE forecast_horizon_hours = 1
                  AND derated_margin_mw IS NOT NULL;
                """,
                conn,
            )
        return df["derated_margin_mw"]

    # --- Model inputs -----------------------------------------------------------

    def model_targets(self) -> pd.DataFrame:
        with self._read() as conn:
            df = pd.read_sql_query(
                config.MODEL_DATASET_SQL_PATH.read_text(encoding="utf-8"), conn
            )
        df["target_time_utc"] = _utc(df["target_time_utc"])
        df["target_published_at_utc"] = _utc(df["target_published_at_utc"])
        return df

    def model_demand(self) -> pd.DataFrame:
        with self._read() as conn:
            df = pd.read_sql_query(
                """
                SELECT event_time_utc, published_at_utc, demand_mw
                FROM elexon_demand_indo
                WHERE demand_mw IS NOT NULL
                ORDER BY published_at_utc;
                """,
                conn,
            )
        df["event_time_utc"] = _utc(df["event_time_utc"])
        df["published_at_utc"] = _utc(df["published_at_utc"])
        return df.rename(
            columns={
                "event_time_utc": "demand_event_time_utc",
                "published_at_utc": "demand_published_at_utc",
            }
        )

    def model_fuel(self, fuel_types: list[str]) -> pd.DataFrame:
        placeholders = ",".join("?" for _ in fuel_types)

        with self._read() as conn:
            df = pd.read_sql_query(
                f"""
                SELECT event_time_utc, published_at_utc, fuel_type, generation_mw
                FROM elexon_generation_fuelhh
                WHERE fuel_type IN ({placeholders})
                ORDER BY published_at_utc;
                """,
                conn,
                params=list(fuel_types),
            )

        df["event_time_utc"] = _utc(df["event_time_utc"])
        df["published_at_utc"] = _utc(df["published_at_utc"])

        wide = df.pivot_table(
            index=["event_time_utc", "published_at_utc"],
            columns="fuel_type",
            values="generation_mw",
            aggfunc="last",
        ).reset_index()
        wide.columns.name = None

        return wide.rename(
            columns={
                "event_time_utc": "fuel_event_time_utc",
                "published_at_utc": "fuel_published_at_utc",
                "WIND": "wind_mw",
                "CCGT": "ccgt_mw",
                "NUCLEAR": "nuclear_mw",
                "BIOMASS": "biomass_mw",
            }
        )

    def model_margin_history(self) -> pd.DataFrame:
        with self._read() as conn:
            df = pd.read_sql_query(
                """
                SELECT event_time_utc, published_at_utc,
                       forecast_horizon_hours, derated_margin_mw
                FROM elexon_margin_lolpdrm
                WHERE forecast_horizon_hours = 1
                  AND derated_margin_mw IS NOT NULL
                ORDER BY published_at_utc;
                """,
                conn,
            )
        df["event_time_utc"] = _utc(df["event_time_utc"])
        df["published_at_utc"] = _utc(df["published_at_utc"])
        return df

    # --- Ingestion writes -------------------------------------------------------

    def _upsert(self, sql_file: str, values: list[tuple]) -> None:
        query = (config.INGESTION_SQL_DIR / sql_file).read_text(encoding="utf-8")
        with self._write() as conn:
            conn.executemany(query, values)

    def upsert_margin_lolpdrm(self, rows: Iterable[Row]) -> None:
        self._upsert(
            "upsert_elexon_margin_lolpdrm.sql",
            [
                (
                    _iso(row["event_time_utc"]),
                    _iso(row["published_at_utc"]),
                    row["forecast_horizon_hours"],
                    _iso(row["settlement_date"]),
                    row["settlement_period"],
                    row["derated_margin_mw"],
                    row["loss_of_load_probability"],
                    row["source"],
                )
                for row in rows
            ],
        )

    def upsert_demand_indo(self, rows: Iterable[Row]) -> None:
        self._upsert(
            "upsert_elexon_demand_indo.sql",
            [
                (
                    _iso(row["event_time_utc"]),
                    _iso(row["published_at_utc"]),
                    _iso(row["settlement_date"]),
                    row["settlement_period"],
                    row["demand_mw"],
                    row["source"],
                )
                for row in rows
            ],
        )

    def _generation_values(self, rows: Iterable[Row]) -> list[tuple]:
        return [
            (
                _iso(row["event_time_utc"]),
                _iso(row["published_at_utc"]),
                _iso(row["settlement_date"]),
                row["settlement_period"],
                row["fuel_type"],
                row["generation_mw"],
                row["source"],
            )
            for row in rows
        ]

    def upsert_generation_fuelhh(self, rows: Iterable[Row]) -> None:
        self._upsert("upsert_elexon_generation_fuelhh.sql", self._generation_values(rows))

    def upsert_generation_fuelinst(self, rows: Iterable[Row]) -> None:
        self._upsert("upsert_elexon_generation_fuelinst.sql", self._generation_values(rows))

    def upsert_neso_generation_mix(self, rows: Iterable[Row]) -> None:
        self._upsert(
            "upsert_neso_generation_mix.sql",
            [
                (
                    _iso(row["interval_start_utc"]),
                    _iso(row["interval_end_utc"]),
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
            ],
        )

    def upsert_neso_demand_update(self, rows: Iterable[Row]) -> None:
        # NESO settlement dates arrive as strings already (see core.normalise).
        self._upsert(
            "upsert_neso_demand_update.sql",
            [
                (
                    row["settlement_date"],
                    row["settlement_period"],
                    row["forecast_actual_indicator"],
                    row["embedded_wind_mw"],
                    row["embedded_solar_mw"],
                    row["pump_storage_pumping_mw"],
                    row["source"],
                )
                for row in rows
            ],
        )

    def save_model_dataset(self, dataset: pd.DataFrame) -> None:
        df = dataset.copy()

        # SQLite has no timezone-aware datetime type: store ISO-8601 strings.
        for column in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[column]):
                df[column] = df[column].apply(
                    lambda value: value.isoformat() if pd.notna(value) else None
                )

        with self._write() as conn:
            df.to_sql("model_dataset", conn, if_exists="replace", index=False)
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_model_dataset_target_time
                ON model_dataset (target_time_utc);
                """
            )

    # --- Freshness and counts ---------------------------------------------------

    @staticmethod
    def _columns(conn: sqlite3.Connection, dataset: Dataset) -> list[str]:
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1;",
            (dataset,),
        ).fetchone()
        if exists is None:
            return []
        return [row[1] for row in conn.execute(f'PRAGMA table_info("{dataset}")')]

    def _max(self, conn: sqlite3.Connection, dataset: Dataset, candidates) -> pd.Timestamp | None:
        columns = self._columns(conn, dataset)
        column = next((c for c in candidates if c in columns), None)
        if column is None:
            return None
        return _utc_scalar(
            conn.execute(f'SELECT MAX("{column}") FROM "{dataset}"').fetchone()[0]
        )

    def latest_times(
        self,
        dataset: Dataset,
    ) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
        try:
            with self._read() as conn:
                return (
                    self._max(conn, dataset, _EVENT_COLUMNS),
                    self._max(conn, dataset, _FRESHNESS_COLUMNS),
                )
        except DatabaseUnavailableError:
            return None, None

    def row_count(self, dataset: Dataset) -> int:
        try:
            with self._read() as conn:
                if not self._columns(conn, dataset):
                    return 0
                return conn.execute(f'SELECT COUNT(*) FROM "{dataset}"').fetchone()[0]
        except DatabaseUnavailableError:
            return 0

    def target_row_count(self) -> int:
        try:
            with self._read() as conn:
                if not self._columns(conn, "elexon_margin_lolpdrm"):
                    return 0
                return conn.execute(
                    """
                    SELECT COUNT(*) FROM elexon_margin_lolpdrm
                    WHERE forecast_horizon_hours = 1
                    """
                ).fetchone()[0]
        except DatabaseUnavailableError:
            return 0
