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
        </style>
        """,
        unsafe_allow_html=True,
    )
