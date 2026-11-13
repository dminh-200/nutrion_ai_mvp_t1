"""Cân chỉnh khẩu phần bằng code theo thuật toán SPEC mục 6.5."""

from typing import Any

from core.food import load_food_db_from_sqlite
from core.nutrition import load_rules
from core.schemas import MealPlanLLM, NutritionTargets
from core.scoring import score_menu


def _round_to_5(value: float) -> float:
    """Làm tròn khối lượng về bội số của 5g."""
    return float(round(value / 5.0) * 5)


def adjust_portions(
    plan: MealPlanLLM,
    targets: NutritionTargets,
    food_db: list[dict[str, Any]] | None = None,
    rules: dict[str, Any] | None = None,
) -> tuple[MealPlanLLM, list[str]]:
    """Cân chỉnh grams mỗi món theo tỷ lệ target_kcal/kcal_thực_tế, tối đa 3 vòng."""
    items_db = food_db if food_db is not None else load_food_db_from_sqlite()
    cfg = rules or load_rules()
    v_cfg = cfg["verifier"]
    grams_min = float(v_cfg["grams_min"])
    grams_max = float(v_cfg["grams_max"])
    tol_pct = float(v_cfg["kcal_tolerance_pct"]) / 100.0

    adjusted = plan.model_copy(deep=True)
    trace_notes: list[str] = []

    for _ in range(3):
        scored = score_menu(adjusted, food_db=items_db)
        daily_map = {d["day"]: d["kcal"] for d in scored["daily_totals"]}
        changed = False

        for day_plan in adjusted.days:
            actual_kcal = daily_map.get(day_plan.day, 0.0)
            if actual_kcal <= 0:
                continue
            diff_ratio = abs(actual_kcal - targets.target_kcal) / targets.target_kcal
            if diff_ratio <= tol_pct:
                continue

            k = targets.target_kcal / actual_kcal
            for meal in day_plan.meals:
                for item in meal.items:
                    new_grams = _round_to_5(item.grams * k)
                    new_grams = max(grams_min, min(grams_max, new_grams))
                    if new_grams != item.grams:
                        item.grams = new_grams
                        changed = True

            trace_notes.append(f"Ngày {day_plan.day}: đã cân chỉnh khẩu phần ×{k:.2f}")

        if not changed:
            break

    return adjusted, trace_notes
