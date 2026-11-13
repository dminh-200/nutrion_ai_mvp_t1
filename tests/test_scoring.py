"""Kiểm thử tính dinh dưỡng thực đơn trong core/scoring.py."""

import pytest

from core.schemas import DayPlan, Meal, MealPlanLLM, PlannedItem
from core.scoring import score_menu

SAMPLE_DB = [
    {
        "id": 1,
        "name_vi": "Cơm gạo tẻ",
        "kcal": 130.0,
        "protein_g": 2.7,
        "fat_g": 0.3,
        "carb_g": 28.2,
        "fiber_g": 0.4,
        "sugar_g": 0.1,
        "sodium_mg": 1.0,
    },
    {
        "id": 2,
        "name_vi": "Ức gà luộc",
        "kcal": 165.0,
        "protein_g": 31.0,
        "fat_g": 3.6,
        "carb_g": 0.0,
        "fiber_g": 0.0,
        "sugar_g": 0.0,
        "sodium_mg": 74.0,
    },
]


def test_score_menu_calculates_items_and_daily_totals() -> None:
    """Tính đúng kcal và macro theo gram."""
    plan = MealPlanLLM(
        days=[
            DayPlan(
                day=1,
                meals=[
                    Meal(
                        meal="lunch",
                        items=[
                            PlannedItem(food_id=1, grams=200.0),
                            PlannedItem(food_id=2, grams=100.0),
                        ],
                    )
                ],
            )
        ]
    )
    res = score_menu(plan, food_db=SAMPLE_DB)
    assert len(res["items"]) == 2
    assert res["daily_totals"][0]["kcal"] == 260.0 + 165.0
    assert res["daily_totals"][0]["protein_g"] == 5.4 + 31.0


def test_score_menu_missing_food_raises() -> None:
    """Món không tồn tại phải ném ValueError rõ ràng."""
    plan = MealPlanLLM(
        days=[
            DayPlan(
                day=1,
                meals=[Meal(meal="lunch", items=[PlannedItem(food_id=999, grams=100)])],
            )
        ]
    )
    with pytest.raises(ValueError, match="food_id=999"):
        score_menu(plan, food_db=SAMPLE_DB)
