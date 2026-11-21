"""Chuẩn bị dữ liệu hiển thị cho màn Thực đơn desktop."""

from collections import defaultdict
from functools import cache
from math import isfinite
from pathlib import Path
from typing import Any

import streamlit as st

from app_redesign import ui

DIST = Path(__file__).parent / "frontend" / "dist"
DISH_FIELDS = ("grams", "kcal", "protein_g", "fat_g", "carb_g", "sodium_mg")
GOAL_FIELDS = ("target_kcal", "sodium_max_mg", "fiber_min_g", "bmi", "bmr", "tdee")
NEEDS = {
    "kiem_soat_duong_huyet": "Kiểm soát đường huyết",
    "giam_natri": "Giảm natri",
    "han_che_purin": "Hạn chế purin",
    "giam_can": "Hỗ trợ quản lý cân nặng",
    "can_bang_dinh_duong": "Cân bằng dinh dưỡng",
}
STATUSES = {
    "pending_review": ("Chờ chuyên gia duyệt", "Hãy chờ chuyên gia duyệt trước khi áp dụng."),
    "approved": ("Đã được chuyên gia duyệt", "Xem quyết định và ghi chú của chuyên gia bên dưới."),
    "needs_human_review": ("Cần chuyên gia xem xét", "Kế hoạch chưa được duyệt để áp dụng."),
    "rejected": ("Thực đơn bị từ chối", "Xem ghi chú của chuyên gia hoặc quay lại Hồ sơ."),
    "blocked": ("Chưa thể xử lý yêu cầu", "Kiểm tra lại thông tin đã nhập trong Hồ sơ."),
    "redirect_to_doctor": (
        "Cần tư vấn trực tiếp",
        "Thông tin trong hồ sơ cần được bác sĩ hoặc chuyên gia đánh giá trực tiếp.",
    ),
    "unavailable": ("Chưa có khẩu phần", "Không có món ăn hoặc số liệu để trình bày cho ca này."),
    "empty": ("Bạn chưa có thực đơn", "Tạo hồ sơ giả lập để xem kế hoạch theo ngày và từng bữa."),
}
PLAN_STATUSES = {"pending_review", "approved", "needs_human_review"}
MEAL_ORDER = {kind: index for index, kind in enumerate(ui.MEALS)}


def _number(value: Any) -> float | None:
    """Giữ giá trị hữu hạn, phân biệt số 0 với dữ liệu thiếu."""
    return float(value) if type(value) in (int, float) and isfinite(value) else None


def _days(detail: dict[str, Any], result: dict[str, Any], edited: bool) -> list[dict[str, Any]]:
    """Nhóm các dòng khẩu phần và giữ tổng ngày do backend trả về."""
    by_day: dict[int, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in detail.get("items", []):
        kind = str(row["meal"])
        by_day[int(row["day"])][kind].append(
            {
                "id": row.get("id"),
                "name": str(row["name_vi"]),
                **{field: _number(row.get(field)) for field in DISH_FIELDS},
            }
        )
    totals = {int(row["day"]): row for row in detail.get("daily_totals", [])}
    scored = result.get("plan_scored") or []
    if isinstance(scored, dict):
        scored = scored.get("daily_totals", [])
    fiber = {} if edited else {int(row["day"]): _number(row.get("fiber_g")) for row in scored}
    days = []
    for day, meal_rows in sorted(by_day.items()):
        meals = []
        for kind in sorted(meal_rows, key=lambda k: MEAL_ORDER.get(k, len(MEAL_ORDER))):
            items = meal_rows[kind]
            kcal = [item["kcal"] for item in items]
            meals.append(
                {
                    "kind": kind,
                    "label": ui.MEALS.get(kind, "Bữa khác"),
                    "items": items,
                    "kcal": round(sum(kcal), 1) if None not in kcal else None,
                }
            )
        total = totals.get(day, {})
        days.append(
            {
                "number": day,
                "metrics": {
                    **{field: _number(total.get(field)) for field in DISH_FIELDS[1:]},
                    "fiber_g": fiber.get(day),
                },
                "meals": meals,
            }
        )
    return days


def _sources(snippets: list[Any], allow_excerpt: bool) -> list[dict[str, Any]]:
    """Gom trích đoạn theo tài liệu và trang, hiển thị nội dung dạng văn bản."""
    entries: dict[tuple[str, str], list[str]] = {}
    for snippet in snippets:
        row = snippet.model_dump() if hasattr(snippet, "model_dump") else snippet
        if not isinstance(row, dict) or not row.get("source_name"):
            continue
        name = str(row["source_name"]).strip()
        page = str(row["page"]) if row.get("page") is not None else ""
        excerpts = entries.setdefault((name, page), [])
        excerpt = str(row.get("text") or "").strip()
        if allow_excerpt and excerpt and excerpt not in excerpts:
            excerpts.append(excerpt)
    return [
        {"name": name, "page": page, "excerpts": excerpts}
        for (name, page), excerpts in entries.items()
    ]


def build_model(
    plan_id: int | None,
    detail: dict[str, Any] | None,
    result: dict[str, Any],
    role: str,
) -> dict[str, Any]:
    """Ánh xạ dữ liệu của một ca và chặn thực đơn chưa được phép hiển thị."""
    record = detail or {}
    plan = record.get("meal_plan") or result
    status = plan.get("status")
    patient = record.get("patient") or {}
    reviews = record.get("reviews", [])
    note = str(reviews[-1].get("note") or "") if reviews else ""
    days = []
    if status in PLAN_STATUSES:
        days = _days(record, result, edited=any(row.get("decision") == "edit" for row in reviews))
    state = status if status in STATUSES else "unavailable" if detail or result else "empty"
    title, message = STATUSES[state]
    model = {
        "identity": str(plan_id) if plan_id is not None else state,
        "status": state,
        "status_label": title,
        "message": message,
        "patient_code": str(patient.get("code") or ""),
        "days": days,
        "review_note": note,
    }
    if days:
        goals = record.get("targets") or {}
        needs = (record.get("needs") or {}).get("needs", [])
        execution = result.get("execution")
        model.update(
            {
                "goals": {key: _number(goals.get(key)) for key in GOAL_FIELDS},
                "needs": [NEEDS[code] for code in needs if code in NEEDS],
                "sources": _sources(
                    result.get("snippets") or [], allow_excerpt=role in {"Chuyên gia", "Quản trị"}
                ),
                "retry_count": _number(plan.get("retry_count")),
                "diagnostics": (
                    {
                        key: _number(execution.get(key))
                        for key in ("api_attempts", "mock_calls", "cache_hits")
                    }
                    if isinstance(execution, dict)
                    else None
                ),
            }
        )
    return model


@cache
def component_asset(name: str, root_class: str) -> Any:
    """Đăng ký mã và kiểu dáng cục bộ của một component."""
    return st.components.v2.component(
        f"nutri_{name.replace('-', '_')}",
        html=f'<div class="{root_class}"></div>',
        css=(DIST / f"{name}.css").read_text(encoding="utf-8"),
        js=(DIST / f"{name}.js").read_text(encoding="utf-8"),
    )


@cache
def font_styles() -> str:
    """Đọc phông chữ dùng chung cho hai vùng React."""
    return (DIST / "fonts.css").read_text(encoding="utf-8")


def _go_profile() -> None:
    """Chuyển về Hồ sơ bằng bộ điều hướng của bản thử."""
    st.session_state["next_page"] = "Hồ sơ"


def render(model: dict[str, Any]) -> None:
    """Gắn dữ liệu của ca hiện tại vào giao diện React."""
    try:
        component = component_asset("meal-studio", "nutri-meal-root")
    except FileNotFoundError:
        st.error("Chưa có bản build Thực đơn. Chạy npm run build trong app_redesign/frontend.")
        return
    with st.container(key="nutri-meal-studio"):
        component(data=model, key="meal-studio", on_go_profile_change=_go_profile)
