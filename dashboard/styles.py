"""
Dashboard colours and global CSS.

Colours come from tokens/tokens.json, shared with the Flutter app. Mappings
there refer to palette names; they are resolved to hex values here.
"""

import json
from pathlib import Path

import streamlit as st

TOKENS_PATH = Path(__file__).resolve().parents[1] / "tokens" / "tokens.json"


def _load_tokens(path: Path = TOKENS_PATH) -> dict:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _resolve(mapping: dict[str, str], palette: dict[str, str]) -> dict[str, str]:
    """Replace palette names with their hex values."""
    return {key: palette[name] for key, name in mapping.items()}


_TOKENS = _load_tokens()

PALETTE: dict[str, str] = _TOKENS["palette"]
FUEL_COLOURS = _resolve(_TOKENS["fuel_colours"], PALETTE)
MODEL_COLOURS = _resolve(_TOKENS["model_colours"], PALETTE)
DEMAND_PROFILE_COLOURS = _resolve(_TOKENS["demand_profile_colours"], PALETTE)


def apply_styles() -> None:
    st.markdown(
        f"""
        <style>
            h1 {{
                letter-spacing: -0.03em;
                color: {PALETTE["forecast"]};
            }}

            h2 {{
                margin-top: 2.25rem;
                margin-bottom: 0.75rem;
                color: {PALETTE["text_primary"]};
            }}

            h3 {{
                margin-top: 1.25rem;
                color: {PALETTE["text_secondary"]};
            }}

            [data-testid="stMetricDelta"] > div:has([data-testid="stMetricDeltaIcon-Up"]) {{
                color: {PALETTE["margin_comfortable"]} !important;
            }}
            [data-testid="stMetricDelta"] > div:has([data-testid="stMetricDeltaIcon-Down"]) {{
                color: {PALETTE["margin_tight"]} !important;
            }}

            .block-container {{
                max-width: 1180px;
                padding-top: 2rem;
                padding-bottom: 4rem;
            }}

            div[data-testid="stMetric"] {{
                border: 1px solid {PALETTE["grid_border"]};
                border-radius: 12px;
                padding: 1rem;
                background: {PALETTE["card_surface"]};
            }}

            div[data-testid="stAlert"] {{
                border-radius: 10px;
            }}

            [data-testid="stCaptionContainer"] {{
                opacity: 0.78;
            }}

            .flow-header,
            .flow-row {{
                display: grid;
                grid-template-columns:
                    1fr auto auto 24px;
                align-items: center;
                gap: 12px;
            }}

            .flow-header {{
                padding: 10px 12px;
                margin-top: 8px;
                border-bottom: 1px solid {PALETTE["grid_border"]};
            }}

            .flow-header span {{
                grid-column: 2 / 5;
                text-align: right;
            }}

            .flow-row {{
                padding: 8px 12px;
                border-bottom: 1px solid {PALETTE["grid_border"]};
            }}

            .flow-name {{
                font-weight: 500;
            }}

            .flow-direction {{
                color: {PALETTE["text_secondary"]};
                font-size: 0.85rem;
            }}

            .flow-value {{
                text-align: right;
                font-variant-numeric: tabular-nums;
            }}

            .flow-arrow {{
                text-align: center;
                font-weight: 600;
                color: {PALETTE["interconnector"]};
            }}

            .data-status-banner {{
                display: flex;
                align-items: flex-start;
                gap: 10px;

                padding: 12px 14px;
                margin: 8px 0 12px 0;

                border: 1px solid {PALETTE["grid_border"]};
                border-left: 4px solid {PALETTE["delayed_text"]};
                border-radius: 10px;

                background: {PALETTE["delayed_background"]};
                color: {PALETTE["text_primary"]};
            }}

            .data-status-dot {{
                color: {PALETTE["delayed_text"]};
                line-height: 1.4;
            }}

            .data-status-content {{
                display: flex;
                flex-direction: column;
                gap: 2px;
            }}

            .data-status-title {{
                color: {PALETTE["delayed_text"]};
                font-weight: 600;
            }}

            .data-status-message {{
                color: {PALETTE["text_secondary"]};
                font-size: 0.92rem;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )