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


def test_adjust_portions_lifts_below_kcal_floor_within_10pct_tol() -> None:
    """Khi target_kcal == kcal_floor (1200) và thực đơn hụt nhẹ (1162 kcal), phải kéo >= 1200."""
    db_with_oil = [
        *SAMPLE_DB,
        {
            "id": 3,
            "name_vi": "Dầu ô liu",
            "kcal": 900.0,
            "protein_g": 0.0,
            "fat_g": 100.0,
            "carb_g": 0.0,
            "fiber_g": 0.0,
            "sugar_g": 0.0,
            "sodium_mg": 0.0,
        },
    ]
    # 1200 kcal (45% carb=135g, 25% protein=75g, 30% fat=40g)
    targets = NutritionTargets(
        bmi=30.4,
        bmr=1405.0,
        tdee=1685.0,
        target_kcal=1200.0,
        protein_g=75.0,
        fat_g=40.0,
        carb_g=135.0,
        fiber_min_g=20.0,
        sodium_max_mg=2000.0,
        sugar_max_g=25.0,
        kcal_floor=1200.0,
    )
    # 440g cơm + 215g gà + 25g dầu ~ 1152 kcal (< sàn 1200 nhưng lệch < 10%)
    plan = MealPlanLLM(
        days=[
            DayPlan(
                day=1,
                meals=[
                    Meal(
                        meal="lunch",
                        items=[
                            PlannedItem(food_id=1, grams=220.0),
                            PlannedItem(food_id=2, grams=110.0),
                            PlannedItem(food_id=3, grams=15.0),
                        ],
                    ),
                    Meal(
                        meal="dinner",
                        items=[
                            PlannedItem(food_id=1, grams=220.0),
                            PlannedItem(food_id=2, grams=105.0),
                            PlannedItem(food_id=3, grams=10.0),
                        ],
                    ),
                ],
            )
        ]
    )
    adjusted, _ = adjust_portions(plan, targets, food_db=db_with_oil)
    tot = score_menu(adjusted, food_db=db_with_oil)["daily_totals"][0]
    assert tot["kcal"] >= 1200.0
    assert abs(tot["kcal"] - 1200.0) / 1200.0 <= 0.10


def test_adjust_portions_rebalances_macro_skew_without_changing_food_ids() -> None:
    """Khi đạm/béo vượt trần còn carb thiếu dưới sàn, tinh chỉnh gram giữ nguyên food_id."""
    db_with_oil = [
        *SAMPLE_DB,
        {
            "id": 3,
            "name_vi": "Dầu ô liu",
            "kcal": 900.0,
            "protein_g": 0.0,
            "fat_g": 100.0,
            "carb_g": 0.0,
            "fiber_g": 0.0,
            "sugar_g": 0.0,
            "sodium_mg": 0.0,
        },
    ]
    targets = NutritionTargets(
        bmi=26.5,
        bmr=1549.0,
        tdee=1860.0,
        target_kcal=1860.0,
        protein_g=93.0,
        fat_g=72.0,
        carb_g=209.0,
        fiber_min_g=25.0,
        sodium_max_mg=2000.0,
        sugar_max_g=25.0,
        kcal_floor=1500.0,
    )
    # Quá nhiều gà (400g -> P=124g > trần) và dầu (85g -> F=99g > trần), thiếu cơm
    plan = MealPlanLLM(
        days=[
            DayPlan(
                day=1,
                meals=[
                    Meal(
                        meal="lunch",
                        items=[
                            PlannedItem(food_id=1, grams=200.0),
                            PlannedItem(food_id=2, grams=200.0),
                            PlannedItem(food_id=3, grams=45.0),
                        ],
                    ),
                    Meal(
                        meal="dinner",
                        items=[
                            PlannedItem(food_id=1, grams=200.0),
                            PlannedItem(food_id=2, grams=200.0),
                            PlannedItem(food_id=3, grams=40.0),
                        ],
                    ),
                ],
            )
        ]
    )
    adjusted, _ = adjust_portions(plan, targets, food_db=db_with_oil)
    tot = score_menu(adjusted, food_db=db_with_oil)["daily_totals"][0]
    assert abs(tot["kcal"] - 1860.0) / 1860.0 <= 0.10
    assert abs(tot["protein_g"] - 93.0) / 93.0 <= 0.15
    assert abs(tot["fat_g"] - 72.0) / 72.0 <= 0.15
    assert abs(tot["carb_g"] - 209.0) / 209.0 <= 0.15
    orig_ids = [it.food_id for m in plan.days[0].meals for it in m.items]
    new_ids = [it.food_id for m in adjusted.days[0].meals for it in m.items]
    assert new_ids == orig_ids
