"""Mô-đun gọi LLM cho mốc M7 (tạm thời hỗ trợ LLM_MODE=mock tất định từ allowed_foods)."""

from typing import Any

from config.settings import get_settings
from core.schemas import (
    DayPlan,
    GuidelineSnippet,
    Meal,
    MealPlanLLM,
    NeedsResult,
    NutritionTargets,
    PlannedItem,
)


def generate_mock_meal_plan(
    *,
    days: int,
    allowed_foods: list[dict[str, Any]],
    targets: NutritionTargets,
    force_violation: bool = False,
) -> MealPlanLLM:
    """Sinh thực đơn tất định từ allowed_foods; hỗ trợ cờ force_violation để test."""
    if not allowed_foods:
        return MealPlanLLM(
            days=[],
            cannot_plan=True,
            reason="Không có thực phẩm hợp lệ trong danh sách cho phép.",
        )

    if force_violation:
        # Chọn 1 món năng lượng thấp nhất với khối lượng tối thiểu để ngay cả sau khi
        # portion_adjust kẹp ở ngưỡng grams_max (400g) thì tổng kcal ngày vẫn thấp hơn mục tiêu.
        low_food = min(allowed_foods, key=lambda f: float(f.get("kcal", 100.0)))
        bad_days: list[DayPlan] = []
        for d in range(1, days + 1):
            bad_days.append(
                DayPlan(
                    day=d,
                    meals=[
                        Meal(
                            meal="breakfast",
                            items=[PlannedItem(food_id=int(low_food["id"]), grams=10.0)],
                        )
                    ],
                )
            )
        return MealPlanLLM(days=bad_days, cannot_plan=False, reason="")

    dense_foods = [f for f in allowed_foods if float(f.get("kcal", 0.0)) >= 80.0]
    pool = dense_foods if len(dense_foods) >= 6 else list(allowed_foods)
    chosen = pool[:6]
    while len(chosen) < 6:
        chosen.append(pool[len(chosen) % len(pool)])

    per_item_kcal = targets.target_kcal / 6.0
    day_plans: list[DayPlan] = []

    for d in range(1, days + 1):
        meals: list[Meal] = []
        for idx, meal_name in enumerate(["breakfast", "lunch", "dinner"]):
            meal_items: list[PlannedItem] = []
            for food in chosen[idx * 2 : idx * 2 + 2]:
                kcal_100 = max(float(food.get("kcal", 100.0)), 20.0)
                grams = round((per_item_kcal / kcal_100) * 100.0, 1)
                grams = max(10.0, min(400.0, grams))
                meal_items.append(PlannedItem(food_id=int(food["id"]), grams=grams))
            meals.append(Meal(meal=meal_name, items=meal_items))  # type: ignore[arg-type]
        day_plans.append(DayPlan(day=d, meals=meals))

    return MealPlanLLM(days=day_plans, cannot_plan=False, reason="")


def call_planner_llm(
    *,
    days: int,
    allowed_foods: list[dict[str, Any]],
    targets: NutritionTargets,
    force_violation: bool = False,
    mode: str | None = None,
) -> tuple[MealPlanLLM, dict[str, int]]:
    """Gọi planner ở chế độ mock, trả về (MealPlanLLM, usage)."""
    active_mode = mode or get_settings().LLM_MODE
    if active_mode != "mock":
        # M7 chỉ triển khai LLM_MODE=mock; chế độ Gemini thật sẽ hoàn thiện ở M8.
        pass
    plan = generate_mock_meal_plan(
        days=days,
        allowed_foods=allowed_foods,
        targets=targets,
        force_violation=force_violation,
    )
    return plan, {"tokens_in": 0, "tokens_out": 0}


def call_explain_llm(
    *,
    needs: NeedsResult,
    targets: NutritionTargets,
    snippets: list[GuidelineSnippet],
    mode: str | None = None,
) -> tuple[str, dict[str, int]]:
    """Sinh văn bản giải thích thực đơn (chế độ mock) kèm trích dẫn nguồn từ snippets."""
    _ = mode or get_settings().LLM_MODE
    needs_str = ", ".join(needs.needs) if needs.needs else "duy_tri_can_bang"
    lines = [
        f"Thực đơn được xây dựng phù hợp với nhu cầu **{needs_str}** "
        f"và mức năng lượng mục tiêu **{targets.target_kcal:.0f} kcal/ngày**.",
    ]
    if snippets:
        for snip in snippets[:3]:
            lines.append(
                f"- Khuyến nghị dinh dưỡng cho {snip.disease}: {snip.text[:120].strip()}... "
                f"[{snip.source_name}, tr. {snip.page}]"
            )
    return "\n".join(lines), {"tokens_in": 0, "tokens_out": 0}
