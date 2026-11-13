"""Kiểm thử tìm kiếm thực phẩm không dấu, lọc món cho phép và import CSV."""

from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from core.food import get_allowed_foods, search_food
from core.schemas import NeedsResult
from db.import_food import import_food_csv
from db.models import Food, FoodNutrient

SAMPLE_DB = [
    {
        "id": 1,
        "name_vi": "Cá hồi áp chảo",
        "name_ascii": "ca hoi ap chao",
        "food_group": "thit_ca",
        "purine_level": "medium",
        "allergen_tags": "seafood",
        "tags": "dam_nac|omega3",
        "kcal": 208.0,
    },
    {
        "id": 2,
        "name_vi": "Cơm gạo lứt",
        "name_ascii": "com gao lut",
        "food_group": "ngu_coc",
        "purine_level": "low",
        "allergen_tags": "",
        "tags": "ngu_coc_nguyen_hat",
        "kcal": 111.0,
    },
    {
        "id": 3,
        "name_vi": "Gan lợn luộc",
        "name_ascii": "gan lon luoc",
        "food_group": "thit_ca",
        "purine_level": "high",
        "allergen_tags": "",
        "tags": "noi_tang",
        "kcal": 134.0,
    },
    {
        "id": 4,
        "name_vi": "Nước ngọt có ga",
        "name_ascii": "nuoc ngot co ga",
        "food_group": "do_uong",
        "purine_level": "low",
        "allergen_tags": "",
        "tags": "nuoc_ngot|do_ngot",
        "kcal": 42.0,
    },
]


def test_search_food_unaccented_ca_hoi() -> None:
    """Tìm 'ca hoi' phải ra 'Cá hồi áp chảo'."""
    res = search_food(query="ca hoi", food_db=SAMPLE_DB)
    assert len(res) == 1
    assert res[0]["name_vi"] == "Cá hồi áp chảo"


def test_search_food_filters() -> None:
    """Lọc theo dị ứng, tag, purine và kcal."""
    res = search_food(
        query="",
        exclude_allergens=["seafood"],
        exclude_tags=["do_ngot"],
        max_purine_level="medium",
        food_db=SAMPLE_DB,
    )
    names = [r["name_vi"] for r in res]
    assert names == ["Cơm gạo lứt"]


def test_get_allowed_foods_by_needs() -> None:
    """get_allowed_foods lọc đúng món cấm cho gout + t2d + dị ứng."""
    needs = NeedsResult(
        needs=["kiem_soat_duong_huyet", "han_che_purin"],
        rule_refs=["NEED_T2D", "NEED_GOUT"],
    )
    allowed = get_allowed_foods(needs, allergens=["seafood"], food_db=SAMPLE_DB)
    assert [f["name_vi"] for f in allowed] == ["Cơm gạo lứt"]


def test_get_allowed_foods_prioritizes_group_diversity() -> None:
    """Ưu tiên đa dạng food_group theo thứ tự round-robin."""
    db = [
        {"id": 1, "name_vi": "Gà", "name_ascii": "ga", "food_group": "thit_ca", "kcal": 150.0},
        {"id": 2, "name_vi": "Bò", "name_ascii": "bo", "food_group": "thit_ca", "kcal": 180.0},
        {"id": 3, "name_vi": "Cơm", "name_ascii": "com", "food_group": "ngu_coc", "kcal": 130.0},
        {"id": 4, "name_vi": "Cải", "name_ascii": "cai", "food_group": "rau", "kcal": 20.0},
    ]
    needs = NeedsResult(needs=[], rule_refs=[])
    allowed = get_allowed_foods(needs, allergens=[], limit=3, food_db=db)
    assert [f["food_group"] for f in allowed] == ["ngu_coc", "rau", "thit_ca"]


def test_import_food_sample_csv_and_search(tmp_path: Path) -> None:
    """Import data/food_sample.csv (40 dòng) vào SQLite tạm và tìm 'ca hoi'."""
    db_file = tmp_path / "test_food.db"
    engine = create_engine(f"sqlite:///{db_file}")
    report = import_food_csv(engine=engine, csv_path=Path("data/food_sample.csv"))

    assert report["is_sample"] is True
    assert report["total_rows"] == 40
    assert report["inserted"] == 40
    assert report["errors"] == []

    with Session(engine) as session:
        rows = session.execute(
            select(Food, FoodNutrient).join(FoodNutrient, Food.id == FoodNutrient.food_id)
        ).all()
        food_db = [
            {
                "id": f.id,
                "name_vi": f.name_vi,
                "name_ascii": f.name_ascii,
                "food_group": f.food_group,
                "purine_level": f.purine_level,
                "allergen_tags": f.allergen_tags,
                "tags": f.tags,
                "kcal": n.kcal,
            }
            for f, n in rows
        ]

    res = search_food(query="ca hoi", food_db=food_db)
    assert any(r["name_vi"] == "Cá hồi áp chảo" for r in res)


def test_import_food_csv_checks_missing_columns(tmp_path: Path) -> None:
    """Thiếu cột bắt buộc phải báo lỗi rõ ràng."""
    bad_csv = tmp_path / "missing_col.csv"
    bad_csv.write_text("code,name_vi\nF1,Cơm\n", encoding="utf-8")
    engine = create_engine(f"sqlite:///{tmp_path / 'bad.db'}")
    report = import_food_csv(engine=engine, csv_path=bad_csv)
    assert report["inserted"] == 0
    assert any("Thiếu cột bắt buộc" in e for e in report["errors"])


def test_import_food_csv_checks_duplicate_negative_and_kcal_warning(tmp_path: Path) -> None:
    """Kiểm tra trùng code, giá trị âm (lỗi) và kcal lệch >20% (cảnh báo, vẫn nạp)."""
    csv_path = tmp_path / "check.csv"
    header = (
        "code,name_vi,food_group,unit_default_g,kcal,protein_g,fat_g,carb_g,"
        "fiber_g,sugar_g,sodium_mg,sat_fat_g,purine_level,allergen_tags,tags,source\n"
    )
    rows = [
        "F1,Món lệch kcal,ngu_coc,100,300,10,0,10,0,0,0,0,low,,,SAMPLE_DATA",
        "F1,Món trùng code,ngu_coc,100,80,10,0,10,0,0,0,0,low,,,SAMPLE_DATA",
        "F2,Món âm,ngu_coc,100,-10,1,0,1,0,0,0,0,low,,,SAMPLE_DATA",
    ]
    csv_path.write_text(header + "\n".join(rows) + "\n", encoding="utf-8")

    engine = create_engine(f"sqlite:///{tmp_path / 'check.db'}")
    report = import_food_csv(engine=engine, csv_path=csv_path)

    assert report["inserted"] == 1
    assert len(report["warnings"]) == 1
    assert "4P+9F+4C" in report["warnings"][0]
    assert any("trùng code" in e for e in report["errors"])
    assert any("âm" in e for e in report["errors"])
