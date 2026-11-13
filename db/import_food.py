"""Nhập dữ liệu thực phẩm từ data/food.csv (hoặc data/food_sample.csv) vào SQLite."""

import csv
from pathlib import Path

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session
from unidecode import unidecode

from db.init_db import init_db
from db.models import Food, FoodNutrient
from db.session import get_engine

PRIMARY_FOOD_CSV = Path("data/food.csv")
SAMPLE_FOOD_CSV = Path("data/food_sample.csv")
REQUIRED_COLUMNS = (
    "code",
    "name_vi",
    "food_group",
    "unit_default_g",
    "kcal",
    "protein_g",
    "fat_g",
    "carb_g",
    "fiber_g",
    "sugar_g",
    "sodium_mg",
    "sat_fat_g",
    "purine_level",
    "allergen_tags",
    "tags",
    "source",
)


def resolve_food_csv(csv_path: Path | None = None) -> tuple[Path, bool]:
    """Chọn file CSV thực phẩm: ưu tiên data/food.csv, fallback data/food_sample.csv."""
    if csv_path is not None:
        return csv_path, "sample" in csv_path.name.lower()
    if PRIMARY_FOOD_CSV.exists():
        return PRIMARY_FOOD_CSV, False
    return SAMPLE_FOOD_CSV, True


def import_food_csv(
    engine: Engine | None = None,
    csv_path: Path | None = None,
) -> dict[str, object]:
    """Đọc CSV thực phẩm, kiểm tra hợp lệ và ghi vào bảng food + food_nutrient."""
    target_engine = engine or get_engine()
    init_db(target_engine)

    path, is_sample = resolve_food_csv(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file thực phẩm: {path}")

    inserted = 0
    updated = 0
    errors: list[str] = []
    warnings: list[str] = []

    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = set(reader.fieldnames or [])
        missing_cols = [col for col in REQUIRED_COLUMNS if col not in fieldnames]
        if missing_cols:
            errors.append(f"Thiếu cột bắt buộc: {', '.join(missing_cols)}")
            return {
                "file": str(path),
                "is_sample": is_sample,
                "total_rows": 0,
                "inserted": 0,
                "updated": 0,
                "errors": errors,
                "warnings": warnings,
            }
        rows = list(reader)

    seen_codes: set[str] = set()
    with Session(target_engine) as session:
        existing_foods = {food.code: food for food in session.scalars(select(Food)).all()}

        for idx, row in enumerate(rows, start=2):
            code = (row.get("code") or "").strip()
            name_vi = (row.get("name_vi") or "").strip()
            if not code or not name_vi:
                errors.append(f"Dòng {idx}: thiếu code hoặc name_vi")
                continue
            if code in seen_codes:
                errors.append(f"Dòng {idx} ({code}): trùng code trong file CSV")
                continue
            seen_codes.add(code)

            try:
                kcal = float(row["kcal"])
                protein_g = float(row["protein_g"])
                fat_g = float(row["fat_g"])
                carb_g = float(row["carb_g"])
                fiber_g = float(row.get("fiber_g") or 0.0)
                sugar_g = float(row.get("sugar_g") or 0.0)
                sodium_mg = float(row.get("sodium_mg") or 0.0)
                sat_fat_g = float(row.get("sat_fat_g") or 0.0)
                unit_default_g = float(row.get("unit_default_g") or 100.0)
            except (KeyError, ValueError) as exc:
                errors.append(f"Dòng {idx} ({code}): lỗi số liệu ({exc})")
                continue

            if min(kcal, protein_g, fat_g, carb_g, fiber_g, sugar_g, sodium_mg, sat_fat_g) < 0:
                errors.append(f"Dòng {idx} ({code}): giá trị dinh dưỡng âm")
                continue

            expected_kcal = 4.0 * protein_g + 9.0 * fat_g + 4.0 * carb_g
            if (expected_kcal > 0 and abs(kcal - expected_kcal) / expected_kcal > 0.20) or (
                expected_kcal == 0 and kcal > 0
            ):
                warnings.append(
                    f"Dòng {idx} ({code}): kcal={kcal:.1f} lệch >20% "
                    f"so với 4P+9F+4C ({expected_kcal:.1f})"
                )

            name_ascii = unidecode(name_vi).lower()
            food_obj = existing_foods.get(code)
            if food_obj is None:
                food_obj = Food(
                    code=code,
                    name_vi=name_vi,
                    name_ascii=name_ascii,
                    food_group=(row.get("food_group") or "khac").strip(),
                    unit_default_g=unit_default_g,
                    purine_level=(row.get("purine_level") or "unknown").strip(),
                    allergen_tags=(row.get("allergen_tags") or "").strip(),
                    tags=(row.get("tags") or "").strip(),
                    source=(row.get("source") or "").strip(),
                )
                session.add(food_obj)
                session.flush()
                existing_foods[code] = food_obj
                inserted += 1
            else:
                food_obj.name_vi = name_vi
                food_obj.name_ascii = name_ascii
                food_obj.food_group = (row.get("food_group") or "khac").strip()
                food_obj.unit_default_g = unit_default_g
                food_obj.purine_level = (row.get("purine_level") or "unknown").strip()
                food_obj.allergen_tags = (row.get("allergen_tags") or "").strip()
                food_obj.tags = (row.get("tags") or "").strip()
                food_obj.source = (row.get("source") or "").strip()
                updated += 1

            nutrient = session.get(FoodNutrient, food_obj.id)
            if nutrient is None:
                nutrient = FoodNutrient(
                    food_id=food_obj.id,
                    kcal=kcal,
                    protein_g=protein_g,
                    fat_g=fat_g,
                    carb_g=carb_g,
                    fiber_g=fiber_g,
                    sugar_g=sugar_g,
                    sodium_mg=sodium_mg,
                    sat_fat_g=sat_fat_g,
                )
                session.add(nutrient)
            else:
                nutrient.kcal = kcal
                nutrient.protein_g = protein_g
                nutrient.fat_g = fat_g
                nutrient.carb_g = carb_g
                nutrient.fiber_g = fiber_g
                nutrient.sugar_g = sugar_g
                nutrient.sodium_mg = sodium_mg
                nutrient.sat_fat_g = sat_fat_g

        session.commit()

    return {
        "file": str(path),
        "is_sample": is_sample,
        "total_rows": len(rows),
        "inserted": inserted,
        "updated": updated,
        "errors": errors,
        "warnings": warnings,
    }


if __name__ == "__main__":
    report = import_food_csv()
    print(f"File: {report['file']} (sample={report['is_sample']})")
    print(
        f"Tổng dòng: {report['total_rows']} | "
        f"Thêm mới: {report['inserted']} | Cập nhật: {report['updated']}"
    )
    if report["warnings"]:
        print(f"Cảnh báo ({len(report['warnings'])}):")
        for warn in report["warnings"]:
            print(f"  - {warn}")
    if report["errors"]:
        print(f"Lỗi ({len(report['errors'])}):")
        for err in report["errors"]:
            print(f"  - {err}")
    if not report["errors"] and not report["warnings"]:
        print("Kiểm tra dữ liệu: không có lỗi hay cảnh báo.")
