"""Cân chỉnh khẩu phần bằng code theo thuật toán SPEC mục 6.5."""

from typing import Any

from core.food import load_food_db_from_sqlite
from core.nutrition import load_rules
from core.schemas import DayPlan, MealPlanLLM, NutritionTargets, PlannedItem


def _round_to_5(value: float) -> float:
    """Làm tròn khối lượng về bội số của 5g."""
    return float(round(value / 5.0) * 5)


def _score_day(day_plan: DayPlan, food_map: dict[int, dict[str, Any]]) -> dict[str, float]:
    """Tính tổng dinh dưỡng một ngày từ food_map khớp quy tắc làm tròn của score_menu."""
    totals = {
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
            food = food_map.get(int(item.food_id))
            if food is None:
                continue
            ratio = item.grams / 100.0
            for key in totals:
                val = round(float(food.get(key) or 0.0) * ratio, 1)
                totals[key] = round(totals[key] + val, 1)
    return totals


def _macros_consistent_with_kcal(targets: NutritionTargets) -> bool:
    """Kiểm tra mục tiêu P/F/C có nhất quán với target_kcal và sàn năng lượng không."""
    if targets.target_kcal <= 0:
        return False
    if targets.kcal_floor > 0 and targets.target_kcal < targets.kcal_floor:
        return False
    macro_kcal = 4.0 * targets.protein_g + 9.0 * targets.fat_g + 4.0 * targets.carb_g
    return abs(macro_kcal - targets.target_kcal) / targets.target_kcal <= 0.25


def _day_is_compliant(
    tot: dict[str, float],
    targets: NutritionTargets,
    tol_pct: float,
    macro_tol: float,
    floor_applies: bool,
    check_macros: bool,
    fiber_floor: float = 0.0,
) -> bool:
    """Kiểm tra ngày ăn đã đạt kcal, sàn năng lượng, xơ và macro trong ngưỡng chưa."""
    if floor_applies and tot["kcal"] < targets.kcal_floor:
        return False
    if targets.target_kcal > 0:
        if abs(tot["kcal"] - targets.target_kcal) / targets.target_kcal > tol_pct:
            return False
    if check_macros:
        for field in ("protein_g", "fat_g", "carb_g"):
            t_val = float(getattr(targets, field))
            if t_val > 0 and abs(tot[field] - t_val) / t_val > macro_tol:
                return False
    if fiber_floor > 0 and tot["fiber_g"] < fiber_floor - 1e-9:
        return False
    return True


def _day_loss(
    tot: dict[str, float],
    targets: NutritionTargets,
    tol_pct: float,
    macro_tol: float,
    floor_applies: bool,
    optimize_macros: bool,
    fiber_floor: float = 0.0,
) -> float:
    """Hàm mục tiêu ưu tiên kéo ngày ăn vượt sàn, đúng khoảng kcal, cân macro và đủ chất xơ."""
    kcal = tot["kcal"]
    target_k = targets.target_kcal
    loss = 0.0

    if floor_applies and kcal < targets.kcal_floor:
        loss += 1000.0 * ((targets.kcal_floor - kcal) / max(targets.kcal_floor, 1.0) + 0.02)

    if target_k > 0:
        kcal_min = (
            max(targets.kcal_floor, target_k * (1.0 - tol_pct))
            if floor_applies
            else target_k * (1.0 - tol_pct)
        )
        kcal_max = target_k * (1.0 + tol_pct)
        if kcal < kcal_min:
            loss += 300.0 * ((kcal_min - kcal) / target_k + 0.01)
        elif kcal > kcal_max:
            loss += 300.0 * ((kcal - kcal_max) / target_k + 0.01)
        loss += ((kcal - target_k) / target_k) ** 2

    if optimize_macros:
        for field in ("protein_g", "fat_g", "carb_g"):
            t_val = float(getattr(targets, field))
            if t_val <= 0:
                continue
            rel = abs(tot[field] - t_val) / t_val
            if rel > macro_tol:
                loss += 150.0 * ((rel - macro_tol) + 0.01)
            loss += rel**2

    if fiber_floor > 0 and tot["fiber_g"] < fiber_floor:
        loss += 100.0 * ((fiber_floor - tot["fiber_g"]) / fiber_floor + 0.01)

    return loss


def _safety_ceilings_ok(
    cand_tot: dict[str, float],
    cur_tot: dict[str, float],
    targets: NutritionTargets,
) -> bool:
    """Đảm bảo bước tinh chỉnh không làm vượt hoặc tăng thêm natri và đường."""
    na_max = float(targets.sodium_max_mg)
    if cand_tot["sodium_mg"] > na_max and cand_tot["sodium_mg"] > cur_tot["sodium_mg"]:
        return False
    if targets.sugar_max_g is not None:
        sg_max = float(targets.sugar_max_g)
        if cand_tot["sugar_g"] > sg_max and cand_tot["sugar_g"] > cur_tot["sugar_g"]:
            return False
    return True


def _refine_day_portions(
    day_plan: DayPlan,
    targets: NutritionTargets,
    food_map: dict[int, dict[str, Any]],
    grams_min: float,
    grams_max: float,
    tol_pct: float,
    macro_tol: float,
    floor_applies: bool,
    optimize_macros: bool,
    fiber_floor: float = 0.0,
) -> bool:
    """Tinh chỉnh bước ±5..30g trên các món sẵn có khi còn lệch sàn kcal, macro hoặc chất xơ."""
    items: list[PlannedItem] = [
        item
        for meal in day_plan.meals
        for item in meal.items
        if int(item.food_id) in food_map
    ]
    if not items:
        return False

    max_possible_fiber = sum(
        float(food_map[int(it.food_id)].get("fiber_g") or 0.0) * (grams_max / 100.0)
        for it in items
    )
    active_fiber_floor = (
        fiber_floor if (fiber_floor > 0 and max_possible_fiber >= fiber_floor) else 0.0
    )

    cur_tot = _score_day(day_plan, food_map)
    if _day_is_compliant(
        cur_tot,
        targets,
        tol_pct,
        macro_tol,
        floor_applies,
        optimize_macros,
        fiber_floor=active_fiber_floor,
    ):
        return False

    changed = False
    single_steps = (-20.0, 20.0, -10.0, 10.0, -5.0, 5.0)
    pair_steps = (
        (-5.0, 5.0),
        (-5.0, 10.0),
        (-5.0, 20.0),
        (-5.0, 30.0),
        (-10.0, 10.0),
        (-10.0, 20.0),
        (-10.0, 30.0),
        (-20.0, 10.0),
        (5.0, -5.0),
        (10.0, -5.0),
        (20.0, -5.0),
    )

    for _ in range(45):
        cur_tot = _score_day(day_plan, food_map)
        if _day_is_compliant(
            cur_tot,
            targets,
            tol_pct,
            macro_tol,
            floor_applies,
            optimize_macros,
            fiber_floor=active_fiber_floor,
        ):
            break

        cur_loss = _day_loss(
            cur_tot,
            targets,
            tol_pct,
            macro_tol,
            floor_applies,
            optimize_macros,
            fiber_floor=active_fiber_floor,
        )
        best_loss = cur_loss
        best_action: tuple[int, float, int | None, float] | None = None

        for idx, item in enumerate(items):
            orig = item.grams
            for delta in single_steps:
                cand_g = _round_to_5(orig + delta)
                if cand_g < grams_min or cand_g > grams_max or cand_g == orig:
                    continue
                item.grams = cand_g
                cand_tot = _score_day(day_plan, food_map)
                if _safety_ceilings_ok(cand_tot, cur_tot, targets):
                    cand_loss = _day_loss(
                        cand_tot,
                        targets,
                        tol_pct,
                        macro_tol,
                        floor_applies,
                        optimize_macros,
                        fiber_floor=active_fiber_floor,
                    )
                    if cand_loss < best_loss - 1e-9:
                        best_loss = cand_loss
                        best_action = (idx, cand_g, None, 0.0)
            item.grams = orig

        if best_action is None and len(items) >= 2:
            for i, item_i in enumerate(items):
                orig_i = item_i.grams
                for j, item_j in enumerate(items):
                    if i == j:
                        continue
                    orig_j = item_j.grams
                    for d_i, d_j in pair_steps:
                        cand_i = _round_to_5(orig_i + d_i)
                        cand_j = _round_to_5(orig_j + d_j)
                        if (
                            cand_i < grams_min
                            or cand_i > grams_max
                            or cand_j < grams_min
                            or cand_j > grams_max
                            or (cand_i == orig_i and cand_j == orig_j)
                        ):
                            continue
                        item_i.grams = cand_i
                        item_j.grams = cand_j
                        cand_tot = _score_day(day_plan, food_map)
                        if _safety_ceilings_ok(cand_tot, cur_tot, targets):
                            cand_loss = _day_loss(
                                cand_tot,
                                targets,
                                tol_pct,
                                macro_tol,
                                floor_applies,
                                optimize_macros,
                                fiber_floor=active_fiber_floor,
                            )
                            if cand_loss < best_loss - 1e-9:
                                best_loss = cand_loss
                                best_action = (i, cand_i, j, cand_j)
                    item_j.grams = orig_j
                item_i.grams = orig_i

        if best_action is None:
            break

        idx_a, g_a, idx_b, g_b = best_action
        items[idx_a].grams = g_a
        if idx_b is not None:
            items[idx_b].grams = g_b
        changed = True

    return changed


def adjust_portions(
    plan: MealPlanLLM,
    targets: NutritionTargets,
    food_db: list[dict[str, Any]] | None = None,
    rules: dict[str, Any] | None = None,
) -> tuple[MealPlanLLM, list[str]]:
    """Cân chỉnh grams mỗi món theo tỷ lệ target_kcal/kcal_thực_tế và tinh chỉnh sàn/macro."""
    items_db = food_db if food_db is not None else load_food_db_from_sqlite()
    food_map = {int(item["id"]): item for item in items_db}
    cfg = rules or load_rules()
    v_cfg = cfg["verifier"]
    grams_min = float(v_cfg["grams_min"])
    grams_max = float(v_cfg["grams_max"])
    tol_pct = float(v_cfg["kcal_tolerance_pct"]) / 100.0
    macro_tol = float(v_cfg["macro_tolerance_pct"]) / 100.0
    fiber_tol = float(v_cfg.get("fiber_tolerance_pct", v_cfg["macro_tolerance_pct"])) / 100.0
    fiber_floor = targets.fiber_min_g * (1.0 - fiber_tol) if targets.fiber_min_g > 0 else 0.0
    floor_applies = targets.kcal_floor > 0 and targets.target_kcal >= targets.kcal_floor

    adjusted = plan.model_copy(deep=True)
    trace_notes: list[str] = []

    for _ in range(3):
        changed = False
        for day_plan in adjusted.days:
            day_tot = _score_day(day_plan, food_map)
            actual_kcal = day_tot["kcal"]
            if actual_kcal <= 0 or targets.target_kcal <= 0:
                continue
            diff_ratio = abs(actual_kcal - targets.target_kcal) / targets.target_kcal
            below_floor = floor_applies and actual_kcal < targets.kcal_floor
            if diff_ratio <= tol_pct and not below_floor:
                continue

            # Khi target_kcal sát sàn kcal_floor, nhắm cao hơn ~1.5% tránh làm tròn 5g rớt sàn
            if below_floor and targets.target_kcal <= targets.kcal_floor * 1.03:
                aim_kcal = min(
                    targets.target_kcal * (1.0 + tol_pct * 0.5),
                    max(targets.target_kcal, targets.kcal_floor * 1.015),
                )
            else:
                aim_kcal = targets.target_kcal

            k = aim_kcal / actual_kcal
            for meal in day_plan.meals:
                for item in meal.items:
                    new_grams = _round_to_5(item.grams * k)
                    new_grams = max(grams_min, min(grams_max, new_grams))
                    if new_grams != item.grams:
                        item.grams = new_grams
                        changed = True

            trace_notes.append(f"Ngày {day_plan.day}: đã cân chỉnh khẩu phần ×{k:.2f}")

        if not changed:
            break

    optimize_macros = _macros_consistent_with_kcal(targets)
    for day_plan in adjusted.days:
        if _refine_day_portions(
            day_plan=day_plan,
            targets=targets,
            food_map=food_map,
            grams_min=grams_min,
            grams_max=grams_max,
            tol_pct=tol_pct,
            macro_tol=macro_tol,
            floor_applies=floor_applies,
            optimize_macros=optimize_macros,
            fiber_floor=fiber_floor,
        ):
            trace_notes.append(
                f"Ngày {day_plan.day}: đã tinh chỉnh gram món để đạt sàn năng lượng và cân macro"
            )

    return adjusted, trace_notes
