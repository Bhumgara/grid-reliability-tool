# TODO: Flutter front-end migration

Move the dashboard from Streamlit to a FastAPI backend and a Flutter client.
One Flutter codebase builds every platform (Android, iOS, Windows, macOS,
Linux, web), with no embedded JS/CSS. The backend is containerised and split
into swappable parts so it can move between hosts.

## How to use this list

- Each `##` heading under a phase is **one branch**. The suggested branch name
  is in backticks.
- Each checkbox is **one commit**. Commits are small and leave the app working.
- **Needs:** lists the branches that must be merged first. Branches with no
  overlapping dependencies can run in parallel.
- Streamlit keeps working until Phase 8, so every branch can be checked against
  the current dashboard.

## Decisions

- [x] **Chart library:** fl_chart. MIT is permissive: the app can be commercial or closed source, provided the licence notices ship with it (Flutter's licence page collects them). Every dependency must use a permissive licence (MIT, BSD, Apache-2.0); no GPL or AGPL. Checked in 7.2.
- [x] **Live updates:** cheap polling. The client polls `GET /api/status`, and fetches data only when the last refresh time is newer than its own copy. Data endpoints send `ETag` headers, so unchanged data returns `304 Not Modified`. Built in 2.4 and 4.2.
- [x] **Hosting:** local for development, then Google Cloud (Compute Engine VMs, Cloud Run, BigQuery or similar services), then on-premise. The backend is containerised from Phase 2 (2.5). API, worker and storage are separate, swappable parts (2.3, 2.6). The device keeps the last data it fetched, so the app works offline (4.1).
- [x] **Platforms and embedded JS/CSS:** one Flutter codebase builds the apps and the website (Chrome and Firefox), with small per-platform adapters only where needed. There is no embedded JS/CSS, so no platform needs a web view. Showpiece visuals are drawn in Flutter (7.1).
- [x] **Swiper:** retire `dashboard/swiper.py` in 8.1.

## Open decisions

- [ ] First storage backend after SQLite: Postgres (e.g. Cloud SQL) for the live data, BigQuery for history and analytics, or both. Needed when the backend outgrows a single VM with a disk; 2.6 adds the seam, not the switch.

---

## Phase 0: Groundwork

### 0.1 `chore/repo-groundwork`

- [x] Fill in `requirements.txt` with the current dependencies (it is empty), with versions pinned
- [x] Fix `.gitignore` so the Python `lib/` rule does not hide Flutter's `app/lib/` (anchor it as `/lib/`)
- [x] Add Flutter and Dart ignores (`app/build/`, `.dart_tool/`, `*.iml`, platform build outputs)
- [x] Add a `tests/` package with pytest config and an empty smoke test
- [x] Add a small fixture SQLite database builder for tests (`tests/fixtures/`)

---

## Phase 1: Separate the data logic from Streamlit

### 1.1 `refactor/data-loaders-core`

Needs: 0.1

- [x] Add `core/queries.py` containing the SQL loaders from `dashboard/data.py`, with no Streamlit imports
- [x] Make `dashboard/data.py` thin `st.cache_data` wrappers around `core/queries.py`
- [x] Move the file-based loaders (metrics, forecast, refresh status, validation CSV) into `core/queries.py`
- [x] Move `calculate_margin_percentile` and `describe_margin_percentile` from `components.py` into `core/`
- [x] Add tests for each loader against the fixture database

### 1.2 `refactor/chart-data-transforms`

Needs: 1.1. Pull the pandas data preparation out of each live chart builder in
`dashboard/graphs.py` into `core/views/`. Altair keeps only the drawing.

- [x] Forecast: margin history in GW plus the forecast point (`build_forecast_graphs`)
- [x] DRM change bridge steps (`build_drm_change_bridge`)
- [x] Demand settlement bars, with an `estimated` flag on filled-in periods (`build_demand_settlement_bars`)
- [x] Typical-day profile: current, latest full day, median, IQR (`build_typical_day_demand_dashboard`)
- [x] Live generation snapshot and doughnut shares (`_latest_generation_snapshot`, `build_generation_doughnut_dashboard`)
- [x] Generation change (`build_generation_change_dashboard`)
- [x] Interconnector grouping (`INTERCONNECTOR_GROUPS`, `render_interconnector_list`)
- [x] Validation residuals and model vs persistence (`build_validation_graphs`, `build_model_vs_persistence_vertical`)
- [x] Add tests for each view function, and check that the Streamlit charts look unchanged

### 1.3 `chore/design-tokens`

Needs: 0.1. Can run in parallel with 1.1 and 1.2.

- [x] Export `PALETTE`, `FUEL_COLOURS`, `MODEL_COLOURS` and `DEMAND_PROFILE_COLOURS` to `tokens/tokens.json`
- [x] Make `dashboard/styles.py` load its colours from `tokens.json`
- [x] Add dark-mode values for each token

### 1.4 `fix/view-error-handling`

Needs: 1.2. Behaviour fixes found while extracting the views. Each view should
raise `ValueError` for unusable data, and the dashboard should show a message
instead of breaking the page.

- [x] Raise the intended `ValueError` (not `KeyError`) in `generation_change_view` when no fuel has values at both snapshots, with a test
- [x] Show an info message instead of breaking the page when the generation change chart can't be built (`render_generation_section`)
- [x] Raise `ValueError` (not `KeyError`) in `model_vs_persistence_view` when no complete rows remain, with a test
- [x] Show an info message instead of breaking the page when the generation doughnut can't be built (`render_generation_section`)

### 1.5 `chore/post-merge-cleanup`

Needs: the merge of `main` into `flutter-front-end-migration`. Small fixes for
loose ends that merge left behind.

- [x] Record the post-merge follow-ups in `TODO.md`
- [x] Remove the unused `from xgboost import XGBRegressor` in `model/train.py` (xgboost is no longer a dependency)
- [x] Add `.gitignore` exceptions for the committed `artifacts/` files (`metrics.json`, `feature_columns.json`, `ridge_drm_24h.joblib`)
- [x] Fix the "every 15 minutes" comment in `app.py` (the refresh check now runs every 150 seconds)

### 1.6 `refactor/deployment-core`

Needs: 1.5. `main` added deployment code outside `core/`. Bring it in line so
the API and worker (Phase 2) can share it.

- [x] Make the `core/config.py` paths absolute from the repo root, use them in `dashboard/bootstrap.py`, and update the smoke test for `DB_PATH`
- [x] Move `ensure_deployment_data()` into `core/`, taking the bundle URL as a parameter or from `DEPLOYMENT_BUNDLE_URL`; `bootstrap.py` passes the `st.secrets` value, and the debug prints become logging. Test it with a local zip (no network)
- [x] Point the hard-coded paths in `pipelines/`, `model/`, `core/api/`, `core/db.py` and `dashboard/swiper.py` at `core/config.py`
- [x] Add one shared refresh-interval constant (currently 150 seconds) in `core/config.py`, used by `bootstrap.py`

---

## Phase 2: Backend API

### 2.1 `feature/api-skeleton`

Needs: 1.1

- [x] Add `fastapi`, `uvicorn` and `pydantic` to the requirements
- [x] Add `backend/api/main.py` with an app factory and `GET /api/health`
- [x] Configure CORS from an environment variable, and document it in `.env.example`
- [x] Add shared response models (timestamps, `EmptyState` with `state` and `message`)
- [x] Add an API test for health using `TestClient`

### 2.2 `feature/api-endpoints`

Needs: 1.2, 1.6, 2.1

- [x] `GET /api/status` (refresh status)
- [x] `GET /api/forecast/hero` (forecast, margin percentile, bridge steps)
- [x] Open the database read-only in `core/queries.py`, so a missing `grid.db` raises an error instead of creating an empty file (which would stop `ensure_deployment_data()` downloading the real one); the API returns `503` with an `unavailable` `EmptyState`
- [x] `GET /api/grid/now` (current margin, demand and generation metrics)
- [x] `GET /api/history/margin` and `/api/history/demand` (`?days=`)
- [x] `GET /api/demand/typical-day`
- [x] `GET /api/generation/live`, `/api/generation/change` and `/api/interconnectors/live`
- [x] `GET /api/model/metrics` and `/api/model/validation`
- [x] Add a server-side TTL cache matching the current 45 s and 15 s TTLs
- [x] Compress responses with `GZipMiddleware` (the validation points can reach about 1.2 MB of JSON)
- [x] Add a script that exports the OpenAPI schema to `backend/openapi.json`

### 2.3 `feature/refresh-worker`

Needs: 1.6

- [x] Add `backend/worker.py`, a standalone loop that calls `refresh_live_data()` on the shared refresh interval from `core/config.py`
- [x] Add a `--once` mode that refreshes once and exits, so a scheduler (cron, Cloud Scheduler with a Cloud Run job) can run it instead of the loop
- [x] Have the worker call `ensure_deployment_data()` before its first refresh
- [x] Have the worker record a `last_refresh_completed` timestamp the API can read
- [x] Put the Streamlit thread in `dashboard/bootstrap.py` behind an environment flag, so only one refresher runs
- [x] Document running the API and the worker in `README.md`

### 2.4 `feature/change-detection`

Needs: 2.2, 2.3. Lets clients poll cheaply (see Decisions).

- [x] Include `last_refresh_completed` in `GET /api/status`, so a client can tell whether anything changed
- [x] Send an `ETag` on each data endpoint, built from a hash of the response body (so it also changes on a model retrain or a format change, not only on a refresh), and return `304 Not Modified` when `If-None-Match` matches. Add both headers to the CORS config (`allow_headers` and `expose_headers`), or the web build can't use them
- [x] Add `Cache-Control` headers: `no-cache` on success (always revalidate with the `ETag`; a `max-age` would let the browser answer a post-refresh refetch with old data), `no-store` on errors. The refresh interval sets the client's polling pace instead (4.2)
- [x] Add tests: `304` while the data is unchanged, `200` with a new `ETag` after the refresh timestamp changes

### 2.5 `chore/containerise`

Needs: 2.1, 2.3. One image runs the API or the worker, so every host (local,
Compute Engine, Cloud Run, on-premise) runs the same thing.

- [x] Make the data folder configurable with a `GRID_DATA_DIR` environment variable in `core/config.py` (default `<repo>/data`), with a test
- [x] Add a `Dockerfile` and `.dockerignore`; the API and the worker are separate commands on the same image
- [x] Add a `compose.yaml` for local development: API, worker and a shared data volume
- [x] Document building and running the containers in `README.md`

### 2.6 `refactor/storage-backends`

Needs: 2.2, 2.3. Puts storage behind interfaces so SQLite can later be swapped
for Postgres, BigQuery or object storage without touching the API or worker.

- [x] Add a `GridStore` interface in `core/storage/` for the reads in `core/queries.py` and the writes in `pipelines/`
- [x] Add the SQLite implementation (`SQLiteStore`), with tests that it matches the current code
- [x] Route `core/queries.py` through it
- [ ] Route `pipelines/` and `core/db.py` through it
- [ ] Put the JSON and CSV outputs (forecast, refresh status, validation) behind a file-store interface: a local folder now, object storage (e.g. Cloud Storage) later
- [ ] Choose the backends with environment variables (default SQLite and the local folder)
- [ ] Add contract tests that every backend must pass, run against SQLite

---

## Phase 3: Flutter shell

### 3.1 `feature/flutter-scaffold`

Needs: 0.1

- [ ] Run `flutter create app` for android, ios, web, windows, macos and linux
- [ ] Add lint rules (`flutter_lints` or `very_good_analysis`) and an `analysis_options.yaml`
- [ ] Set up the folder layout: `lib/{theme,api,state,features,widgets}/`
- [ ] Add placeholder pages: Now, Forecast, Generation, Model

### 3.2 `feature/flutter-theme`

Needs: 1.3, 3.1

- [ ] Load `tokens.json` (copied as an asset, or generated into Dart)
- [ ] Add a `GridColors` `ThemeExtension` (margin status, fuels, models, demand profiles)
- [ ] Build light and dark `ThemeData`: typography, card and surface styles
- [ ] Add a theme-mode toggle (system, light, dark)

### 3.3 `feature/flutter-adaptive-shell`

Needs: 3.1

- [ ] Add a breakpoint helper (compact, medium, expanded)
- [ ] Show a bottom `NavigationBar` on compact screens and a `NavigationRail` on medium and expanded
- [ ] Add a responsive dashboard grid that reflows the section cards by width
- [ ] Add routing with deep links to each page, using `go_router` (needed for web URLs)

---

## Phase 4: Flutter data layer and shared widgets

### 4.1 `feature/flutter-data-layer`

Needs: 2.2, 3.1

- [ ] Set the API base URL per environment with `--dart-define`
- [ ] Generate (or write) Dart models from `openapi.json`
- [ ] Add an HTTP client with error handling, timeouts and empty-state mapping
- [ ] Add Riverpod providers, one per endpoint
- [ ] Store the last successful response for each endpoint on the device, using storage that works on every platform including web
- [ ] Show the stored data with its "last updated" time when the device is offline or the API fails
- [ ] Add pull-to-refresh and a manual refresh action

### 4.2 `feature/flutter-live-updates`

Needs: 2.4, 4.1

- [ ] Poll `GET /api/status` on a set interval, and refetch the data only when `last_refresh_completed` is newer than the stored copy
- [ ] Send `If-None-Match` with the stored `ETag`, and keep the stored copy on `304`
- [ ] Pause polling while the app is in the background, and check once when it resumes (app lifecycle)

### 4.3 `feature/flutter-shared-widgets`

Needs: 3.2

- [ ] `SectionCard` (title, body, caption)
- [ ] `MetricCard` (value, change, status colour)
- [ ] `StatusBanner` (data freshness, delayed or stale states)
- [ ] `EmptyState` and loading skeletons
- [ ] `ChartFrame` (chart wrapper with title, legend, caption, loading and error)

---

## Phase 5: Port the dashboard sections

Each branch needs 4.1 and 4.3. Ported in order of difficulty, easiest first.

### 5.1 `feature/ui-status-grid-now`

- [ ] Refresh status banner on the Now page
- [ ] Grid-now metric cards (margin, demand, generation, upload time)
- [ ] Layout for phone and desktop

### 5.2 `feature/ui-recent-history`

- [ ] Margin line chart
- [ ] Demand settlement bars, with faded estimated bars
- [ ] Side-by-side on desktop, stacked on phone

### 5.3 `feature/ui-forecast-hero`

- [ ] Forecast metrics, percentile and risk band colour
- [ ] DRM change bridge (floating bar chart)
- [ ] History plus forecast line with an uncertainty band
- [ ] Captions and explanation text

### 5.4 `feature/ui-demand-context`

- [ ] Typical-day chart (IQR band, median, current, latest full day)
- [ ] Empty state when there is not enough history

### 5.5 `feature/ui-generation`

- [ ] Live generation doughnut with the total in the centre
- [ ] Interconnector list
- [ ] Generation change chart (diverging bars)

### 5.6 `feature/ui-model-performance`

- [ ] Model metric cards
- [ ] Residuals chart
- [ ] Model vs persistence chart
- [ ] Parity review: compare every page against Streamlit and note the gaps

---

## Phase 6: Motion and polish

### 6.1 `feature/motion-polish`

Needs: Phase 5

- [ ] Animated number counters for metric cards
- [ ] Chart entry and update animations
- [ ] Page transitions and Hero transitions between overview and detail
- [ ] Accessibility pass: semantics labels, contrast, text scaling

---

## Phase 7: Showpiece visuals and packaging

### 7.1 `feature/grid-flow-visual`

Needs: Phase 5. Drawn in Flutter (`CustomPainter` and animations), so it runs
the same on every platform with no web view.

- [ ] Grid-flow map: generation, demand and interconnector flows, using the live endpoints
- [ ] Animate flow direction and size from the latest data
- [ ] Simplified layout for compact screens, and a reduced-motion option

### 7.2 `chore/packaging`

Needs: Phase 5, 2.5

- [ ] App name, icons and splash screens (`flutter_launcher_icons`, `flutter_native_splash`)
- [ ] Deploy the backend container to a Google Cloud Compute Engine VM with a persistent disk for the data
- [ ] Web build, static hosting config, and a plain loading screen in `app/web/index.html`
- [ ] Android release build (signing, Play Store metadata)
- [ ] iOS release build (bundle ID, signing, App Store metadata)
- [ ] Windows MSIX packaging
- [ ] macOS release build (signing, notarisation)
- [ ] Linux packaging (Flatpak or AppImage)
- [ ] Dependency licence check (Python and Dart): permissive licences only, notices included
- [ ] CI workflow: Python tests, `flutter analyze`, `flutter test`, web tests in Chrome and Firefox, platform builds

---

## Phase 8: Retire Streamlit

### 8.1 `chore/retire-streamlit`

Needs: 5.6 parity review signed off

- [ ] Remove `app.py`, `dashboard/components.py` and `dashboard/bootstrap.py`
- [ ] Remove `dashboard/swiper.py`, `SWIPER_RESULTS_PATH` in `core/config.py`, and the `results.json` rules in `.gitignore`
- [ ] Remove the rest of `dashboard/` (`graphs.py` with its live, swiper and unused builders; `data.py`; `styles.py`). `tokens/tokens.json` stays for Flutter
- [ ] Remove `streamlit` and `altair` from the requirements
- [ ] Update `README.md`, `docs/` and `CHANGELOG.md` for the new architecture
