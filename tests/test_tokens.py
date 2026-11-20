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


# --- Dark palette ------------------------------------------------------------

DARK = TOKENS["palette_dark"]

# Background-style colours, exempt from the mark contrast check.
DARK_FILLS = {
    "background",
    "card_surface",
    "grid_border",
    "risk_comfortable",
    "risk_watch",
    "risk_tight",
    "forecast_uncertainty",
    "historical_iqr",
    "delayed_background",
}
DARK_TEXT = {"text_primary", "text_secondary"}


def _luminance(hex_colour: str) -> float:
    channels = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [
        c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        for c in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(a: str, b: str) -> float:
    """WCAG contrast ratio between two hex colours."""
    high, low = sorted([_luminance(a), _luminance(b)], reverse=True)
    return (high + 0.05) / (low + 0.05)


def test_dark_palette_has_same_names_as_light():
    assert list(DARK) == list(TOKENS["palette"])


def test_dark_palette_values_are_hex_colours():
    for name, value in DARK.items():
        assert re.fullmatch(r"#[0-9A-F]{6}", value), name


@pytest.mark.parametrize("surface", ["background", "card_surface"])
def test_dark_text_meets_wcag_aa(surface):
    for name in DARK_TEXT:
        assert _contrast(DARK[name], DARK[surface]) >= 4.5, name

    assert _contrast(DARK["delayed_text"], DARK["delayed_background"]) >= 4.5


@pytest.mark.parametrize("surface", ["background", "card_surface"])
def test_dark_chart_marks_meet_non_text_contrast(surface):
    marks = set(DARK) - DARK_FILLS - DARK_TEXT - {"delayed_text"}

    for name in marks:
        assert _contrast(DARK[name], DARK[surface]) >= 3.0, name
