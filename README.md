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

Implementation is currently in progress. Setup and run instructions will be added once the first end-to-end data pipeline is working.

The first technical milestone is:

```text
Elexon API -> raw cache -> normalisation -> SQL
```

## Repository

Core code will be organised around:

```text
core/       API clients, configuration and shared utilities
pipelines/  ingestion and modelling-dataset pipelines
sql/        schema and reusable SQL
model/      feature engineering, baselines, training and evaluation
data/       local raw/processed development data
 tests/     automated tests and fixtures
app.py      Streamlit application
```

## Project Stage

The immediate focus is validating the Elexon De-Rated Margin data source and building the first reproducible ingestion pipeline. See the implementation plan in `docs/` for the full build sequence and scope.
