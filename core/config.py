from pathlib import Path

# core/config.py -> core -> repo root. Paths below are absolute so they point at
# the same files whichever directory a process (dashboard, API, worker) starts in.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
SQL_DIR = PROJECT_ROOT / "sql"

DB_PATH = DATA_DIR / "grid.db"

# SQL files.
SCHEMA_PATH = SQL_DIR / "schema.sql"
INGESTION_SQL_DIR = SQL_DIR / "ingestion"
MODEL_DATASET_SQL_PATH = SQL_DIR / "datasets" / "build_model_dataset.sql"

# Raw API responses cached by core.api.
ELEXON_RAW_DIR = RAW_DIR / "elexon"
NESO_RAW_DIR = RAW_DIR / "neso"

# Model artefacts (committed; see .gitignore).
MODEL_PATH = ARTIFACTS_DIR / "ridge_drm_24h.joblib"
FEATURE_COLUMNS_PATH = ARTIFACTS_DIR / "feature_columns.json"
METRICS_PATH = ARTIFACTS_DIR / "metrics.json"

# Files written by the model and refresh pipelines, read by the dashboard/API.
MODEL_DATASET_PATH = PROCESSED_DIR / "model_dataset.csv"
FORECAST_PATH = PROCESSED_DIR / "latest_forecast.json"
STATUS_PATH = PROCESSED_DIR / "refresh_status.json"
VALIDATION_PATH = PROCESSED_DIR / "validation_predictions.csv"
TEST_PATH = PROCESSED_DIR / "test_predictions.csv"

# Scores saved by the chart design tester (dashboard/swiper.py).
SWIPER_RESULTS_PATH = PROJECT_ROOT / "results.json"
