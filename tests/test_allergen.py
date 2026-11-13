"""Kiểm thử phát hiện dị ứng thực phẩm trong core/allergen.py."""

import pytest

from core.allergen import check_allergen

SAMPLE_DB = [
    {"id": 1, "name_vi": "Cá hồi áp chảo", "allergen_tags": "seafood"},
    {"id": 2, "name_vi": "Cơm gạo lứt", "allergen_tags": ""},
]


def test_check_allergen_detects_violation() -> None:
    """Phát hiện đúng vi phạm dị ứng mã ALLERGEN."""
    violations = check_allergen([1, 2], ["seafood"], food_db=SAMPLE_DB)
    assert len(violations) == 1
    assert violations[0].code == "ALLERGEN"
    assert violations[0].food_id == 1


def test_check_allergen_missing_food_raises() -> None:
    """Món không tồn tại phải báo lỗi rõ ràng, không crash ngầm."""
    with pytest.raises(ValueError, match="food_id=999"):
        check_allergen([999], ["seafood"], food_db=SAMPLE_DB)
