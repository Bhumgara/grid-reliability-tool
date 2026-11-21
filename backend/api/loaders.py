"""
Cached data loaders for the API.

The same loaders as ``core.queries``, with a time-to-live cache in front, as
``dashboard/data.py`` adds ``st.cache_data``. Each app built by
``create_app()`` gets its own ``Loaders``, and routes receive it as a
dependency (``LoadersDep``), so tests start with an empty cache.

Each call returns a copy of the cached value, so a view can't change it for
the next request. Errors (e.g. a missing database) are not cached.
"""

from __future__ import annotations

import copy
import threading
import time
from collections.abc import Callable
from typing import Annotated, Any

import pandas as pd
from fastapi import Depends, Request

from core import queries

# Seconds each kind of data is cached. Live, forecast and status match the
# dashboard. The dashboard caches the rest for the life of the process; the
# API refreshes them hourly, so new history or a retrained model shows up
# without a restart.
LIVE_TTL_SECONDS = 45
FORECAST_TTL_SECONDS = 15
STATUS_TTL_SECONDS = 5
SLOW_TTL_SECONDS = 3600


class Loaders:
    """``core.queries`` loaders behind a TTL cache. ``enabled=False`` turns caching off."""

    def __init__(
        self,
        enabled: bool = True,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.enabled = enabled
        self._clock = clock
        self._lock = threading.Lock()
        self._entries: dict[tuple, tuple[float, Any]] = {}

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def _cached(self, ttl: float, loader: Callable[..., Any], *args: Any) -> Any:
        if not self.enabled:
            return loader(*args)

        key = (loader.__name__, args)
        now = self._clock()

        with self._lock:
            entry = self._entries.get(key)

        if entry is not None and entry[0] > now:
            return copy.deepcopy(entry[1])

        # Loaded outside the lock: two requests may both load on a miss,
        # which is harmless, and slow loads don't block other keys.
        value = loader(*args)

        with self._lock:
            self._entries[key] = (now + ttl, value)

        return copy.deepcopy(value)

    # --- Live data --------------------------------------------------------

    def load_recent_margin(self, days: int = 7) -> pd.DataFrame:
        return self._cached(LIVE_TTL_SECONDS, queries.load_recent_margin, days)

    def load_recent_demand(self, days: int = 7) -> pd.DataFrame:
        return self._cached(LIVE_TTL_SECONDS, queries.load_recent_demand, days)

    def load_recent_generation(self, days: int = 7) -> pd.DataFrame:
        return self._cached(LIVE_TTL_SECONDS, queries.load_recent_generation, days)

    def load_live_generation_mix(self) -> pd.DataFrame:
        return self._cached(LIVE_TTL_SECONDS, queries.load_live_generation_mix)

    def load_live_interconnectors(self) -> pd.DataFrame:
        return self._cached(LIVE_TTL_SECONDS, queries.load_live_interconnectors)

    # --- Forecast and status ----------------------------------------------

    def load_latest_forecast(self) -> dict | None:
        return self._cached(FORECAST_TTL_SECONDS, queries.load_latest_forecast)

    def load_refresh_status(self) -> dict:
        return self._cached(STATUS_TTL_SECONDS, queries.load_refresh_status)

    def load_last_refresh_completed(self) -> pd.Timestamp | None:
        return self._cached(STATUS_TTL_SECONDS, queries.load_last_refresh_completed)

    # --- Slow-changing ----------------------------------------------------

    def load_margin_history(self) -> pd.Series:
        return self._cached(SLOW_TTL_SECONDS, queries.load_margin_history)

    def load_model_metrics(self) -> dict:
        return self._cached(SLOW_TTL_SECONDS, queries.load_model_metrics)

    def load_validation_predictions(self) -> pd.DataFrame:
        return self._cached(SLOW_TTL_SECONDS, queries.load_validation_predictions)


def get_loaders(request: Request) -> Loaders:
    return request.app.state.loaders


LoadersDep = Annotated[Loaders, Depends(get_loaders)]
