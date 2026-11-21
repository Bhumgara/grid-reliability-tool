# UK Grid Reliability Tool

A capstone project exploring a forward-looking view of the UK's electricity system, with a focus on forecasting grid margin tightness over the next 24 hours.

> **Current status:** Planning and target definition complete; implementation is beginning.

## Documentation

Detailed project decisions, scope, methodology, target definition, and implementation planning live in [`docs/`](./docs/).

- [Project Proposal](./docs/UK_Energy_Reliability_Tool_Proposal.md)
- [Implementation Plan](./docs/UK_Energy_Reliability_Tool_Implementation_Plan.md)
- [Prediction Target Definition](./docs/UK_Energy_Target.md)
- [Documentation / GenAI Note](./docs/README.md)

## Planned Stack

Python · SQL · pandas · scikit-learn · Streamlit

## Getting Started

Install the dependencies (Python 3.13), from the repository root:

```bash
pip install -r requirements.txt       # app, API and worker
pip install -r requirements-dev.txt   # also tests and model plots
```

The app reads its data from `data/grid.db`. If that file is missing, it is
downloaded on first run from the zip bundle at `DEPLOYMENT_BUNDLE_URL` (see
`.env.example`). The Streamlit dashboard can read the URL from the
`deployment_bundle_url` secret instead.

Run the Streamlit dashboard:

```bash
python -m streamlit run app.py
```

## Running the API and Refresh Worker

The Flutter client talks to a FastAPI backend made of two processes: the
**API**, which only reads, and the **refresh worker**, which keeps the data
and forecast up to date. Settings come from environment variables; every one
is documented in [`.env.example`](./.env.example).

### Refresh worker

```bash
python -m backend.worker          # check now, then every 150 seconds, until Ctrl+C
python -m backend.worker --once   # one check, then exit (for cron or scheduled jobs)
```

- Before its first check it downloads the deployment bundle if `data/grid.db`
  is missing. If it can't (no `DEPLOYMENT_BUNDLE_URL`, or the download fails),
  it logs why and exits with code 1.
- Each check only calls the Elexon and NESO APIs for data that is out of date.
  After each one it records the time in `data/processed/last_refresh.json`.
- `--once` exits with code 1 if the check failed, so a scheduler can flag it.
- Ctrl+C or `SIGTERM` stops it after the current check.

### API

```bash
uvicorn backend.api.main:app --reload
```

- Interactive docs: <http://127.0.0.1:8000/docs>. Health check:
  <http://127.0.0.1:8000/api/health>.
- Every endpoint is under `/api` (status, forecast, grid now, history, demand,
  generation, interconnectors and model). Responses carry a `state` field:
  `"ok"` with data, or `"unavailable"` / `"insufficient"` with a message.
- Until the worker has set up `data/grid.db`, data endpoints return `503`
  with `"state": "unavailable"`.
- Set `GRID_CORS_ORIGINS` to let a browser build call it, e.g.
  `http://localhost:5000` for `flutter run -d chrome --web-port 5000`.

### Running the dashboard alongside the worker

The dashboard starts its own refresh thread by default. Only one refresher
should run, so turn the dashboard's off while the worker runs:

```bash
# bash
GRID_DASHBOARD_REFRESH=0 python -m streamlit run app.py
```

```powershell
# PowerShell
$env:GRID_DASHBOARD_REFRESH = "0"; python -m streamlit run app.py
```

### Tests and the API schema

```bash
python -m pytest                     # all tests (needs requirements-dev.txt)
python -m backend.export_openapi     # rewrite backend/openapi.json after API changes
```

`backend/openapi.json` is committed; a test fails if it no longer matches the
API.

## Repository

Core code will be organised around:

```text
core/       API clients, configuration, data loaders and chart-ready views
pipelines/  ingestion, refresh and modelling-dataset pipelines
sql/        schema and reusable SQL
model/      feature engineering, baselines, training and evaluation
backend/    FastAPI service (api/) and the standalone refresh worker
dashboard/  Streamlit components, charts and styles
tokens/     design tokens shared by the dashboard and the Flutter app
data/       local raw/processed development data
tests/      automated tests and fixtures
app.py      Streamlit application
```

## Project Stage

The immediate focus is validating the Elexon De-Rated Margin data source and building the first reproducible ingestion pipeline. See the implementation plan in `docs/` for the full build sequence and scope.
