import streamlit as st

PALETTE = {
    # Margin status
    "margin_comfortable": "#15803D",
    "margin_watch": "#D97706",
    "margin_tight": "#DC2626",

    # Margin risk bands
    "risk_comfortable": "#DCFCE7",
    "risk_watch": "#FEF3C7",
    "risk_tight": "#FEE2E2",

    # Core semantic series
    "observed": "#1E293B",
    "forecast": "#2563EB",
    "forecast_uncertainty": "#DBE6FD",
    "reference": "#94A3B8",
    "latest_profile": "#64748B",
    "historical_iqr": "#E2E8F0",
    "direction": "#1E293B",

    # Movement magnitude
    "movement_light": "#CBD5E1",
    "movement_dark": "#334155",

    # Generation
    "generation_gas": "#9A6B3F",
    "generation_other_fossil": "#5C4033",
    "generation_wind": "#0F8B8D",
    "generation_hydro": "#5EC4C0",
    "generation_solar": "#EAD34A",
    "generation_nuclear": "#7C3AED",
    "generation_biomass": "#7A8B3A",
    "interconnector": "#CDB98C",
    "storage": "#B4C0D0",
    "other": "#CBD5E1",

    # UI
    "background": "#FFFFFF",
    "card_surface": "#F8FAFC",
    "grid_border": "#E2E8F0",
    "text_primary": "#0F172A",
    "text_secondary": "#64748B",
    "delayed_text": "#475569",
    "delayed_background": "#F1F5F9",
}


FUEL_COLOURS = {
    "CCGT": PALETTE["generation_gas"],
    "OCGT": PALETTE["generation_gas"],

    "COAL": PALETTE["generation_other_fossil"],
    "OIL": PALETTE["generation_other_fossil"],

    "WIND": PALETTE["generation_wind"],
    "NPSHYD": PALETTE["generation_hydro"],
    "SOLAR": PALETTE["generation_solar"],
    "NUCLEAR": PALETTE["generation_nuclear"],
    "BIOMASS": PALETTE["generation_biomass"],

    "PS": PALETTE["storage"],
    "OTHER": PALETTE["other"],

    "INTELEC": PALETTE["interconnector"],
    "INTEW": PALETTE["interconnector"],
    "INTFR": PALETTE["interconnector"],
    "INTGRNL": PALETTE["interconnector"],
    "INTIFA2": PALETTE["interconnector"],
    "INTIRL": PALETTE["interconnector"],
    "INTNED": PALETTE["interconnector"],
    "INTNEM": PALETTE["interconnector"],
    "INTNSL": PALETTE["interconnector"],
    "INTVKL": PALETTE["interconnector"],
}


MODEL_COLOURS = {
    "Ridge": PALETTE["forecast"],
    "Persistence": PALETTE["reference"],
}


DEMAND_PROFILE_COLOURS = {
    "Current profile": PALETTE["observed"],
    "Latest full profile": PALETTE["latest_profile"],
    "Historical median": PALETTE["reference"],
}

def apply_styles() -> None:
    st.markdown(
        f"""
        <style>
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

            h1 {{
                letter-spacing: -0.03em;
            }}

            h2 {{
                margin-top: 2.25rem;
                margin-bottom: 0.75rem;
            }}

            h3 {{
                margin-top: 1.25rem;
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