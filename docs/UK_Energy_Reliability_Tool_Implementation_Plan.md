# UK Energy Reliability Tool — Implementation Plan

> **Source of truth:** this plan is based on the shortened `UK_Energy_Grid_Tool_Proposal-ZB` proposal.  
> **Note on GenAI:** this plan was based on prior documents and the latest proposal using GenAI to flesh it out.
> **Human-in-the-loop:** core architectural decisions were made by me, GenAI was **only** used as a supporting tool.

---

## 1. Project Goal

Build a small, defensible UK energy reliability prototype that turns open grid data into a **forward-looking 24-hour supply-demand margin forecast**.

The core product should:

1. ingest and store UK grid data from NESO and Elexon;
2. present recent/current grid context in Streamlit;
3. engineer time-series features;
4. train and validate a regression model for 24-hour margin tightness;
5. compare the model against a naive baseline;
6. remain demoable if a live API is unavailable.

Everything beyond that is optional stretch scope.

### MVP definition

The MVP is complete when all of the following are true:

- national-level NESO/Elexon data can be ingested reproducibly;
- the data is stored locally and can be re-used without re-calling the APIs;
- a Streamlit dashboard can display recent grid context;
- a 24-hour margin regression can be trained on historical data;
- evaluation uses a time-ordered holdout set;
- MAE and RMSE are reported;
- model performance is shown against a naive baseline;
- the demo can run from cached/local data if a live source is unavailable.

### Stretch scope

Only add these after the MVP is stable:

- GenAI briefing;
- weather enrichment;
- regional comparison;
- shortfall/tight-margin classification;
- REPD renewable-project gap analysis;
- conversational/chatbot interface.

---

# 2. Architecture

## Repository Structure

```text
energy-reliability-tool/
├── core/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── elexon.py
│   │   ├── neso.py
│   │   └── open_meteo.py          # stretch
│   ├── config.py
│   ├── db.py
│   ├── normalise.py
│   └── time_utils.py
│
├── pipelines/
│   ├── ingest.py
│   └── build_dataset.py
|
├── sql/
│   ├── schema.sql
│   ├── ingestion/
│   │   ├── upsert_demand.sql
│   │   ├── upsert_generation.sql
│   │   └── upsert_margin.sql
│   └── datasets/
│       └── build_model_dataset.sql
│
├── model/
│   ├── features.py
│   ├── baselines.py
│   ├── train.py
│   └── evaluate.py
│
├── features/
│   ├── briefing.py                # stretch
│   ├── regional.py                # stretch
│   └── repd_analysis.py           # stretch
│
├── data/
│   ├── raw/
│   │   ├── elexon/
│   │   └── neso/
│   ├── processed/
│   └── grid.db
│
├── tests/
│   ├── fixtures/
│   ├── test_api_normalisation.py
│   ├── test_time_alignment.py
│   ├── test_features.py
│   └── test_pipeline.py
│
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
└── CHANGELOG.md
```

## Architectural Rule

Keep external APIs behind small adapters:

```text
API
 ↓
fetch
 ↓
validate
 ↓
normalise
 ↓
cache raw response
 ↓
store clean records
 ↓
build modelling dataset
```

The API clients should **not** contain modelling or Streamlit logic.

The model should consume your own stable dataset schema rather than raw NESO/Elexon response shapes.

---

# 3. API Handling

## `core/api/base.py`

Create a minimal shared HTTP client responsible for:

- a reusable `requests.Session`;
- explicit connect/read timeouts;
- retries for temporary `429`/`5xx` errors;
- `raise_for_status()`;
- JSON parsing;
- consistent API exceptions.

Keep it synchronous. The expected data volume does not justify async complexity during a short capstone build.

Suggested exception hierarchy:

```python
class ApiError(RuntimeError):
    pass

class ApiResponseError(ApiError):
    pass

class SchemaError(ApiError):
    pass
```

## `core/api/elexon.py`

Responsibilities:

- fetch the Elexon datasets selected for the MVP;
- pass query parameters cleanly;
- perform basic response-shape validation;
- return provider-shaped Python objects only.

Do **not**:

- write directly to SQL;
- engineer model features;
- calculate dashboard metrics;
- call Streamlit.

Initial methods should be kept narrow, for example:

```python
fetch_demand(...)
fetch_generation(...)
fetch_margin_data(...)
```

The exact datasets/endpoints should be frozen only after the historical target for margin tightness has been defined.

## `core/api/neso.py`

Responsibilities:

- fetch national/relevant NESO data;
- handle known response quirks;
- validate required fields;
- return provider-shaped data for normalisation.

Regional handling should remain optional until the regional-demand question is resolved.

If regional Carbon Intensity data is later used, explicitly distinguish the 14 operational regions from the national/country aggregate rollups.

## `core/api/open_meteo.py`

Do not build this during the first vertical slice.

Add it only after:

- the margin target is fixed;
- the baseline works;
- the first regression model trains;
- the holdout evaluation runs end-to-end.

Weather should be an experiment that tries to improve the model, not a dependency of the MVP.

---

# 4. Raw Data and Caching

Every external response used during development should be cacheable locally.

Example:

```text
data/raw/
├── elexon/
│   ├── demand_2026-09-17.json
│   ├── generation_2026-09-17.json
│   └── margin_2026-09-17.json
└── neso/
    └── carbon_intensity_2026-09-17.json
```

Benefits:

- avoids repeatedly hitting APIs during development;
- creates reproducible test fixtures;
- preserves the exact source response for debugging;
- allows the model to be rebuilt offline;
- provides a demo fallback when APIs are unavailable.

Each ingestion run should record:

```text
source
dataset
requested_from
requested_to
fetched_at_utc
status
rows_received
cache_path
error_message
```

---

# 5. Time Handling

Time alignment is one of the project's highest-risk areas.

## Canonical rule

Store internal timestamps in **UTC**.

Convert to `Europe/London` only for presentation.

Where available, preserve both:

```text
event_time_utc
published_at_utc
```

This matters because a forecasting model must not use information published after the point at which the prediction is supposedly made.

## Required tests

Write explicit tests for:

- half-hour settlement alignment;
- hourly-to-half-hour alignment if weather is added;
- missing settlement periods;
- duplicate timestamps;
- March daylight-saving transition;
- October daylight-saving transition;
- records published after the forecast origin.

---

# 6. Database Design

Use SQL for the capstone.

Keep source tables separate from the final modelling table so the modelling dataset can be rebuilt without another API call.

A simple first schema:

## `ingestion_runs`

```text
id
source
dataset
requested_from
requested_to
fetched_at_utc
status
rows_received
cache_path
error_message
```

## Source tables

Exact fields should follow the selected APIs, but likely separate tables such as:

```text
elexon_demand
elexon_generation
elexon_margin
neso_grid_context
weather              # stretch
```

Each record should include:

```text
event_time_utc
published_at_utc     # nullable if unavailable
source
```

plus source-specific fields.

## `model_features`

This should be generated from the source tables rather than populated directly by API code.

Example conceptual shape:

```text
forecast_origin_utc
target_time_utc
target_margin
demand_lag_1
demand_lag_48
generation_lag_1
generation_lag_48
margin_lag_1
margin_lag_48
rolling_demand_24h
rolling_generation_24h
hour_sin
hour_cos
day_of_week_sin
day_of_week_cos
...
```

Do not freeze the complete feature list until the actual source data has been inspected.

---

# 7. Critical Day-1 Decision: Define the Prediction Target

Before model development, write down exactly what the regression target means.

The proposal defines the task as:

> predicting continuous supply-demand margin tightness 24 hours ahead.

The implementation still needs a precise historical target definition.

Document:

```text
Target name:
Unit:
Source dataset:
Exact field/formula:
Forecast horizon:
Data publication timing:
Why it represents margin tightness:
```

Do not start serious feature engineering until this is fixed.

This prevents:

- target leakage;
- accidentally predicting a value derived from a future forecast;
- mixing demand forecasts with realised demand;
- presenting an ambiguous "reliability" score that cannot be defended.

---

# 8. Data Pipeline

## Pipeline 1 — Ingestion

Command:

```bash
python -m pipelines.ingest
```

Responsibilities:

1. call selected API adapters;
2. write raw responses to `data/raw/`;
3. normalise the data;
4. upsert records into SQL;
5. record the ingestion run;
6. continue gracefully if one non-essential source fails.

MVP behaviour:

- Elexon failure should be surfaced clearly because it may block the margin model;
- NESO context failure should not corrupt existing stored data;
- previous cached data should remain usable.

## Pipeline 2 — Build Modelling Dataset

Command:

```bash
python -m pipelines.build_dataset
```

Responsibilities:

1. load clean source tables from SQL;
2. align timestamps;
3. remove/flag invalid or duplicate records;
4. build lagged features;
5. build rolling features;
6. build cyclical time features;
7. construct the target;
8. enforce no-future-information rules;
9. write the finished dataset to `data/processed/` and/or `model_features`.

Keep this deterministic.

The same source tables should always produce the same modelling dataset.

---

# 9. Modelling Plan

## Baselines first

Before fitting ML, implement at least one naive forecast.

Preferred baselines:

```text
Baseline A:
same settlement period yesterday

Baseline B:
same settlement period one week ago
```

At least one baseline must be usable for the final presentation.

## First ML model

Start with a straightforward scikit-learn regression model.

Reasonable candidates:

- `RandomForestRegressor`;
- `GradientBoostingRegressor`;
- a simple linear model as a sanity check.

Do not spend the build window on exhaustive model selection.

The project is demonstrating a defensible prediction pipeline, not leaderboard optimisation.

## Validation

Never randomly split a time series.

Use:

```text
earlier period -> training
later period   -> validation/test
```

Keep the final holdout untouched during feature/model iteration where practical.

Metrics:

```text
MAE
RMSE
```

Report the exact same metrics for:

```text
naive baseline
ML model
```

## Success criterion

The desirable result is that the regression model beats the naive baseline on later unseen data.

If it does not, do not hide this.

A well-explained negative result is preferable to leakage or an invalid evaluation.

---

# 10. Feature Engineering

Start small.

## Core candidates

Time features:

```text
hour of day
day of week
weekend flag
cyclical hour encoding
cyclical weekday encoding
```

Lagged variables:

```text
t-1
t-2
t-48
t-336
```

depending on the underlying half-hourly series.

Rolling features:

```text
rolling mean
rolling min
rolling max
rolling standard deviation
```

Potential source variables:

```text
demand
generation
previous margin
generation mix/context
settlement price
```

Weather features are stretch.

Do not introduce a feature unless you can answer:

> Would this value genuinely have been available at the forecast origin?

---

# 11. Streamlit Application

The dashboard should read local/processed data rather than making API calls during page rendering.

Basic architecture:

```text
ingestion/model pipeline
        ↓
SQL + saved model/results
        ↓
Streamlit
```

## MVP dashboard

A single-page application is sufficient.

Suggested sections:

### Current / recent grid context

- recent demand;
- recent generation;
- margin history;
- optional carbon/generation-mix context.

### 24-hour forecast

- target timestamp;
- predicted margin;
- historical context;
- simple risk/tightness presentation.

### Model validation

- MAE;
- RMSE;
- naive baseline metrics;
- forecast-vs-actual holdout chart.

### Data status

Show:

```text
Last successful update:
Data source:
Cached/live status:
```

This makes graceful fallback visible rather than silently serving stale data.

Do not build a multi-page UI unless the single page becomes genuinely crowded.

---

# 12. GenAI Briefing — Stretch

Add only after the forecasting pipeline and dashboard work.

The LLM should receive structured facts only.

Conceptual input:

```json
{
  "forecast_window": "...",
  "minimum_predicted_margin": 0,
  "time_of_minimum_margin": "...",
  "baseline_prediction": 0,
  "recent_demand": 0,
  "recent_generation": 0
}
```

The exact fields should come from your finished model output.

System prompt requirements:

- plain English;
- concise;
- non-alarmist;
- use only supplied values;
- do not invent numbers;
- distinguish observed facts from model predictions;
- do not claim certainty.

Testing:

- manually review at least 5–10 briefings;
- verify every stated number against the payload;
- preserve example good/bad outputs for the presentation.

No RAG, tool-calling or memory is required.

---

# 13. Regional Forecasting — Stretch

Do not let regional work block the national model.

Only proceed if:

- regional demand exists at suitable granularity;
- region mappings are defensible;
- timestamps align reliably;
- national MVP is already working.

If regional demand remains unsuitable:

```text
National forecast = MVP
Regional context/comparison = optional visual analysis
```

Do not fabricate regional demand from national data merely to retain the original concept.

---

# 14. Shortfall / Tight-Margin Classification — Stretch

A true shortfall classifier is not core scope.

If classification is attempted, frame it around a defined historically tight-margin threshold/event rather than literal demand exceeding supply.

Before building it:

- define the positive class;
- count positive examples;
- assess class imbalance;
- establish whether there is enough data to evaluate precision/recall meaningfully.

If there are too few positives, skip it.

---

# 15. REPD Gap Analysis — Stretch

Only begin after the margin model and GenAI briefing are stable.

Possible flow:

```text
predicted tight-margin periods
        +
planned renewable projects
        ↓
structured comparison
        ↓
GenAI explanation
```

Keep the output explicitly analytical rather than claiming a project would definitively solve a reliability problem.

This feature should never be required for the final demo.

---

# 16. Testing Strategy

Testing should focus on the parts most likely to silently produce wrong results.

## Unit tests

Prioritise:

```text
API response validation
normalisation
timestamp conversion
settlement alignment
lag construction
rolling feature construction
target construction
no-future-data checks
baseline prediction
```

## Integration test

Use cached fixtures, not live APIs.

A single integration test should prove:

```text
fixture
  ↓
normalise
  ↓
SQL
  ↓
build_dataset
  ↓
feature matrix / target
```

Do not make CI dependent on NESO/Elexon availability.

## Manual demo checks

Before presentation:

- API unavailable;
- missing rows;
- stale cached data;
- empty date range;
- duplicate records;
- model file missing;
- malformed API response;
- GenAI unavailable;
- Streamlit restart.

---

# 17. Git / GitHub Strategy

Use short-lived branches around real milestones rather than one branch for every possible feature.

Suggested branches:

```text
feature/data-pipeline
feature/dashboard
feature/forecast-model
feature/genai-briefing        # stretch
feature/regional-analysis     # stretch
```

Suggested releases:

```text
v0.1.0  data pipeline works
v0.2.0  dashboard works
v0.3.0  baseline + regression works
v0.4.0  validated MVP
v0.5.0  GenAI briefing (if completed)
v1.0.0  presentation-ready build
```

CI should run:

```bash
pip install -r requirements.txt
pytest -q
python -m py_compile app.py core/**/*.py pipelines/*.py model/*.py
```

Live API tests should not run in normal CI.

---

# 18. Seven-Day Build Plan

The course constraint is approximately five days of technical building, so the final two days should not be treated as spare engineering capacity.

## Day 1 — Data and target definition

### Goals

- scaffold repository;
- create SQL database;
- implement shared API client;
- implement first Elexon adapter;
- fetch and cache a real historical response;
- define the exact margin target;
- document timestamp/publication semantics.

### Exit criteria

By the end of Day 1:

```text
API -> cache -> normalise -> SQL
```

works for at least one core Elexon dataset.

The target definition is written in the README.

---

## Day 2 — Complete the core data pipeline + simple dashboard

### Goals

- add required Elexon/NESO data;
- finish normalisation;
- align half-hourly timestamps;
- create processed/canonical dataset;
- implement first Streamlit charts;
- add cached-data fallback.

### Exit criteria

The application can show real recent/historical data without re-querying the APIs.

At this point you already have a working data product even if modelling goes badly.

---

## Day 3 — Baseline + first regression

### Goals

- implement target construction;
- create lag/rolling/cyclical features;
- build naive baseline;
- create time-based train/test split;
- train first regression;
- calculate MAE/RMSE;
- produce forecast-vs-actual validation plot.

### Exit criteria

```text
historical data
     ↓
features
     ↓
baseline + model
     ↓
holdout MAE/RMSE
```

runs end-to-end.

This is the most important technical milestone.

---

## Day 4 — Improve and validate the forecasting pipeline

### Goals

- inspect errors;
- fix leakage;
- refine feature set;
- test one or two model alternatives only if justified;
- save final model/result artefacts;
- integrate forecast into Streamlit;
- add validation/baseline section to dashboard.

### Exit criteria

The complete MVP works from local data.

Freeze the fundamental architecture at the end of this day.

---

## Day 5 — Product integration and robustness

### Goals

- polish dashboard;
- verify fresh ingestion;
- verify cached/offline mode;
- improve model presentation;
- complete tests;
- write README methodology;
- capture final benchmark numbers.

### Stretch only if core is stable

Choose **one**:

1. GenAI briefing;
2. weather enrichment;
3. regional comparison.

Do not start all three.

### Exit criteria

A presentation-ready MVP exists by the end of Day 5.

---

## Day 6 — Stretch or presentation work

Default activity:

- README;
- architecture diagram;
- methodology write-up;
- screenshots;
- demo script;
- failure/fallback rehearsal.

If and only if the MVP is comfortably stable, complete one small stretch feature.

No major architecture changes.

---

## Day 7 — Presentation and rehearsal

No new features.

Tasks:

- build/finalise slide deck;
- rehearse demo;
- test clean environment;
- test cached fallback;
- confirm attribution/licensing text;
- tag `v1.0.0`;
- final README/CHANGELOG proofread.

---

# 19. Decision Checkpoints

## Checkpoint A — after first Elexon historical pull

Ask:

> Can I obtain enough historical data, reliably enough, to construct the intended target?

If no, resolve this before touching weather/GenAI.

## Checkpoint B — after target construction

Ask:

> Can I explain exactly what one target value means and when it would have been knowable?

If no, do not train the model yet.

## Checkpoint C — after baseline

Ask:

> Does the baseline behave sensibly?

If no, investigate the dataset before adding ML complexity.

## Checkpoint D — after first regression

Ask:

> Does the model show any improvement over the naive baseline on later unseen data?

If no, spend time on data/features/evaluation before stretch work.

## Checkpoint E — end of Day 5

Ask:

> Would I be comfortable demonstrating the project tomorrow if every stretch feature disappeared?

The answer must be yes.

---

# 20. Risk Register

| Risk | Effect | Mitigation |
|---|---|---|
| API schema changes | ingestion breaks | validate required fields; retain cached responses |
| API downtime | demo failure | local SQL + cached demo data |
| Timestamp mismatch | silent bad joins | central UTC normalisation + alignment tests |
| Daylight-saving issues | duplicated/missing periods | dedicated DST tests |
| Target leakage | unrealistic model result | publication timestamps + strict chronological features |
| Weak model | cannot claim predictive improvement | compare honestly against naive baseline; explain result |
| Regional demand unavailable | regional concept blocked | national MVP; regional remains stretch |
| Weather integration consumes time | delays model | add only after baseline regression works |
| GenAI hallucinates figures | misleading briefing | structured inputs + strict prompt + manual checks |
| Stretch scope expands | unfinished capstone | freeze MVP first; one stretch feature at a time |

---

# 21. Definition of Done

## MVP

The project is done when:

- [ ] Elexon/NESO historical data can be ingested;
- [ ] raw API responses can be cached;
- [ ] clean records are persisted in SQL;
- [ ] timestamps are consistently aligned;
- [ ] the margin target is explicitly defined;
- [ ] a deterministic modelling dataset can be rebuilt;
- [ ] at least one naive baseline exists;
- [ ] a regression model is trained;
- [ ] evaluation uses later unseen data;
- [ ] MAE and RMSE are reported for baseline and model;
- [ ] Streamlit displays recent grid context;
- [ ] Streamlit displays the 24-hour forecast/model output;
- [ ] the app works from cached/local data;
- [ ] README documents methodology, assumptions and limitations;
- [ ] attribution for data sources is included.

## Stretch

- [ ] grounded GenAI briefing;
- [ ] weather feature experiment;
- [ ] regional comparison;
- [ ] tight-margin classifier;
- [ ] REPD gap analysis;
- [ ] conversational interface.

---

# 22. Build Principle

The project should always remain usable at the latest completed layer:

```text
Layer 1
Reliable energy data pipeline

Layer 2
Historical/current dashboard

Layer 3
Naive forecast baseline

Layer 4
Validated ML margin forecast        <- MVP

Layer 5
GenAI explanation                   <- stretch

Layer 6
Weather / regional / REPD analysis  <- stretch
```

Never make a higher layer a dependency of a lower one.

The strongest capstone outcome is not the version with the most APIs or features. It is the version where the data lineage, forecasting target, validation method and limitations are clear enough that another person can understand exactly what was built and why the result should be trusted.
