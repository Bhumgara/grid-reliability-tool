import streamlit as st


def apply_styles() -> None:
    st.markdown(
        """
        <style>
            .block-container {
                max-width: 1200px;
                padding-top: 2rem;
                padding-bottom: 4rem;
            }

            .forecast-card {
                border: 1px solid rgba(128, 128, 128, 0.25);
                border-radius: 14px;
                padding: 2rem 2.25rem;
                margin-top: 1rem;
                margin-bottom: 1.5rem;
                background: rgba(128, 128, 128, 0.035);
            }

            .forecast-top {
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                gap: 2rem;
            }

            .forecast-label {
                font-size: 0.78rem;
                font-weight: 700;
                letter-spacing: 0.09em;
                opacity: 0.65;
                text-transform: uppercase;
            }

            .forecast-value {
                font-size: 4rem;
                line-height: 1;
                font-weight: 700;
                margin-top: 0.6rem;
            }

            .forecast-unit {
                font-size: 1.4rem;
                font-weight: 500;
                opacity: 0.7;
            }

            .forecast-description {
                margin-top: 0.4rem;
                font-size: 1rem;
                opacity: 0.75;
            }

            .forecast-target {
                text-align: right;
                font-size: 0.95rem;
                opacity: 0.75;
                line-height: 1.6;
            }

            .margin-scale {
                position: relative;
                height: 12px;
                border-radius: 999px;
                margin-top: 1.8rem;
                background:
                    linear-gradient(
                        90deg,
                        #d9534f 0%,
                        #e6a34a 20%,
                        #d5d5d5 50%,
                        #69b86b 100%
                    );
            }

            .margin-marker {
                position: absolute;
                top: -7px;
                width: 4px;
                height: 26px;
                background: currentColor;
                border-radius: 2px;
            }

            .scale-labels {
                display: flex;
                justify-content: space-between;
                margin-top: 0.45rem;
                font-size: 0.75rem;
                opacity: 0.6;
            }

            .forecast-context {
                margin-top: 1rem;
                display: flex;
                gap: 2rem;
                flex-wrap: wrap;
                font-size: 0.9rem;
            }

            .context-label {
                opacity: 0.55;
            }

            .context-value {
                font-weight: 600;
            }

            div[data-testid="stMetric"] {
                border: 1px solid rgba(128, 128, 128, 0.18);
                border-radius: 10px;
                padding: 1rem;
            }

            h2 {
                margin-top: 2rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )