"""Kiểm thử sàng lọc nguy cơ cao trong core/classify.py."""

import pytest

from core.classify import assess_risk
from core.schemas import PatientProfile


def _profile(**overrides) -> PatientProfile:
    base = {
        "patient_code": "P0001",
        "age": 35,
        "sex": "female",
        "height_cm": 160.0,
        "weight_kg": 55.0,
        "activity_level": "light",
        "conditions": ["t2d"],
    }
    base.update(overrides)
    return PatientProfile(**base)


def test_assess_risk_normal_patient() -> None:
    """Bệnh nhân bình thường không bị đánh dấu nguy cơ cao."""
    res = assess_risk(_profile())
    assert res.high_risk is False
    assert res.reasons == []


@pytest.mark.parametrize(
    ("overrides", "expected_code"),
    [
        ({"pregnancy": True}, "RISK_PREG"),
        ({"lactating": True}, "RISK_LACT"),
        ({"age": 16}, "RISK_MINOR"),
        ({"ckd_stage": 4}, "RISK_CKD"),
        ({"dialysis": True}, "RISK_CKD"),
        ({"eating_disorder": True}, "RISK_ED"),
        ({"weight_kg": 38.0, "height_cm": 160.0}, "RISK_BMI_LOW"),
        ({"preferences_text": "Tôi đang mang thai tháng thứ 3"}, "RISK_PREG"),
    ],
)
def test_assess_risk_triggers(overrides: dict, expected_code: str) -> None:
    """Các điều kiện nguy cơ cao đều bị chặn đúng mã luật."""
    res = assess_risk(_profile(**overrides))
    assert res.high_risk is True
    assert expected_code in res.reasons
    assert len(res.message_vi) > 0
