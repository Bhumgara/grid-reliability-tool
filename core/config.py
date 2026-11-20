from pathlib import Path

# core/config.py -> core -> repo root. Paths below are absolute so they point at
# the same files whichever directory a process (dashboard, API, worker) starts in.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

DB_PATH = PROJECT_ROOT / "data" / "grid.db"

# Files written by the model and refresh pipelines, read by the dashboard/API.
METRICS_PATH = PROJECT_ROOT / "artifacts" / "metrics.json"
FORECAST_PATH = PROJECT_ROOT / "data" / "processed" / "latest_forecast.json"
STATUS_PATH = PROJECT_ROOT / "data" / "processed" / "refresh_status.json"
VALIDATION_PATH = PROJECT_ROOT / "data" / "processed" / "validation_predictions.csv"
TEST_PATH = PROJECT_ROOT / "data" / "processed" / "test_predictions.csv"
