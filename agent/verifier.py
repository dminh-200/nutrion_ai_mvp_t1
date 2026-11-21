"""Bộ kiểm chứng thực đơn đầy đủ 12 mã vi phạm và cảnh báo DATA_MISSING (SPEC 9.3–9.4)."""

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
    fiber_tol = float(
        verifier_cfg.get("fiber_tolerance_pct", verifier_cfg["macro_tolerance_pct"])
    ) / 100.0

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
    day_missing_fiber: dict[int, bool] = {}
    day_has_known_foods: dict[int, bool] = {}
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
        missing_fiber = False
        has_known_food = False
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
                has_known_food = True
                known_occurrences.append((day_plan.day, meal.meal, fid))

                if not _is_missing_val(food.get("sugar_g")):
                    has_sugar = True
                if _is_missing_val(food.get("fiber_g")):
                    missing_fiber = True

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
        day_missing_fiber[day_plan.day] = missing_fiber
        day_has_known_foods[day_plan.day] = has_known_food

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

        # FIBER_LOW (khi đủ dữ liệu chất xơ; dung sai fiber_tolerance_pct / macro_tolerance_pct)
        if (
            targets.fiber_min_g > 0
            and day_has_known_foods.get(day_num, False)
            and not day_missing_fiber.get(day_num, False)
        ):
            fiber = float(day_tot.get("fiber_g", 0.0))
            min_fiber = targets.fiber_min_g * (1.0 - fiber_tol)
            if fiber < min_fiber - 1e-9:
                violations.append(
                    Violation(
                        code="FIBER_LOW",
                        message_vi=(
                            f"Ngày {day_num}: tổng chất xơ {fiber:.1f}g thấp hơn ngưỡng "
                            f"{min_fiber:.1f}g (mục tiêu {targets.fiber_min_g:.1f}g, "
                            f"dung sai -{fiber_tol * 100:.0f}%)."
                        ),
                        day=day_num,
                    )
                )

    # 13. PORTION_UNREALISTIC & MEAL_IMBALANCE (chỉ kiểm tra trên DB đầy đủ >= 15 món)
    day_food_sets: dict[int, set[int]] = {}
    check_realistic = len(food_map) >= 15
    for day_plan in plan.days:
        day_seed_g = 0.0
        meal_kcals: dict[str, float] = {}
        day_fids: set[int] = set()
        for meal in day_plan.meals:
            m_kcal = 0.0
            for item in meal.items:
                fid = int(item.food_id)
                day_fids.add(fid)
                food = food_map.get(fid)
                if not food:
                    continue
                m_kcal += float(food.get("kcal") or 0.0) * (item.grams / 100.0)
                if not check_realistic or "food_group" not in food:
                    continue
                grp = str(food.get("food_group") or "").strip().lower()
                unit_g = float(food.get("unit_default_g") or 100.0)
                fat_g = float(food.get("fat_g") or 0.0)
                tags = _split_tags(str(food.get("tags", "")))
                name_vi = str(food.get("name_vi", fid))

                if grp in ("dau_hat", "dau_mo_hat"):
                    if fat_g >= 80.0 and item.grams > 25.0:
                        violations.append(
                            Violation(
                                code="PORTION_UNREALISTIC",
                                message_vi=(
                                    f"Ngày {day_plan.day} ({meal.meal}): dầu/mỡ '{name_vi}' "
                                    f"{item.grams:.0f}g quá nhiều cho 1 bữa (tối đa 25g)."
                                ),
                                day=day_plan.day,
                                meal=meal.meal,
                                food_id=fid,
                            )
                        )
                    elif fat_g < 80.0:
                        day_seed_g += float(item.grams)
                        max_seed_meal = 30.0 if unit_g <= 15.0 else 35.0
                        if item.grams > max_seed_meal:
                            violations.append(
                                Violation(
                                    code="PORTION_UNREALISTIC",
                                    message_vi=(
                                        f"Ngày {day_plan.day} ({meal.meal}): hạt '{name_vi}' "
                                        f"{item.grams:.0f}g vượt khẩu phần thực tế "
                                        f"(tối đa {max_seed_meal:.0f}g/bữa)."
                                    ),
                                    day=day_plan.day,
                                    meal=meal.meal,
                                    food_id=fid,
                                )
                            )
                elif (
                    grp in ("thit_gia_cam", "thuy_hai_san", "thit_ca")
                    and "che_bien_san" not in tags
                    and unit_g > 60.0
                    and item.grams < 45.0
                ):
                    violations.append(
                        Violation(
                            code="PORTION_UNREALISTIC",
                            message_vi=(
                                f"Ngày {day_plan.day} ({meal.meal}): đạm chính '{name_vi}' "
                                f"chỉ {item.grams:.0f}g quá nhỏ, không thực tế (tối thiểu 45g)."
                            ),
                            day=day_plan.day,
                            meal=meal.meal,
                            food_id=fid,
                        )
                    )
            meal_kcals[meal.meal] = meal_kcals.get(meal.meal, 0.0) + m_kcal

        day_food_sets[day_plan.day] = day_fids
        if day_seed_g > 35.0:
            violations.append(
                Violation(
                    code="PORTION_UNREALISTIC",
                    message_vi=(
                        f"Ngày {day_plan.day}: tổng lượng hạt khô {day_seed_g:.0f}g/ngày "
                        "quá cao (tối đa 35g/ngày)."
                    ),
                    day=day_plan.day,
                )
            )

        day_tot_k = sum(meal_kcals.values())
        if (
            check_realistic
            and targets.target_kcal >= 1000.0
            and day_tot_k >= 800.0
            and all(m in meal_kcals and meal_kcals[m] > 0 for m in MAIN_MEALS)
        ):
            has_snack = meal_kcals.get("snack", 0.0) > 0.0
            min_main_share = 0.12 if has_snack else 0.15
            for m in MAIN_MEALS:
                share = meal_kcals[m] / day_tot_k
                if share < min_main_share or share > 0.50:
                    violations.append(
                        Violation(
                            code="MEAL_IMBALANCE",
                            message_vi=(
                                f"Ngày {day_plan.day} ({m}): năng lượng chiếm {share * 100:.0f}% "
                                "tổng ngày, mất cân đối bữa ăn "
                                f"(nên trong khoảng {int(min_main_share * 100)}%–50%)."
                            ),
                            day=day_plan.day,
                            meal=m,
                        )
                    )
            if has_snack:
                snack_share = meal_kcals["snack"] / day_tot_k
                if snack_share > 0.35:
                    violations.append(
                        Violation(
                            code="MEAL_IMBALANCE",
                            message_vi=(
                                f"Ngày {day_plan.day} (snack): bữa phụ chiếm "
                                f"{snack_share * 100:.0f}% tổng ngày, vượt ngưỡng 35%."
                            ),
                            day=day_plan.day,
                            meal="snack",
                        )
                    )

    # 14. DAY_DUPLICATE: phát hiện lặp nguyên ngày khi có >= 12 món hợp lệ
    pool_size = len(allowed_ids) if allowed_ids is not None else len(food_map)
    if len(plan.days) >= 2 and pool_size >= 12:
        sorted_days = sorted(day_food_sets.keys())
        reported_dup = False
        for i, d_a in enumerate(sorted_days):
            if reported_dup:
                break
            set_a = day_food_sets[d_a]
            if not set_a:
                continue
            for d_b in sorted_days[i + 1 :]:
                set_b = day_food_sets[d_b]
                if not set_b:
                    continue
                union = set_a | set_b
                jaccard = len(set_a & set_b) / len(union) if union else 0.0
                if jaccard >= 0.85:
                    violations.append(
                        Violation(
                            code="DAY_DUPLICATE",
                            message_vi=(
                                f"Ngày {d_a} và Ngày {d_b} lặp lại gần như y hệt "
                                f"({jaccard * 100:.0f}% món trùng nhau). "
                                "Cần đổi món đạm/rau/tinh bột để đa dạng giữa các ngày."
                            ),
                            day=d_b,
                        )
                    )
                    reported_dup = True
                    break

    return violations, daily_totals
