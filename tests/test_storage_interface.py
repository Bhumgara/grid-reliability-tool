"""
Tests that the GridStore interface covers every storage operation the app
uses today, so moving code onto it (and adding backends) misses nothing.
"""

import inspect
import re
import typing

from core import db, queries
from core.config import SCHEMA_PATH
from core.storage import Dataset, GridStore
from pipelines import build_dataset

# Interface methods, excluding typing.Protocol's own attributes.
METHODS = {
    name
    for name, member in vars(GridStore).items()
    if callable(member) and not name.startswith("_")
}

# Existing function -> the GridStore method that replaces it.
QUERY_LOADERS = {
    "load_recent_margin": "recent_margin",
    "load_recent_demand": "recent_demand",
    "load_recent_generation": "recent_generation",
    "load_live_generation_mix": "live_generation_mix",
    "load_live_interconnectors": "live_interconnectors",
    "load_margin_history": "margin_history",
}
MODEL_LOADERS = {
    "load_targets": "model_targets",
    "load_demand": "model_demand",
    "load_fuelhh": "model_fuel",
    "load_margin_history": "model_margin_history",
    "save_dataset_to_db": "save_model_dataset",
}


def test_every_core_db_operation_has_a_method():
    upserts = {name for name in vars(db) if name.startswith("upsert_")}

    assert upserts, "core.db has no upserts?"
    for name in upserts:
        method = name.removesuffix("_rows")
        assert method in METHODS, f"{name} has no GridStore.{method}"

    assert "initialise" in METHODS  # initialise_database
    assert {"row_count", "target_row_count"} <= METHODS  # count_*_rows


def test_every_database_loader_in_queries_has_a_method():
    # Loaders that take db_path read the database (the rest read files).
    database_loaders = {
        name
        for name, function in vars(queries).items()
        if name.startswith("load_")
        and callable(function)
        and "db_path" in inspect.signature(function).parameters
    }

    assert database_loaders == set(QUERY_LOADERS)
    assert set(QUERY_LOADERS.values()) <= METHODS


def test_every_model_input_has_a_method():
    for function, method in MODEL_LOADERS.items():
        assert hasattr(build_dataset, function), function
        assert method in METHODS, method


def test_refresh_freshness_has_a_method():
    assert "latest_times" in METHODS


def test_datasets_match_the_schema():
    tables = set(re.findall(
        r"CREATE TABLE IF NOT EXISTS\s+(\w+)",
        SCHEMA_PATH.read_text(encoding="utf-8"),
        flags=re.IGNORECASE,
    ))

    # model_dataset is created by pipelines.build_dataset, not the schema.
    assert set(typing.get_args(Dataset)) == tables | {"model_dataset"}


class CompleteStore:
    """A do-nothing store with every method."""

for _name in METHODS:
    setattr(CompleteStore, _name, lambda self, *args, **kwargs: None)


def test_a_complete_store_satisfies_the_interface():
    assert isinstance(CompleteStore(), GridStore)


def test_a_store_missing_a_method_does_not():
    class Incomplete:
        pass

    for name in METHODS - {"recent_margin"}:
        setattr(Incomplete, name, lambda self, *args, **kwargs: None)

    assert not isinstance(Incomplete(), GridStore)


def test_every_method_declares_its_return_type():
    missing = [
        name
        for name in sorted(METHODS)
        if inspect.signature(getattr(GridStore, name)).return_annotation
        is inspect.Signature.empty
    ]

    assert missing == []
