import pandas as pd
import pytest

from core.views.status import STARTING_MESSAGE, refresh_status_view

# Shaped like the "degraded" payload pipelines.refresh.refresh_live_data writes.
DEGRADED = {
    "state": "degraded",
    "message": "Refresh completed but required data is still stale.",
    "started_at_utc": "2026-11-20T10:00:00+00:00",
    "completed_at_utc": "2026-11-20T10:01:30+00:00",
    "sources_before": {},
    "sources": {
        "LOLPDRM": {
            "name": "LOLPDRM",
            "required": True,
            "latest_event_utc": "2026-11-20T09:30:00+00:00",
            "latest_freshness_utc": "2026-11-20T09:35:00+00:00",
            "age_minutes": 26.5,
            "stale": False,
        },
        "NESO generation mix": {
            "name": "NESO generation mix",
            "required": False,
            "latest_event_utc": None,
            "latest_freshness_utc": None,
            "age_minutes": None,
            "stale": True,
        },
    },
    "source_refresh": {
        "LOLPDRM": {"refresh_status": "updated", "error": None},
        "NESO generation mix": {
            "refresh_status": "error",
            "error": "HTTPError: 503 error",
        },
    },
    "prediction": {
        "status": "error",
        "generated_at_utc": None,
        "error": "ValueError: no rows",
    },
}


def test_empty_status_means_worker_is_starting():
    view = refresh_status_view({})

    assert view.state == "starting"
    assert view.message == STARTING_MESSAGE
    assert view.completed_at_utc is None
    assert view.sources == ()
    assert view.errors == ()


def test_degraded_status():
    view = refresh_status_view(DEGRADED)

    assert view.state == "degraded"
    assert view.message == DEGRADED["message"]
    assert view.started_at_utc == pd.Timestamp("2026-11-20T10:00:00Z")
    assert view.completed_at_utc == pd.Timestamp("2026-11-20T10:01:30Z")
    assert view.forecast_generated_at_utc is None
    assert [s.name for s in view.sources] == ["LOLPDRM", "NESO generation mix"]

    drm, neso = view.sources
    assert drm.required and not drm.stale
    assert drm.latest_event_utc == pd.Timestamp("2026-11-20T09:30:00Z")
    assert drm.age_minutes == pytest.approx(26.5)
    assert not neso.required and neso.stale
    assert neso.latest_event_utc is None and neso.age_minutes is None

    assert view.errors == (
        "NESO generation mix: HTTPError: 503 error",
        "Prediction: ValueError: no rows",
    )


def test_fresh_status_reads_forecast_time():
    view = refresh_status_view({
        "state": "fresh",
        "message": "Local data and forecast are fresh.",
        "completed_at_utc": "2026-11-20T10:01:30+00:00",
        "prediction": {"status": "current", "generated_at_utc": "2026-11-20T09:00:00"},
    })

    assert view.state == "fresh"
    # Naive times in the file are UTC.
    assert view.forecast_generated_at_utc == pd.Timestamp("2026-11-20T09:00:00Z")
    assert view.errors == ()


def test_refreshing_status_has_no_completed_time():
    view = refresh_status_view({
        "state": "refreshing",
        "message": "Refreshing source data in the background.",
        "started_at_utc": "2026-11-20T10:00:00+00:00",
        "sources": {},
    })

    assert view.state == "refreshing"
    assert view.completed_at_utc is None


def test_times_are_converted_to_utc():
    view = refresh_status_view({
        "state": "fresh",
        "completed_at_utc": "2026-11-20T11:00:00+01:00",
    })

    assert view.completed_at_utc == pd.Timestamp("2026-11-20T10:00:00Z")
    assert str(view.completed_at_utc.tz) == "UTC"


def test_unrecognised_state_is_unknown():
    assert refresh_status_view({"state": "exploded"}).state == "unknown"
    assert refresh_status_view({"message": "no state"}).state == "unknown"


def test_malformed_fields_are_treated_as_missing():
    view = refresh_status_view({
        "state": "fresh",
        "message": None,
        "completed_at_utc": "not a time",
        "started_at_utc": 12345678901234567890,
        "prediction": "oops",
        "sources": {
            "bad": "not a dict",
            "LOLPDRM": {"age_minutes": "soon", "latest_event_utc": "never"},
        },
        "source_refresh": ["not", "a", "dict"],
    })

    assert view.message == ""
    assert view.completed_at_utc is None
    assert view.started_at_utc is None
    assert view.forecast_generated_at_utc is None
    assert len(view.sources) == 1
    source = view.sources[0]
    assert source.name == "LOLPDRM"
    assert source.latest_event_utc is None
    assert source.age_minutes is None
    # Missing freshness counts as stale, as in pipelines.refresh.
    assert source.stale
    assert view.errors == ()
