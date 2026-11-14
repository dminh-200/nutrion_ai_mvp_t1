"""Kiểm thử gọi trực tiếp 5 tool qua MCP Client (stdio)."""

import asyncio
import sys

import pytest
from mcp import Client
from mcp.client.stdio import StdioServerParameters

from core.schemas import DayPlan, Meal, MealPlanLLM, PatientProfile, PlannedItem
from db.import_food import import_food_csv


@pytest.fixture(scope="module", autouse=True)
def _ensure_food_db() -> None:
    import_food_csv()


async def _run_mcp_checks() -> None:
    """Kết nối MCPServer qua stdio và gọi đủ 5 tool."""
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server.server"],
    )
    async with Client(params) as client:
        tools_res = await client.list_tools()
        tool_names = {t.name for t in tools_res.tools}
        assert {
            "calc_targets",
            "search_food",
            "check_allergen",
            "get_guideline",
            "score_menu",
        }.issubset(tool_names)

        profile = PatientProfile(
            patient_code="P0001",
            age=45,
            sex="male",
            height_cm=170.0,
            weight_kg=70.0,
            activity_level="moderate",
            conditions=["t2d"],
        )
        r1 = await client.call_tool("calc_targets", {"profile": profile.model_dump()})
        assert r1.structured_content is not None
        assert r1.structured_content["targets"]["target_kcal"] > 0

        r2 = await client.call_tool("search_food", {"query": "ca hoi", "limit": 5})
        assert r2.structured_content is not None
        foods = r2.structured_content["items"]
        assert len(foods) >= 1
        food_id = foods[0]["id"]

        r3 = await client.call_tool(
            "check_allergen",
            {"food_ids": [food_id], "allergens": ["seafood"]},
        )
        assert r3.structured_content is not None
        assert len(r3.structured_content["violations"]) == 1

        r4 = await client.call_tool("get_guideline", {"query": "tiểu đường", "disease": "t2d"})
        assert r4.structured_content is not None
        assert isinstance(r4.structured_content["snippets"], list)

        plan = MealPlanLLM(
            days=[
                DayPlan(
                    day=1,
                    meals=[Meal(meal="lunch", items=[PlannedItem(food_id=food_id, grams=100)])],
                )
            ]
        )
        r5 = await client.call_tool("score_menu", {"plan": plan.model_dump()})
        assert r5.structured_content is not None
        assert len(r5.structured_content["items"]) == 1

        # Kiểm tra trả lỗi có cấu trúc {"error": {"code", "message"}} khi food_id không tồn tại
        r_err = await client.call_tool(
            "check_allergen",
            {"food_ids": [999999], "allergens": ["seafood"]},
        )
        assert r_err.structured_content is not None
        assert "error" in r_err.structured_content
        assert r_err.structured_content["error"]["code"] == "CHECK_ALLERGEN_ERROR"
        assert "999999" in r_err.structured_content["error"]["message"]


@pytest.mark.mcp
def test_mcp_server_all_5_tools() -> None:
    """Chạy kiểm thử 5 tool qua MCP Client bằng asyncio.run."""
    asyncio.run(_run_mcp_checks())
