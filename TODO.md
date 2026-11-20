# TODO: Flutter front-end migration

Move the dashboard from Streamlit to a FastAPI backend and a Flutter client
(Android, iOS, Windows, Linux, web), with JS/CSS used only for optional
embedded visuals.

## How to use this list

- Each `##` heading under a phase is **one branch**. The suggested branch name
  is in backticks.
- Each checkbox is **one commit**. Commits are small and leave the app working.
- **Needs:** lists the branches that must be merged first. Branches with no
  overlapping dependencies can run in parallel.
- Streamlit keeps working until Phase 6, so every branch can be checked against
  the current dashboard.

## Open decisions

Settle these before the branch that depends on them.

- [ ] Chart library: fl_chart (MIT) by default, or Syncfusion (check licence). Needed by Phase 5.
- [ ] Live updates: server-sent events, or simple polling at first. Needed by 2.4.
- [ ] Backend hosting target (VPS, container platform, etc.). Needed by 7.2.
- [ ] Linux web view: check current package support, or go native-only on Linux. Needed by 7.1.
- [ ] Keep `dashboard/swiper.py` as an internal Streamlit tool, or retire it. Needed by 8.1.

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

- [ ] Export `PALETTE`, `FUEL_COLOURS`, `MODEL_COLOURS` and `DEMAND_PROFILE_COLOURS` to `tokens/tokens.json`
- [ ] Make `dashboard/styles.py` load its colours from `tokens.json`
- [ ] Add dark-mode values for each token

### 1.4 `fix/view-error-handling`

Needs: 1.2. Behaviour fixes found while extracting the views. Each view should
raise `ValueError` for unusable data, and the dashboard should show a message
instead of breaking the page.

- [ ] Raise the intended `ValueError` (not `KeyError`) in `generation_change_view` when no fuel has values at both snapshots, with a test
- [ ] Show an info message instead of breaking the page when the generation change chart can't be built (`render_generation_section`)
- [ ] Raise `ValueError` (not `KeyError`) in `model_vs_persistence_view` when no complete rows remain, with a test

---

## Phase 2: Backend API

### 2.1 `feature/api-skeleton`

Needs: 1.1

- [ ] Add `fastapi`, `uvicorn` and `pydantic` to the requirements
- [ ] Add `backend/api/main.py` with an app factory and `GET /api/health`
- [ ] Configure CORS from an environment variable, and document it in `.env.example`
- [ ] Add shared response models (timestamps, `EmptyState` with `state` and `message`)
- [ ] Add an API test for health using `TestClient`

### 2.2 `feature/api-endpoints`

Needs: 1.2, 2.1

- [ ] `GET /api/status` (refresh status)
- [ ] `GET /api/forecast/hero` (forecast, margin percentile, bridge steps)
- [ ] `GET /api/grid/now` (current margin, demand and generation metrics)
- [ ] `GET /api/history/margin` and `/api/history/demand` (`?days=`)
- [ ] `GET /api/demand/typical-day`
- [ ] `GET /api/generation/live`, `/api/generation/change` and `/api/interconnectors/live`
- [ ] `GET /api/model/metrics` and `/api/model/validation`
- [ ] Add a server-side TTL cache matching the current 45 s and 15 s TTLs
- [ ] Add a script that exports the OpenAPI schema to `backend/openapi.json`

### 2.3 `feature/refresh-worker`

Needs: 0.1

- [ ] Add `backend/worker.py`, a standalone loop that calls `refresh_live_data()` every 15 minutes
- [ ] Have the worker record a `last_refresh_completed` timestamp the API can read
- [ ] Put the Streamlit thread in `dashboard/bootstrap.py` behind an environment flag, so only one refresher runs
- [ ] Document running the API and the worker in `README.md`

### 2.4 `feature/live-updates`

Needs: 2.2, 2.3

- [ ] Add a `GET /api/events` stream (SSE) that sends a `data_refreshed` event when the worker finishes
- [ ] Add a test that the event fires after the refresh timestamp changes

---

## Phase 3: Flutter shell

### 3.1 `feature/flutter-scaffold`

Needs: 0.1

- [ ] Run `flutter create app` for android, ios, web, windows and linux
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
- [ ] Add pull-to-refresh and a manual refresh action

### 4.2 `feature/flutter-live-updates`

Needs: 2.4, 4.1

- [ ] Listen to `/api/events` and invalidate the matching providers
- [ ] Fall back to polling every 60 s when SSE is unavailable
- [ ] Pause updates while the app is in the background (app lifecycle)

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

## Phase 7: JS/CSS embeds and packaging

### 7.1 `feature/embedded-visuals`

Needs: Phase 5

- [ ] `EmbeddedVisual` widget with conditional imports (`HtmlElementView` on web)
- [ ] Web view implementation for Android, iOS and Windows
- [ ] Native Flutter fallback for Linux and load failures
- [ ] First showpiece: interconnector or grid-flow map (JS/CSS bundled as an asset)
- [ ] CSS loading screen in `app/web/index.html`

### 7.2 `chore/packaging`

Needs: Phase 5

- [ ] App name, icons and splash screens (`flutter_launcher_icons`, `flutter_native_splash`)
- [ ] Backend `Dockerfile` for the API and worker, plus a deployment config
- [ ] Web build and static hosting config
- [ ] Android release build (signing, Play Store metadata)
- [ ] iOS release build (bundle ID, signing, App Store metadata)
- [ ] Windows MSIX packaging
- [ ] Linux packaging (Flatpak or AppImage)
- [ ] CI workflow: Python tests, `flutter analyze`, `flutter test`, platform builds

---

## Phase 8: Retire Streamlit

### 8.1 `chore/retire-streamlit`

Needs: 5.6 parity review signed off

- [ ] Remove `app.py`, `dashboard/components.py` and `dashboard/bootstrap.py`
- [ ] Remove the live Altair builders from `dashboard/graphs.py` (keep the swiper builders if swiper stays)
- [ ] Remove the unused builders (`build_concept_graphs`, `build_confidence_fan_graph`, `_fuel_scale`)
- [ ] Remove `streamlit` and `altair` from the requirements, if swiper is retired
- [ ] Update `README.md`, `docs/` and `CHANGELOG.md` for the new architecture
