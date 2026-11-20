import pandas as pd
import pytest

from core import queries
from core.views.interconnectors import (
    FLOW_COLUMNS,
    INTERCONNECTOR_GROUPS,
    interconnector_view,
)


def test_interconnector_view_groups_by_country():
    data = pd.DataFrame(
        {
            "fuel_type": ["INTFR", "INTIFA2", "INTNED", "INTIRL", "INTVKL"],
            "generation_mw": [1500.0, -400.0, -900.0, 5.0, -8.0],
        }
    )

    view = interconnector_view(data)
    flows = view.flows.set_index("country")

    assert list(view.flows.columns) == FLOW_COLUMNS
    assert list(flows.index) == list(INTERCONNECTOR_GROUPS)

    assert flows.loc["France", "flow_gw"] == pytest.approx(1.1)
    assert flows.loc["France", "direction"] == "Import"
    assert flows.loc["Netherlands", "direction"] == "Export"
    # Within 0.01 GW of zero counts as idle; countries with no data are zero.
    assert flows.loc["Ireland", "direction"] == "Idle"
    assert flows.loc["Denmark", "direction"] == "Idle"
    assert flows.loc["Belgium", "flow_gw"] == 0.0

    assert view.net_flow_gw == pytest.approx(1.5 - 0.4 - 0.9 + 0.005 - 0.008)


def test_interconnector_view_from_fixture(grid_db):
    view = interconnector_view(
        queries.load_live_interconnectors(db_path=grid_db)
    )
    flows = view.flows.set_index("country")["flow_gw"]

    assert flows["France"] == pytest.approx(1.5)
    assert flows["Netherlands"] == pytest.approx(0.8)
    assert flows["Norway"] == pytest.approx(1.2)
    assert view.net_flow_gw == pytest.approx(3.5)


def test_interconnector_view_accepts_flow_gw():
    view = interconnector_view(
        pd.DataFrame({"fuel_type": ["INTFR"], "flow_gw": [1.234]})
    )

    assert view.net_flow_gw == pytest.approx(1.234)


def test_interconnector_view_empty_and_invalid_input():
    empty = interconnector_view(pd.DataFrame())
    assert empty.flows.empty
    assert list(empty.flows.columns) == FLOW_COLUMNS
    assert empty.net_flow_gw == 0.0

    with pytest.raises(ValueError, match="'flow_gw' or 'generation_mw'"):
        interconnector_view(pd.DataFrame({"fuel_type": ["INTFR"], "value": [1.0]}))
