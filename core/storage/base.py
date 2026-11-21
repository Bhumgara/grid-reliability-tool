"""
The storage interface: everything the app reads from and writes to its
grid database, as operations on data rather than SQL.

Today this is SQLite (``data/grid.db``). Writing the API, worker and pipelines
against ``GridStore`` instead of a connection lets another backend (Postgres
for live data, BigQuery for history, ...) be swapped in by implementing these
methods; see TODO.md 2.6 and the open storage decision.

Conventions every implementation follows:

- Times in returned frames are timezone-aware UTC (``datetime64[ns, UTC]``).
- Read methods return an empty frame or series when there is no data, and
  raise ``DatabaseUnavailableError`` when the store itself is missing (e.g.
  the deployment data hasn't been set up yet).
- Upserts insert new rows and replace existing ones with the same key, so
  re-fetching an overlapping time window is safe.
- Rows passed to upserts are the normalised records from ``core.normalise``
  (one mapping per row, with datetime and date values).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Literal, Protocol, runtime_checkable

import pandas as pd

# The datasets the store holds, named after their SQLite tables.
Dataset = Literal[
    "elexon_margin_lolpdrm",
    "elexon_demand_indo",
    "elexon_generation_fuelhh",
    "elexon_generation_fuelinst",
    "neso_generation_mix",
    "neso_demand_update",
    "model_dataset",
]

Row = Mapping[str, Any]


class DatabaseUnavailableError(RuntimeError):
    """The store does not exist (e.g. deployment data not set up yet)."""


@runtime_checkable
class GridStore(Protocol):
    """Reads and writes for the grid database. See the module docstring."""

    # --- Set-up --------------------------------------------------------------

    def initialise(self) -> None:
        """Create any missing tables or datasets. Safe to call repeatedly."""
        ...

    # --- Dashboard and API reads (core.queries) --------------------------------

    def recent_margin(self, days: int) -> pd.DataFrame:
        """
        The latest ``days`` of 1-hour-ahead de-rated margin, oldest first.
        Columns: ``event_time_utc``, ``derated_margin_mw`` (nulls excluded).
        """
        ...

    def recent_demand(self, days: int) -> pd.DataFrame:
        """
        The latest ``days`` of INDO demand, oldest first.
        Columns: ``event_time_utc``, ``demand_mw``.
        """
        ...

    def recent_generation(self, days: int) -> pd.DataFrame:
        """
        FUELHH generation for the ``days`` before the latest settlement period:
        one row per ``event_time_utc`` (the index), one column per fuel type (MW).
        """
        ...

    def live_generation_mix(self) -> pd.DataFrame:
        """
        The latest FUELINST snapshot combined with NESO embedded wind and solar.
        Columns: ``event_time_utc``, ``fuel_type``, ``generation_mw``,
        ``embedded_data_status`` (see ``core.queries.load_live_generation_mix``).
        """
        ...

    def live_interconnectors(self) -> pd.DataFrame:
        """
        Interconnector flows (fuel types starting ``INT``) from the latest
        FUELINST snapshot. Columns: ``event_time_utc``, ``fuel_type``,
        ``generation_mw``.
        """
        ...

    def margin_history(self) -> pd.Series:
        """Every non-null 1-hour-ahead de-rated margin (MW), for percentiles."""
        ...

    # --- Model inputs (pipelines.build_dataset, pipelines.predict) -------------

    def model_targets(self) -> pd.DataFrame:
        """
        Prediction targets: 1-hour-ahead margins, oldest first. Columns:
        ``target_time_utc``, ``target_published_at_utc``, ``settlement_date``,
        ``settlement_period``, ``target_drm_mw``.
        """
        ...

    def model_demand(self) -> pd.DataFrame:
        """
        All non-null demand by publication time. Columns:
        ``demand_event_time_utc``, ``demand_published_at_utc``, ``demand_mw``.
        """
        ...

    def model_fuel(self, fuel_types: list[str]) -> pd.DataFrame:
        """
        FUELHH output for ``fuel_types``, one row per event and publication
        time, one column per fuel (see ``pipelines.build_dataset.load_fuelhh``).
        """
        ...

    def model_margin_history(self) -> pd.DataFrame:
        """
        1-hour-ahead margins by publication time. Columns: ``event_time_utc``,
        ``published_at_utc``, ``forecast_horizon_hours``, ``derated_margin_mw``.
        """
        ...

    # --- Ingestion writes (core.db, pipelines.ingest) --------------------------

    def upsert_margin_lolpdrm(self, rows: Iterable[Row]) -> None: ...

    def upsert_demand_indo(self, rows: Iterable[Row]) -> None: ...

    def upsert_generation_fuelhh(self, rows: Iterable[Row]) -> None: ...

    def upsert_generation_fuelinst(self, rows: Iterable[Row]) -> None: ...

    def upsert_neso_generation_mix(self, rows: Iterable[Row]) -> None: ...

    def upsert_neso_demand_update(self, rows: Iterable[Row]) -> None: ...

    def save_model_dataset(self, dataset: pd.DataFrame) -> None:
        """Replace the stored model dataset (one row per ``target_time_utc``)."""
        ...

    # --- Freshness and counts (pipelines.refresh, pipelines.ingest) ------------

    def latest_times(
        self,
        dataset: Dataset,
    ) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
        """
        ``(latest_event, latest_freshness)`` for ``dataset``, in UTC.

        The event time is the latest data time (event or interval start);
        freshness is the latest publication time, falling back to the event
        time for datasets without one. ``(None, None)`` when empty or missing.
        """
        ...

    def row_count(self, dataset: Dataset) -> int:
        """Rows in ``dataset`` (0 if it doesn't exist yet). For ingestion logs."""
        ...

    def target_row_count(self) -> int:
        """1-hour-ahead margin rows, the model's targets. For ingestion logs."""
        ...
