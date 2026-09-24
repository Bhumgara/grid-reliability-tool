import streamlit as st


def apply_styles() -> None:
    st.markdown(
        """
        <style>
            .block-container {
                max-width: 1180px;
                padding-top: 2rem;
                padding-bottom: 4rem;
            }

            div[data-testid="stMetric"] {
                border: 1px solid rgba(128, 128, 128, 0.20);
                border-radius: 12px;
                padding: 1rem;
                background: rgba(128, 128, 128, 0.025);
            }

            h1 {
                letter-spacing: -0.03em;
            }

            h2 {
                margin-top: 2.25rem;
                margin-bottom: 0.75rem;
            }

            h3 {
                margin-top: 1.25rem;
            }

            div[data-testid="stAlert"] {
                border-radius: 10px;
            }

            [data-testid="stCaptionContainer"] {
                opacity: 0.78;
            }

            .flow-header,
            .flow-row {
                display: grid;
                grid-template-columns:
                    1fr auto auto 24px;
                align-items: center;
                gap: 12px;
            }

            .flow-header {
                padding: 10px 12px;
                margin-top: 8px;
                border-bottom: 1px solid rgba(128, 128, 128, 0.22);
            }

            .flow-header span {
                grid-column: 2 / 5;
                text-align: right;
            }

            .flow-row {
                padding: 8px 12px;
                border-bottom: 1px solid rgba(128, 128, 128, 0.12);
            }

            .flow-name {
                font-weight: 500;
            }

            .flow-direction {
                color: #6b7280;
                font-size: 0.85rem;
            }

            .flow-value {
                text-align: right;
                font-variant-numeric: tabular-nums;
            }

            .flow-arrow {
                text-align: center;
                font-weight: 600;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )