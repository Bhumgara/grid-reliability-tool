from pathlib import Path

DB_PATH = Path("data/grid.db")

# Files written by the model and refresh pipelines, read by the dashboard/API.
METRICS_PATH = Path("artifacts/metrics.json")
FORECAST_PATH = Path("data/processed/latest_forecast.json")
STATUS_PATH = Path("data/processed/refresh_status.json")
VALIDATION_PATH = Path("data/processed/validation_predictions.csv")
TEST_PATH = Path("data/processed/test_predictions.csv")
