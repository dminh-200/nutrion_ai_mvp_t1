"""Bộ kiểm chứng thực đơn tối thiểu cho mốc M7 (KCAL_OUT_OF_RANGE, ALLERGEN) qua ToolsGateway."""

from typing import Any

from agent.tools_gateway import ToolsGateway
from core.nutrition import load_rules
from core.schemas import (
    MealPlanLLM,
    NutritionTargets,
    PatientProfile,
    Violation,
)


def verify_meal_plan(
    plan: MealPlanLLM,
    profile: PatientProfile,
    targets: NutritionTargets,
    gateway: ToolsGateway,
    rules: dict[str, Any] | None = None,
) -> tuple[list[Violation], list[dict[str, Any]]]:
    """Kiểm chứng thực đơn tối thiểu (KCAL, ALLERGEN) qua ToolsGateway."""
    if plan.cannot_plan or not plan.days:
        return [
            Violation(
                code="CANNOT_PLAN",
                message_vi=plan.reason or "Không thể lập thực đơn hợp lệ.",
            )
        ], []

    cfg = rules or load_rules()
    kcal_tol = float(cfg["verifier"]["kcal_tolerance_pct"]) / 100.0

    violations: list[Violation] = []
    food_ids: list[int] = [
        item.food_id
        for day_plan in plan.days
        for meal in day_plan.meals
        for item in meal.items
    ]

    if food_ids and profile.allergens:
        allergen_violations = gateway.check_allergen(
            food_ids=food_ids,
            allergens=list(profile.allergens),
        )
        violations.extend(allergen_violations)

    scored = gateway.score_menu(plan)
    daily_totals: list[dict[str, Any]] = list(scored["daily_totals"])

    for day_tot in daily_totals:
        day_num = int(day_tot["day"])
        kcal = float(day_tot["kcal"])
        if targets.target_kcal > 0:
            diff_ratio = abs(kcal - targets.target_kcal) / targets.target_kcal
            if diff_ratio > kcal_tol:
                violations.append(
                    Violation(
                        code="KCAL_OUT_OF_RANGE",
                        message_vi=(
                            f"Ngày {day_num}: {kcal:.1f} kcal lệch mục tiêu "
                            f"{targets.target_kcal:.1f} kcal quá {kcal_tol * 100:.0f}%."
                        ),
                        day=day_num,
                    )
                )

    return violations, daily_totals
