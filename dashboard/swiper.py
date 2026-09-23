"""
Rapid A/B preference testing for dashboard chart variants.

Run from the repository root with:

    python -m streamlit run dashboard/swiper.py

The page builds chart variants from dashboard.graphs, presents them in
a quick head-to-head "king of the hill" tournament, and writes the final
selection history to:

    results.json

This module displays charts and records preferences. It does not build
chart specifications itself.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from dashboard.data import (
    load_latest_forecast,
    load_recent_demand,
    load_recent_generation,
    load_recent_margin,
)
from dashboard.graphs import (
    build_demand_graphs,
    build_forecast_graphs,
    build_generation_graphs,
    build_margin_graphs,
    build_validation_graphs,
)


RESULTS_PATH = Path("results.json")
VALIDATION_PATH = Path(
    "data/processed/validation_predictions.csv"
)
TEST_PATH = Path(
    "data/processed/test_predictions.csv"
)

CATEGORY_ORDER = [
    "forecast",
    "margin",
    "demand",
    "generation",
    "validation",
]

CATEGORY_TITLES = {
    "forecast": "24-hour-ahead forecast",
    "margin": "De-rated margin",
    "demand": "Electricity demand",
    "generation": "Generation by fuel",
    "validation": "Model validation",
}


@st.cache_data
def load_model_predictions() -> pd.DataFrame:
    """
    Load historical model predictions for chart-design testing.

    Validation predictions are preferred because they were created
    specifically for model inspection. The final test predictions are
    used as a fallback if the validation file is unavailable.
    """
    path = (
        VALIDATION_PATH
        if VALIDATION_PATH.exists()
        else TEST_PATH
    )

    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path)

    if "target_time_utc" in df.columns:
        df["target_time_utc"] = pd.to_datetime(
            df["target_time_utc"],
            utc=True,
        )

    return df


def build_graph_catalog() -> dict[str, dict[str, Any]]:
    """
    Build all graph variants required by the preference test.

    Graph construction is delegated entirely to dashboard.graphs.
    """
    margin = load_recent_margin(days=7)
    demand = load_recent_demand(days=7)
    generation = load_recent_generation(days=7)
    forecast = load_latest_forecast()
    predictions = load_model_predictions()

    catalog: dict[str, dict[str, Any]] = {}

    if (
        forecast is not None
        and not margin.empty
    ):
        catalog["forecast"] = (
            build_forecast_graphs(
                recent_margin=margin,
                forecast=forecast,
            )
        )

    if not margin.empty:
        catalog["margin"] = (
            build_margin_graphs(
                margin=margin,
            )
        )

    if not demand.empty:
        catalog["demand"] = (
            build_demand_graphs(
                demand=demand,
            )
        )

    if not generation.empty:
        catalog["generation"] = (
            build_generation_graphs(
                generation=generation,
            )
        )

    if not predictions.empty:
        required = {
            "target_time_utc",
            "target_drm_mw",
            "predicted_drm_mw",
            "absolute_error_mw",
            "error_mw",
        }

        if required.issubset(
            predictions.columns
        ):
            catalog["validation"] = (
                build_validation_graphs(
                    predictions=predictions,
                )
            )

    return catalog


def ordered_categories(
    catalog: dict[str, dict[str, Any]],
) -> list[str]:
    return [
        category
        for category in CATEGORY_ORDER
        if category in catalog
        and len(catalog[category]) >= 2
    ]


def initialise_state(
    catalog: dict[str, dict[str, Any]],
) -> None:
    categories = ordered_categories(
        catalog
    )

    if "graph_swiper" in st.session_state:
        return

    st.session_state.graph_swiper = {
        "categories": categories,
        "category_index": 0,
        "champion": None,
        "challenger_index": 1,
        "matches": [],
        "category_results": {},
        "pending_match": None,
        "complete": False,
    }


def reset_state() -> None:
    if "graph_swiper" in st.session_state:
        del st.session_state.graph_swiper

    if RESULTS_PATH.exists():
        RESULTS_PATH.unlink()

    st.rerun()


def current_category(
    state: dict,
) -> str | None:
    categories = state["categories"]
    index = state["category_index"]

    if index >= len(categories):
        return None

    return categories[index]


def variant_names(
    catalog: dict[str, dict[str, Any]],
    category: str,
) -> list[str]:
    return list(
        catalog[category].keys()
    )


def ensure_champion(
    state: dict,
    catalog: dict[str, dict[str, Any]],
    category: str,
) -> None:
    if state["champion"] is not None:
        return

    variants = variant_names(
        catalog,
        category,
    )

    state["champion"] = variants[0]
    state["challenger_index"] = 1


def current_match(
    state: dict,
    catalog: dict[str, dict[str, Any]],
    category: str,
) -> tuple[str, str]:
    ensure_champion(
        state,
        catalog,
        category,
    )

    variants = variant_names(
        catalog,
        category,
    )

    challenger = variants[
        state["challenger_index"]
    ]

    champion = state["champion"]

    # Alternate the champion's side to reduce persistent
    # left/right position bias.
    round_number = (
        state["challenger_index"] - 1
    )

    if round_number % 2 == 0:
        return champion, challenger

    return challenger, champion


def save_results(
    state: dict,
    catalog: dict[str, dict[str, Any]],
) -> None:
    output = {
        "generated_at_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "method":
            "sequential_pairwise_preference_tournament",

        "notes":
            (
                "Each category used a quick king-of-the-hill "
                "A/B tournament. A tie retains the incumbent "
                "champion. This is a design preference exercise, "
                "not a statistical user study. Optional free-text "
                "comments are stored on individual matches."
            ),

        "categories": {},
        "matches": state["matches"],
    }

    for category in state["categories"]:
        result = state[
            "category_results"
        ].get(category)

        output["categories"][
            category
        ] = {
            "title":
                CATEGORY_TITLES.get(
                    category,
                    category,
                ),

            "winner":
                (
                    result["winner"]
                    if result
                    else None
                ),

            "variants":
                list(
                    catalog[
                        category
                    ].keys()
                ),
        }

    with RESULTS_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            output,
            file,
            indent=2,
        )


def finish_category(
    state: dict,
    catalog: dict[str, dict[str, Any]],
    category: str,
) -> None:
    state["category_results"][
        category
    ] = {
        "winner": state["champion"],
    }

    state["category_index"] += 1
    state["champion"] = None
    state["challenger_index"] = 1

    if (
        state["category_index"]
        >= len(state["categories"])
    ):
        state["complete"] = True

        save_results(
            state,
            catalog,
        )


def queue_choice(
    choice: str,
    state: dict,
    category: str,
    left_variant: str,
    right_variant: str,
) -> None:
    """Store a swipe until its optional comment has been handled."""
    incumbent = state["champion"]

    if choice == "left":
        winner = left_variant
    elif choice == "right":
        winner = right_variant
    else:
        winner = incumbent

    state["pending_match"] = {
        "category": category,
        "round": state["challenger_index"],
        "left_variant": left_variant,
        "right_variant": right_variant,
        "choice": choice,
        "winner": winner,
    }


def finalise_pending_match(
    state: dict,
    catalog: dict[str, dict[str, Any]],
    comment: str | None,
) -> None:
    pending = state.get("pending_match")

    if pending is None:
        return

    match = pending.copy()
    cleaned_comment = comment.strip() if comment else ""
    match["comment"] = cleaned_comment or None

    state["matches"].append(match)
    state["champion"] = match["winner"]
    state["challenger_index"] += 1
    state["pending_match"] = None

    category = match["category"]
    variants = variant_names(catalog, category)

    if state["challenger_index"] >= len(variants):
        finish_category(
            state,
            catalog,
            category,
        )

    st.rerun()


@st.dialog(
    "Add a comment?",
    width="medium",
)
def render_comment_dialog(
    state: dict,
    catalog: dict[str, dict[str, Any]],
) -> None:
    """Ask for an optional free-text note after each swipe."""
    pending = state.get("pending_match")

    if pending is None:
        return

    choice_label = {
        "left": "A",
        "right": "B",
        "tie": "No preference",
    }[pending["choice"]]

    st.caption(
        f"Recorded choice: {choice_label}"
    )

    comment = st.text_area(
        "Optional comment",
        placeholder=(
            "e.g. clearer hierarchy, too busy, "
            "better for a non-technical audience..."
        ),
        key=(
            "pending_comment_"
            f"{pending['category']}_"
            f"{pending['round']}"
        ),
        height=110,
    )

    skip_column, save_column = st.columns(2)

    with skip_column:
        if st.button(
            "Skip",
            width="stretch",
            key=(
                "skip_comment_"
                f"{pending['category']}_"
                f"{pending['round']}"
            ),
        ):
            finalise_pending_match(
                state=state,
                catalog=catalog,
                comment=None,
            )

    with save_column:
        if st.button(
            "Save comment",
            width="stretch",
            type="primary",
            key=(
                "save_comment_"
                f"{pending['category']}_"
                f"{pending['round']}"
            ),
        ):
            finalise_pending_match(
                state=state,
                catalog=catalog,
                comment=comment,
            )


def render_progress(
    state: dict,
    catalog: dict[str, dict[str, Any]],
) -> None:
    total_matches = sum(
        max(
            len(
                catalog[category]
            ) - 1,
            0,
        )
        for category
        in state["categories"]
    )

    completed = len(
        state["matches"]
    )

    if total_matches == 0:
        return

    st.progress(
        completed / total_matches,
        text=(
            f"{completed} of "
            f"{total_matches} comparisons"
        ),
    )


def render_complete(
    state: dict,
) -> None:
    st.success(
        "Graph preference test complete."
    )

    st.subheader(
        "Selected graph variants"
    )

    rows = []

    for category in state["categories"]:
        result = state[
            "category_results"
        ][category]

        rows.append(
            {
                "Data section":
                    CATEGORY_TITLES.get(
                        category,
                        category,
                    ),

                "Selected variant":
                    result["winner"],
            }
        )

    st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        width="stretch",
    )

    st.caption(
        f"Results saved to {RESULTS_PATH}"
    )

    with RESULTS_PATH.open(
        encoding="utf-8",
    ) as file:
        result_text = file.read()

    st.download_button(
        label="Download results.json",
        data=result_text,
        file_name="results.json",
        mime="application/json",
    )

    if st.button(
        "Restart preference test"
    ):
        reset_state()


def render_match(
    state: dict,
    catalog: dict[str, dict[str, Any]],
    category: str,
) -> None:
    ensure_champion(
        state,
        catalog,
        category,
    )

    left_variant, right_variant = (
        current_match(
            state,
            catalog,
            category,
        )
    )

    st.subheader(
        CATEGORY_TITLES.get(
            category,
            category,
        )
    )

    st.caption(
        "Choose the graph that communicates "
        "this information more clearly. "
        "Variant names are hidden until the end "
        "to reduce naming bias."
    )

    left_column, right_column = (
        st.columns(2)
    )

    with left_column:
        st.markdown("### A")

        st.altair_chart(
            catalog[
                category
            ][left_variant],
            width="stretch",
        )

    with right_column:
        st.markdown("### B")

        st.altair_chart(
            catalog[
                category
            ][right_variant],
            width="stretch",
        )

    choice_left, choice_tie, choice_right = (
        st.columns([1, 1, 1])
    )

    with choice_left:
        if st.button(
            "← Prefer A",
            width="stretch",
            key=(
                f"left_"
                f"{category}_"
                f"{state['challenger_index']}"
            ),
        ):
            queue_choice(
                choice="left",
                state=state,
                category=category,
                left_variant=left_variant,
                right_variant=right_variant,
            )
            st.rerun()

    with choice_tie:
        if st.button(
            "No preference",
            width="stretch",
            key=(
                f"tie_"
                f"{category}_"
                f"{state['challenger_index']}"
            ),
        ):
            queue_choice(
                choice="tie",
                state=state,
                category=category,
                left_variant=left_variant,
                right_variant=right_variant,
            )
            st.rerun()

    with choice_right:
        if st.button(
            "Prefer B →",
            width="stretch",
            key=(
                f"right_"
                f"{category}_"
                f"{state['challenger_index']}"
            ),
        ):
            queue_choice(
                choice="right",
                state=state,
                category=category,
                left_variant=left_variant,
                right_variant=right_variant,
            )
            st.rerun()


def main() -> None:
    st.set_page_config(
        page_title="Graph Swiper",
        page_icon="📊",
        layout="wide",
    )

    st.title(
        "Dashboard Graph Swiper"
    )

    st.caption(
        "Rapid A/B preference testing for the "
        "UK Energy Reliability Tool."
    )

    catalog = build_graph_catalog()

    if not catalog:
        st.error(
            "No graph data is currently available."
        )
        return

    initialise_state(
        catalog
    )

    state = st.session_state.graph_swiper

    if not state["categories"]:
        st.error(
            "No graph category has at least two "
            "available variants."
        )
        return

    render_progress(
        state,
        catalog,
    )

    if state["complete"]:
        render_complete(
            state
        )
        return

    if state.get("pending_match") is not None:
        render_comment_dialog(
            state=state,
            catalog=catalog,
        )

    category = current_category(
        state
    )

    if category is None:
        state["complete"] = True

        save_results(
            state,
            catalog,
        )

        st.rerun()

    render_match(
        state,
        catalog,
        category,
    )

    st.divider()

    st.caption(
        "This is a quick design-selection exercise. "
        "It chooses a preferred chart variant per section; "
        "it does not measure statistical significance."
    )


if __name__ == "__main__":
    main()
