"""Trang 3: Cổng phê duyệt lâm sàng & điều chỉnh dinh dưỡng Human-in-the-loop (M11 - R2)."""

from typing import Any

import streamlit as st

from agent.graph import resume_review
from app.ui_helpers import (
    format_condition,
    format_meal_name,
    get_status_badge_html,
    init_session_state,
    inject_custom_css,
    render_disclaimer,
    render_hero_banner,
)
from db.repo import (
    get_meal_plan_detail,
    list_meal_plans_for_ui,
    preview_and_verify_edited_items,
    record_review_for_finalized_plan,
)

init_session_state()
inject_custom_css()

render_hero_banner(
    title="Cổng Phê Duyệt Lâm Sàng & Điều Chỉnh Dinh Dưỡng (HITL)",
    subtitle="Kiểm duyệt các ca cần can thiệp y khoa, chỉnh sửa định lượng hoặc từ chối thực đơn.",
    icon="🩺",
)

# Bộ lọc hàng đợi
col_f1, col_f2 = st.columns([2, 1])
with col_f1:
    filter_status = st.selectbox(
        "Lọc hàng đợi theo trạng thái:",
        options=[
            "Tất cả ca chờ duyệt (pending_review & needs_human_review)",
            "Chỉ ca chờ duyệt trong luồng (pending_review)",
            "Chỉ ca cần can thiệp sâu (needs_human_review)",
            "Tất cả thực đơn (toàn bộ trạng thái)",
        ],
        key="queue_status_filter",
    )

status_filter_val: list[str] | str | None
if filter_status.startswith("Tất cả ca chờ duyệt"):
    status_filter_val = ["pending_review", "needs_human_review"]
elif "pending_review" in filter_status:
    status_filter_val = "pending_review"
elif "needs_human_review" in filter_status:
    status_filter_val = "needs_human_review"
else:
    status_filter_val = None

plans_in_queue = list_meal_plans_for_ui(status=status_filter_val, limit=50)

if not plans_in_queue:
    st.info("🎉 Hiện không có ca nào trong hàng đợi cần chuyên gia kiểm duyệt.")
    st.caption("Các ca mới tạo yêu cầu duyệt sẽ tự động xuất hiện tại đây.")
    render_disclaimer()
    st.stop()

# Danh sách chọn ca cần duyệt
options_map: dict[str, int] = {}
for p in plans_in_queue:
    conds_str = ", ".join(format_condition(c) for c in p.get("conditions", []))
    label = (
        f"#{p['id']} - BN: {p.get('patient_code', '')} ({p.get('display_name', '')}) | "
        f"Bệnh lý: [{conds_str or 'Bình thường'}] | "
        f"Trạng thái: {p['status']} | Lần thử: {p.get('retry_count', 0)}"
    )
    options_map[label] = p["id"]

selected_label = st.selectbox(
    "📋 Chọn ca cần duyệt từ hàng đợi:",
    options=list(options_map.keys()),
    key="selected_plan_label",
)
selected_plan_id = options_map[selected_label]
if st.session_state.get("preview_plan_id") != selected_plan_id:
    st.session_state["edit_preview_result"] = None
    st.session_state["preview_plan_id"] = selected_plan_id
    st.session_state["preview_items"] = None
st.session_state["review_selected_plan_id"] = selected_plan_id

# Tải chi tiết thực đơn
detail = get_meal_plan_detail(selected_plan_id)
if not detail:
    st.error("Không tìm thấy thông tin chi tiết của thực đơn này.")
    st.stop()

mp = detail["meal_plan"]
patient_info = detail["patient"]
targets = detail["targets"]
current_status = mp["status"]

# Thông tin tổng quan hồ sơ
with st.container(border=True):
    col_i1, col_i2, col_i3, col_i4 = st.columns(4)
    with col_i1:
        p_name = patient_info.get("display_name", "")
        p_code = patient_info.get("code", "")
        st.markdown(f"**Bệnh nhân:** {p_name} ({p_code})")
        sex_txt = "Nam" if patient_info.get("sex") == "male" else "Nữ"
        st.caption(f"Tuổi: {patient_info.get('age')} | Giới tính: {sex_txt}")
    with col_i2:
        conds = [format_condition(c) for c in patient_info.get("conditions", [])]
        st.markdown(f"**Bệnh lý:** {', '.join(conds) or 'Không'}")
        allergens = patient_info.get("allergens", [])
        st.caption(f"Dị ứng: {', '.join(allergens) or 'Không'}")
    with col_i3:
        st.markdown(f"**Mục tiêu Kcal:** {targets.get('target_kcal', 0):.0f} kcal/ngày")
        st.caption(f"BMR: {targets.get('bmr', 0):.0f} | TDEE: {targets.get('tdee', 0):.0f}")
    with col_i4:
        badge_html = get_status_badge_html(current_status)
        st.markdown(f"**Trạng thái:** {badge_html}", unsafe_allow_html=True)
        st.caption(f"Thread: `{mp.get('thread_id', '')[:16]}...`")

# Kiểm tra vi phạm / Sự kiện guardrail
guardrails = detail.get("guardrail_events", [])
if guardrails or current_status in ("pending_review", "needs_human_review"):
    with st.container(border=True):
        st.markdown("#### ⚠️ Lý do cần chuyên gia xem xét & Vi phạm ghi nhận")
        if guardrails:
            for ge in guardrails:
                lyr = ge.get("layer", "").upper()
                typ = ge.get("type", "")
                st.warning(f"• **[{lyr} / {typ}]**: {ge.get('reason')}")
        else:
            st.info("Thực đơn cần chuyên gia xem xét để đảm bảo an toàn hoặc tối ưu định lượng.")

# Trình chỉnh sửa thực đơn tương tác st.data_editor
st.markdown("#### ✏️ Điều Chỉnh Định Lượng Khẩu Phần Ăn")
st.caption("Chuyên gia có thể sửa grams từng món ăn (nhập 0g để xóa món khỏi thực đơn).")

meal_reverse_map = {
    "Bữa sáng": "breakfast",
    "Bữa trưa": "lunch",
    "Bữa tối": "dinner",
    "Bữa phụ": "snack",
}

editor_rows = [
    {
        "id": it["id"],
        "day": it["day"],
        "meal": format_meal_name(it["meal"]),
        "food_id": it["food_id"],
        "name_vi": it["name_vi"],
        "grams": float(it["grams"]),
    }
    for it in detail.get("items", [])
]

has_menu_items = bool(editor_rows)
if not has_menu_items:
    st.warning("Ca này chưa có món ăn để duyệt. Chuyên gia có thể từ chối và ghi rõ lý do.")
elif current_status == "needs_human_review":
    st.warning("Thực đơn chưa đạt kiểm chứng tự động. Chỉ duyệt sau khi bản sửa đạt kiểm chứng.")

edited_df = st.data_editor(
    editor_rows,
    column_config={
        "id": None,
        "day": st.column_config.NumberColumn("Ngày", disabled=True, width="small"),
        "meal": st.column_config.TextColumn("Bữa ăn", disabled=True, width="medium"),
        "food_id": st.column_config.NumberColumn("Mã món", disabled=True, width="small"),
        "name_vi": st.column_config.TextColumn("Tên món ăn (VN)", disabled=True, width="large"),
        "grams": st.column_config.NumberColumn(
            "Định lượng (g) (*)",
            min_value=0.0,
            max_value=1000.0,
            step=10.0,
            width="medium",
        ),
    },
    use_container_width=True,
    num_rows="fixed",
    key="meal_items_editor",
)

# Chuyển đổi dữ liệu bảng sửa thành format cho DAL
edited_items_payload: list[dict[str, Any]] = []
for r in edited_df:
    m_txt = r.get("meal", "breakfast")
    m_code = meal_reverse_map.get(m_txt, m_txt)
    edited_items_payload.append(
        {
            "day": int(r["day"]),
            "meal": m_code,
            "food_id": int(r["food_id"]),
            "grams": float(r["grams"]),
        }
    )

if st.session_state.get("preview_items") != edited_items_payload:
    st.session_state["edit_preview_result"] = None

# Nút kiểm chứng lại bản sửa (Dry-run)
col_v1, col_v2 = st.columns([1, 2])
with col_v1:
    verify_clicked = st.button(
        "🔍 Kiểm chứng lại bản sửa",
        use_container_width=True,
        key="btn_dry_run_verify",
    )

if verify_clicked:
    with st.spinner("Đang tính toán lại dinh dưỡng và kiểm chứng 11 tiêu chí lâm sàng..."):
        try:
            preview_res = preview_and_verify_edited_items(selected_plan_id, edited_items_payload)
            st.session_state["edit_preview_result"] = preview_res
            st.session_state["preview_items"] = edited_items_payload

            if preview_res.get("is_valid"):
                st.success("✅ Bản sửa hợp lệ! Đạt toàn bộ 11 tiêu chí kiểm chứng an toàn y tế.")
            else:
                st.error("❌ Bản sửa chưa đạt chuẩn lâm sàng. Các vi phạm còn tồn đọng:")
                for v in preview_res.get("violations", []):
                    st.warning(f"• Mã: `{v.get('code')}` | {v.get('message_vi', '')}")
        except Exception as e:
            st.error(f"Lỗi khi kiểm chứng: {e}")

# Form phê duyệt / từ chối
st.markdown("---")
st.markdown("#### 📝 Quyết Định Của Chuyên Gia Dinh Dưỡng")

col_d1, col_d2 = st.columns([1, 2])
with col_d1:
    reviewer_name = st.text_input(
        "Họ tên chuyên gia (*):",
        value="BS. Dinh dưỡng",
        key="reviewer_name_input",
    )
with col_d2:
    review_note = st.text_area(
        "Ghi chú chuyên môn (* bắt buộc nếu từ chối):",
        placeholder="Nhập ghi chú cho bệnh nhân hoặc lý do từ chối thực đơn...",
        key="review_note_input",
    )

# Nút hành động
col_act1, col_act2, col_act3 = st.columns(3)

with col_act1:
    approve_orig_clicked = st.button(
        "✅ Phê duyệt nguyên bản",
        type="primary",
        use_container_width=True,
        disabled=not has_menu_items or current_status != "pending_review",
        key="btn_approve_original",
    )

with col_act2:
    # Nếu đã chạy kiểm chứng và không hợp lệ thì cảnh báo
    preview_state = st.session_state.get("edit_preview_result")
    save_edit_disabled = not has_menu_items or not (
        preview_state is not None and preview_state.get("is_valid", False)
    )

    save_edit_clicked = st.button(
        "💾 Lưu chỉnh sửa & Duyệt",
        use_container_width=True,
        disabled=save_edit_disabled,
        key="btn_save_and_approve",
    )

with col_act3:
    reject_clicked = st.button(
        "❌ Từ chối thực đơn",
        use_container_width=True,
        key="btn_reject_plan",
    )

# Xử lý: Phê duyệt nguyên bản
if approve_orig_clicked:
    with st.spinner("Đang lưu phê duyệt..."):
        try:
            if not has_menu_items or current_status != "pending_review":
                raise ValueError("Chỉ thực đơn đang chờ duyệt và có món ăn mới được duyệt.")
            if current_status == "pending_review":
                review_result = resume_review(
                    thread_id=mp["thread_id"],
                    decision="approve",
                    note=review_note.strip(),
                    reviewer_name=reviewer_name.strip() or "Chuyên gia",
                )
            else:
                review_result = record_review_for_finalized_plan(
                    meal_plan_id=selected_plan_id,
                    reviewer_name=reviewer_name.strip() or "Chuyên gia",
                    decision="approve",
                    note=review_note.strip(),
                )
            st.success("Đã phê duyệt thực đơn thành công!")
            st.rerun()
        except Exception as e:
            st.error(f"Lỗi khi phê duyệt: {e}")

# Xử lý: Lưu chỉnh sửa & Duyệt
if save_edit_clicked:
    with st.spinner("Đang lưu bản chỉnh sửa và phê duyệt..."):
        try:
            preview_res = preview_and_verify_edited_items(selected_plan_id, edited_items_payload)
            if not preview_res["is_valid"]:
                raise ValueError("Bản sửa chưa đạt kiểm chứng. Vui lòng kiểm tra lại.")
            if current_status == "pending_review":
                review_result = resume_review(
                    thread_id=mp["thread_id"],
                    decision="edit",
                    note=review_note.strip(),
                    edited_items=edited_items_payload,
                    reviewer_name=reviewer_name.strip() or "Chuyên gia",
                )
            else:
                review_result = record_review_for_finalized_plan(
                    meal_plan_id=selected_plan_id,
                    reviewer_name=reviewer_name.strip() or "Chuyên gia",
                    decision="edit",
                    note=review_note.strip(),
                    edited_items=edited_items_payload,
                )
            if review_result.get("status") != "approved":
                raise ValueError("Bản sửa chưa được phê duyệt; cần chuyên gia xem lại.")
            st.success("Đã lưu chỉnh sửa và phê duyệt thực đơn thành công!")
            st.session_state["edit_preview_result"] = None
            st.rerun()
        except Exception as e:
            st.error(f"Lỗi khi lưu chỉnh sửa: {e}")

# Xử lý: Từ chối thực đơn (BẮT BUỘC CÓ LÝ DO)
if reject_clicked:
    if not review_note.strip():
        st.error("⚠️ Từ chối thực đơn BẮT BUỘC phải có lý do (Ghi chú chuyên môn).")
    else:
        with st.spinner("Đang ghi nhận từ chối thực đơn..."):
            try:
                if current_status == "pending_review":
                    resume_review(
                        thread_id=mp["thread_id"],
                        decision="reject",
                        note=review_note.strip(),
                        reviewer_name=reviewer_name.strip() or "Chuyên gia",
                    )
                else:
                    record_review_for_finalized_plan(
                        meal_plan_id=selected_plan_id,
                        reviewer_name=reviewer_name.strip() or "Chuyên gia",
                        decision="reject",
                        note=review_note.strip(),
                    )
                st.warning("Đã từ chối thực đơn thành công.")
                st.rerun()
            except Exception as e:
                st.error(f"Lỗi khi từ chối: {e}")

render_disclaimer()
