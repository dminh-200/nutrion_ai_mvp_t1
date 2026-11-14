"""MCP server (stdio) expose 5 tool dinh dưỡng theo SPEC mục 7.4."""

import logging
import sys
import time
from pathlib import Path
from typing import Any

from mcp.server import MCPServer

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from core.allergen import check_allergen as core_check_allergen  # noqa: E402
from core.classify import classify_needs  # noqa: E402
from core.food import search_food as core_search_food  # noqa: E402
from core.nutrition import build_targets  # noqa: E402
from core.schemas import MealPlanLLM, PatientProfile  # noqa: E402
from core.scoring import score_menu as core_score_menu  # noqa: E402

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [MCP] %(levelname)s %(message)s",
)
logger = logging.getLogger("mcp_server")

mcp = MCPServer("nutrition-ai-mvp")


def _err(code: str, message: str) -> dict[str, Any]:
    return {"error": {"code": code, "message": message}}


@mcp.tool(structured_output=True)
def calc_targets(profile: PatientProfile) -> dict[str, Any]:
    """Tính toán nhu cầu dinh dưỡng và mục tiêu kcal/macro từ hồ sơ bệnh nhân."""
    t0 = time.perf_counter()
    try:
        needs = classify_needs(profile)
        targets = build_targets(profile, needs)
        return {
            "targets": targets.model_dump(),
            "needs": needs.model_dump(),
        }
    except Exception as exc:
        return _err("CALC_TARGETS_ERROR", str(exc))
    finally:
        logger.info("tool=calc_targets duration_ms=%.2f", (time.perf_counter() - t0) * 1000)


@mcp.tool(structured_output=True)
def search_food(
    query: str = "",
    max_kcal_per_100g: float | None = None,
    exclude_allergens: list[str] | None = None,
    exclude_tags: list[str] | None = None,
    max_purine_level: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Tìm kiếm thực phẩm theo tên không dấu và các bộ lọc dinh dưỡng, dị ứng."""
    t0 = time.perf_counter()
    try:
        items = core_search_food(
            query=query,
            max_kcal_per_100g=max_kcal_per_100g,
            exclude_allergens=exclude_allergens,
            exclude_tags=exclude_tags,
            max_purine_level=max_purine_level,
            limit=limit,
        )
        return {"items": items}
    except Exception as exc:
        return _err("SEARCH_FOOD_ERROR", str(exc))
    finally:
        logger.info("tool=search_food duration_ms=%.2f", (time.perf_counter() - t0) * 1000)


@mcp.tool(structured_output=True)
def check_allergen(food_ids: list[int], allergens: list[str]) -> dict[str, Any]:
    """Kiểm tra danh sách food_id có chứa dị nguyên của bệnh nhân hay không."""
    t0 = time.perf_counter()
    try:
        violations = core_check_allergen(food_ids=food_ids, allergens=allergens)
        return {"violations": [v.model_dump() for v in violations]}
    except Exception as exc:
        return _err("CHECK_ALLERGEN_ERROR", str(exc))
    finally:
        logger.info("tool=check_allergen duration_ms=%.2f", (time.perf_counter() - t0) * 1000)


@mcp.tool(structured_output=True)
def get_guideline(query: str, disease: str | None = None, k: int = 4) -> dict[str, Any]:
    """Truy xuất đoạn hướng dẫn dinh dưỡng từ RAG (ChromaDB)."""
    t0 = time.perf_counter()
    try:
        from rag.retrieve import retrieve

        snippets = retrieve(query=query, disease=disease, k=k)
        return {"snippets": [s.model_dump() for s in snippets]}
    except Exception as exc:
        return _err("GET_GUIDELINE_ERROR", str(exc))
    finally:
        logger.info("tool=get_guideline duration_ms=%.2f", (time.perf_counter() - t0) * 1000)


@mcp.tool(structured_output=True)
def score_menu(plan: MealPlanLLM) -> dict[str, Any]:
    """Tính lại giá trị dinh dưỡng từng món và tổng theo ngày từ cơ sở dữ liệu."""
    t0 = time.perf_counter()
    try:
        res = core_score_menu(plan)
        return {
            "items": [item.model_dump() for item in res["items"]],
            "daily_totals": res["daily_totals"],
        }
    except Exception as exc:
        return _err("SCORE_MENU_ERROR", str(exc))
    finally:
        logger.info("tool=score_menu duration_ms=%.2f", (time.perf_counter() - t0) * 1000)


if __name__ == "__main__":
    mcp.run(transport="stdio")
