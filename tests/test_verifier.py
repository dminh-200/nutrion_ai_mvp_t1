"""Kiểm thử 12 mã vi phạm verifier (SPEC 9.3 + FIBER_LOW) và cảnh báo DATA_MISSING."""

from copy import deepcopy
from typing import Any

from agent.tools_gateway import ToolsGateway
from agent.verifier import verify_meal_plan
from core.nutrition import load_rules
from core.schemas import (
    DayPlan,
    Meal,
    MealPlanLLM,
    NeedsResult,
    NutritionTargets,
    PatientProfile,
    PlannedItem,
)

SAMPLE_FOOD_DB: list[dict[str, Any]] = [
    {
        "id": 1,
        "code": "T01",
        "name_vi": "Cơm gạo tẻ",
        "food_group": "ngu_coc",
        "purine_level": "low",
        "allergen_tags": "",
        "tags": "tinh_bot",
        "kcal": 130.0,
        "protein_g": 2.7,
        "fat_g": 0.3,
        "carb_g": 28.2,
        "fiber_g": 0.4,
        "sugar_g": 0.1,
        "sodium_mg": 2.0,
    },
    {
        "id": 2,
        "code": "T02",
        "name_vi": "Ức gà luộc",
        "food_group": "thit_gia_cam",
        "purine_level": "medium",
        "allergen_tags": "",
        "tags": "dam_nac",
        "kcal": 140.0,
        "protein_g": 29.5,
        "fat_g": 2.5,
        "carb_g": 0.0,
        "fiber_g": 0.0,
        "sugar_g": 0.0,
        "sodium_mg": 65.0,
    },
    {
        "id": 3,
        "code": "T03",
        "name_vi": "Dầu ô liu",
        "food_group": "dau_hat",
        "purine_level": "low",
        "allergen_tags": "",
        "tags": "chat_beo_tot",
        "kcal": 884.0,
        "protein_g": 0.0,
        "fat_g": 100.0,
        "carb_g": 0.0,
        "fiber_g": 0.0,
        "sugar_g": 0.0,
        "sodium_mg": 0.0,
    },
    {
        "id": 4,
        "code": "T04",
        "name_vi": "Tôm sú hấp",
        "food_group": "thuy_san",
        "purine_level": "medium",
        "allergen_tags": "seafood",
        "tags": "hai_san",
        "kcal": 99.0,
        "protein_g": 20.0,
        "fat_g": 1.0,
        "carb_g": 0.0,
        "fiber_g": 0.0,
        "sugar_g": 0.0,
        "sodium_mg": 120.0,
    },
    {
        "id": 5,
        "code": "T05",
        "name_vi": "Bánh ngọt kem",
        "food_group": "banh_keo",
        "purine_level": "low",
        "allergen_tags": "gluten,egg",
        "tags": "do_ngot",
        "kcal": 350.0,
        "protein_g": 4.0,
        "fat_g": 15.0,
        "carb_g": 50.0,
        "fiber_g": 1.0,
        "sugar_g": 30.0,
        "sodium_mg": 150.0,
    },
    {
        "id": 6,
        "code": "T06",
        "name_vi": "Dưa cải muối",
        "food_group": "rau_cu",
        "purine_level": "low",
        "allergen_tags": "",
        "tags": "do_muoi",
        "kcal": 25.0,
        "protein_g": 1.0,
        "fat_g": 0.2,
        "carb_g": 4.5,
        "fiber_g": 1.5,
        "sugar_g": 1.0,
        "sodium_mg": 1400.0,
    },
    {
        "id": 7,
        "code": "T07",
        "name_vi": "Gan heo luộc",
        "food_group": "noi_tang",
        "purine_level": "high",
        "allergen_tags": "",
        "tags": "noi_tang",
        "kcal": 135.0,
        "protein_g": 21.0,
        "fat_g": 3.8,
        "carb_g": 2.5,
        "fiber_g": 0.0,
        "sugar_g": 0.0,
        "sodium_mg": 80.0,
    },
    {
        "id": 8,
        "code": "T08",
        "name_vi": "Thịt thiếu natri",
        "food_group": "thit",
        "purine_level": "low",
        "allergen_tags": "",
        "tags": "dam",
        "kcal": 150.0,
        "protein_g": 20.0,
        "fat_g": 5.0,
        "carb_g": 5.0,
        "fiber_g": 0.0,
        "sugar_g": 0.0,
        "sodium_mg": None,
    },
    {
        "id": 9,
        "code": "T09",
        "name_vi": "Thịt chưa rõ purin",
        "food_group": "thit",
        "purine_level": "unknown",
        "allergen_tags": "",
        "tags": "dam",
        "kcal": 150.0,
        "protein_g": 20.0,
        "fat_g": 5.0,
        "carb_g": 5.0,
        "fiber_g": 0.0,
        "sugar_g": 0.0,
        "sodium_mg": 50.0,
    },
    {
        "id": 10,
        "code": "T10",
        "name_vi": "Nước ngọt có gas",
        "food_group": "do_uong",
        "purine_level": "low",
        "allergen_tags": "",
        "tags": "nuoc_ngot",
        "kcal": 42.0,
        "protein_g": 0.0,
        "fat_g": 0.0,
        "carb_g": 10.6,
        "fiber_g": 0.0,
        "sugar_g": 10.6,
        "sodium_mg": 10.0,
    },
    {
        "id": 11,
        "code": "T11",
        "name_vi": "Cải xanh luộc",
        "food_group": "rau_cu",
        "purine_level": "low",
        "allergen_tags": "",
        "tags": "rau",
        "kcal": 20.0,
        "protein_g": 1.8,
        "fat_g": 0.2,
        "carb_g": 3.5,
        "fiber_g": 2.0,
        "sugar_g": 0.5,
        "sodium_mg": 20.0,
    },
    {
        "id": 12,
        "code": "T12",
        "name_vi": "Yến mạch cán dẹt",
        "food_group": "ngu_coc",
        "purine_level": "low",
        "allergen_tags": "",
        "tags": "ngu_coc_nguyen_hat",
        "kcal": 389.0,
        "protein_g": 16.9,
        "fat_g": 6.9,
        "carb_g": 66.3,
        "fiber_g": 10.6,
        "sugar_g": 0.0,
        "sodium_mg": 2.0,
    },
]


def _base_profile(**overrides: Any) -> PatientProfile:
    data: dict[str, Any] = {
        "patient_code": "TV01",
        "age": 40,
        "sex": "male",
        "height_cm": 170.0,
        "weight_kg": 70.0,
        "activity_level": "moderate",
        "conditions": [],
        "allergens": [],
        "days": 1,
    }
    data.update(overrides)
    return PatientProfile(**data)


def _base_targets(**overrides: Any) -> NutritionTargets:
    data: dict[str, Any] = {
        "bmi": 24.2,
        "bmr": 1600.0,
        "tdee": 2400.0,
        "target_kcal": 1600.0,
        "protein_g": 85.0,
        "fat_g": 53.0,
        "carb_g": 200.0,
        "fiber_min_g": 20.0,
        "sodium_max_mg": 2000.0,
        "sugar_max_g": 25.0,
        "kcal_floor": 1500.0,
        "rationale": ["test"],
    }
    data.update(overrides)
    return NutritionTargets(**data)


def _clean_day(day: int = 1) -> DayPlan:
    # Tổng chuẩn: ~1628.6 kcal, ~92.9g P, ~54.0g F, ~196.7g C, ~22.2g xơ, ~180mg Na, ~3.1g đường
    return DayPlan(
        day=day,
        meals=[
            Meal(
                meal="breakfast",
                items=[
                    PlannedItem(food_id=1, grams=150.0),
                    PlannedItem(food_id=12, grams=100.0),
                    PlannedItem(food_id=2, grams=50.0),
                ],
            ),
            Meal(
                meal="lunch",
                items=[
                    PlannedItem(food_id=1, grams=150.0),
                    PlannedItem(food_id=2, grams=100.0),
                    PlannedItem(food_id=3, grams=20.0),
                    PlannedItem(food_id=11, grams=250.0),
                ],
            ),
            Meal(
                meal="dinner",
                items=[
                    PlannedItem(food_id=1, grams=100.0),
                    PlannedItem(food_id=2, grams=40.0),
                    PlannedItem(food_id=3, grams=20.0),
                    PlannedItem(food_id=11, grams=250.0),
                ],
            ),
        ],
    )


def _verify(
    plan: MealPlanLLM,
    profile: PatientProfile | None = None,
    targets: NutritionTargets | None = None,
    needs: NeedsResult | None = None,
    allowed_foods: list[dict[str, Any]] | None = None,
    rules: dict[str, Any] | None = None,
) -> tuple[set[str], list[dict[str, Any]]]:
    with ToolsGateway(mode="direct") as gw:
        viols, daily = verify_meal_plan(
            plan=plan,
            profile=profile or _base_profile(),
            targets=targets or _base_targets(),
            gateway=gw,
            rules=rules,
            needs=needs,
            allowed_foods=allowed_foods,
            food_db=SAMPLE_FOOD_DB,
        )
    return {v.code for v in viols}, daily


# --- 1. UNKNOWN_FOOD ---
def test_unknown_food_positive_missing_in_db_and_not_allowed() -> None:
    """Dương tính UNKNOWN_FOOD: food_id không có trong DB và ngoài allowed_foods."""
    plan = _clean_day()
    plan.meals[0].items.append(PlannedItem(food_id=9999, grams=50.0))
    codes, _ = _verify(MealPlanLLM(days=[plan]), allowed_foods=SAMPLE_FOOD_DB[:3])
    assert "UNKNOWN_FOOD" in codes

    # Món có trong DB (id=11) nhưng không có trong allowed_foods (chỉ gồm id=1,2,3)
    codes2, _ = _verify(MealPlanLLM(days=[_clean_day()]), allowed_foods=SAMPLE_FOOD_DB[:3])
    assert "UNKNOWN_FOOD" in codes2


def test_unknown_food_negative() -> None:
    """Âm tính UNKNOWN_FOOD: mọi food_id đều thuộc DB và allowed_foods."""
    codes, _ = _verify(MealPlanLLM(days=[_clean_day()]), allowed_foods=SAMPLE_FOOD_DB)
    assert "UNKNOWN_FOOD" not in codes


# --- 2. GRAMS_OUT_OF_RANGE ---
def test_grams_out_of_range_positive_from_rules() -> None:
    """Dương tính GRAMS_OUT_OF_RANGE: nhỏ hơn grams_min và lớn hơn grams_max trong rules.yaml."""
    plan = _clean_day()
    plan.meals[0].items[0] = PlannedItem.model_construct(food_id=1, grams=5.0)
    plan.meals[1].items[0] = PlannedItem.model_construct(food_id=1, grams=450.0)
    codes, _ = _verify(MealPlanLLM(days=[plan]))
    assert "GRAMS_OUT_OF_RANGE" in codes

    # Kiểm chứng đọc ngưỡng từ rules tùy chỉnh (không hard-code 10..400)
    custom_rules = deepcopy(load_rules())
    custom_rules["verifier"]["grams_min"] = 40
    codes_custom, _ = _verify(MealPlanLLM(days=[_clean_day()]), rules=custom_rules)
    assert "GRAMS_OUT_OF_RANGE" in codes_custom


def test_grams_out_of_range_negative() -> None:
    """Âm tính GRAMS_OUT_OF_RANGE: mọi món đều nằm trong [grams_min, grams_max]."""
    codes, _ = _verify(MealPlanLLM(days=[_clean_day()]))
    assert "GRAMS_OUT_OF_RANGE" not in codes


# --- 3. KCAL_OUT_OF_RANGE ---
def test_kcal_out_of_range_positive() -> None:
    """Dương tính KCAL_OUT_OF_RANGE: kcal ngày lệch mục tiêu vượt kcal_tolerance_pct."""
    targets = _base_targets(target_kcal=2500.0)
    codes, _ = _verify(MealPlanLLM(days=[_clean_day()]), targets=targets)
    assert "KCAL_OUT_OF_RANGE" in codes


def test_kcal_out_of_range_negative() -> None:
    """Âm tính KCAL_OUT_OF_RANGE: kcal ngày nằm trong dung sai ±10%."""
    codes, _ = _verify(MealPlanLLM(days=[_clean_day()]))
    assert "KCAL_OUT_OF_RANGE" not in codes


# --- 4. MACRO_OUT_OF_RANGE ---
def test_macro_out_of_range_positive() -> None:
    """Dương tính MACRO_OUT_OF_RANGE: đạm/béo/carb ngày lệch quá macro_tolerance_pct."""
    targets = _base_targets(protein_g=180.0)  # Thực tế ~88.6g -> lệch >50%
    codes, _ = _verify(MealPlanLLM(days=[_clean_day()]), targets=targets)
    assert "MACRO_OUT_OF_RANGE" in codes


def test_macro_out_of_range_negative() -> None:
    """Âm tính MACRO_OUT_OF_RANGE: cả 3 macro đều trong ngưỡng ±15%."""
    codes, _ = _verify(MealPlanLLM(days=[_clean_day()]))
    assert "MACRO_OUT_OF_RANGE" not in codes


# --- 5. ALLERGEN ---
def test_allergen_positive() -> None:
    """Dương tính ALLERGEN: có món chứa dị nguyên đã khai báo."""
    plan = _clean_day()
    plan.meals[1].items.append(PlannedItem(food_id=4, grams=50.0))  # Tôm sú (seafood)
    profile = _base_profile(allergens=["seafood"])
    codes, _ = _verify(MealPlanLLM(days=[plan]), profile=profile)
    assert "ALLERGEN" in codes


def test_allergen_negative() -> None:
    """Âm tính ALLERGEN: không chứa dị nguyên đã khai báo."""
    profile = _base_profile(allergens=["seafood", "peanut"])
    codes, _ = _verify(MealPlanLLM(days=[_clean_day()]), profile=profile)
    assert "ALLERGEN" not in codes


# --- 6. SODIUM_OVER ---
def test_sodium_over_positive() -> None:
    """Dương tính SODIUM_OVER: tổng natri ngày vượt sodium_max_mg."""
    plan = _clean_day()
    plan.meals[2].items.append(PlannedItem(food_id=6, grams=150.0))  # 150g dưa muối = 2100mg Na
    codes, _ = _verify(
        MealPlanLLM(days=[plan]),
        targets=_base_targets(sodium_max_mg=2000.0),
    )
    assert "SODIUM_OVER" in codes


def test_sodium_over_negative() -> None:
    """Âm tính SODIUM_OVER: tổng natri ngày <= sodium_max_mg."""
    codes, _ = _verify(MealPlanLLM(days=[_clean_day()]))
    assert "SODIUM_OVER" not in codes


# --- 7. SUGAR_OVER ---
def test_sugar_over_positive() -> None:
    """Dương tính SUGAR_OVER: tổng đường ngày vượt sugar_max_g."""
    plan = _clean_day()
    plan.meals[2].items.append(PlannedItem(food_id=5, grams=100.0))  # +30g đường
    codes, _ = _verify(
        MealPlanLLM(days=[plan]),
        targets=_base_targets(sugar_max_g=25.0),
    )
    assert "SUGAR_OVER" in codes


def test_sugar_over_negative() -> None:
    """Âm tính SUGAR_OVER: tổng đường ngày <= sugar_max_g."""
    codes, _ = _verify(MealPlanLLM(days=[_clean_day()]))
    assert "SUGAR_OVER" not in codes


# --- 8. PURINE_HIGH ---
def test_purine_high_positive_for_gout() -> None:
    """Dương tính PURINE_HIGH: bệnh nhân gout có món purine_level=high."""
    plan = _clean_day()
    plan.meals[1].items.append(PlannedItem(food_id=7, grams=50.0))  # Gan heo (high purine)
    profile = _base_profile(conditions=["gout"])
    needs = NeedsResult(needs=["han_che_purin"], rule_refs=["NEED_GOUT"])
    codes, _ = _verify(MealPlanLLM(days=[plan]), profile=profile, needs=needs)
    assert "PURINE_HIGH" in codes


def test_purine_high_negative_for_gout_and_non_gout() -> None:
    """Âm tính PURINE_HIGH: ca gout chỉ dùng món low/medium; ca không gout không bị chặn purin."""
    profile_gout = _base_profile(conditions=["gout"])
    needs_gout = NeedsResult(needs=["han_che_purin"], rule_refs=["NEED_GOUT"])
    codes_gout, _ = _verify(
        MealPlanLLM(days=[_clean_day()]), profile=profile_gout, needs=needs_gout
    )
    assert "PURINE_HIGH" not in codes_gout

    # Người không bị gout ăn gan heo không bị gắn PURINE_HIGH
    plan_with_liver = _clean_day()
    plan_with_liver.meals[1].items.append(PlannedItem(food_id=7, grams=50.0))
    codes_no_gout, _ = _verify(MealPlanLLM(days=[plan_with_liver]))
    assert "PURINE_HIGH" not in codes_no_gout


# --- 9. AVOID_TAG ---
def test_avoid_tag_positive() -> None:
    """Dương tính AVOID_TAG: món có tag thuộc avoid_tags của nhu cầu (t2d/htn/gout)."""
    plan = _clean_day()
    plan.meals[1].items.append(PlannedItem(food_id=10, grams=100.0))  # tag nuoc_ngot
    profile = _base_profile(conditions=["t2d"])
    needs = NeedsResult(needs=["kiem_soat_duong_huyet"], rule_refs=["NEED_T2D"])
    codes, _ = _verify(MealPlanLLM(days=[plan]), profile=profile, needs=needs)
    assert "AVOID_TAG" in codes


def test_avoid_tag_negative() -> None:
    """Âm tính AVOID_TAG: không có món nào mang tag bị cấm của nhu cầu."""
    profile = _base_profile(conditions=["t2d", "htn", "gout"])
    needs = NeedsResult(
        needs=["kiem_soat_duong_huyet", "giam_natri", "han_che_purin"],
        rule_refs=["NEED_T2D", "NEED_HTN", "NEED_GOUT"],
    )
    codes, _ = _verify(MealPlanLLM(days=[_clean_day()]), profile=profile, needs=needs)
    assert "AVOID_TAG" not in codes


# --- 10. BELOW_FLOOR ---
def test_below_floor_positive() -> None:
    """Dương tính BELOW_FLOOR: kcal ngày thấp hơn kcal_floor (kể cả khi trong tolerance 10%)."""
    # Thực đơn ngày = ~1649.8 kcal; đặt target=1700 và kcal_floor=1700 (lệch 3% nhưng < floor!)
    targets = _base_targets(target_kcal=1700.0, kcal_floor=1700.0)
    codes, _ = _verify(MealPlanLLM(days=[_clean_day()]), targets=targets)
    assert "BELOW_FLOOR" in codes


def test_below_floor_negative() -> None:
    """Âm tính BELOW_FLOOR: kcal ngày >= kcal_floor."""
    codes, _ = _verify(MealPlanLLM(days=[_clean_day()]))
    assert "BELOW_FLOOR" not in codes


# --- 11. DAY_COUNT ---
def test_day_count_positive_wrong_days_and_missing_meal() -> None:
    """Dương tính DAY_COUNT: sai số ngày yêu cầu hoặc thiếu bữa chính."""
    # Sai số ngày (yêu cầu 3 ngày, trả 1 ngày)
    codes1, _ = _verify(MealPlanLLM(days=[_clean_day(1)]), profile=_base_profile(days=3))
    assert "DAY_COUNT" in codes1

    # Thiếu bữa tối (dinner)
    missing_dinner = _clean_day(1)
    missing_dinner.meals = missing_dinner.meals[:2]
    codes2, _ = _verify(MealPlanLLM(days=[missing_dinner]), profile=_base_profile(days=1))
    assert "DAY_COUNT" in codes2


def test_day_count_negative() -> None:
    """Âm tính DAY_COUNT: đủ số ngày 1..days và mỗi ngày có đủ sáng, trưa, tối."""
    plan = MealPlanLLM(days=[_clean_day(1), _clean_day(2)])
    codes, _ = _verify(plan, profile=_base_profile(days=2))
    assert "DAY_COUNT" not in codes


# --- 12. DATA_MISSING (SPEC 9.4) ---
def test_data_missing_positive_nutrient_and_unknown_purine() -> None:
    """Dương tính DATA_MISSING: thiếu sodium_mg hoặc ca gout gặp purine_level=unknown."""
    plan_na = _clean_day()
    plan_na.meals[0].items.append(PlannedItem(food_id=8, grams=50.0))  # sodium_mg=None
    codes_na, _ = _verify(MealPlanLLM(days=[plan_na]))
    assert "DATA_MISSING" in codes_na

    plan_pu = _clean_day()
    plan_pu.meals[0].items.append(PlannedItem(food_id=9, grams=50.0))  # purine_level=unknown
    profile_gout = _base_profile(conditions=["gout"])
    needs_gout = NeedsResult(needs=["han_che_purin"], rule_refs=["NEED_GOUT"])
    codes_pu, _ = _verify(MealPlanLLM(days=[plan_pu]), profile=profile_gout, needs=needs_gout)
    assert "DATA_MISSING" in codes_pu


def test_data_missing_negative_and_cannot_plan() -> None:
    """Âm tính DATA_MISSING với dữ liệu đủ và xử lý đúng cờ cannot_plan=True."""
    codes, daily = _verify(MealPlanLLM(days=[_clean_day()]))
    assert codes == set()
    assert len(daily) == 1

    codes_cp, daily_cp = _verify(MealPlanLLM(days=[], cannot_plan=True, reason="Không đủ món"))
    assert codes_cp == {"CANNOT_PLAN"}
    assert daily_cp == []


# --- 13. FIBER_LOW & DỮ LIỆU XƠ ---
def test_fiber_low_zero_boundary_and_missing_data() -> None:
    """Kiểm tra FIBER_LOW với 0g chất xơ, tại ngưỡng dung sai, ngưỡng 0% và khi thiếu fiber_g."""
    # 1) Thực đơn đủ kcal/macro nhưng 0g chất xơ so với mục tiêu 25g -> FIBER_LOW
    zero_fiber_db = [deepcopy(f) for f in SAMPLE_FOOD_DB]
    for f in zero_fiber_db:
        f["fiber_g"] = 0.0
    plan_zero = MealPlanLLM(days=[_clean_day()])
    targets_25 = _base_targets(fiber_min_g=25.0)
    with ToolsGateway(mode="direct") as gw:
        viols_zero, _ = verify_meal_plan(
            plan=plan_zero,
            profile=_base_profile(),
            targets=targets_25,
            gateway=gw,
            food_db=zero_fiber_db,
        )
    assert "FIBER_LOW" in {v.code for v in viols_zero}

    # 2) Kiểm tra đúng ngưỡng dung sai 15% của fiber_min_g=25.0 (ngưỡng = 21.25g)
    exact_food_db = deepcopy(SAMPLE_FOOD_DB)
    # _clean_day() hiện có 100g id=12 (10.6g) + 500g id=11 (10.0g) + 400g id=1 (1.6g) = 22.2g
    # Tăng/giảm lượng xơ id=12 để kiểm thử chính xác ngưỡng 21.25g (21.25 -> pass, 21.20 -> fail)
    exact_food_db[-1]["fiber_g"] = 9.65  # Tổng ngày = 9.65 + 10.0 + 1.6 = 21.25g (chạm ngưỡng)
    with ToolsGateway(mode="direct") as gw:
        viols_edge_ok, _ = verify_meal_plan(
            plan=MealPlanLLM(days=[_clean_day()]),
            profile=_base_profile(),
            targets=targets_25,
            gateway=gw,
            food_db=exact_food_db,
        )
    assert "FIBER_LOW" not in {v.code for v in viols_edge_ok}

    exact_food_db[-1]["fiber_g"] = 9.6  # Tổng ngày = 21.2g (< 21.25g)
    with ToolsGateway(mode="direct") as gw:
        viols_edge_fail, _ = verify_meal_plan(
            plan=MealPlanLLM(days=[_clean_day()]),
            profile=_base_profile(),
            targets=targets_25,
            gateway=gw,
            food_db=exact_food_db,
        )
    assert "FIBER_LOW" in {v.code for v in viols_edge_fail}

    # 3) Khi cấu hình fiber_tolerance_pct = 0 thì dưới 25.0g phải báo FIBER_LOW
    strict_rules = deepcopy(load_rules())
    strict_rules["verifier"]["fiber_tolerance_pct"] = 0
    codes_strict, _ = _verify(
        MealPlanLLM(days=[_clean_day()]),
        targets=targets_25,
        rules=strict_rules,
    )
    assert "FIBER_LOW" in codes_strict

    # 4) Khi món ăn thiếu dữ liệu fiber_g=None -> báo DATA_MISSING, không giả lập 0.0g vượt qua
    missing_db = deepcopy(SAMPLE_FOOD_DB)
    missing_db[0]["fiber_g"] = None
    with ToolsGateway(mode="direct") as gw:
        viols_missing, _ = verify_meal_plan(
            plan=MealPlanLLM(days=[_clean_day()]),
            profile=_base_profile(),
            targets=targets_25,
            gateway=gw,
            food_db=missing_db,
        )
    missing_codes = {v.code for v in viols_missing}
    assert "DATA_MISSING" in missing_codes
    assert "FIBER_LOW" not in missing_codes


def test_mock_planner_and_portion_meet_fiber_on_real_food_csv_t2d_gout() -> None:
    """Mock planner + adjust_portions trên data/food.csv (ĐTĐ + Gout) không rớt FIBER_LOW."""
    import csv
    from pathlib import Path

    from agent.llm import generate_mock_meal_plan
    from core.nutrition import build_targets
    from core.portion import adjust_portions

    csv_foods: list[dict[str, Any]] = []
    with Path("data/food.csv").open(encoding="utf-8") as f:
        for idx, row in enumerate(csv.DictReader(f), start=1):
            csv_foods.append(
                {
                    "id": idx,
                    "code": row["code"],
                    "name_vi": row["name_vi"],
                    "food_group": row["food_group"],
                    "unit_default_g": float(row["unit_default_g"] or 100.0),
                    "kcal": float(row["kcal"] or 0.0),
                    "protein_g": float(row["protein_g"] or 0.0),
                    "fat_g": float(row["fat_g"] or 0.0),
                    "carb_g": float(row["carb_g"] or 0.0),
                    "fiber_g": float(row["fiber_g"] or 0.0),
                    "sugar_g": float(row["sugar_g"] or 0.0),
                    "sodium_mg": float(row["sodium_mg"] or 0.0),
                    "purine_level": row["purine_level"] or "low",
                    "allergen_tags": row["allergen_tags"] or "",
                    "tags": row["tags"] or "",
                }
            )

    # Lọc món hợp lệ cho ĐTĐ + Gout tương tự node retrieve/allowed_foods
    allowed = [
        it
        for it in csv_foods
        if it["purine_level"] in ("low", "medium")
        and not (set(it["tags"].split("|")) & {"duong_cao", "nuoc_ngot", "noi_tang", "bia_ruou"})
    ]
    profile = _base_profile(conditions=["t2d", "gout"], days=3)
    needs = NeedsResult(
        needs=["kiem_soat_duong_huyet", "han_che_purin"],
        rule_refs=["NEED_T2D", "NEED_GOUT"],
    )
    targets = build_targets(profile, needs)
    raw_plan = generate_mock_meal_plan(days=3, allowed_foods=allowed, targets=targets)
    adj_plan, _ = adjust_portions(raw_plan, targets, food_db=allowed)
    with ToolsGateway(mode="direct") as gw:
        viols, _ = verify_meal_plan(
            plan=adj_plan,
            profile=profile,
            targets=targets,
            gateway=gw,
            needs=needs,
            allowed_foods=allowed,
            food_db=allowed,
        )
    assert {v.code for v in viols} == set()


def test_verifier_catches_unrealistic_portion_imbalance_and_duplicate_days() -> None:
    """Verifier bắt được định lượng phi thực tế, mất cân đối bữa và lặp nguyên ngày."""
    rich_db: list[dict[str, Any]] = [
        {
            "id": i,
            "name_vi": f"Món {i}",
            "food_group": (
                "rau_cu"
                if i > 3
                else ("dau_mo_hat" if i == 3 else ("thit_gia_cam" if i == 2 else "ngu_coc"))
            ),
            "unit_default_g": 15.0 if i == 3 else 120.0,
            "kcal": 510.0 if i == 3 else (140.0 if i == 2 else (120.0 if i == 1 else 30.0)),
            "protein_g": 16.0 if i == 3 else (28.0 if i == 2 else 3.0),
            "fat_g": 30.0 if i == 3 else 2.0,
            "carb_g": 40.0 if i == 3 else (25.0 if i == 1 else 3.0),
            "fiber_g": 2.0,
            "sugar_g": 0.5,
            "sodium_mg": 30.0,
            "purine_level": "low",
            "allergen_tags": "",
            "tags": "",
        }
        for i in range(1, 16)
    ]
    day1 = DayPlan(
        day=1,
        meals=[
            Meal(
                meal="breakfast",
                items=[PlannedItem(food_id=1, grams=100.0), PlannedItem(food_id=2, grams=15.0)],
            ),
            Meal(
                meal="lunch",
                items=[PlannedItem(food_id=1, grams=200.0), PlannedItem(food_id=3, grams=105.0)],
            ),
            Meal(
                meal="dinner",
                items=[PlannedItem(food_id=1, grams=100.0), PlannedItem(food_id=4, grams=150.0)],
            ),
        ],
    )
    day2 = DayPlan(day=2, meals=day1.meals)
    profile = _base_profile(days=2)
    with ToolsGateway(mode="direct") as gw:
        viols, _ = verify_meal_plan(
            plan=MealPlanLLM(days=[day1, day2]),
            profile=profile,
            targets=_base_targets(),
            gateway=gw,
            allowed_foods=rich_db,
            food_db=rich_db,
        )
    codes = {v.code for v in viols}
    assert "PORTION_UNREALISTIC" in codes
    assert "MEAL_IMBALANCE" in codes
    assert "DAY_DUPLICATE" in codes
