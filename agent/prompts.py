"""Nạp và dựng prompt từ thư mục prompts/ theo SPEC Phụ lục C và mục 10.1."""

from pathlib import Path
from typing import Any

from core.schemas import (
    GuidelineSnippet,
    MealPlanLLM,
    NeedsResult,
    NutritionTargets,
    PatientProfile,
    Violation,
)

DEFAULT_PROMPTS_DIR = Path("prompts")


def load_prompt_template(filename: str, prompts_dir: Path = DEFAULT_PROMPTS_DIR) -> str:
    """Đọc nội dung template prompt từ thư mục prompts/."""
    path = prompts_dir / filename
    return path.read_text(encoding="utf-8")


def sanitize_user_data(text: str) -> str:
    """Khử thẻ rào <user_data> bên trong văn bản người dùng để chống thoát khối dữ liệu."""
    if not text:
        return ""
    cleaned = text.replace("</user_data>", "[/user_data]").replace("<user_data>", "[user_data]")
    return cleaned.strip()


def format_allowed_foods_compact(allowed_foods: list[dict[str, Any]]) -> str:
    """Định dạng danh sách món được phép dạng gọn: id|tên|kcal/100g|nhóm|tags."""
    if not allowed_foods:
        return "Không có món hợp lệ."
    lines: list[str] = []
    for food in allowed_foods:
        fid = int(food["id"])
        name_vi = str(food.get("name_vi", "")).replace("|", "/")
        kcal = food.get("kcal")
        kcal_str = f"{float(kcal):.1f}" if kcal is not None else "0.0"
        group = str(food.get("food_group", "khac")).replace("|", "/")
        tags = str(food.get("tags", "")).strip() or "-"
        lines.append(f"{fid}|{name_vi}|{kcal_str}|{group}|{tags}")
    return "\n".join(lines)


def format_violations_text(violations: list[Violation] | None) -> str:
    """Định dạng danh sách vi phạm từ vòng trước để planner sửa chính xác."""
    if not violations:
        return "Không có"
    lines: list[str] = []
    for v in violations:
        loc_parts: list[str] = []
        if v.day is not None:
            loc_parts.append(f"ngày {v.day}")
        if v.meal:
            loc_parts.append(f"bữa {v.meal}")
        if v.food_id is not None:
            loc_parts.append(f"food_id={v.food_id}")
        loc = f" ({', '.join(loc_parts)})" if loc_parts else ""
        lines.append(f"- [{v.code}]{loc}: {v.message_vi}")
    return "\n".join(lines)


def format_menu_summary(
    plan_scored: list[dict[str, Any]] | None,
    plan_llm: MealPlanLLM | None = None,
    food_name_map: dict[int, str] | None = None,
) -> str:
    """Tạo tóm tắt thực đơn đã kiểm chứng từ số liệu do code tính."""
    parts: list[str] = []
    if plan_scored:
        for d in plan_scored:
            parts.append(
                f"Ngày {d['day']}: {float(d.get('kcal', 0.0)):.0f} kcal "
                f"(Đạm {float(d.get('protein_g', 0.0)):.1f}g, "
                f"Béo {float(d.get('fat_g', 0.0)):.1f}g, "
                f"Carb {float(d.get('carb_g', 0.0)):.1f}g, "
                f"Natri {float(d.get('sodium_mg', 0.0)):.0f}mg)"
            )
    if plan_llm and plan_llm.days:
        name_map = food_name_map or {}
        for day_plan in plan_llm.days:
            meal_strs: list[str] = []
            for meal in day_plan.meals:
                item_strs = [
                    f"{name_map.get(it.food_id, f'food#{it.food_id}')} ({it.grams:.0f}g)"
                    for it in meal.items
                ]
                if item_strs:
                    meal_strs.append(f"{meal.meal}: {', '.join(item_strs)}")
            if meal_strs:
                parts.append(f"Chi tiết ngày {day_plan.day}: " + "; ".join(meal_strs))
    return " | ".join(parts) if parts else "Chưa có chi tiết thực đơn."


def format_snippets_with_source(snippets: list[GuidelineSnippet]) -> str:
    """Định dạng các đoạn hướng dẫn kèm trích dẫn chuẩn [tên tài liệu, tr. X]."""
    if not snippets:
        return "Không có đoạn hướng dẫn nào được truy xuất."
    lines: list[str] = []
    for idx, snip in enumerate(snippets, start=1):
        cite = f"[{snip.source_name}, tr. {snip.page}]"
        clean_text = " ".join(snip.text.split())
        lines.append(f"{idx}. ({snip.disease or 'chung'}) {clean_text} {cite}")
    return "\n".join(lines)


def _render_placeholders(template: str, mapping: dict[str, str]) -> str:
    """Thay thế các biến {{key}} an toàn mà không lỗi khi dữ liệu chứa dấu ngoặc nhọn."""
    rendered = template
    for key, value in mapping.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered


def build_planner_prompt(
    *,
    profile: PatientProfile,
    targets: NutritionTargets,
    needs: NeedsResult,
    allowed_foods: list[dict[str, Any]],
    violations: list[Violation] | None = None,
    prompts_dir: Path = DEFAULT_PROMPTS_DIR,
) -> str:
    """Dựng prompt cho planner từ prompts/planner_system.txt (bọc <user_data>, không gửi tên)."""
    template = load_prompt_template("planner_system.txt", prompts_dir=prompts_dir)
    needs_str = ", ".join(needs.needs) if needs.needs else "duy_tri_can_bang"
    allergens_str = ", ".join(profile.allergens) if profile.allergens else "Không có"
    allowed_str = "\n" + format_allowed_foods_compact(allowed_foods)
    violations_str = format_violations_text(violations)
    preferences_str = sanitize_user_data(profile.preferences_text) or "Không có"

    return _render_placeholders(
        template,
        {
            "days": str(profile.days),
            "patient_code": profile.patient_code,
            "target_kcal": f"{targets.target_kcal:.0f}",
            "protein_g": f"{targets.protein_g:.1f}",
            "fat_g": f"{targets.fat_g:.1f}",
            "carb_g": f"{targets.carb_g:.1f}",
            "sodium_max_mg": f"{targets.sodium_max_mg:.0f}",
            "needs": needs_str,
            "allergens": allergens_str,
            "allowed_foods": allowed_str,
            "violations": violations_str,
            "preferences": preferences_str,
        },
    )


def build_explain_prompt(
    *,
    needs: NeedsResult,
    targets: NutritionTargets,
    snippets: list[GuidelineSnippet],
    plan_scored: list[dict[str, Any]] | None = None,
    plan_llm: MealPlanLLM | None = None,
    food_name_map: dict[int, str] | None = None,
    prompts_dir: Path = DEFAULT_PROMPTS_DIR,
) -> str:
    """Dựng prompt cho bước explain từ prompts/explain_user.txt (chỉ dùng snippets đã truy xuất)."""
    template = load_prompt_template("explain_user.txt", prompts_dir=prompts_dir)
    needs_str = ", ".join(needs.needs) if needs.needs else "duy_tri_can_bang"
    menu_summary = format_menu_summary(
        plan_scored=plan_scored,
        plan_llm=plan_llm,
        food_name_map=food_name_map,
    )
    snippets_str = "\n" + format_snippets_with_source(snippets)

    return _render_placeholders(
        template,
        {
            "needs": needs_str,
            "target_kcal": f"{targets.target_kcal:.0f}",
            "menu_summary": menu_summary,
            "snippets_with_source": snippets_str,
        },
    )
