"""
Response models shared by every endpoint.

Every response has a ``state`` field, so the client can switch on it:

- ``"ok"``: a ``DataResponse`` subclass carrying the data.
- ``"unavailable"`` or ``"insufficient"``: an ``EmptyState`` with a message to
  show in place of the section (what the dashboard shows with ``st.info``).

Times are timezone-aware UTC and serialise as ISO 8601 with a ``Z`` suffix.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel


def _as_utc(value: datetime) -> datetime:
    """Convert to UTC. Naive times are taken as UTC, as in the database."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


UtcDatetime = Annotated[datetime, AfterValidator(_as_utc)]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class DataResponse(BaseModel):
    """Base for endpoints that return data."""

    state: Literal["ok"] = "ok"
    # Time of the latest data point in this response, for "last updated"
    # labels. None when the response has no single data time.
    as_of_utc: UtcDatetime | None = None


EmptyReason = Literal[
    # The data is missing: no rows, or no saved file.
    "unavailable",
    # Data exists but is too little to use, e.g. a view raised ValueError.
    "insufficient",
]


class EmptyState(BaseModel):
    """Returned instead of data when a section has nothing to show."""

    state: EmptyReason
    message: str

    @classmethod
    def from_error(cls, error: ValueError) -> EmptyState:
        """An ``insufficient`` state carrying a view's ``ValueError`` message."""
        return cls(state="insufficient", message=str(error))
