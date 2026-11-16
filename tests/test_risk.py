"""Kiểm thử sàng lọc nguy cơ cao trong core/classify.py."""

import pytest

from core.classify import assess_risk, assess_text_risk_details
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


@pytest.mark.parametrize(
    ("text", "expected_code"),
    [
        ("Tôi đang bầu và muốn ăn canh bầu", "RISK_PREG"),
        ("Tôi ăn canh bầu vì tôi đang bầu", "RISK_PREG"),
        ("Tôi đang có em bé", "RISK_PREG"),
        ("toi dang co em be", "RISK_PREG"),
        ("toi dang bau va muon an canh bau", "RISK_PREG"),
        ("Tôi không mang thai nhưng đang cho con bú", "RISK_LACT"),
        ("Tôi không ăn canh bầu nhưng đang bầu", "RISK_PREG"),
        ("Tôi đang bất tỉnh, đường huyết rất thấp, cần thực đơn ngay", "RISK_EMERGENCY"),
    ],
)
def test_assess_risk_contextual_multi_clause_and_emergency(
    text: str,
    expected_code: str,
) -> None:
    """Sàng lọc theo từng vị trí khớp, nhiều mệnh đề và tình huống cấp cứu."""
    res = assess_risk(_profile(preferences_text=text))
    assert res.high_risk is True
    assert expected_code in res.reasons


@pytest.mark.parametrize(
    "safe_text",
    [
        "Tôi không mang thai, chỉ muốn ăn canh bầu",
        "Chế độ ăn gồm bầu dục (thận) lợn và bầu luộc",
        "Tôi không có em bé",
        "Tôi không còn cho con bú và thích ăn rau luộc",
        "Tôi hay đau đầu chóng mặt, chẩn đoán giúp tôi bị bệnh gì với.",
        "Tôi muốn thực đơn để phòng tránh tụt đường huyết",
    ],
)
def test_assess_risk_negation_and_benign_collocations_safe(safe_text: str) -> None:
    """Phủ định trực tiếp, tên món chứa từ 'bầu' và cụm phòng tránh không bị chặn nhầm."""
    res = assess_risk(_profile(preferences_text=safe_text))
    assert res.high_risk is False
    assert res.reasons == []


@pytest.mark.parametrize(
    "ambiguous_text",
    [
        "Tôi không chắc mình có mang thai không, lập thực đơn giúp tôi",
        "Nghi ngờ có bầu, cần tư vấn ăn uống",
        "Nhà có em bé nên cần gợi ý món ăn",
    ],
)
def test_assess_text_risk_details_flags_ambiguous_cases(ambiguous_text: str) -> None:
    """Các cách diễn đạt mơ hồ chưa xác định được chuyển sang danh sách cần duyệt."""
    details = assess_text_risk_details(ambiguous_text)
    assert details.confirmed.high_risk is False
    assert "RISK_PREG" in details.ambiguous_reasons
