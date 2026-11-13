"""Kiểm thử phân loại nhu cầu dinh dưỡng trong core/classify.py."""

from core.classify import classify_needs
from core.schemas import PatientProfile


def _profile(**overrides) -> PatientProfile:
    base = {
        "patient_code": "P0001",
        "age": 45,
        "sex": "male",
        "height_cm": 170.0,
        "weight_kg": 65.0,
        "activity_level": "light",
        "conditions": [],
    }
    base.update(overrides)
    return PatientProfile(**base)


def test_classify_single_diseases() -> None:
    """Phân loại đúng từng bệnh đơn lẻ."""
    res_t2d = classify_needs(_profile(conditions=["t2d"]))
    assert "kiem_soat_duong_huyet" in res_t2d.needs
    assert "NEED_T2D" in res_t2d.rule_refs

    res_htn = classify_needs(_profile(conditions=["htn"]))
    assert "giam_natri" in res_htn.needs
    assert "NEED_HTN" in res_htn.rule_refs

    res_gout = classify_needs(_profile(conditions=["gout"]))
    assert "han_che_purin" in res_gout.needs
    assert "NEED_GOUT" in res_gout.rule_refs


def test_classify_obesity_by_bmi_threshold() -> None:
    """BMI >= 25 tự động sinh nhu cầu giam_can dù conditions không có obesity."""
    # 75 / 1.7^2 = 26.0 >= 25
    res = classify_needs(_profile(weight_kg=75.0, conditions=["htn"]))
    assert "giam_can" in res.needs
    assert "NEED_WEIGHT" in res.rule_refs


def test_classify_allergens_and_default() -> None:
    """Dị ứng sinh nhu cầu tránh dị ứng; không có gì sinh mặc định."""
    res_allergy = classify_needs(_profile(allergens=["seafood", "peanut"]))
    assert "tranh_di_ung:seafood" in res_allergy.needs
    assert "tranh_di_ung:peanut" in res_allergy.needs
    assert "NEED_ALLERGY" in res_allergy.rule_refs

    res_default = classify_needs(_profile())
    assert res_default.needs == ["duy_tri_can_bang"]
    assert res_default.rule_refs == ["NEED_DEFAULT"]
