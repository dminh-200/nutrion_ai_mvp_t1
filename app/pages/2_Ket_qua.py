"""Trang 2: Kết quả thực đơn dinh dưỡng & phân tích lâm sàng (M11 - R2, R3)."""

from typing import Any

import plotly.graph_objects as go
import streamlit as st

from app.ui_helpers import (
    format_meal_name,
    get_status_badge_html,
    init_session_state,
    inject_custom_css,
    render_disclaimer,
    render_hero_banner,
)
from db.repo import get_meal_plan_detail

init_session_state()
inject_custom_css()

render_hero_banner(
    title="Kết Quả Thực Đơn & Phân Tích Lâm Sàng",
    subtitle="Đánh giá chỉ số thể trạng, khẩu phần ăn cá nhân hóa và báo cáo kiểm chứng an toàn.",
    icon="🥗",
)

result: dict[str, Any] | None = st.session_state.get("current_result")

# Nếu chưa có kết quả trong session_state, thử kiểm tra selected_meal_plan_id
if not result and st.session_state.get("review_selected_plan_id"):
    plan_id = st.session_state["review_selected_plan_id"]
    detail = get_meal_plan_detail(plan_id)
    if detail:
        mp = detail["meal_plan"]
        result = {
            "status": mp["status"],
            "meal_plan_id": mp["id"],
            "thread_id": mp["thread_id"],
            "targets": detail.get("targets"),
            "needs": detail.get("needs"),
            "explanation_md": mp.get("explanation_md", ""),
            "plan_scored": {
                "items": detail.get("items", []),
                "daily_totals": detail.get("daily_totals", []),
            },
            "violations": [],
            "citations": [],
        }

if not result:
    st.info("ℹ️ Hiện chưa có kết quả phân tích nào trong phiên làm việc.")
    st.write("Vui lòng nhập hồ sơ sức khỏe tại **Trang 1** để AI tiến hành phân tích.")
    if st.button("👉 Đi đến Trang 1: Hồ sơ bệnh nhân", key="goto_p1_btn"):
        st.switch_page("pages/1_Ho_so.py")
    render_disclaimer()
    st.stop()

# Trích xuất trạng thái
status = str(result.get("status", "draft"))

# ==============================================================================
# QUY TẮC AN TOÀN Y TẾ BẤT BIẾN: BỊ CHẶN HOẶC CHUYỂN HƯỚNG BÁC SĨ (SPEC 6.4)
# ==============================================================================
if status in ("blocked", "redirect_to_doctor"):
    badge_html = get_status_badge_html(status)
    st.markdown(f"### Trạng thái yêu cầu: {badge_html}", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    if status == "redirect_to_doctor":
        st.error("### 🩺 YÊU CẦU ĐÃ ĐƯỢC CHUYỂN HƯỚNG BÁC SĨ CHUYÊN KHOA")
        st.markdown(
            """
            **Hệ thống AI từ chối sinh thực đơn tự động vì an toàn y tế của người bệnh.**
            
            Theo quy chuẩn an toàn lâm sàng (**docs/SPEC.md mục 6.4**), các đối tượng có yếu tố 
            nguy cơ cao cần được bác sĩ chuyên khoa hoặc chuyên gia dinh dưỡng lâm sàng trực tiếp 
            thăm khám, xét nghiệm và chỉ định phác đồ điều trị chuyên biệt:
            """
        )

        risk_data = result.get("risk")
        reasons: list[str] = []
        if isinstance(risk_data, dict):
            reasons = risk_data.get("reasons", [])
        elif hasattr(risk_data, "reasons"):
            reasons = getattr(risk_data, "reasons", [])

        if reasons:
            st.markdown("##### 🔍 Yếu tố nguy cơ được hệ thống phát hiện:")
            for r in reasons:
                st.warning(f"• {r}")
        else:
            st.warning(
                "• Bệnh nhân thuộc nhóm đối tượng nguy cơ cao (thai kỳ/suy thận/rối loạn ăn uống)."
            )

        st.info(
            "💡 **Khuyến nghị:** Vui lòng liên hệ cơ sở y tế hoặc đặt lịch khám chuyên khoa "
            "dinh dưỡng để được tư vấn an toàn."
        )

    else:  # blocked
        st.error("### 🚫 YÊU CẦU ĐÃ BỊ CHẶN AN TOÀN (SAFETY GUARDRAIL)")
        st.markdown(
            """
            Yêu cầu không thể xử lý do vi phạm chính sách bảo mật hoặc an toàn thông tin:
            - Phát hiện dấu hiệu tấn công prompt injection hoặc chỉ dẫn ghi đè hệ thống.
            - Hoặc nội dung đầu vào không liên quan đến dinh dưỡng lâm sàng.
            """
        )

    st.markdown("---")
    st.markdown(
        "**LƯU Ý NGHIÊM NGẶT:** TUYỆT ĐỐI KHÔNG CUNG CẤP THỰC ĐƠN TỰ ĐỘNG CHO TRƯỜNG HỢP NÀY."
    )
    render_disclaimer()
    st.stop()

# ==============================================================================
# TRƯỜNG HỢP THỰC ĐƠN HỢP LỆ (APPROVED / PENDING_REVIEW / NEEDS_HUMAN_REVIEW)
# ==============================================================================
st.markdown(f"### Trạng thái thực đơn: {get_status_badge_html(status)}", unsafe_allow_html=True)

# Lấy dữ liệu targets
targets_raw = result.get("targets")
targets: dict[str, Any] = {}
if isinstance(targets_raw, dict):
    targets = targets_raw
elif hasattr(targets_raw, "model_dump"):
    targets = targets_raw.model_dump()

bmi = float(targets.get("bmi", 0.0))
bmr = float(targets.get("bmr", 0.0))
tdee = float(targets.get("tdee", 0.0))
target_kcal = float(targets.get("target_kcal", 0.0))
protein_target_g = float(targets.get("protein_g", 0.0))
fat_target_g = float(targets.get("fat_g", 0.0))
carb_target_g = float(targets.get("carb_g", 0.0))
sodium_max_mg = float(targets.get("sodium_max_mg", 2000.0))
fiber_min_g = float(targets.get("fiber_min_g", 25.0))

# Phân loại BMI
def _classify_bmi(v: float) -> str:
    if v < 18.5:
        return "Thiếu cân"
    if v < 23.0:
        return "Bình thường (Chuẩn châu Á)"
    if v < 25.0:
        return "Thừa cân"
    return "Béo phì"

with st.container(border=True):
    st.markdown("#### 📊 Chỉ số thể trạng & Năng lượng mục tiêu")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Chỉ số BMI", f"{bmi:.1f}", help=_classify_bmi(bmi))
    with c2:
        st.metric("BMR (Cơ bản)", f"{bmr:.0f} kcal", help="Năng lượng chuyển hóa cơ bản")
    with c3:
        st.metric("TDEE (Tiêu hao)", f"{tdee:.0f} kcal", help="Tổng năng lượng tiêu hao hàng ngày")
    with c4:
        st.metric(
            "Mục tiêu khẩu phần", f"{target_kcal:.0f} kcal/ngày", help="Năng lượng AI khuyến nghị"
        )

# Trích xuất dữ liệu scored items và daily totals
plan_scored = result.get("plan_scored") or {}
items_list: list[dict[str, Any]] = []
daily_totals: list[dict[str, Any]] = []

if isinstance(plan_scored, dict):
    raw_items = plan_scored.get("items", [])
    for it in raw_items:
        if isinstance(it, dict):
            items_list.append(it)
        elif hasattr(it, "model_dump"):
            items_list.append(it.model_dump())
    daily_totals = plan_scored.get("daily_totals", [])

# Tính trung bình dinh dưỡng các ngày
n_days = len(daily_totals) if daily_totals else 1
avg_kcal = sum(d.get("kcal", 0) for d in daily_totals) / n_days if daily_totals else 0.0
avg_protein = sum(d.get("protein_g", 0) for d in daily_totals) / n_days if daily_totals else 0.0
avg_fat = sum(d.get("fat_g", 0) for d in daily_totals) / n_days if daily_totals else 0.0
avg_carb = sum(d.get("carb_g", 0) for d in daily_totals) / n_days if daily_totals else 0.0
avg_sodium = sum(d.get("sodium_mg", 0) for d in daily_totals) / n_days if daily_totals else 0.0
avg_fiber = sum(d.get("fiber_g", 0) for d in daily_totals) / n_days if daily_totals else 0.0

# Nâng cấp trực quan R3: Biểu đồ Donut Macro & Progress Bars
with st.container(border=True):
    st.markdown("#### ⚖️ Cân Bằng Dinh Dưỡng Thực Tế (Trung Bình Mỗi Ngày)")
    col_chart, col_prog = st.columns([1, 1])

    with col_chart:
        # Năng lượng từng chất: Protein 4 kcal/g, Fat 9 kcal/g, Carb 4 kcal/g
        p_kcal = avg_protein * 4
        f_kcal = avg_fat * 9
        c_kcal = avg_carb * 4
        total_macro_kcal = max(p_kcal + f_kcal + c_kcal, 1.0)

        fig = go.Figure(
            data=[
                go.Pie(
                    labels=["Đạm (Protein)", "Béo (Fat)", "Tinh bột (Carb)"],
                    values=[round(p_kcal, 1), round(f_kcal, 1), round(c_kcal, 1)],
                    hole=0.55,
                    marker=dict(colors=["#0D9488", "#F59E0B", "#0284C7"]),
                    textinfo="label+percent",
                    hoverinfo="label+value+percent",
                )
            ]
        )
        fig.update_layout(
            showlegend=False,
            margin=dict(t=10, b=10, l=10, r=10),
            height=260,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with col_prog:
        st.markdown(f"**Năng lượng thực tế:** {avg_kcal:.0f} / {target_kcal:.0f} kcal")
        kcal_ratio = min(max(avg_kcal / target_kcal, 0.0), 1.5) if target_kcal > 0 else 0.0
        st.progress(min(kcal_ratio, 1.0))

        st.markdown(f"**Natri trung bình:** {avg_sodium:.0f} / {sodium_max_mg:.0f} mg")
        sod_ratio = min(max(avg_sodium / sodium_max_mg, 0.0), 1.5) if sodium_max_mg > 0 else 0.0
        st.progress(min(sod_ratio, 1.0))

        st.markdown(f"**Chất xơ trung bình:** {avg_fiber:.1f} / {fiber_min_g:.0f} g")
        fib_ratio = min(max(avg_fiber / fiber_min_g, 0.0), 1.5) if fiber_min_g > 0 else 0.0
        st.progress(min(fib_ratio, 1.0))

        st.caption("Khẩu phần đã được cân bằng tỷ lệ chất sinh năng lượng theo hướng dẫn.")

# Bảng thực đơn chi tiết từng ngày
st.markdown("#### 🍱 Chi Tiết Thực Đơn Từng Ngày")

# Phân nhóm món ăn theo Ngày và Bữa
by_day: dict[int, dict[str, list[dict[str, Any]]]] = {}
for it in items_list:
    d = int(it.get("day", 1))
    m = str(it.get("meal", "breakfast"))
    by_day.setdefault(d, {}).setdefault(m, []).append(it)

days_sorted = sorted(by_day.keys()) if by_day else [1]
tabs = st.tabs([f"📅 Ngày {d}" for d in days_sorted])

for tab, day_num in zip(tabs, days_sorted, strict=False):
    with tab:
        day_meals = by_day.get(day_num, {})
        for meal_code in ("breakfast", "lunch", "dinner", "snack"):
            meal_items = day_meals.get(meal_code, [])
            if not meal_items:
                continue

            st.markdown(f"##### 🍴 {format_meal_name(meal_code)}")
            table_data: list[dict[str, Any]] = []
            for it in meal_items:
                table_data.append(
                    {
                        "Tên món ăn (Việt Nam)": it.get("name_vi", "Món ăn"),
                        "Định lượng (g)": f"{it.get('grams', 0):.0f}g",
                        "Kcal": round(it.get("kcal", 0), 1),
                        "Đạm (g)": round(it.get("protein_g", 0), 1),
                        "Béo (g)": round(it.get("fat_g", 0), 1),
                        "Tinh bột (g)": round(it.get("carb_g", 0), 1),
                        "Natri (mg)": round(it.get("sodium_mg", 0), 1),
                    }
                )
            st.dataframe(table_data, use_container_width=True, hide_index=True)

        # Hiển thị tổng ngày
        curr_total = next((t for t in daily_totals if t.get("day") == day_num), None)
        if curr_total:
            st.info(
                f"**Tổng ngày {day_num}:** {curr_total.get('kcal', 0):.0f} Kcal | "
                f"Đạm: {curr_total.get('protein_g', 0):.1f}g | "
                f"Béo: {curr_total.get('fat_g', 0):.1f}g | "
                f"Tinh bột: {curr_total.get('carb_g', 0):.1f}g | "
                f"Natri: {curr_total.get('sodium_mg', 0):.0f}mg"
            )

# Giải thích & Trích dẫn hướng dẫn lâm sàng
explanation_md = result.get("explanation_md", "")
if explanation_md:
    with st.container(border=True):
        st.markdown("#### 📖 Báo Cáo Giải Trình Lâm Sàng")
        st.markdown(explanation_md)

citations = result.get("citations", [])
if citations:
    with st.expander("📚 Tài Liệu Hướng Dẫn Lâm Sàng Đã Trích Dẫn (RAG)"):
        for c in citations:
            if isinstance(c, dict):
                src = c.get("source_name", "Hướng dẫn lâm sàng")
                yr = c.get("year", "")
                pg = c.get("page", "")
                txt = c.get("text", "")
            else:
                src = getattr(c, "source_name", "Hướng dẫn")
                yr = getattr(c, "year", "")
                pg = getattr(c, "page", "")
                txt = getattr(c, "text", "")
            st.markdown(f"**{src} ({yr})** — *Trang {pg}*")
            st.caption(f'"{txt}"')

render_disclaimer()
