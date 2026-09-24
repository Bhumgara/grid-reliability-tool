import streamlit as st

PALETTE = {
    # Margin status
    "margin_comfortable": "#00CC66",
    "margin_watch": "#D1AC00",
    "margin_tight": "#F75C03",

    "risk_comfortable": "#CDF5DE",
    "risk_watch": "#FBF0C2",
    "risk_tight": "#FDE0CC",

    # Section-specific "observed" colours
    "margin_observed": "#5E9AD3",
    "demand_observed": "#9333EA",
    "residual_observed": "#DB2777",
    "typical_day_observed": "#0891B2",

    # Everything else unchanged from the last version
    "forecast": "#2274A5",
    "forecast_uncertainty": "#D6E9F2",
    "reference": "#7C93A0",
    "latest_profile": "#154C6E",
    "historical_iqr": "#D6E9F2",
    "direction": "#16323E",          # kept neutral — it's an arrow/sign, not tied to any one chart's series

    "movement_light": "#17A398",   # was #D6E9F2 — generation_wind teal
    "movement_dark": "#9333EA",    # was #154C6E — demand_observed purple

    "generation_gas": "#8A5A3B",
    "generation_other_fossil": "#5C3A26",
    "generation_wind": "#17A398",
    "generation_hydro": "#9CFFFA",
    "generation_solar": "#F2C94C",
    "generation_nuclear": "#2274A5",
    "generation_biomass": "#007A3D",
    "interconnector": "#7C93A0",
    "storage": "#B33F00",
    "other": "#D6E9F2",

    "background": "#FFFFFF",
    "card_surface": "#F7FAFC",
    "grid_border": "#D6E9F2",
    "text_primary": "#16323E",
    "text_secondary": "#7C93A0",
    "delayed_text": "#8F7500",
    "delayed_background": "#FBF0C2",
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
    "Ridge": PALETTE["forecast"],            # #2274A5 — unchanged
    "Persistence": PALETTE["residual_observed"],  # #DB2777 — was PALETTE["reference"], removes the grey
}


DEMAND_PROFILE_COLOURS = {
    "Current profile": PALETTE["demand_observed"],   # purple — same "today's demand" as Recent grid history
    "Latest full profile": PALETTE["generation_wind"], # teal — ties to wind as the dominant generator
    "Historical median": PALETTE["reference"],         # stays neutral so it reads as the baseline, not a third competing colour
}

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