"""Phân loại nhu cầu dinh dưỡng và sàng lọc nguy cơ cao theo SPEC mục 6.3–6.4."""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from core.nutrition import calc_bmi, load_rules
from core.schemas import NeedsResult, PatientProfile, RiskResult

DEFAULT_RISK_RULES_PATH = Path("config/risk_rules.yaml")


@lru_cache(maxsize=4)
def load_risk_rules(path: Path = DEFAULT_RISK_RULES_PATH) -> dict[str, Any]:
    """Đọc cấu hình luật nguy cơ cao từ config/risk_rules.yaml."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def classify_needs(
    profile: PatientProfile,
    rules: dict[str, Any] | None = None,
) -> NeedsResult:
    """Phân loại nhu cầu dinh dưỡng từ hồ sơ bệnh nhân theo SPEC mục 6.3."""
    cfg = rules or load_rules()
    needs: list[str] = []
    rule_refs: list[str] = []

    if "t2d" in profile.conditions:
        needs.append("kiem_soat_duong_huyet")
        rule_refs.append("NEED_T2D")
    if "htn" in profile.conditions:
        needs.append("giam_natri")
        rule_refs.append("NEED_HTN")
    if "gout" in profile.conditions:
        needs.append("han_che_purin")
        rule_refs.append("NEED_GOUT")

    bmi = calc_bmi(profile.weight_kg, profile.height_cm)
    bmi_threshold = float(cfg["needs"]["giam_can"]["bmi_threshold"]["value"])
    if "obesity" in profile.conditions or bmi >= bmi_threshold:
        needs.append("giam_can")
        rule_refs.append("NEED_WEIGHT")

    if profile.allergens:
        for allergen in profile.allergens:
            needs.append(f"tranh_di_ung:{allergen}")
        rule_refs.append("NEED_ALLERGY")

    if not needs:
        needs.append("duy_tri_can_bang")
        rule_refs.append("NEED_DEFAULT")

    return NeedsResult(needs=needs, rule_refs=rule_refs)


def assess_risk(
    profile: PatientProfile,
    risk_rules: dict[str, Any] | None = None,
) -> RiskResult:
    """Sàng lọc ca nguy cơ cao theo SPEC mục 6.4; trả về RiskResult."""
    cfg = risk_rules or load_risk_rules()
    thresholds = cfg["thresholds"]
    rules_cfg = cfg["rules"]

    reasons: list[str] = []
    messages: list[str] = []

    def _add(code: str) -> None:
        if code not in reasons:
            reasons.append(code)
            messages.append(rules_cfg[code]["message_vi"])

    if profile.pregnancy:
        _add("RISK_PREG")
    if profile.lactating:
        _add("RISK_LACT")
    if profile.age < int(thresholds["minor_age"]):
        _add("RISK_MINOR")
    if profile.ckd_stage >= int(thresholds["ckd_stage_min"]) or profile.dialysis:
        _add("RISK_CKD")
    if profile.eating_disorder:
        _add("RISK_ED")

    bmi = calc_bmi(profile.weight_kg, profile.height_cm)
    bmi_low = float(thresholds["bmi_low"]["value"])
    if bmi < bmi_low:
        _add("RISK_BMI_LOW")

    text_lower = profile.preferences_text.lower()
    if text_lower.strip():
        for code, rule_data in rules_cfg.items():
            for kw in rule_data.get("keywords", []):
                if kw.lower() in text_lower:
                    _add(code)
                    break

    return RiskResult(
        high_risk=bool(reasons),
        reasons=reasons,
        message_vi=" ".join(messages),
    )
