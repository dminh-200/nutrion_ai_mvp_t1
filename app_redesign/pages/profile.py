"""Biểu mẫu hồ sơ ba bước, lưu bản nháp độc lập với widget."""

from html import escape
from typing import Any

import streamlit as st
from pydantic import ValidationError

from app_redesign import ui

DEFAULTS: dict[str, Any] = {
    "patient_code": "DEMO-001",
    "age": 45,
    "sex": "male",
    "height_cm": 170.0,
    "weight_kg": 70.0,
    "activity_level": "moderate",
    "conditions": [],
    "allergens": [],
    "pregnancy": False,
    "lactating": False,
    "ckd_stage": 0,
    "dialysis": False,
    "eating_disorder": False,
    "days": 1,
    "preferences_text": "",
}


def select_sample(samples: list[dict[str, Any]]) -> None:
    """Nạp lại toàn bộ bản nháp khi thay mẫu."""
    index = st.session_state["sample"]
    selected = samples[index - 1] if index else DEFAULTS
    st.session_state["draft"] = {key: selected.get(key, value) for key, value in DEFAULTS.items()}
    st.session_state["step"] = 0
    st.session_state["revision"] = st.session_state.get("revision", 0) + 1


def render() -> None:
    """Hiển thị biểu mẫu và chỉ gọi agent khi người dùng xác nhận."""
    from db.repo import load_sample_patients

    samples = load_sample_patients()
    st.session_state.setdefault("draft", DEFAULTS.copy())
    st.session_state.setdefault("step", 0)
    st.session_state.setdefault("revision", 0)
    if not st.session_state.get("profile_started"):
        ui.hero(
            "DINH DƯỠNG CÓ CHUYÊN GIA ĐỒNG HÀNH",
            "Lên kế hoạch ăn uống phù hợp với bạn",
            "Tạo hồ sơ sức khỏe và sở thích để nhận đề xuất thực đơn có chuyên gia xem xét.",
        )
        first, second = st.columns(2, gap="medium")
        with first, st.container(border=True, key="start-card"):
            ui.card_heading("Tự nhập hồ sơ", "Tạo hồ sơ giả lập qua ba bước.", "profile")
            st.caption("Chuẩn bị thông tin cơ thể, bệnh lý đã xác định và dị ứng thực phẩm.")
            if st.button("Bắt đầu nhập", type="primary", width="stretch"):
                st.session_state["profile_started"] = True
                st.rerun()
        with second, st.container(border=True, key="sample-card"):
            _choose_sample(samples)
        return
    ui.heading("Hồ sơ dinh dưỡng", "Nhập hoặc kiểm tra các thông tin giả lập bên dưới.", "profile")
    with st.expander("Đổi hồ sơ mẫu hoặc bắt đầu lại"):
        _choose_sample(samples)
    step = st.session_state["step"]
    draft = st.session_state["draft"]
    if st.session_state.pop("profile_saved", False):
        st.caption("Đã lưu bước trước vào bản nháp. Chưa gọi mô hình.")
    steps = ["Thông tin cơ thể", "Sức khỏe & dị ứng", "Sở thích & xác nhận"]
    st.html(
        '<div class="stepper">'
        + "".join(
            f'<div class="step {"active" if i == step else "done" if i < step else ""}"'
            f"{' aria-current=step' if i == step else ''}>"
            f"<strong>{ui.icon('check') if i < step else i + 1}</strong>{title}</div>"
            for i, title in enumerate(steps)
        )
        + "</div>"
    )
    left, right = st.columns([2.25, 1], gap="large")
    updates: dict[str, Any] = {}
    with left:
        with st.form(f"profile-{step}-{st.session_state['revision']}", border=True):
            ui.section(f"BƯỚC {step + 1} / 3", steps[step])
            if step == 0:
                updates["patient_code"] = st.text_input(
                    "Mã hồ sơ",
                    draft["patient_code"],
                    help="Chỉ dùng mã giả lập, không nhập tên thật.",
                )
                c1, c2 = st.columns(2)
                updates["age"] = c1.number_input("Tuổi", 1, 120, int(draft["age"]))
                updates["sex"] = c2.selectbox(
                    "Giới tính",
                    ["male", "female"],
                    index=0 if draft["sex"] == "male" else 1,
                    format_func=lambda v: "Nam" if v == "male" else "Nữ",
                )
                updates["height_cm"] = c1.number_input(
                    "Chiều cao (cm)", 50.0, 250.0, float(draft["height_cm"]), step=0.5
                )
                updates["weight_kg"] = c2.number_input(
                    "Cân nặng (kg)", 2.0, 400.0, float(draft["weight_kg"]), step=0.5
                )
                updates["activity_level"] = st.selectbox(
                    "Mức độ vận động",
                    list(ui.ACTIVITIES),
                    index=list(ui.ACTIVITIES).index(draft["activity_level"]),
                    format_func=ui.ACTIVITIES.get,
                    help="Chọn mức phản ánh hoạt động thường ngày, gồm đi lại và tập luyện.",
                )
            elif step == 1:
                updates["conditions"] = st.multiselect(
                    "Bệnh lý đã được xác định",
                    list(ui.CONDITIONS),
                    draft["conditions"],
                    format_func=ui.CONDITIONS.get,
                )
                updates["allergens"] = st.multiselect(
                    "Dị ứng thực phẩm",
                    list(ui.ALLERGENS),
                    draft["allergens"],
                    format_func=ui.ALLERGENS.get,
                )
                st.info("Hãy khai báo đầy đủ. Một số tình trạng cần bác sĩ tư vấn trực tiếp.")
                a, b = st.columns(2)
                updates["pregnancy"] = a.checkbox("Đang mang thai", draft["pregnancy"])
                updates["lactating"] = a.checkbox("Đang cho con bú", draft["lactating"])
                updates["dialysis"] = b.checkbox("Đang chạy thận", draft["dialysis"])
                updates["eating_disorder"] = b.checkbox(
                    "Tiền sử rối loạn ăn uống", draft["eating_disorder"]
                )
                updates["ckd_stage"] = st.number_input(
                    "Giai đoạn bệnh thận mạn (0–5)",
                    0,
                    5,
                    int(draft["ckd_stage"]),
                    help="Chỉ nhập giai đoạn đã được bác sĩ xác định. 0 nghĩa là chưa khai báo.",
                )
            else:
                updates["days"] = st.slider("Số ngày thực đơn", 1, 7, int(draft["days"]))
                updates["preferences_text"] = st.text_area(
                    "Bạn thích ăn gì?",
                    draft["preferences_text"],
                    max_chars=500,
                    placeholder="Ví dụ: thích món Việt, ưu tiên món dễ nấu…",
                )
                st.caption("Kiểm tra bản tóm tắt bên phải trước khi tạo thực đơn.")
            back_col, next_col = st.columns(2)
            back = back_col.form_submit_button("Quay lại", disabled=step == 0, width="stretch")
            forward = next_col.form_submit_button(
                "Tạo thực đơn" if step == 2 else "Tiếp tục →", type="primary", width="stretch"
            )
        if back or forward:
            draft.update(updates)
            if not draft["patient_code"].strip():
                st.error("Mã hồ sơ không được để trống.")
            elif back:
                st.session_state["step"] -= 1
                st.rerun()
            elif step < 2:
                st.session_state["profile_saved"] = True
                st.session_state["step"] += 1
                st.rerun()
            else:
                _create(draft)
    with right:
        ui.section("", "Bản nháp đã lưu", "Cập nhật sau khi bấm Tiếp tục hoặc Quay lại.")
        with st.container(border=True):
            st.markdown(f"**{escape(str(draft['patient_code']))}**")
            st.write(f"{draft['age']} tuổi · {draft['height_cm']:g} cm · {draft['weight_kg']:g} kg")
            st.caption("BỆNH LÝ")
            st.write(
                ", ".join(ui.CONDITIONS.get(c, c) for c in draft["conditions"]) or "Không khai báo"
            )
            st.caption("DỊ ỨNG")
            st.write(
                ", ".join(ui.ALLERGENS.get(c, c) for c in draft["allergens"]) or "Không khai báo"
            )
            flags = [
                label
                for key, label in [
                    ("pregnancy", "Mang thai"),
                    ("lactating", "Cho con bú"),
                    ("dialysis", "Chạy thận"),
                    ("eating_disorder", "Tiền sử rối loạn ăn uống"),
                ]
                if draft[key]
            ]
            if draft["ckd_stage"]:
                flags.append(f"Bệnh thận giai đoạn {draft['ckd_stage']}")
            if flags:
                st.warning(" · ".join(flags))


def _choose_sample(samples: list[dict[str, Any]]) -> None:
    """Thay bản nháp qua thao tác xác nhận riêng."""
    ui.card_heading("Thử với hồ sơ mẫu", "Nạp thông tin giả lập có sẵn.", "sample")
    st.selectbox(
        "Hồ sơ giả lập",
        range(len(samples) + 1),
        format_func=lambda i: (
            "Bản nháp mới"
            if not i
            else (
                ", ".join(ui.CONDITIONS.get(c, c) for c in samples[i - 1].get("conditions", []))
                or "Không có bệnh lý khai báo"
            )
            + f" · {samples[i - 1]['patient_code']}"
        ),
        key="sample",
    )
    if st.session_state.get("profile_started"):
        st.warning("Nạp lựa chọn sẽ thay bản nháp hiện tại, kể cả phần chưa lưu.")
    if st.button("Nạp hồ sơ đã chọn", width="stretch"):
        select_sample(samples)
        st.session_state["profile_started"] = True
        st.rerun()


def _create(draft: dict[str, Any]) -> None:
    """Chạy backend thật ở chế độ mock đã khóa bởi launcher."""
    from agent.graph import run_request
    from core.schemas import PatientProfile

    if st.session_state.get("profile_processing"):
        return
    st.session_state["profile_processing"] = True
    try:
        profile = PatientProfile.model_validate(draft)
        with st.spinner("Đang kiểm tra hồ sơ và xây dựng thực đơn…"):
            result = run_request(profile, tools_mode="direct")
    except ValidationError:
        st.error("Hồ sơ chưa hợp lệ. Vui lòng kiểm tra các trường đã nhập.")
        return
    except Exception:
        st.error("Chưa thể xử lý hồ sơ. Dữ liệu bạn nhập vẫn được giữ để thử lại.")
        return
    finally:
        st.session_state["profile_processing"] = False
    st.session_state["step"] = 0
    st.session_state["result"] = result
    st.session_state["current_profile"] = profile.model_dump()
    st.session_state["active_plan"] = result.get("meal_plan_id")
    owned = st.session_state.setdefault("owned_threads", [])
    if result.get("thread_id"):
        owned.append(result["thread_id"])
    st.session_state.setdefault("preview_results", {})[result.get("meal_plan_id")] = result
    st.session_state["next_page"] = "Thực đơn"
    st.rerun()
