"""Bộ kiểm chứng thực đơn đầy đủ 11 mã vi phạm và cảnh báo DATA_MISSING (SPEC 9.3–9.4)."""

from typing import Any

from agent.tools_gateway import ToolsGateway
from core.allergen import check_allergen as core_check_allergen
from core.classify import classify_needs
from core.food import _split_tags
from core.nutrition import load_rules
from core.schemas import (
    DayPlan,
    Meal,
    MealPlanLLM,
    NeedsResult,
    NutritionTargets,
    PatientProfile,
    PlannedItem,
    Violation,
)
from core.scoring import score_menu as core_score_menu

MAIN_MEALS = ("breakfast", "lunch", "dinner")
PURINE_RANK = {"low": 0, "medium": 1, "high": 2}
REQUIRED_NUTRIENT_FIELDS = (
    "kcal",
    "protein_g",
    "fat_g",
    "carb_g",
    "sodium_mg",
    "sugar_g",
    "fiber_g",
)


def _is_missing_val(val: Any) -> bool:
    """Kiểm tra giá trị dinh dưỡng có bị thiếu (None hoặc chuỗi rỗng) hay không."""
    if val is None:
        return True
    if isinstance(val, str) and not val.strip():
        return True
    return False


def _collect_need_constraints(
    needs: NeedsResult,
    cfg: dict[str, Any],
) -> tuple[set[str], str | None]:
    """Tổng hợp avoid_tags (hợp) và max_purine_level từ rules.yaml theo nhu cầu."""
    avoid_tags: set[str] = set()
    max_purine_level: str | None = None
    needs_cfg = cfg.get("needs") or {}

    for need_name in needs.needs:
        need_cfg = needs_cfg.get(need_name) or {}
        for tag in need_cfg.get("avoid_tags", []):
            tag_norm = str(tag).strip().lower()
            if tag_norm:
                avoid_tags.add(tag_norm)
        if "max_purine_level" in need_cfg and need_cfg["max_purine_level"]:
            candidate = str(need_cfg["max_purine_level"]).strip().lower()
            if max_purine_level is None or (
                PURINE_RANK.get(candidate, 99) < PURINE_RANK.get(max_purine_level, 99)
            ):
                max_purine_level = candidate

    return avoid_tags, max_purine_level


def _score_known_items(
    plan: MealPlanLLM,
    food_map: dict[int, dict[str, Any]],
    gateway: ToolsGateway,
    food_db: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Tính dinh dưỡng cho các món hợp lệ tồn tại trong food DB mà không crash."""
    scorable_days: list[DayPlan] = []
    has_known_item = False
    for day_plan in plan.days:
        scorable_meals: list[Meal] = []
        for meal in day_plan.meals:
            known_items = [
                PlannedItem.model_construct(food_id=item.food_id, grams=item.grams)
                for item in meal.items
                if item.food_id in food_map
            ]
            if known_items:
                has_known_item = True
            scorable_meals.append(Meal.model_construct(meal=meal.meal, items=known_items))
        scorable_days.append(DayPlan.model_construct(day=day_plan.day, meals=scorable_meals))

    if not has_known_item:
        return [
            {
                "day": d.day,
                "kcal": 0.0,
                "protein_g": 0.0,
                "fat_g": 0.0,
                "carb_g": 0.0,
                "fiber_g": 0.0,
                "sugar_g": 0.0,
                "sodium_mg": 0.0,
            }
            for d in plan.days
        ]

    scorable_plan = MealPlanLLM.model_construct(
        days=scorable_days, cannot_plan=False, reason=""
    )
    if food_db is not None:
        scored = core_score_menu(scorable_plan, food_db=food_db)
    else:
        scored = gateway.score_menu(scorable_plan)
    return list(scored["daily_totals"])


def verify_meal_plan(
    plan: MealPlanLLM,
    profile: PatientProfile,
    targets: NutritionTargets,
    gateway: ToolsGateway,
    rules: dict[str, Any] | None = None,
    needs: NeedsResult | None = None,
    allowed_foods: list[dict[str, Any]] | None = None,
    food_db: list[dict[str, Any]] | None = None,
) -> tuple[list[Violation], list[dict[str, Any]]]:
    """Kiểm chứng thực đơn theo đủ 11 mã vi phạm (9.3) và cảnh báo DATA_MISSING (9.4)."""
    if plan.cannot_plan:
        return [
            Violation(
                code="CANNOT_PLAN",
                message_vi=plan.reason or "Không thể lập thực đơn hợp lệ.",
            )
        ], []

    cfg = rules or load_rules()
    active_needs = needs or classify_needs(profile, rules=cfg)

    verifier_cfg = cfg["verifier"]
    grams_min = float(verifier_cfg["grams_min"])
    grams_max = float(verifier_cfg["grams_max"])
    kcal_tol = float(verifier_cfg["kcal_tolerance_pct"]) / 100.0
    macro_tol = float(verifier_cfg["macro_tolerance_pct"]) / 100.0

    avoid_tags_set, max_purine_level = _collect_need_constraints(active_needs, cfg)

    all_foods = food_db if food_db is not None else gateway.search_food(query="", limit=1000)
    food_map: dict[int, dict[str, Any]] = {int(f["id"]): f for f in all_foods}
    allowed_ids: set[int] | None = (
        {int(f["id"]) for f in allowed_foods} if allowed_foods is not None else None
    )

    violations: list[Violation] = []

    # 1. DAY_COUNT: kiểm tra số ngày và đủ 3 bữa chính (breakfast, lunch, dinner) mỗi ngày
    expected_days = list(range(1, profile.days + 1))
    actual_days = [d.day for d in plan.days]
    if len(plan.days) != profile.days or sorted(actual_days) != expected_days:
        violations.append(
            Violation(
                code="DAY_COUNT",
                message_vi=(
                    f"Số ngày hoặc danh sách ngày không khớp yêu cầu {profile.days} ngày "
                    f"(nhận được: {actual_days})."
                ),
            )
        )

    day_has_sugar_data: dict[int, bool] = {}
    known_occurrences: list[tuple[int, str, int]] = []
    seen_missing_food_fields: set[tuple[int, int, str]] = set()

    for day_plan in plan.days:
        meals_with_items = {m.meal for m in day_plan.meals if m.items}
        missing_main = [m for m in MAIN_MEALS if m not in meals_with_items]
        if missing_main:
            violations.append(
                Violation(
                    code="DAY_COUNT",
                    message_vi=(
                        f"Ngày {day_plan.day}: thiếu bữa chính ({', '.join(missing_main)})."
                    ),
                    day=day_plan.day,
                    meal=missing_main[0],
                )
            )

        has_sugar = False
        for meal in day_plan.meals:
            for item in meal.items:
                fid = int(item.food_id)

                # 2. GRAMS_OUT_OF_RANGE
                if item.grams < grams_min or item.grams > grams_max:
                    violations.append(
                        Violation(
                            code="GRAMS_OUT_OF_RANGE",
                            message_vi=(
                                f"Ngày {day_plan.day} ({meal.meal}): food_id={fid} có "
                                f"khối lượng {item.grams:.1f}g ngoài khoảng "
                                f"[{grams_min:.0f}, {grams_max:.0f}]g."
                            ),
                            day=day_plan.day,
                            meal=meal.meal,
                            food_id=fid,
                        )
                    )

                # 3. UNKNOWN_FOOD
                in_db = fid in food_map
                in_allowed = True if allowed_ids is None else fid in allowed_ids
                if not in_db or not in_allowed:
                    reason_detail = (
                        "không tồn tại trong cơ sở dữ liệu"
                        if not in_db
                        else "không nằm trong danh sách allowed_foods"
                    )
                    violations.append(
                        Violation(
                            code="UNKNOWN_FOOD",
                            message_vi=(
                                f"Ngày {day_plan.day} ({meal.meal}): food_id={fid} "
                                f"{reason_detail}."
                            ),
                            day=day_plan.day,
                            meal=meal.meal,
                            food_id=fid,
                        )
                    )
                    continue

                food = food_map[fid]
                known_occurrences.append((day_plan.day, meal.meal, fid))

                if not _is_missing_val(food.get("sugar_g")):
                    has_sugar = True

                # 4. DATA_MISSING (SPEC 9.4)
                missing_fields = [
                    fld for fld in REQUIRED_NUTRIENT_FIELDS if _is_missing_val(food.get(fld))
                ]
                purine_val = str(food.get("purine_level") or "unknown").strip().lower()
                if max_purine_level is not None and purine_val == "unknown":
                    missing_fields.append("purine_level")

                if missing_fields:
                    miss_key = (day_plan.day, fid, ",".join(missing_fields))
                    if miss_key not in seen_missing_food_fields:
                        seen_missing_food_fields.add(miss_key)
                        violations.append(
                            Violation(
                                code="DATA_MISSING",
                                message_vi=(
                                    f"Món '{food.get('name_vi', fid)}' thiếu dữ liệu: "
                                    f"{', '.join(missing_fields)}."
                                ),
                                day=day_plan.day,
                                meal=meal.meal,
                                food_id=fid,
                            )
                        )

                # 5. PURINE_HIGH
                if max_purine_level is not None and purine_val in PURINE_RANK:
                    max_rank = PURINE_RANK.get(max_purine_level, 1)
                    if PURINE_RANK[purine_val] > max_rank:
                        violations.append(
                            Violation(
                                code="PURINE_HIGH",
                                message_vi=(
                                    f"Ngày {day_plan.day} ({meal.meal}): món "
                                    f"'{food['name_vi']}' có mức purin '{purine_val}' "
                                    f"vượt ngưỡng '{max_purine_level}'."
                                ),
                                day=day_plan.day,
                                meal=meal.meal,
                                food_id=fid,
                            )
                        )

                # 6. AVOID_TAG
                if avoid_tags_set:
                    food_tags = _split_tags(str(food.get("tags", "")))
                    hit_tags = sorted(food_tags & avoid_tags_set)
                    if hit_tags:
                        violations.append(
                            Violation(
                                code="AVOID_TAG",
                                message_vi=(
                                    f"Ngày {day_plan.day} ({meal.meal}): món "
                                    f"'{food['name_vi']}' chứa tag cần tránh "
                                    f"({', '.join(hit_tags)})."
                                ),
                                day=day_plan.day,
                                meal=meal.meal,
                                food_id=fid,
                            )
                        )

        day_has_sugar_data[day_plan.day] = has_sugar

    # 7. ALLERGEN (gọi qua gateway hoặc core nếu test truyền food_db riêng)
    if known_occurrences and profile.allergens:
        known_ids = [occ[2] for occ in known_occurrences]
        if food_db is not None:
            allergen_viols = core_check_allergen(
                food_ids=known_ids,
                allergens=list(profile.allergens),
                food_db=food_db,
            )
        else:
            allergen_viols = gateway.check_allergen(
                food_ids=known_ids,
                allergens=list(profile.allergens),
            )
        # Gắn thêm thông tin ngày/bữa nếu thiếu để planner sửa chính xác
        occ_by_fid: dict[int, list[tuple[int, str]]] = {}
        for d_num, m_name, fid in known_occurrences:
            occ_by_fid.setdefault(fid, []).append((d_num, m_name))
        for av in allergen_viols:
            if av.day is None and av.food_id is not None and occ_by_fid.get(av.food_id):
                d_num, m_name = occ_by_fid[av.food_id].pop(0)
                av.day = d_num
                av.meal = m_name
            violations.append(av)

    # 8–12. Tính tổng ngày từ food DB và kiểm tra năng lượng, sàn, macro, natri, đường
    daily_totals = _score_known_items(plan, food_map, gateway, food_db)

    for day_tot in daily_totals:
        day_num = int(day_tot["day"])
        kcal = float(day_tot["kcal"])

        # BELOW_FLOOR
        if kcal < targets.kcal_floor:
            violations.append(
                Violation(
                    code="BELOW_FLOOR",
                    message_vi=(
                        f"Ngày {day_num}: tổng {kcal:.1f} kcal thấp hơn sàn an toàn "
                        f"{targets.kcal_floor:.1f} kcal."
                    ),
                    day=day_num,
                )
            )

        # KCAL_OUT_OF_RANGE
        if targets.target_kcal > 0:
            diff_ratio = abs(kcal - targets.target_kcal) / targets.target_kcal
            if diff_ratio > kcal_tol:
                direction = "thiếu" if kcal < targets.target_kcal else "vượt"
                violations.append(
                    Violation(
                        code="KCAL_OUT_OF_RANGE",
                        message_vi=(
                            f"Ngày {day_num}: {kcal:.1f} kcal ({direction} "
                            f"{abs(kcal - targets.target_kcal):.1f} kcal) lệch mục tiêu "
                            f"{targets.target_kcal:.1f} kcal quá {kcal_tol * 100:.0f}%."
                        ),
                        day=day_num,
                    )
                )

        # MACRO_OUT_OF_RANGE
        for field, label_vi in (
            ("protein_g", "Đạm"),
            ("fat_g", "Béo"),
            ("carb_g", "Tinh bột"),
        ):
            target_val = float(getattr(targets, field))
            actual_val = float(day_tot[field])
            if target_val > 0:
                m_diff = abs(actual_val - target_val) / target_val
                if m_diff > macro_tol:
                    status_vi = "thiếu" if actual_val < target_val else "thừa"
                    violations.append(
                        Violation(
                            code="MACRO_OUT_OF_RANGE",
                            message_vi=(
                                f"Ngày {day_num}: {label_vi} đạt {actual_val:.1f}g "
                                f"({status_vi} {abs(actual_val - target_val):.1f}g, "
                                f"lệch {m_diff * 100:.1f}% so với mục tiêu {target_val:.1f}g, "
                                f"ngưỡng ±{macro_tol * 100:.0f}%)."
                            ),
                            day=day_num,
                        )
                    )

        # SODIUM_OVER
        sodium = float(day_tot["sodium_mg"])
        if sodium > targets.sodium_max_mg:
            violations.append(
                Violation(
                    code="SODIUM_OVER",
                    message_vi=(
                        f"Ngày {day_num}: tổng natri {sodium:.1f}mg vượt giới hạn "
                        f"{targets.sodium_max_mg:.1f}mg."
                    ),
                    day=day_num,
                )
            )

        # SUGAR_OVER (khi có dữ liệu đường)
        if day_has_sugar_data.get(day_num, False):
            sugar = float(day_tot["sugar_g"])
            if sugar > targets.sugar_max_g:
                violations.append(
                    Violation(
                        code="SUGAR_OVER",
                        message_vi=(
                            f"Ngày {day_num}: tổng đường {sugar:.1f}g vượt giới hạn "
                            f"{targets.sugar_max_g:.1f}g."
                        ),
                        day=day_num,
                    )
                )

    return violations, daily_totals
