import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.api.main import create_app
from core import config
from core.views.model import model_vs_persistence_view
from tests.test_views_model import METRICS


@pytest.fixture
def client():
    return TestClient(create_app())


@pytest.fixture
def files(tmp_path, monkeypatch):
    """Point the metrics and predictions loaders at temporary files (not created)."""
    paths = {
        "metrics": tmp_path / "metrics.json",
        "validation": tmp_path / "validation_predictions.csv",
        "test": tmp_path / "test_predictions.csv",
    }
    monkeypatch.setattr(config, "METRICS_PATH", paths["metrics"])
    monkeypatch.setattr(config, "VALIDATION_PATH", paths["validation"])
    monkeypatch.setattr(config, "TEST_PATH", paths["test"])
    return paths


def _predictions() -> pd.DataFrame:
    """Ten hourly predictions, model 100 MW high and baseline 300 MW high, newest first."""
    target = [1000.0 * i for i in range(1, 11)]
    data = pd.DataFrame({
        "target_time_utc": pd.date_range("2026-06-01T00:00Z", periods=10, freq="h"),
        "target_drm_mw": target,
        "baseline_drm_yesterday_mw": [t + 300 for t in target],
        "predicted_drm_mw": [t + 100 for t in target],
    })
    data["error_mw"] = data["predicted_drm_mw"] - data["target_drm_mw"]
    data["absolute_error_mw"] = data["error_mw"].abs()
    return data.iloc[::-1]


# --- /api/model/metrics --------------------------------------------------------


def test_model_metrics(files, client):
    files["metrics"].write_text(json.dumps(METRICS), encoding="utf-8")

    assert client.get("/api/model/metrics").json() == {
        "state": "ok",
        "as_of_utc": "2026-09-21T00:00:00Z",
        "model": "Ridge Regression",
        "alpha": 350.0,
        "forecast_horizon_hours": 24,
        "model_mae_gw": pytest.approx(3.4),
        "baseline_mae_gw": pytest.approx(4.1),
        "mae_improvement_pct": 17.5,
        "model_rmse_gw": pytest.approx(4.3),
        "baseline_rmse_gw": pytest.approx(5.3),
        "test_start_utc": "2026-01-01T00:00:00Z",
        "test_end_utc": "2026-09-21T00:00:00Z",
        "test_rows": 12356,
    }


def test_committed_metrics_file_is_served(client):
    # artifacts/metrics.json is committed, so the real file must parse.
    body = client.get("/api/model/metrics").json()

    assert body["state"] == "ok"
    assert body["model_mae_gw"] < body["baseline_mae_gw"]


def test_missing_metrics_are_unavailable(files, client):
    assert client.get("/api/model/metrics").json() == {
        "state": "unavailable",
        "message": "Final model metrics are unavailable.",
    }


def test_incomplete_metrics_are_insufficient(files, client):
    files["metrics"].write_text(json.dumps({"model": "Ridge"}), encoding="utf-8")

    assert client.get("/api/model/metrics").json() == {
        "state": "insufficient",
        "message": "The saved model metrics are incomplete.",
    }


# --- /api/model/validation -----------------------------------------------------


def test_model_validation(files, client):
    predictions = _predictions()
    predictions.to_csv(files["validation"], index=False)
    expected = model_vs_persistence_view(predictions)

    body = client.get("/api/model/validation").json()

    assert body["state"] == "ok"
    assert body["as_of_utc"] == "2026-06-01T09:00:00Z"
    assert len(body["points"]) == 10
    # Sorted oldest first even though the file is newest first.
    assert body["points"][0] == {
        "time_utc": "2026-06-01T00:00:00Z",
        "actual_gw": 1.0,
        "predicted_gw": pytest.approx(1.1),
        "error_gw": pytest.approx(0.1),
    }
    assert body["comparison_message"] is None
    assert body["comparison"]["bars"] == [
        {"segment": row.segment, "method": row.method, "mae_gw": pytest.approx(row.mae_gw)}
        for row in expected.compare.itertuples()
    ]
    assert body["comparison"]["axis_min_gw"] == pytest.approx(expected.axis_min_gw)
    assert body["comparison"]["axis_max_gw"] == pytest.approx(expected.axis_max_gw)


def test_validation_falls_back_to_test_predictions(files, client):
    _predictions().to_csv(files["test"], index=False)

    assert len(client.get("/api/model/validation").json()["points"]) == 10


def test_validation_without_baseline_still_returns_points(files, client):
    _predictions().drop(columns="baseline_drm_yesterday_mw").to_csv(
        files["validation"], index=False
    )

    body = client.get("/api/model/validation").json()

    assert body["state"] == "ok"
    assert len(body["points"]) == 10
    assert body["comparison"] is None
    assert "baseline prediction column" in body["comparison_message"]


def test_validation_drops_rows_with_missing_values(files, client):
    predictions = _predictions()
    predictions.loc[predictions.index[0], "predicted_drm_mw"] = None
    predictions.to_csv(files["validation"], index=False)

    body = client.get("/api/model/validation").json()

    assert len(body["points"]) == 9
    assert all(point["predicted_gw"] is not None for point in body["points"])


def test_missing_predictions_are_unavailable(files, client):
    assert client.get("/api/model/validation").json() == {
        "state": "unavailable",
        "message": "Validation predictions are unavailable.",
    }


def test_predictions_missing_a_column_are_insufficient(files, client):
    _predictions().drop(columns="error_mw").to_csv(files["validation"], index=False)

    body = client.get("/api/model/validation").json()

    assert body["state"] == "insufficient"
    assert "error_mw" in body["message"]
