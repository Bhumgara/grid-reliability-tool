"""Tests for the shared API response models."""

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
from pydantic import TypeAdapter, ValidationError

from backend.api.models import DataResponse, EmptyState

EXPECTED_JSON = '{"state":"ok","as_of_utc":"2026-11-20T10:00:00Z"}'


@pytest.mark.parametrize(
    "as_of",
    [
        datetime(2026, 11, 20, 10, 0),
        datetime(2026, 11, 20, 11, 0, tzinfo=timezone(timedelta(hours=1))),
        pd.Timestamp("2026-11-20 10:00", tz="Europe/London"),
        "2026-11-20T10:00:00Z",
    ],
    ids=["naive", "plus-one-hour", "pandas-london", "iso-string"],
)
def test_times_serialise_as_utc(as_of):
    assert DataResponse(as_of_utc=as_of).model_dump_json() == EXPECTED_JSON


def test_data_response_defaults():
    assert DataResponse().model_dump() == {"state": "ok", "as_of_utc": None}


def test_data_response_state_is_always_ok():
    with pytest.raises(ValidationError):
        DataResponse(state="unavailable")


@pytest.mark.parametrize("state", ["unavailable", "insufficient"])
def test_empty_state_accepts_its_reasons(state):
    empty = EmptyState(state=state, message="Nothing to show.")

    assert empty.model_dump() == {"state": state, "message": "Nothing to show."}


def test_empty_state_rejects_ok():
    with pytest.raises(ValidationError):
        EmptyState(state="ok", message="x")


def test_empty_state_from_view_error():
    empty = EmptyState.from_error(ValueError("Not enough history."))

    assert empty.state == "insufficient"
    assert empty.message == "Not enough history."


def test_union_schema_keeps_both_models():
    schema = TypeAdapter(DataResponse | EmptyState).json_schema()

    assert [option["$ref"] for option in schema["anyOf"]] == [
        "#/$defs/DataResponse",
        "#/$defs/EmptyState",
    ]
