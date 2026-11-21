"""Bàn làm việc chuyên gia với kiểm chứng gắn đúng phiên bản."""

import json

import streamlit as st

from app_redesign import ui


def render() -> None:
    """Hiển thị hàng đợi và xử lý quyết định bằng backend gốc."""
    from agent.graph import resume_review
    from db.repo import (
        get_meal_plan_detail,
        list_meal_plans_for_ui,
        preview_and_verify_edited_items,
        record_review_for_finalized_plan,
    )

    ui.heading("Bàn duyệt", "Đối chiếu dị ứng, kiểm chứng khẩu phần và lưu quyết định.", "shield")
    if st.session_state.pop("review_success", False):
        st.success("Đã lưu quyết định trên dữ liệu thử nghiệm.")
    pending = list_meal_plans_for_ui(status=["pending_review", "needs_human_review"], limit=100)
    queue, workspace = st.columns([1, 2.55], gap="medium")
    with queue, st.container(border=True, key="queue-card"):
        ui.section("", "Hàng đợi")
        st.caption(f"{len(pending)} ca chờ duyệt hoặc cần xem xét trong danh sách.")
        kind = st.selectbox("Trạng thái", ["Tất cả", "Chờ duyệt", "Cần xem xét"])
        selected_status = {"Chờ duyệt": "pending_review", "Cần xem xét": "needs_human_review"}.get(
            kind
        )
        search = st.text_input("Tìm hồ sơ", placeholder="Mã hồ sơ hoặc số ca").strip().casefold()
        plans = [
            p
            for p in pending
            if (not selected_status or p["status"] == selected_status)
            and search in f"#{p['id']} {p['patient_code']}".casefold()
        ]
        if not plans:
            ui.empty_state("Không có ca phù hợp", "Đổi bộ lọc hoặc mã tìm kiếm.", "sample")
            return
        by_id = {p["id"]: p for p in plans}
        plan_id = st.selectbox(
            "Chọn hồ sơ",
            list(by_id),
            format_func=lambda i: f"#{i} · {by_id[i]['patient_code']}",
        )
        detail = get_meal_plan_detail(plan_id)
        if not detail:
            st.warning("Ca này không còn tồn tại.")
            return
    with workspace, st.container(border=True, key="review-card"):
        patient = detail["patient"]
        mp = detail["meal_plan"]
        owned = mp["thread_id"] in st.session_state.get("owned_threads", [])
        ui.section("", f"Hồ sơ {patient['code']}")
        st.write(
            f"{patient['age']} tuổi · {patient['height_cm']:g} cm · {patient['weight_kg']:g} kg"
        )
        st.write(
            ", ".join(ui.CONDITIONS.get(c, c) for c in patient["conditions"])
            or "Không có bệnh khai báo"
        )
        if patient["allergens"]:
            st.warning("Dị ứng: " + ", ".join(ui.ALLERGENS.get(a, a) for a in patient["allergens"]))
        else:
            st.caption("Không có dị ứng được khai báo.")
        ui.status_panel(
            mp["status"],
            "Kiểm chứng bản đang xem trước khi duyệt."
            if owned
            else "Ca lịch sử chỉ để xem. Tạo ca mới trong bản thử để thực hành duyệt.",
        )
        if st.button("Xem trang thực đơn"):
            st.session_state["active_plan"] = plan_id
            st.session_state["next_page"] = "Thực đơn"
            st.rerun()
        st.divider()
        ui.section(
            "",
            "Điều chỉnh khẩu phần",
            "Nhập 0 g để bỏ món. Mỗi thay đổi cần được kiểm chứng lại.",
        )
        for event in detail.get("guardrail_events", []):
            st.warning(event["reason"])
        with st.expander("Giải thích và nguồn tham khảo"):
            result = st.session_state.get("preview_results", {}).get(plan_id, {})
            ui.references(mp.get("explanation_md"), result.get("snippets", []))
        rows = [
            {
                **{key: item[key] for key in ("day", "meal", "food_id", "name_vi", "grams")},
                "meal_label": ui.MEALS.get(item["meal"], item["meal"]),
            }
            for item in detail["items"]
        ]
        if not rows:
            st.warning("Ca này chưa có món ăn. Không thể phê duyệt thực đơn rỗng.")
            edited = []
        else:
            edited = st.data_editor(
                rows,
                key=f"editor-{plan_id}",
                width="stretch",
                hide_index=True,
                column_order=["day", "meal_label", "name_vi", "grams"],
                disabled=["day", "meal", "meal_label", "food_id", "name_vi"] if owned else True,
                column_config={
                    "day": st.column_config.NumberColumn("Ngày"),
                    "meal": None,
                    "meal_label": st.column_config.TextColumn("Bữa", width="small"),
                    "food_id": None,
                    "name_vi": st.column_config.TextColumn("Món ăn", width="medium"),
                    "grams": st.column_config.NumberColumn(
                        "Khẩu phần (g)", min_value=0.0, step=5.0, width="small"
                    ),
                },
            )
        payload = [{key: row[key] for key in ("day", "meal", "food_id", "grams")} for row in edited]
        stamp = json.dumps([plan_id, payload], sort_keys=True)
        preview = st.session_state.get("review_preview", {})
        if preview and preview.get("stamp") != stamp:
            st.session_state.pop("review_preview", None)
            preview = {}
            st.info("Ca hoặc định lượng đã thay đổi. Hãy kiểm chứng lại trước khi duyệt.")
        if st.button("Kiểm chứng bản đang xem", disabled=not rows or not owned):
            try:
                result = preview_and_verify_edited_items(plan_id, payload)
                preview = {"stamp": stamp, "result": result}
                st.session_state["review_preview"] = preview
            except Exception:
                st.session_state.pop("review_preview", None)
                preview = {}
                st.error("Chưa thể kiểm chứng bản sửa. Quyết định duyệt vẫn bị khóa.")
        checked = preview.get("result", {})
        if checked:
            if checked["is_valid"]:
                st.success("Bản đang xem đã đạt kiểm chứng dinh dưỡng.")
            else:
                for v in checked["violations"]:
                    where = " · ".join(
                        str(v[key]) for key in ("day", "meal") if v.get(key) is not None
                    )
                    st.warning(f"{where} — {v['message_vi']}" if where else v["message_vi"])
        name = st.text_input(
            "Tên chuyên gia (giả lập)",
            "Chuyên gia thử nghiệm",
            key=f"expert-{plan_id}",
            disabled=not owned,
        )
        note = st.text_area(
            "Ghi chú chuyên môn",
            placeholder="Bắt buộc ghi lý do nếu từ chối.",
            key=f"note-{plan_id}",
            disabled=not owned,
        )
        valid = bool(rows) and checked.get("is_valid", False) and owned and bool(name.strip())
        if owned and rows and not checked.get("is_valid"):
            st.caption("Nút duyệt sẽ mở khi bản đang xem đạt kiểm chứng.")
        if owned and not name.strip():
            st.caption("Nhập tên chuyên gia để ghi lại quyết định.")
        save, reject = st.columns(2)
        save_clicked = save.button(
            "Duyệt bản đã kiểm chứng", type="primary", width="stretch", disabled=not valid
        )
        reject_clicked = reject.button(
            "Từ chối", width="stretch", disabled=not owned or not name.strip()
        )
        if save_clicked or reject_clicked:
            if reject_clicked and not note.strip():
                st.error("Vui lòng ghi rõ lý do từ chối.")
                return
            decision = "edit" if save_clicked else "reject"
            try:
                if save_clicked:
                    latest = preview_and_verify_edited_items(plan_id, payload)
                    if not latest["is_valid"]:
                        st.session_state.pop("review_preview", None)
                        st.error("Bản sửa chưa đạt kiểm chứng.")
                        return
                kwargs = dict(
                    decision=decision,
                    note=note.strip(),
                    reviewer_name=name.strip(),
                    edited_items=payload if save_clicked else None,
                )
                if mp["status"] == "pending_review":
                    outcome = resume_review(mp["thread_id"], **kwargs)
                else:
                    outcome = record_review_for_finalized_plan(plan_id, **kwargs)
                expected = "approved" if save_clicked else "rejected"
                if outcome.get("status") != expected:
                    st.error("Chưa lưu được quyết định mong muốn. Vui lòng xem lại kiểm chứng.")
                    return
            except Exception:
                st.error("Không thể lưu quyết định. Có thể ca đã đổi trạng thái; hãy tải lại.")
                return
            st.session_state["review_success"] = True
            st.session_state.pop("review_preview", None)
            st.rerun()
