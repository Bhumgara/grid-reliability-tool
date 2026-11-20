"""Data for the interconnector flow list."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# Elexon interconnector fuel types grouped by connected country.
INTERCONNECTOR_GROUPS = {
    "Belgium": [
        "INTNEM",
    ],
    "Denmark": [
        "INTVKL",
    ],
    "France": [
        "INTFR",
        "INTIFA2",
        "INTELEC",
    ],
    "Ireland": [
        "INTIRL",
        "INTEW",
        "INTGRNL",
    ],
    "Netherlands": [
        "INTNED",
    ],
    "Norway": [
        "INTNSL",
    ],
}

# Flows within this many GW of zero are treated as idle.
IDLE_THRESHOLD_GW = 0.01

FLOW_COLUMNS = ["country", "flow_gw", "direction"]


@dataclass(frozen=True)
class InterconnectorView:
    """
    Current interconnector flows by country.

    ``flows`` has columns ``country``, ``flow_gw`` (positive = import into
    GB, negative = export) and ``direction`` (``Import``, ``Export`` or
    ``Idle``), one row per country in ``INTERCONNECTOR_GROUPS`` order. It is
    empty when there is no interconnector data.
    """

    flows: pd.DataFrame
    net_flow_gw: float


def interconnector_view(
    interconnectors: pd.DataFrame,
) -> InterconnectorView:
    """
    Build per-country flows from ``load_live_interconnectors`` output
    (``fuel_type`` plus ``generation_mw`` or ``flow_gw``).

    Countries with no data count as zero flow. Raises ValueError if neither
    flow column is present.
    """
    if interconnectors.empty:
        return InterconnectorView(
            flows=pd.DataFrame(columns=FLOW_COLUMNS),
            net_flow_gw=0.0,
        )

    data = interconnectors.copy()

    if "flow_gw" not in data.columns:
        if "generation_mw" not in data.columns:
            raise ValueError(
                "Interconnector data requires "
                "'flow_gw' or 'generation_mw'."
            )

        data["flow_gw"] = data["generation_mw"] / 1000

    flows = data.set_index("fuel_type")["flow_gw"].to_dict()

    rows = []

    for country, codes in INTERCONNECTOR_GROUPS.items():
        flow_gw = sum(
            flows.get(code, 0.0)
            for code in codes
        )

        if flow_gw > IDLE_THRESHOLD_GW:
            direction = "Import"
        elif flow_gw < -IDLE_THRESHOLD_GW:
            direction = "Export"
        else:
            direction = "Idle"

        rows.append(
            {
                "country": country,
                "flow_gw": flow_gw,
                "direction": direction,
            }
        )

    return InterconnectorView(
        flows=pd.DataFrame(rows, columns=FLOW_COLUMNS),
        net_flow_gw=sum(row["flow_gw"] for row in rows),
    )
