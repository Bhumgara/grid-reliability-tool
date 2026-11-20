"""Checks for tokens/tokens.json."""

import json
import re
from pathlib import Path

import pytest

from dashboard import styles

TOKENS = json.loads(Path("tokens/tokens.json").read_text(encoding="utf-8"))
MAPPINGS = ["fuel_colours", "model_colours", "demand_profile_colours"]


def test_palette_values_are_hex_colours():
    for name, value in TOKENS["palette"].items():
        assert re.fullmatch(r"#[0-9A-F]{6}", value), name


@pytest.mark.parametrize("mapping", MAPPINGS)
def test_mappings_reference_palette_names(mapping):
    for key, palette_name in TOKENS[mapping].items():
        assert palette_name in TOKENS["palette"], f"{mapping}[{key!r}]"


@pytest.mark.parametrize(
    ("mapping", "resolved"),
    [
        ("fuel_colours", styles.FUEL_COLOURS),
        ("model_colours", styles.MODEL_COLOURS),
        ("demand_profile_colours", styles.DEMAND_PROFILE_COLOURS),
    ],
)
def test_styles_resolve_mappings_to_hex(mapping, resolved):
    assert styles.PALETTE == TOKENS["palette"]
    assert resolved == {
        key: TOKENS["palette"][name]
        for key, name in TOKENS[mapping].items()
    }
