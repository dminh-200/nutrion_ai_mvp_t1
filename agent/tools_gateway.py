"""Gateway gọi 5 tool dinh dưỡng theo chế độ direct hoặc mcp (SPEC mục 7.5)."""

import asyncio
import sys
import threading
from typing import Any

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from config.settings import get_settings
from core.allergen import check_allergen as core_check_allergen
from core.classify import classify_needs
from core.food import search_food as core_search_food
from core.nutrition import build_targets
from core.schemas import (
    GuidelineSnippet,
    MealPlanLLM,
    NeedsResult,
    NutritionTargets,
    PatientProfile,
    ScoredItem,
    Violation,
)
from core.scoring import score_menu as core_score_menu


class _MCPSessionRunner:
    """Quản lý kết nối MCP stdio chạy trên event loop riêng trong suốt phiên."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self._close_event: asyncio.Event | None = None
        self._client: Client | None = None
        self._connect_error: BaseException | None = None
        self._thread = threading.Thread(target=self._run_thread, daemon=True)
        self._thread.start()

    def _run_thread(self) -> None:
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._session_main())
        finally:
            self._loop.close()

    async def _session_main(self) -> None:
        self._close_event = asyncio.Event()
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_server.server"],
        )
        try:
            async with Client(params) as client:
                self._client = client
                self._ready.set()
                await self._close_event.wait()
        except BaseException as exc:
            self._connect_error = exc
            self._ready.set()
        finally:
            self._client = None

    def ensure_connected(self) -> Client:
        self._ready.wait(timeout=30)
        if self._connect_error is not None:
            raise RuntimeError(f"Lỗi kết nối MCP server: {self._connect_error}")
        if self._client is None:
            raise RuntimeError("MCP client chưa sẵn sàng hoặc đã đóng.")
        return self._client

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        client = self.ensure_connected()

        async def _call() -> dict[str, Any]:
            result = await client.call_tool(name, arguments)
            if result.structured_content is not None:
                return dict(result.structured_content)
            return {}

        fut = asyncio.run_coroutine_threadsafe(_call(), self._loop)
        data = fut.result(timeout=30)
        if "error" in data:
            err = data["error"]
            raise RuntimeError(f"[{err.get('code', 'MCP_ERROR')}] {err.get('message', '')}")
        return data

    def close(self) -> None:
        if self._close_event is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._close_event.set)
        self._thread.join(timeout=10)


class ToolsGateway:
    """Cổng gọi 5 tool thống nhất cho cả TOOLS_MODE=direct và TOOLS_MODE=mcp."""

    def __init__(self, mode: str | None = None) -> None:
        self.mode = mode or get_settings().TOOLS_MODE
        self._mcp_runner: _MCPSessionRunner | None = (
            _MCPSessionRunner() if self.mode == "mcp" else None
        )

    def __enter__(self) -> "ToolsGateway":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        """Đóng kết nối MCP sạch sẽ nếu đang mở."""
        if self._mcp_runner is not None:
            self._mcp_runner.close()
            self._mcp_runner = None

    def calc_targets(self, profile: PatientProfile) -> dict[str, Any]:
        """Tính nhu cầu và mục tiêu dinh dưỡng."""
        if self.mode == "mcp":
            assert self._mcp_runner is not None
            data = self._mcp_runner.call_tool("calc_targets", {"profile": profile.model_dump()})
            return {
                "targets": NutritionTargets(**data["targets"]),
                "needs": NeedsResult(**data["needs"]),
            }
        needs = classify_needs(profile)
        targets = build_targets(profile, needs)
        return {"targets": targets, "needs": needs}

    def search_food(
        self,
        query: str = "",
        max_kcal_per_100g: float | None = None,
        exclude_allergens: list[str] | None = None,
        exclude_tags: list[str] | None = None,
        max_purine_level: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Tìm kiếm thực phẩm."""
        if self.mode == "mcp":
            assert self._mcp_runner is not None
            data = self._mcp_runner.call_tool(
                "search_food",
                {
                    "query": query,
                    "max_kcal_per_100g": max_kcal_per_100g,
                    "exclude_allergens": exclude_allergens,
                    "exclude_tags": exclude_tags,
                    "max_purine_level": max_purine_level,
                    "limit": limit,
                },
            )
            return list(data.get("items", []))
        return core_search_food(
            query=query,
            max_kcal_per_100g=max_kcal_per_100g,
            exclude_allergens=exclude_allergens,
            exclude_tags=exclude_tags,
            max_purine_level=max_purine_level,
            limit=limit,
        )

    def check_allergen(self, food_ids: list[int], allergens: list[str]) -> list[Violation]:
        """Kiểm tra dị ứng cho danh sách food_id."""
        if self.mode == "mcp":
            assert self._mcp_runner is not None
            data = self._mcp_runner.call_tool(
                "check_allergen",
                {"food_ids": food_ids, "allergens": allergens},
            )
            return [Violation(**v) for v in data.get("violations", [])]
        return core_check_allergen(food_ids=food_ids, allergens=allergens)

    def get_guideline(
        self, query: str, disease: str | None = None, k: int = 4
    ) -> list[GuidelineSnippet]:
        """Truy xuất đoạn hướng dẫn dinh dưỡng."""
        if self.mode == "mcp":
            assert self._mcp_runner is not None
            data = self._mcp_runner.call_tool(
                "get_guideline",
                {"query": query, "disease": disease, "k": k},
            )
            return [GuidelineSnippet(**s) for s in data.get("snippets", [])]
        from rag.retrieve import retrieve_guidelines

        return retrieve_guidelines(query=query, disease=disease, k=k)

    def score_menu(self, plan: MealPlanLLM) -> dict[str, Any]:
        """Tính dinh dưỡng từng món và tổng theo ngày."""
        if self.mode == "mcp":
            assert self._mcp_runner is not None
            data = self._mcp_runner.call_tool("score_menu", {"plan": plan.model_dump()})
            return {
                "items": [ScoredItem(**i) for i in data.get("items", [])],
                "daily_totals": list(data.get("daily_totals", [])),
            }
        return core_score_menu(plan)
