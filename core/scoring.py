"""Tính toán giá trị dinh dưỡng thực đơn từ DB theo SPEC mục 7.3."""

from typing import Any

from core.food import load_food_db_from_sqlite
from core.schemas import MealPlanLLM, ScoredItem


def score_menu(
    plan: MealPlanLLM,
    food_db: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Tính dinh dưỡng từng món và tổng theo ngày từ food_db."""
    items_db = food_db if food_db is not None else load_food_db_from_sqlite()
    food_map = {int(f["id"]): f for f in items_db}

    scored_items: list[ScoredItem] = []
    daily_totals: list[dict[str, Any]] = []

    for day_plan in plan.days:
        day_sum = {
            "day": day_plan.day,
            "kcal": 0.0,
            "protein_g": 0.0,
            "fat_g": 0.0,
            "carb_g": 0.0,
            "fiber_g": 0.0,
            "sugar_g": 0.0,
            "sodium_mg": 0.0,
        }
        for meal in day_plan.meals:
            for item in meal.items:
                if item.food_id not in food_map:
                    raise ValueError(
                        f"Không tìm thấy food_id={item.food_id} trong cơ sở dữ liệu thực phẩm."
                    )
                food = food_map[item.food_id]
                ratio = item.grams / 100.0
                kcal = round(float(food.get("kcal") or 0.0) * ratio, 1)
                protein_g = round(float(food.get("protein_g") or 0.0) * ratio, 1)
                fat_g = round(float(food.get("fat_g") or 0.0) * ratio, 1)
                carb_g = round(float(food.get("carb_g") or 0.0) * ratio, 1)
                fiber_g = round(float(food.get("fiber_g") or 0.0) * ratio, 1)
                sugar_g = round(float(food.get("sugar_g") or 0.0) * ratio, 1)
                sodium_mg = round(float(food.get("sodium_mg") or 0.0) * ratio, 1)

                scored_items.append(
                    ScoredItem(
                        food_id=item.food_id,
                        grams=item.grams,
                        name_vi=food["name_vi"],
                        kcal=kcal,
                        protein_g=protein_g,
                        fat_g=fat_g,
                        carb_g=carb_g,
                        sodium_mg=sodium_mg,
                        fiber_g=fiber_g,
                        sugar_g=sugar_g,
                    )
                )
                day_sum["kcal"] = round(day_sum["kcal"] + kcal, 1)
                day_sum["protein_g"] = round(day_sum["protein_g"] + protein_g, 1)
                day_sum["fat_g"] = round(day_sum["fat_g"] + fat_g, 1)
                day_sum["carb_g"] = round(day_sum["carb_g"] + carb_g, 1)
                day_sum["fiber_g"] = round(day_sum["fiber_g"] + fiber_g, 1)
                day_sum["sugar_g"] = round(day_sum["sugar_g"] + sugar_g, 1)
                day_sum["sodium_mg"] = round(day_sum["sodium_mg"] + sodium_mg, 1)

        daily_totals.append(day_sum)

    return {"items": scored_items, "daily_totals": daily_totals}
