"""Mở màn Thực đơn của ca đang được xem."""

import streamlit as st

from app_redesign import meal_studio


def render() -> None:
    """Đọc bản ghi mới nhất rồi chuyển dữ liệu đã chọn cho frontend."""
    from db.repo import get_meal_plan_detail

    result = st.session_state.get("result") or {}
    plan_id = st.session_state.get("active_plan") or result.get("meal_plan_id")
    history = st.session_state.get("preview_results", {})
    result = history.get(plan_id, result if result.get("meal_plan_id") == plan_id else {})
    detail = get_meal_plan_detail(plan_id) if plan_id else None
    role = st.session_state.get("role", "Người bệnh")
    model = meal_studio.build_model(plan_id, detail, result, role)
    meal_studio.render(model)
