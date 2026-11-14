"""So sánh kết quả giữa ToolsGateway(mode='direct') và ToolsGateway(mode='mcp')."""

import pytest

from agent.tools_gateway import ToolsGateway
from core.schemas import DayPlan, Meal, MealPlanLLM, PatientProfile, PlannedItem
from db.import_food import import_food_csv


@pytest.fixture(scope="module", autouse=True)
def _ensure_food_db() -> None:
    import_food_csv()


@pytest.mark.mcp
def test_gateway_parity_direct_vs_mcp() -> None:
    """Hai chế độ direct và mcp phải trả về kết quả tương đương nhau."""
    profile = PatientProfile(
        patient_code="P0001",
        age=40,
        sex="male",
        height_cm=170.0,
        weight_kg=70.0,
        activity_level="moderate",
        conditions=["t2d", "htn"],
        allergens=["seafood"],
    )

    with ToolsGateway(mode="direct") as gw_direct, ToolsGateway(mode="mcp") as gw_mcp:
        t_direct = gw_direct.calc_targets(profile)
        t_mcp = gw_mcp.calc_targets(profile)
        assert t_direct == t_mcp

        s_direct = gw_direct.search_food(query="ca hoi", limit=5)
        s_mcp = gw_mcp.search_food(query="ca hoi", limit=5)
        assert s_direct == s_mcp
        assert len(s_direct) >= 1
        fid = s_direct[0]["id"]

        a_direct = gw_direct.check_allergen([fid], ["seafood"])
        a_mcp = gw_mcp.check_allergen([fid], ["seafood"])
        assert a_direct == a_mcp

        g_direct = gw_direct.get_guideline("tieu duong", disease="t2d")
        g_mcp = gw_mcp.get_guideline("tieu duong", disease="t2d")
        assert g_direct == g_mcp

        plan = MealPlanLLM(
            days=[
                DayPlan(
                    day=1,
                    meals=[Meal(meal="lunch", items=[PlannedItem(food_id=fid, grams=120.0)])],
                )
            ]
        )
        m_direct = gw_direct.score_menu(plan)
        m_mcp = gw_mcp.score_menu(plan)
        assert m_direct == m_mcp
