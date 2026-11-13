"""Kiểm thử các Pydantic schema trong core/schemas.py."""

import pytest
from pydantic import ValidationError

from core.schemas import (
    DayPlan,
    GuidelineSnippet,
    Meal,
    MealPlanLLM,
    NeedsResult,
    NutritionTargets,
    PatientProfile,
    PlannedItem,
    RiskResult,
    ScoredItem,
    Violation,
)


def test_patient_profile_valid() -> None:
    """PatientProfile hợp lệ với đầy đủ ràng buộc."""
    profile = PatientProfile(
        patient_code="P0001",
        age=45,
        sex="male",
        height_cm=170.0,
        weight_kg=72.5,
        activity_level="moderate",
        conditions=["t2d", "htn"],
        allergens=["seafood"],
    )
    assert profile.days == 3
    assert profile.ckd_stage == 0


@pytest.mark.parametrize(
    "bad_kwargs",
    [
        {"age": 0},
        {"age": 121},
        {"height_cm": 40.0},
        {"weight_kg": 450.0},
        {"ckd_stage": 6},
        {"days": 8},
        {"preferences_text": "a" * 501},
        {"conditions": ["unknown_disease"]},
    ],
)
def test_patient_profile_invalid_constraints(bad_kwargs: dict) -> None:
    """PatientProfile từ chối giá trị ngoài ngưỡng."""
    base = {
        "patient_code": "P0001",
        "age": 40,
        "sex": "female",
        "height_cm": 160.0,
        "weight_kg": 60.0,
        "activity_level": "light",
        "conditions": ["t2d"],
    }
    base.update(bad_kwargs)
    with pytest.raises(ValidationError):
        PatientProfile(**base)


def test_meal_plan_and_other_schemas() -> None:
    """Kiểm thử khởi tạo các schema còn lại."""
    item = PlannedItem(food_id=1, grams=150.0)
    meal = Meal(meal="lunch", items=[item])
    day = DayPlan(day=1, meals=[meal])
    plan = MealPlanLLM(days=[day])
    assert plan.cannot_plan is False

    scored = ScoredItem(
        food_id=1,
        grams=150.0,
        name_vi="Cơm trắng",
        kcal=195.0,
        protein_g=4.0,
        fat_g=0.4,
        carb_g=42.0,
        sodium_mg=2.0,
    )
    assert scored.kcal == 195.0

    targets = NutritionTargets(
        bmi=22.5,
        bmr=1500.0,
        tdee=2100.0,
        target_kcal=1800.0,
        protein_g=90.0,
        fat_g=60.0,
        carb_g=225.0,
        fiber_min_g=25.0,
        sodium_max_mg=2000.0,
        sugar_max_g=25.0,
        kcal_floor=1500.0,
        rationale=["R1"],
    )
    assert targets.target_kcal == 1800.0
    assert NeedsResult(needs=["kiem_soat_duong"]).needs == ["kiem_soat_duong"]
    assert RiskResult(high_risk=False).high_risk is False
    assert Violation(code="ALLERGEN", message_vi="Dị ứng").code == "ALLERGEN"
    assert (
        GuidelineSnippet(
            text="Ăn nhạt",
            source_name="BYT",
            year=2023,
            page=12,
            disease="htn",
            score=0.9,
        ).disease
        == "htn"
    )
