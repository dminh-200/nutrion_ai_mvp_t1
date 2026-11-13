"""Kiểm thử cân chỉnh khẩu phần bằng code trong core/portion.py."""

from core.portion import adjust_portions
from core.schemas import DayPlan, Meal, MealPlanLLM, NutritionTargets, PlannedItem
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


def _targets(target_kcal: float) -> NutritionTargets:
    return NutritionTargets(
        bmi=22.0,
        bmr=1500.0,
        tdee=2000.0,
        target_kcal=target_kcal,
        protein_g=80.0,
        fat_g=50.0,
        carb_g=200.0,
        fiber_min_g=20.0,
        sodium_max_mg=2000.0,
        sugar_max_g=25.0,
        kcal_floor=1200.0,
    )


def test_adjust_portions_converges() -> None:
    """Ca hội tụ: thực đơn lệch kcal được cân chỉnh về gần mục tiêu."""
    # Ban đầu: 100g cơm (130) + 100g gà (165) = 295 kcal; mục tiêu 590 kcal -> k ~ 2.0
    plan = MealPlanLLM(
        days=[
            DayPlan(
                day=1,
                meals=[
                    Meal(
                        meal="lunch",
                        items=[
                            PlannedItem(food_id=1, grams=100.0),
                            PlannedItem(food_id=2, grams=100.0),
                        ],
                    )
                ],
            )
        ]
    )
    adjusted, notes = adjust_portions(plan, _targets(590.0), food_db=SAMPLE_DB)
    scored = score_menu(adjusted, food_db=SAMPLE_DB)
    actual_kcal = scored["daily_totals"][0]["kcal"]
    assert abs(actual_kcal - 590.0) / 590.0 <= 0.10
    assert any("đã cân chỉnh khẩu phần" in n for n in notes)


def test_adjust_portions_clamped_at_grams_max() -> None:
    """Ca bị kẹp: mục tiêu quá lớn khiến grams bị kẹp ở mức tối đa 400g."""
    plan = MealPlanLLM(
        days=[
            DayPlan(
                day=1,
                meals=[Meal(meal="lunch", items=[PlannedItem(food_id=1, grams=300.0)])],
            )
        ]
    )
    adjusted, _ = adjust_portions(plan, _targets(3000.0), food_db=SAMPLE_DB)
    assert adjusted.days[0].meals[0].items[0].grams == 400.0
