"""Kiểm thử các hàm thuần tính toán dinh dưỡng trong core/nutrition.py."""

import pytest

from core.nutrition import (
    build_targets,
    calc_bmi,
    calc_bmr,
    calc_macros,
    calc_target_kcal,
    calc_tdee,
    load_rules,
)
from core.schemas import NeedsResult, PatientProfile


def _make_profile(**overrides) -> PatientProfile:
    base = {
        "patient_code": "P0001",
        "age": 40,
        "sex": "male",
        "height_cm": 170.0,
        "weight_kg": 70.0,
        "activity_level": "moderate",
        "conditions": ["t2d"],
    }
    base.update(overrides)
    return PatientProfile(**base)


def test_hand_calc_example_1_male_t2d() -> None:
    """Ví dụ tính tay 1: Nam, 40 tuổi, 170cm, 70kg, moderate, t2d."""
    # BMI = 70 / 1.7^2 = 24.22 -> 24.2
    # BMR = 10*70 + 6.25*170 - 5*40 + 5 = 700 + 1062.5 - 200 + 5 = 1567.5
    # TDEE = 1567.5 * 1.55 = 2429.625 -> 2429.6
    # target_kcal = round(2429.6 / 10) * 10 = 2430.0
    # macro t2d: carb 45%, protein 20%, fat 35%
    profile = _make_profile()
    needs = NeedsResult(needs=["kiem_soat_duong_huyet"], rule_refs=["NEED_T2D"])
    targets = build_targets(profile, needs)

    assert targets.bmi == 24.2
    assert targets.bmr == 1567.5
    assert targets.tdee == 2429.6
    assert targets.target_kcal == 2430.0
    assert targets.carb_g == round(2430.0 * 0.45 / 4.0, 1)
    assert targets.protein_g == round(2430.0 * 0.20 / 4.0, 1)
    assert targets.fat_g == round(2430.0 * 0.35 / 9.0, 1)


def test_hand_calc_example_2_female_obesity_floor() -> None:
    """Ví dụ tính tay 2: Nữ, 55 tuổi, 155cm, 62kg, sedentary, obesity -> chạm sàn 1200."""
    # BMR = 10*62 + 6.25*155 - 5*55 - 161 = 620 + 968.75 - 275 - 161 = 1152.75
    # TDEE = 1152.75 * 1.2 = 1383.3
    # giam_can: 1383.3 - 500 = 883.3 -> áp sàn nữ 1200.0
    profile = _make_profile(
        sex="female",
        age=55,
        height_cm=155.0,
        weight_kg=62.0,
        activity_level="sedentary",
        conditions=["obesity"],
    )
    needs = NeedsResult(needs=["giam_can"], rule_refs=["NEED_WEIGHT"])
    targets = build_targets(profile, needs)

    assert targets.bmr == 1152.8
    assert targets.tdee == 1383.3
    assert targets.kcal_floor == 1200.0
    assert targets.target_kcal == 1200.0


def test_calc_bmi_rounding() -> None:
    """calc_bmi làm tròn 1 chữ số thập phân."""
    assert calc_bmi(68.0, 165.0) == 25.0


def test_calc_bmr_male_vs_female() -> None:
    """Chênh lệch BMR nam và nữ cùng chỉ số đúng bằng 166 kcal."""
    male = calc_bmr("male", 65.0, 168.0, 35)
    female = calc_bmr("female", 65.0, 168.0, 35)
    assert male - female == 166.0


@pytest.mark.parametrize(
    ("activity", "factor"),
    [
        ("sedentary", 1.2),
        ("light", 1.375),
        ("moderate", 1.55),
        ("active", 1.725),
        ("very_active", 1.9),
    ],
)
def test_calc_tdee_all_activities(activity: str, factor: float) -> None:
    """TDEE nhân đúng hệ số hoạt động từ rules.yaml."""
    assert calc_tdee(1000.0, activity) == round(1000.0 * factor, 1)


def test_calc_target_kcal_male_floor() -> None:
    """Nam giảm cân không thấp hơn sàn 1500 kcal."""
    profile = _make_profile(sex="male", conditions=["obesity"])
    needs = NeedsResult(needs=["giam_can"], rule_refs=["NEED_WEIGHT"])
    kcal, floor = calc_target_kcal(1700.0, needs, profile)
    assert floor == 1500.0
    assert kcal == 1500.0


def test_calc_macros_priority_t2d_over_obesity() -> None:
    """Khi có cả t2d và obesity, ưu tiên macro của kiem_soat_duong_huyet."""
    needs = NeedsResult(
        needs=["giam_can", "kiem_soat_duong_huyet"],
        rule_refs=["NEED_WEIGHT", "NEED_T2D"],
    )
    p, f, c, source = calc_macros(2000.0, needs)
    assert source == "kiem_soat_duong_huyet"
    assert (p, f, c) == (100.0, 77.8, 225.0)


def test_calc_macros_default() -> None:
    """Không có bệnh lý đặc biệt thì dùng macro mặc định."""
    needs = NeedsResult(needs=["duy_tri_can_bang"], rule_refs=["NEED_DEFAULT"])
    _, _, _, source = calc_macros(2000.0, needs)
    assert source == "defaults"


def test_multi_disease_merge_sodium_sugar_fiber() -> None:
    """Đa bệnh: sodium/sugar lấy min, fiber lấy max."""
    profile = _make_profile(conditions=["t2d", "htn"])
    needs = NeedsResult(
        needs=["kiem_soat_duong_huyet", "giam_natri"],
        rule_refs=["NEED_T2D", "NEED_HTN"],
    )
    targets = build_targets(profile, needs)
    assert targets.sodium_max_mg == 2000.0
    assert targets.sugar_max_g == 25.0
    assert targets.fiber_min_g == 25.0


def test_load_rules_has_todo_verify() -> None:
    """rules.yaml giữ nguyên cấu trúc và có mục verifier."""
    rules = load_rules()
    assert rules["version"] == 1
    assert "verifier" in rules


def test_build_targets_missing_sugar_default_uses_fallback() -> None:
    """Nếu defaults thiếu sugar_max_g và không có t2d thì dùng giá trị dự phòng 50g."""
    profile = _make_profile(conditions=["htn"])
    needs = NeedsResult(needs=["giam_natri"], rule_refs=["NEED_HTN"])
    targets = build_targets(profile, needs)
    assert targets.sugar_max_g == 50.0
    assert targets.sodium_max_mg == 2000.0


def test_build_targets_supports_scalar_and_dict_value_formats() -> None:
    """Hỗ trợ cả định dạng số trực tiếp X và dict {value: X} trong rules."""
    custom_rules = {
        "version": 1,
        "activity_factors": {"moderate": {"value": 1.55}},
        "energy": {
            "deficit_kcal": 400,
            "kcal_floor": {"male": 1400, "female": {"value": 1150}},
        },
        "needs": {
            "giam_can": {
                "macro_pct": {"carb": {"value": 40}, "protein": 30, "fat": 30},
            },
            "giam_natri": {
                "sodium_max_mg": 1800,
                "sugar_max_g": 30,
                "fiber_min_g": {"value": 28},
            },
        },
        "defaults": {
            "macro_pct": {"carb": 55, "protein": 15, "fat": 30},
            "sodium_max_mg": {"value": 2300},
            "fiber_min_g": 20,
        },
        "priority": ["giam_can"],
    }
    profile = _make_profile(conditions=["obesity", "htn"])
    needs = NeedsResult(needs=["giam_can", "giam_natri"], rule_refs=["NEED_WEIGHT", "NEED_HTN"])
    targets = build_targets(profile, needs, rules=custom_rules)
    assert targets.kcal_floor == 1400.0
    assert targets.sodium_max_mg == 1800.0
    assert targets.sugar_max_g == 30.0
    assert targets.fiber_min_g == 28.0
    assert targets.protein_g == round(targets.target_kcal * 0.30 / 4.0, 1)
