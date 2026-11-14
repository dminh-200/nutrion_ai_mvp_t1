"""Các hàm thuần tính toán nhu cầu năng lượng và dinh dưỡng theo SPEC mục 6.1–6.2."""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from core.schemas import NeedsResult, NutritionTargets, PatientProfile

DEFAULT_RULES_PATH = Path("config/rules.yaml")


@lru_cache(maxsize=4)
def load_rules(path: Path = DEFAULT_RULES_PATH) -> dict[str, Any]:
    """Đọc cấu hình quy tắc từ file YAML."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _get_val(node: Any, default: float | None = None) -> float:
    """Lấy giá trị số từ dict {value: ...} hoặc số trực tiếp; dùng default nếu thiếu."""
    if node is None:
        if default is not None:
            return float(default)
        raise ValueError("Thiếu giá trị cấu hình số trong rules.yaml.")
    if isinstance(node, dict):
        if "value" in node and node["value"] is not None:
            return float(node["value"])
        if default is not None:
            return float(default)
        raise KeyError("value")
    return float(node)


def calc_bmi(weight_kg: float, height_cm: float) -> float:
    """Tính BMI = weight / (height/100)^2, làm tròn 1 chữ số."""
    height_m = height_cm / 100.0
    return round(weight_kg / (height_m * height_m), 1)


def calc_bmr(sex: str, weight_kg: float, height_cm: float, age: int) -> float:
    """Tính BMR theo công thức Mifflin-St Jeor."""
    base = 10.0 * weight_kg + 6.25 * height_cm - 5.0 * age
    return base + 5.0 if sex == "male" else base - 161.0


def calc_tdee(bmr: float, activity_level: str, rules: dict[str, Any] | None = None) -> float:
    """Tính TDEE = BMR * hệ số hoạt động từ rules.yaml."""
    cfg = rules or load_rules()
    factors = cfg.get("activity_factors") or {}
    factor = _get_val(factors.get(activity_level), default=1.2)
    return round(bmr * factor, 1)


def calc_target_kcal(
    tdee: float,
    needs: NeedsResult,
    profile: PatientProfile,
    rules: dict[str, Any] | None = None,
) -> tuple[float, float]:
    """Tính target_kcal (trừ deficit nếu giam_can, áp sàn theo giới, làm tròn 10 kcal)."""
    cfg = rules or load_rules()
    energy_cfg = cfg.get("energy") or {}
    kcal = tdee
    if "giam_can" in needs.needs:
        deficit = _get_val(energy_cfg.get("deficit_kcal"), default=500.0)
        kcal = tdee - deficit

    floor_cfg = energy_cfg.get("kcal_floor") or {}
    default_floor = 1500.0 if profile.sex == "male" else 1200.0
    kcal_floor = _get_val(floor_cfg.get(profile.sex), default=default_floor)
    kcal = max(kcal, kcal_floor)
    target_kcal = float(round(kcal / 10.0) * 10)
    return target_kcal, kcal_floor


def calc_macros(
    target_kcal: float,
    needs: NeedsResult,
    rules: dict[str, Any] | None = None,
) -> tuple[float, float, float, str]:
    """Tính gram protein, fat, carb theo nhu cầu ưu tiên cao nhất trong rules.yaml."""
    cfg = rules or load_rules()
    chosen_need = "defaults"
    defaults = cfg.get("defaults") or {}
    macro_pct = defaults.get("macro_pct") or {"carb": 55, "protein": 15, "fat": 30}
    needs_cfg = cfg.get("needs") or {}

    for need_name in cfg.get("priority", []):
        if need_name in needs.needs:
            need_cfg = needs_cfg.get(need_name) or {}
            if "macro_pct" in need_cfg:
                macro_pct = need_cfg["macro_pct"]
                chosen_need = need_name
                break

    protein_pct = _get_val(macro_pct.get("protein"), default=15.0)
    carb_pct = _get_val(macro_pct.get("carb"), default=55.0)
    fat_pct = _get_val(macro_pct.get("fat"), default=30.0)

    protein_g = round((target_kcal * (protein_pct / 100.0)) / 4.0, 1)
    carb_g = round((target_kcal * (carb_pct / 100.0)) / 4.0, 1)
    fat_g = round((target_kcal * (fat_pct / 100.0)) / 9.0, 1)
    return protein_g, fat_g, carb_g, chosen_need


def build_targets(
    profile: PatientProfile,
    needs: NeedsResult,
    rules: dict[str, Any] | None = None,
) -> NutritionTargets:
    """Gộp các hàm tính toán, áp quy tắc gộp đa bệnh và trả về NutritionTargets."""
    cfg = rules or load_rules()
    bmi = calc_bmi(profile.weight_kg, profile.height_cm)
    bmr = calc_bmr(profile.sex, profile.weight_kg, profile.height_cm, profile.age)
    tdee = calc_tdee(bmr, profile.activity_level, cfg)
    target_kcal, kcal_floor = calc_target_kcal(tdee, needs, profile, cfg)
    protein_g, fat_g, carb_g, macro_source = calc_macros(target_kcal, needs, cfg)

    defaults = cfg.get("defaults") or {}
    sodium_candidates = [_get_val(defaults.get("sodium_max_mg"), default=2300.0)]
    sugar_candidates = [_get_val(defaults.get("sugar_max_g"), default=50.0)]
    fiber_candidates = [_get_val(defaults.get("fiber_min_g"), default=20.0)]

    needs_cfg = cfg.get("needs") or {}
    for need_name in needs.needs:
        need_cfg = needs_cfg.get(need_name) or {}
        if "sodium_max_mg" in need_cfg:
            sodium_candidates.append(_get_val(need_cfg.get("sodium_max_mg")))
        if "sugar_max_g" in need_cfg:
            sugar_candidates.append(_get_val(need_cfg.get("sugar_max_g")))
        if "fiber_min_g" in need_cfg:
            fiber_candidates.append(_get_val(need_cfg.get("fiber_min_g")))

    rationale = [f"Áp dụng quy tắc: {', '.join(needs.rule_refs)}"]
    rationale.append(f"Tỷ lệ macro theo: {macro_source}")
    if "giam_can" in needs.needs:
        deficit_val = _get_val((cfg.get("energy") or {}).get("deficit_kcal"), default=500.0)
        rationale.append(f"Giảm cân: TDEE - {deficit_val:.0f} kcal")
    rationale.append(f"Sàn năng lượng ({profile.sex}): {kcal_floor:.0f} kcal")

    return NutritionTargets(
        bmi=bmi,
        bmr=round(bmr, 1),
        tdee=tdee,
        target_kcal=target_kcal,
        protein_g=protein_g,
        fat_g=fat_g,
        carb_g=carb_g,
        fiber_min_g=max(fiber_candidates),
        sodium_max_mg=min(sodium_candidates),
        sugar_max_g=min(sugar_candidates),
        kcal_floor=kcal_floor,
        rationale=rationale,
    )
