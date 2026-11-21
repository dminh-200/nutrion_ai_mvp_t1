"""Khởi tạo cơ sở dữ liệu SQLite và seed danh mục bệnh, dị nguyên."""

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from db.models import Allergen, Base, Condition
from db.session import get_engine

CONDITIONS = [
    ("t2d", "Tiểu đường type 2"),
    ("htn", "Tăng huyết áp"),
    ("gout", "Gout"),
    ("obesity", "Béo phì"),
]

ALLERGENS = [
    ("seafood", "Hải sản"),
    ("peanut", "Đậu phộng / Lạc"),
    ("milk", "Sữa"),
    ("egg", "Trứng"),
    ("gluten", "Gluten"),
    ("soy", "Đậu nành"),
]


def _ensure_meal_plan_columns(engine: Engine) -> None:
    """Bổ sung các cột lưu trữ nguy cơ/trích dẫn/vi phạm trên meal_plan nếu DB cũ chưa có."""
    with engine.begin() as conn:
        cols = {
            row[1]
            for row in conn.exec_driver_sql("PRAGMA table_info(meal_plan)").fetchall()
        }
        for col_name, col_def in (
            ("risk_json", "TEXT NOT NULL DEFAULT '{}'"),
            ("snippets_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("violations_json", "TEXT NOT NULL DEFAULT '[]'"),
            ("draft_plan_json", "TEXT NOT NULL DEFAULT '{}'"),
        ):
            if col_name not in cols:
                conn.exec_driver_sql(f"ALTER TABLE meal_plan ADD COLUMN {col_name} {col_def}")


def init_db(engine: Engine | None = None) -> None:
    """Tạo toàn bộ bảng và seed danh mục condition, allergen (idempotent)."""
    target_engine = engine or get_engine()
    Base.metadata.create_all(bind=target_engine)
    _ensure_meal_plan_columns(target_engine)

    with Session(target_engine) as session:
        existing_conds = set(session.scalars(select(Condition.code)).all())
        for code, name_vi in CONDITIONS:
            if code not in existing_conds:
                session.add(Condition(code=code, name_vi=name_vi))

        existing_allergens = set(session.scalars(select(Allergen.code)).all())
        for code, name_vi in ALLERGENS:
            if code not in existing_allergens:
                session.add(Allergen(code=code, name_vi=name_vi))

        session.commit()


if __name__ == "__main__":
    init_db()
    print("Đã khởi tạo CSDL và seed danh mục condition, allergen.")
