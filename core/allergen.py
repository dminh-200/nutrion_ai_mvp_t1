"""Kiểm tra dị ứng thực phẩm theo SPEC mục 7.3."""

from typing import Any

from core.food import _split_tags, load_food_db_from_sqlite
from core.schemas import Violation


def check_allergen(
    food_ids: list[int],
    allergens: list[str],
    food_db: list[dict[str, Any]] | None = None,
) -> list[Violation]:
    """Kiểm tra danh sách food_id có chứa dị nguyên của bệnh nhân hay không."""
    items = food_db if food_db is not None else load_food_db_from_sqlite()
    food_map = {int(f["id"]): f for f in items}
    patient_allergens = {a.strip().lower() for a in allergens if a.strip()}

    violations: list[Violation] = []
    for fid in food_ids:
        if fid not in food_map:
            raise ValueError(f"Không tìm thấy food_id={fid} trong cơ sở dữ liệu thực phẩm.")
        food = food_map[fid]
        food_allergens = _split_tags(food.get("allergen_tags", ""))
        matched = sorted(patient_allergens & food_allergens)
        if matched:
            violations.append(
                Violation(
                    code="ALLERGEN",
                    message_vi=(
                        f"Món '{food['name_vi']}' chứa dị nguyên: {', '.join(matched)}."
                    ),
                    food_id=fid,
                )
            )
    return violations
