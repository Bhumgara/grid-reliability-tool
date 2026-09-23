"""
Dashboard chart design tester.

Run from the repository root with:

    python -m streamlit run dashboard/swiper.py

Two modes are provided:

1. A/B Tournament
   Head-to-head comparison of alternative chart variants.

2. Concept Review
   Review genuinely different chart/data concepts one at a time using
   Keep / Maybe / Reject, with an optional comment after every choice.

Both modes write into the same results.json without overwriting the other
mode's output.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import streamlit as st

from dashboard.data import (
    load_latest_forecast,
    load_margin_history,
    load_recent_demand,
    load_recent_generation,
    load_recent_margin,
)
from dashboard.graphs import (
    build_current_demand_percentile_graph,
    build_demand_graphs,
    build_drm_change_bridge,
    build_error_direction_graph,
    build_forecast_graphs,
    build_forecast_percentile_graph,
    build_generation_change_graph,
    build_generation_doughnut_summary,
    build_generation_graphs,
    build_generation_ranking_graph,
    build_margin_demand_scatter,
    build_margin_graphs,
    build_model_vs_persistence_graph,
    build_typical_day_demand_graph,
    build_validation_graphs,
)


RESULTS_PATH = Path("results.json")

VALIDATION_PATH = Path(
    "data/processed/validation_predictions.csv"
)

TEST_PATH = Path(
    "data/processed/test_predictions.csv"
)


# ============================================================
# Labels / ordering
# ============================================================

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

CONCEPT_ORDER = [
    "forecast_percentile",
    "drm_change_bridge",
    "typical_day_demand",
    "current_demand_percentile",
    "generation_doughnut_summary",
    "generation_ranking",
    "generation_change",
    "margin_demand_scatter",
    "error_direction",
    "model_vs_persistence",
]

CONCEPT_META = {
    "forecast_percentile": {
        "title": "Forecast historical position",
        "question": (
            "Does this make the forecast easier to interpret "
            "than a raw GW value alone?"
        ),
    },
    "drm_change_bridge": {
        "title": "Current DRM → 24-hour forecast",
        "question": (
            "Is the expected direction and size of the change "
            "immediately obvious?"
        ),
    },
    "typical_day_demand": {
        "title": "Demand vs a typical day",
        "question": (
            "Does comparing today's shape with a historical "
            "profile add useful context?"
        ),
    },
    "current_demand_percentile": {
        "title": "Demand percentile for this time of day",
        "question": (
            "Does a percentile communicate whether current "
            "demand is unusual?"
        ),
    },
    "generation_doughnut_summary": {
        "title": "Generation doughnut + total",
        "question": (
            "Does the centre statistic make the current "
            "generation mix more useful?"
        ),
    },
    "generation_ranking": {
        "title": "Generation ranking",
        "question": (
            "Is ranking current output easier to understand "
            "than a generation-mix chart?"
        ),
    },
    "generation_change": {
        "title": "Generation movement",
        "question": (
            "Is it useful to see which fuel sources are "
            "increasing or decreasing most?"
        ),
    },
    "margin_demand_scatter": {
        "title": "Demand vs de-rated margin",
        "question": (
            "Does this relationship help explain the system, "
            "or is it too analytical for the main dashboard?"
        ),
    },
    "error_direction": {
        "title": "Prediction error direction",
        "question": (
            "Does this clearly explain whether the model tends "
            "to predict too high or too low?"
        ),
    },
    "model_vs_persistence": {
        "title": "Ridge vs persistence",
        "question": (
            "Does this communicate the model's improvement "
            "over the simple baseline clearly?"
        ),
    },
}


# ============================================================
# Shared data
# ============================================================

@st.cache_data
def load_model_predictions() -> pd.DataFrame:
    """
    Prefer validation predictions for design testing.

    The final test predictions are used only if the validation file is
    unavailable.
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


# ============================================================
# Results persistence
# ============================================================

def read_results_file() -> dict[str, Any]:
    """
    Read existing results and migrate the original one-mode schema.

    Older results.json files contained categories/matches at the root.
    They are preserved under `ab_test`.
    """
    if not RESULTS_PATH.exists():
        return {}

    try:
        with RESULTS_PATH.open(
            encoding="utf-8",
        ) as file:
            existing = json.load(file)
    except (
        json.JSONDecodeError,
        OSError,
    ):
        return {}

    if not isinstance(
        existing,
        dict,
    ):
        return {}

    if (
        "categories" in existing
        and "matches" in existing
        and "ab_test" not in existing
    ):
        return {
            "ab_test": existing,
        }

    return existing


def write_results_section(
    section: str,
    payload: dict[str, Any],
) -> None:
    output = read_results_file()

    output["updated_at_utc"] = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    output[section] = payload

    with RESULTS_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            output,
            file,
            indent=2,
        )


# ============================================================
# A/B tournament
# ============================================================

def build_graph_catalog() -> dict[str, dict[str, Any]]:
    margin = load_recent_margin(
        days=7
    )

    demand = load_recent_demand(
        days=7
    )

    generation = load_recent_generation(
        days=7
    )

    forecast = load_latest_forecast()
    predictions = load_model_predictions()

    catalog: dict[
        str,
        dict[str, Any],
    ] = {}

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
    catalog: dict[
        str,
        dict[str, Any],
    ],
) -> list[str]:
    return [
        category
        for category in CATEGORY_ORDER
        if (
            category in catalog
            and len(
                catalog[category]
            ) >= 2
        )
    ]


def initialise_ab_state(
    catalog: dict[
        str,
        dict[str, Any],
    ],
) -> None:
    if "graph_swiper" in st.session_state:
        return

    st.session_state.graph_swiper = {
        "categories":
            ordered_categories(
                catalog
            ),
        "category_index": 0,
        "champion": None,
        "challenger_index": 1,
        "matches": [],
        "category_results": {},
        "pending_match": None,
        "complete": False,
    }


def reset_ab_state() -> None:
    if "graph_swiper" in st.session_state:
        del st.session_state.graph_swiper

    st.rerun()


def current_category(
    state: dict,
) -> str | None:
    index = state[
        "category_index"
    ]

    categories = state[
        "categories"
    ]

    if index >= len(
        categories
    ):
        return None

    return categories[index]


def variant_names(
    catalog: dict[
        str,
        dict[str, Any],
    ],
    category: str,
) -> list[str]:
    return list(
        catalog[
            category
        ].keys()
    )


def ensure_champion(
    state: dict,
    catalog: dict[
        str,
        dict[str, Any],
    ],
    category: str,
) -> None:
    if state[
        "champion"
    ] is not None:
        return

    variants = variant_names(
        catalog,
        category,
    )

    state["champion"] = (
        variants[0]
    )

    state[
        "challenger_index"
    ] = 1


def current_match(
    state: dict,
    catalog: dict[
        str,
        dict[str, Any],
    ],
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
        state[
            "challenger_index"
        ]
    ]

    champion = state[
        "champion"
    ]

    round_number = (
        state[
            "challenger_index"
        ]
        - 1
    )

    # Alternate incumbent side to reduce left/right bias.
    if round_number % 2 == 0:
        return (
            champion,
            challenger,
        )

    return (
        challenger,
        champion,
    )


def save_ab_results(
    state: dict,
    catalog: dict[
        str,
        dict[str, Any],
    ],
) -> None:
    payload = {
        "generated_at_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "method":
            (
                "sequential_pairwise_"
                "preference_tournament"
            ),

        "notes":
            (
                "Quick king-of-the-hill A/B tournament. "
                "A tie retains the incumbent. Optional "
                "free-text comments are stored on matches. "
                "This is a design preference exercise, not "
                "a statistical user study."
            ),

        "categories": {},
        "matches":
            state["matches"],
    }

    for category in state[
        "categories"
    ]:
        result = state[
            "category_results"
        ].get(category)

        payload[
            "categories"
        ][category] = {
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

    write_results_section(
        "ab_test",
        payload,
    )


def finish_ab_category(
    state: dict,
    catalog: dict[
        str,
        dict[str, Any],
    ],
    category: str,
) -> None:
    state[
        "category_results"
    ][category] = {
        "winner":
            state["champion"],
    }

    state[
        "category_index"
    ] += 1

    state[
        "champion"
    ] = None

    state[
        "challenger_index"
    ] = 1

    if (
        state[
            "category_index"
        ]
        >= len(
            state["categories"]
        )
    ):
        state["complete"] = True

        save_ab_results(
            state,
            catalog,
        )


def queue_ab_choice(
    choice: str,
    state: dict,
    category: str,
    left_variant: str,
    right_variant: str,
) -> None:
    incumbent = state[
        "champion"
    ]

    if choice == "left":
        winner = left_variant

    elif choice == "right":
        winner = right_variant

    else:
        winner = incumbent

    state[
        "pending_match"
    ] = {
        "category":
            category,

        "round":
            state[
                "challenger_index"
            ],

        "left_variant":
            left_variant,

        "right_variant":
            right_variant,

        "choice":
            choice,

        "winner":
            winner,
    }


def finalise_ab_match(
    state: dict,
    catalog: dict[
        str,
        dict[str, Any],
    ],
    comment: str | None,
) -> None:
    pending = state.get(
        "pending_match"
    )

    if pending is None:
        return

    match = pending.copy()

    cleaned = (
        comment.strip()
        if comment
        else ""
    )

    match["comment"] = (
        cleaned or None
    )

    state["matches"].append(
        match
    )

    state["champion"] = (
        match["winner"]
    )

    state[
        "challenger_index"
    ] += 1

    state[
        "pending_match"
    ] = None

    category = match[
        "category"
    ]

    variants = variant_names(
        catalog,
        category,
    )

    if (
        state[
            "challenger_index"
        ]
        >= len(variants)
    ):
        finish_ab_category(
            state,
            catalog,
            category,
        )

    st.rerun()


@st.dialog(
    "Add a comment?",
    width="medium",
)
def render_ab_comment_dialog(
    state: dict,
    catalog: dict[
        str,
        dict[str, Any],
    ],
) -> None:
    pending = state.get(
        "pending_match"
    )

    if pending is None:
        return

    label = {
        "left": "A",
        "right": "B",
        "tie": "No preference",
    }[
        pending["choice"]
    ]

    st.caption(
        f"Recorded choice: {label}"
    )

    comment = st.text_area(
        "Optional comment",
        placeholder=(
            "e.g. clearer hierarchy, too busy, "
            "better for a non-technical audience..."
        ),
        key=(
            "ab_comment_"
            f"{pending['category']}_"
            f"{pending['round']}"
        ),
        height=110,
    )

    skip, save = st.columns(2)

    with skip:
        if st.button(
            "Skip",
            width="stretch",
            key=(
                "ab_skip_"
                f"{pending['category']}_"
                f"{pending['round']}"
            ),
        ):
            finalise_ab_match(
                state,
                catalog,
                None,
            )

    with save:
        if st.button(
            "Save comment",
            width="stretch",
            type="primary",
            key=(
                "ab_save_"
                f"{pending['category']}_"
                f"{pending['round']}"
            ),
        ):
            finalise_ab_match(
                state,
                catalog,
                comment,
            )


def render_ab_progress(
    state: dict,
    catalog: dict[
        str,
        dict[str, Any],
    ],
) -> None:
    total = sum(
        max(
            len(
                catalog[
                    category
                ]
            )
            - 1,
            0,
        )
        for category
        in state[
            "categories"
        ]
    )

    completed = len(
        state["matches"]
    )

    if total == 0:
        return

    st.progress(
        completed / total,
        text=(
            f"{completed} of "
            f"{total} comparisons"
        ),
    )


def render_ab_complete(
    state: dict,
) -> None:
    st.success(
        "A/B graph preference test complete."
    )

    rows = []

    for category in state[
        "categories"
    ]:
        rows.append(
            {
                "Data section":
                    CATEGORY_TITLES.get(
                        category,
                        category,
                    ),

                "Selected variant":
                    state[
                        "category_results"
                    ][category][
                        "winner"
                    ],
            }
        )

    st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        width="stretch",
    )

    st.caption(
        f"Saved into {RESULTS_PATH}"
    )

    if st.button(
        "Restart A/B test"
    ):
        reset_ab_state()


def render_ab_match(
    state: dict,
    catalog: dict[
        str,
        dict[str, Any],
    ],
    category: str,
) -> None:
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
        "Variant names are hidden until the end."
    )

    left, right = st.columns(2)

    with left:
        st.markdown("### A")

        st.altair_chart(
            catalog[
                category
            ][left_variant],
            width="stretch",
        )

    with right:
        st.markdown("### B")

        st.altair_chart(
            catalog[
                category
            ][right_variant],
            width="stretch",
        )

    choose_a, tie, choose_b = (
        st.columns(3)
    )

    with choose_a:
        if st.button(
            "← Prefer A",
            width="stretch",
            key=(
                "ab_left_"
                f"{category}_"
                f"{state['challenger_index']}"
            ),
        ):
            queue_ab_choice(
                "left",
                state,
                category,
                left_variant,
                right_variant,
            )
            st.rerun()

    with tie:
        if st.button(
            "No preference",
            width="stretch",
            key=(
                "ab_tie_"
                f"{category}_"
                f"{state['challenger_index']}"
            ),
        ):
            queue_ab_choice(
                "tie",
                state,
                category,
                left_variant,
                right_variant,
            )
            st.rerun()

    with choose_b:
        if st.button(
            "Prefer B →",
            width="stretch",
            key=(
                "ab_right_"
                f"{category}_"
                f"{state['challenger_index']}"
            ),
        ):
            queue_ab_choice(
                "right",
                state,
                category,
                left_variant,
                right_variant,
            )
            st.rerun()


def render_ab_mode() -> None:
    catalog = build_graph_catalog()

    if not catalog:
        st.error(
            "No A/B chart data is available."
        )
        return

    initialise_ab_state(
        catalog
    )

    state = st.session_state[
        "graph_swiper"
    ]

    if not state[
        "categories"
    ]:
        st.error(
            "No graph category has at least "
            "two available variants."
        )
        return

    render_ab_progress(
        state,
        catalog,
    )

    if state[
        "complete"
    ]:
        render_ab_complete(
            state
        )
        return

    if state.get(
        "pending_match"
    ) is not None:
        render_ab_comment_dialog(
            state,
            catalog,
        )

    category = current_category(
        state
    )

    if category is None:
        state["complete"] = True

        save_ab_results(
            state,
            catalog,
        )

        st.rerun()

    render_ab_match(
        state,
        catalog,
        category,
    )


# ============================================================
# Concept review
# ============================================================

def safe_build_concept(
    name: str,
    builder: Callable[[], Any],
    catalog: dict[str, Any],
    errors: dict[str, str],
) -> None:
    try:
        catalog[name] = builder()

    except Exception as exc:
        errors[name] = (
            f"{type(exc).__name__}: {exc}"
        )


def build_concept_catalog(
) -> tuple[
    dict[str, Any],
    dict[str, str],
]:
    """
    Build each concept independently.

    If one concept lacks the data it needs, the remaining concepts can
    still be reviewed.
    """
    forecast = load_latest_forecast()

    recent_margin = load_recent_margin(
        days=30
    )

    demand_history = load_recent_demand(
        days=30
    )

    generation = load_recent_generation(
        days=7
    )

    predictions = load_model_predictions()

    try:
        margin_history = (
            load_margin_history()
        )
    except Exception:
        margin_history = recent_margin

    catalog: dict[
        str,
        Any,
    ] = {}

    errors: dict[
        str,
        str,
    ] = {}

    if forecast is not None:
        safe_build_concept(
            "forecast_percentile",
            lambda: (
                build_forecast_percentile_graph(
                    forecast,
                    margin_history,
                )
            ),
            catalog,
            errors,
        )

        safe_build_concept(
            "drm_change_bridge",
            lambda: (
                build_drm_change_bridge(
                    forecast
                )
            ),
            catalog,
            errors,
        )

    if not demand_history.empty:
        safe_build_concept(
            "typical_day_demand",
            lambda: (
                build_typical_day_demand_graph(
                    demand_history
                )
            ),
            catalog,
            errors,
        )

        safe_build_concept(
            "current_demand_percentile",
            lambda: (
                build_current_demand_percentile_graph(
                    demand_history
                )
            ),
            catalog,
            errors,
        )

    if not generation.empty:
        safe_build_concept(
            "generation_doughnut_summary",
            lambda: (
                build_generation_doughnut_summary(
                    generation
                )
            ),
            catalog,
            errors,
        )

        safe_build_concept(
            "generation_ranking",
            lambda: (
                build_generation_ranking_graph(
                    generation
                )
            ),
            catalog,
            errors,
        )

        safe_build_concept(
            "generation_change",
            lambda: (
                build_generation_change_graph(
                    generation
                )
            ),
            catalog,
            errors,
        )

    if (
        not recent_margin.empty
        and not demand_history.empty
    ):
        safe_build_concept(
            "margin_demand_scatter",
            lambda: (
                build_margin_demand_scatter(
                    recent_margin,
                    demand_history,
                )
            ),
            catalog,
            errors,
        )

    if not predictions.empty:
        safe_build_concept(
            "error_direction",
            lambda: (
                build_error_direction_graph(
                    predictions
                )
            ),
            catalog,
            errors,
        )

        safe_build_concept(
            "model_vs_persistence",
            lambda: (
                build_model_vs_persistence_graph(
                    predictions
                )
            ),
            catalog,
            errors,
        )

    return (
        catalog,
        errors,
    )


def initialise_concept_state(
    catalog: dict[str, Any],
) -> None:
    if (
        "concept_swiper"
        in st.session_state
    ):
        return

    available = [
        concept
        for concept in CONCEPT_ORDER
        if concept in catalog
    ]

    st.session_state[
        "concept_swiper"
    ] = {
        "concepts": available,
        "index": 0,
        "reviews": [],
        "pending_review": None,
        "complete": False,
    }


def reset_concept_state() -> None:
    if (
        "concept_swiper"
        in st.session_state
    ):
        del st.session_state[
            "concept_swiper"
        ]

    st.rerun()


def current_concept(
    state: dict,
) -> str | None:
    index = state["index"]
    concepts = state[
        "concepts"
    ]

    if index >= len(
        concepts
    ):
        return None

    return concepts[index]


def save_concept_results(
    state: dict,
) -> None:
    summary = {
        "keep": [],
        "maybe": [],
        "reject": [],
    }

    for review in state[
        "reviews"
    ]:
        summary[
            review["rating"]
        ].append(
            review["concept"]
        )

    payload = {
        "generated_at_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "method":
            (
                "individual_concept_"
                "keep_maybe_reject"
            ),

        "notes":
            (
                "Concepts answer different questions, "
                "so they are reviewed individually rather "
                "than forced into one A/B tournament. "
                "Optional comments are stored with each review."
            ),

        "summary":
            summary,

        "reviews":
            state["reviews"],
    }

    write_results_section(
        "concept_review",
        payload,
    )


def queue_concept_rating(
    rating: str,
    state: dict,
    concept: str,
) -> None:
    state[
        "pending_review"
    ] = {
        "concept":
            concept,

        "title":
            CONCEPT_META[
                concept
            ]["title"],

        "rating":
            rating,
    }


def finalise_concept_review(
    state: dict,
    comment: str | None,
) -> None:
    pending = state.get(
        "pending_review"
    )

    if pending is None:
        return

    review = pending.copy()

    cleaned = (
        comment.strip()
        if comment
        else ""
    )

    review["comment"] = (
        cleaned or None
    )

    state[
        "reviews"
    ].append(
        review
    )

    state[
        "pending_review"
    ] = None

    state["index"] += 1

    if (
        state["index"]
        >= len(
            state["concepts"]
        )
    ):
        state[
            "complete"
        ] = True

        save_concept_results(
            state
        )

    st.rerun()


@st.dialog(
    "Add a comment?",
    width="medium",
)
def render_concept_comment_dialog(
    state: dict,
) -> None:
    pending = state.get(
        "pending_review"
    )

    if pending is None:
        return

    st.caption(
        f"{pending['title']} · "
        f"{pending['rating'].upper()}"
    )

    comment = st.text_area(
        "Optional comment",
        placeholder=(
            "What works? What doesn't? "
            "Where would this belong on the dashboard?"
        ),
        key=(
            "concept_comment_"
            f"{pending['concept']}"
        ),
        height=120,
    )

    skip, save = st.columns(2)

    with skip:
        if st.button(
            "Skip",
            width="stretch",
            key=(
                "concept_skip_"
                f"{pending['concept']}"
            ),
        ):
            finalise_concept_review(
                state,
                None,
            )

    with save:
        if st.button(
            "Save comment",
            width="stretch",
            type="primary",
            key=(
                "concept_save_"
                f"{pending['concept']}"
            ),
        ):
            finalise_concept_review(
                state,
                comment,
            )


def render_concept_complete(
    state: dict,
) -> None:
    st.success(
        "Concept review complete."
    )

    rows = [
        {
            "Concept":
                review["title"],

            "Rating":
                review[
                    "rating"
                ].title(),

            "Comment":
                review.get(
                    "comment"
                )
                or "",
        }
        for review
        in state["reviews"]
    ]

    st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        width="stretch",
    )

    st.caption(
        f"Saved into {RESULTS_PATH}"
    )

    if RESULTS_PATH.exists():
        with RESULTS_PATH.open(
            encoding="utf-8",
        ) as file:
            contents = file.read()

        st.download_button(
            "Download results.json",
            data=contents,
            file_name="results.json",
            mime="application/json",
        )

    if st.button(
        "Restart concept review"
    ):
        reset_concept_state()


def render_concept_card(
    concept: str,
    chart: Any,
) -> None:
    meta = CONCEPT_META[
        concept
    ]

    st.subheader(
        meta["title"]
    )

    st.caption(
        meta["question"]
    )

    st.altair_chart(
        chart,
        width="stretch",
    )


def render_concept_mode() -> None:
    catalog, errors = (
        build_concept_catalog()
    )

    if not catalog:
        st.error(
            "No experimental concepts could "
            "be built from the current data."
        )

        if errors:
            with st.expander(
                "Build errors"
            ):
                st.json(errors)

        return

    initialise_concept_state(
        catalog
    )

    state = st.session_state[
        "concept_swiper"
    ]

    total = len(
        state["concepts"]
    )

    completed = len(
        state["reviews"]
    )

    if total:
        st.progress(
            completed / total,
            text=(
                f"{completed} of "
                f"{total} concepts reviewed"
            ),
        )

    if errors:
        with st.expander(
            "Unavailable concepts"
        ):
            for name, error in (
                errors.items()
            ):
                title = (
                    CONCEPT_META.get(
                        name,
                        {},
                    ).get(
                        "title",
                        name,
                    )
                )

                st.caption(
                    f"{title}: {error}"
                )

    if state[
        "complete"
    ]:
        render_concept_complete(
            state
        )
        return

    if state.get(
        "pending_review"
    ) is not None:
        render_concept_comment_dialog(
            state
        )

    concept = current_concept(
        state
    )

    if concept is None:
        state["complete"] = True

        save_concept_results(
            state
        )

        st.rerun()

    render_concept_card(
        concept,
        catalog[concept],
    )

    reject, maybe, keep = (
        st.columns(3)
    )

    with reject:
        if st.button(
            "✕ Reject",
            width="stretch",
            key=(
                f"reject_{concept}"
            ),
        ):
            queue_concept_rating(
                "reject",
                state,
                concept,
            )
            st.rerun()

    with maybe:
        if st.button(
            "? Maybe",
            width="stretch",
            key=(
                f"maybe_{concept}"
            ),
        ):
            queue_concept_rating(
                "maybe",
                state,
                concept,
            )
            st.rerun()

    with keep:
        if st.button(
            "✓ Keep",
            width="stretch",
            type="primary",
            key=(
                f"keep_{concept}"
            ),
        ):
            queue_concept_rating(
                "keep",
                state,
                concept,
            )
            st.rerun()


# ============================================================
# App
# ============================================================

def main() -> None:
    st.set_page_config(
        page_title=(
            "Dashboard Graph Tester"
        ),
        page_icon="📊",
        layout="wide",
    )

    st.title(
        "Dashboard Graph Tester"
    )

    st.caption(
        "Compare chart variants or review "
        "new dashboard concepts."
    )

    mode = st.radio(
        "Testing mode",
        options=[
            "A/B Tournament",
            "Concept Review",
        ],
        horizontal=True,
        label_visibility="collapsed",
    )

    st.divider()

    if mode == "A/B Tournament":
        render_ab_mode()

    else:
        render_concept_mode()

    st.divider()

    st.caption(
        "The A/B mode compares alternative visual treatments "
        "of the same information. Concept Review evaluates "
        "whether a different datapoint or visual idea deserves "
        "a place on the dashboard."
    )


if __name__ == "__main__":
    main()
