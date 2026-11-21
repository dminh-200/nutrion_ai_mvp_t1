"""Tìm kiếm thực phẩm không dấu và lọc danh sách món cho phép theo SPEC 7.3."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session
from unidecode import unidecode

from core.nutrition import load_rules
from core.schemas import NeedsResult, NutritionTargets
from db.models import Food, FoodNutrient
from db.session import get_engine

PURINE_ORDER = {"low": 0, "medium": 1, "high": 2, "unknown": 1}


def _split_tags(raw: str) -> set[str]:
    """Tách chuỗi tag phân tách bằng '|' hoặc ',' thành tập hợp chuẩn hóa."""
    if not raw:
        return set()
    normalized = raw.replace(",", "|")
    return {t.strip().lower() for t in normalized.split("|") if t.strip()}


def load_food_db_from_sqlite(session: Session | None = None) -> list[dict[str, Any]]:
    """Đọc toàn bộ thực phẩm và dinh dưỡng từ SQLite thành danh sách dict."""
    stmt = select(Food, FoodNutrient).join(FoodNutrient, Food.id == FoodNutrient.food_id)
    if session is not None:
        rows = session.execute(stmt).all()
    else:
        engine = get_engine()
        with Session(engine) as sess:
            rows = sess.execute(stmt).all()

    result: list[dict[str, Any]] = []
    for food, nut in rows:
        result.append(
            {
                "id": food.id,
                "code": food.code,
                "name_vi": food.name_vi,
                "name_ascii": food.name_ascii,
                "food_group": food.food_group,
                "unit_default_g": food.unit_default_g,
                "purine_level": food.purine_level,
                "allergen_tags": food.allergen_tags,
                "tags": food.tags,
                "source": food.source,
                "kcal": nut.kcal,
                "protein_g": nut.protein_g,
                "fat_g": nut.fat_g,
                "carb_g": nut.carb_g,
                "fiber_g": nut.fiber_g,
                "sugar_g": nut.sugar_g,
                "sodium_mg": nut.sodium_mg,
                "sat_fat_g": nut.sat_fat_g,
            }
        )
    return result


def search_food(
    query: str = "",
    max_kcal_per_100g: float | None = None,
    exclude_allergens: list[str] | None = None,
    exclude_tags: list[str] | None = None,
    max_purine_level: str | None = None,
    limit: int = 20,
    food_db: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Tìm kiếm món ăn theo tên không dấu và bộ lọc dinh dưỡng/dị ứng."""
    items = food_db if food_db is not None else load_food_db_from_sqlite()
    has_real_data = any("SAMPLE_DATA" not in str(it.get("source", "")) for it in items)
    q_ascii = unidecode(query).strip().lower()
    ex_allergens = {a.strip().lower() for a in (exclude_allergens or []) if a.strip()}
    ex_tags = {t.strip().lower() for t in (exclude_tags or []) if t.strip()}
    max_purine_rank = PURINE_ORDER.get(max_purine_level, 99) if max_purine_level else 99

    matched: list[dict[str, Any]] = []
    for item in items:
        if has_real_data and "SAMPLE_DATA" in str(item.get("source", "")):
            continue
        name_ascii = (item.get("name_ascii") or unidecode(item["name_vi"])).lower()
        if q_ascii and q_ascii not in name_ascii:
            continue
        if max_kcal_per_100g is not None and float(item["kcal"]) > max_kcal_per_100g:
            continue

        item_allergens = _split_tags(item.get("allergen_tags", ""))
        if ex_allergens & item_allergens:
            continue

        item_tags = _split_tags(item.get("tags", ""))
        if ex_tags & item_tags:
            continue

        purine_rank = PURINE_ORDER.get(item.get("purine_level", "unknown"), 1)
        if purine_rank > max_purine_rank:
            continue

        matched.append(item)

    return matched[:limit]


def get_allowed_foods(
    needs: NeedsResult,
    allergens: list[str] | None = None,
    limit: int = 120,
    food_db: list[dict[str, Any]] | None = None,
    rules: dict[str, Any] | None = None,
    targets: NutritionTargets | None = None,
) -> list[dict[str, Any]]:
    """Lọc danh sách món hợp lệ theo nhu cầu và dị ứng, ưu tiên đa dạng food_group."""
    _ = targets  # Giữ tương thích chữ ký SPEC 7.3; lọc hiện dựa vào needs & allergens.
    cfg = rules or load_rules()
    exclude_tags: list[str] = ["nguyen_lieu_song"]
    max_purine_level: str | None = None

    for need_name in needs.needs:
        need_cfg = cfg["needs"].get(need_name, {})
        exclude_tags.extend(need_cfg.get("avoid_tags", []))
        if "max_purine_level" in need_cfg:
            max_purine_level = need_cfg["max_purine_level"]

    candidates = search_food(
        query="",
        exclude_allergens=allergens or [],
        exclude_tags=exclude_tags,
        max_purine_level=max_purine_level,
        limit=1000,
        food_db=food_db,
    )

    # Sắp xếp round-robin theo food_group để ưu tiên đa dạng nhóm thực phẩm
    by_group: dict[str, list[dict[str, Any]]] = {}
    for item in candidates:
        grp = item.get("food_group", "khac")
        by_group.setdefault(grp, []).append(item)

    diversified: list[dict[str, Any]] = []
    groups = sorted(by_group.keys())
    idx = 0
    while len(diversified) < limit:
        added = False
        for grp in groups:
            if idx < len(by_group[grp]):
                diversified.append(by_group[grp][idx])
                added = True
                if len(diversified) >= limit:
                    break
        if not added:
            break
        idx += 1

    return diversified
