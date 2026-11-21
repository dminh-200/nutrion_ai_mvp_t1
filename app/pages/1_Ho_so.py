"""Trang 1: Khảo sát và nhập liệu hồ sơ sức khỏe bệnh nhân (M11 - R2)."""

import streamlit as st

from agent.graph import run_request
from app.ui_helpers import (
    format_activity_level,
    format_allergen,
    format_condition,
    init_session_state,
    inject_custom_css,
    render_hero_banner,
)
from core.schemas import PatientProfile
from db.repo import load_sample_patients

init_session_state()
inject_custom_css()

render_hero_banner(
    title="Khảo Sát Hồ Sơ Dinh Dưỡng Lâm Sàng",
    subtitle="Nhập thông tin thể trạng, bệnh lý nền và nhu cầu để AI tính toán khẩu phần phù hợp.",
    icon="📋",
)

# Nạp 30 bệnh nhân mẫu
sample_patients = load_sample_patients()
sample_options = ["-- Tự nhập hồ sơ mới --"] + [
    f"{p['patient_code']} - {p.get('display_name', '')} "
    f"({', '.join(p.get('conditions', [])) or 'Bình thường'})"
    for p in sample_patients
]

def _apply_sample_profile() -> None:
    """Đồng bộ các ô nhập khi người dùng chọn hồ sơ mẫu."""
    index = st.session_state.get("sample_selector_idx", 0)
    sample = sample_patients[index - 1] if index > 0 else {}
    values = {
        "input_patient_code": str(sample.get("patient_code", "BN-001")),
        "input_age": int(sample.get("age", 45)),
        "input_sex": "Nam" if sample.get("sex", "male") == "male" else "Nữ",
        "input_height": float(sample.get("height_cm", 165.0)),
        "input_weight": float(sample.get("weight_kg", 65.0)),
        "input_activity": str(sample.get("activity_level", "sedentary")),
        "input_conditions": list(sample.get("conditions", [])),
        "input_allergens": list(sample.get("allergens", [])),
        "input_pregnancy": bool(sample.get("pregnancy", False)),
        "input_lactating": bool(sample.get("lactating", False)),
        "input_ckd": int(sample.get("ckd_stage", 0)),
        "input_dialysis": bool(sample.get("dialysis", False)),
        "input_eating_disorder": bool(sample.get("eating_disorder", False)),
        "input_preferences": str(sample.get("preferences_text", "")),
        "input_days": int(sample.get("days", 3)),
    }
    st.session_state.update(values)
    st.session_state["profile_step"] = 1


selected_idx = st.selectbox(
    "Chọn hồ sơ giả lập để thử nhanh:",
    options=range(len(sample_options)),
    format_func=lambda i: sample_options[i],
    key="sample_selector_idx",
    on_change=_apply_sample_profile,
)

selected_p: dict[str, object] = {}
if selected_idx > 0:
    selected_p = sample_patients[selected_idx - 1]

# Giá trị mặc định
def_code = str(selected_p.get("patient_code", "BN-001"))
def_age = int(selected_p.get("age", 45))
def_sex = "Nam" if selected_p.get("sex", "male") == "male" else "Nữ"
def_height = float(selected_p.get("height_cm", 165.0))
def_weight = float(selected_p.get("weight_kg", 65.0))
def_act = str(selected_p.get("activity_level", "sedentary"))
def_conds = list(selected_p.get("conditions", []))
def_allergens = list(selected_p.get("allergens", []))
def_preg = bool(selected_p.get("pregnancy", False))
def_lact = bool(selected_p.get("lactating", False))
def_ckd = int(selected_p.get("ckd_stage", 0))
def_dialysis = bool(selected_p.get("dialysis", False))
def_ed = bool(selected_p.get("eating_disorder", False))
def_pref = str(selected_p.get("preferences_text", ""))
def_days = int(selected_p.get("days", 3))

for key, default in {
    "input_patient_code": def_code,
    "input_age": def_age,
    "input_sex": def_sex,
    "input_height": def_height,
    "input_weight": def_weight,
    "input_activity": def_act,
    "input_conditions": def_conds,
    "input_allergens": def_allergens,
    "input_pregnancy": def_preg,
    "input_lactating": def_lact,
    "input_ckd": def_ckd,
    "input_dialysis": def_dialysis,
    "input_eating_disorder": def_ed,
    "input_preferences": def_pref,
    "input_days": def_days,
}.items():
    st.session_state.setdefault(key, default)

# Giữ dữ liệu widget khi chuyển bước trên Streamlit.
for key in list(st.session_state):
    if key.startswith("input_"):
        st.session_state[key] = st.session_state[key]
st.session_state.setdefault("profile_step", 1)
step = st.session_state["profile_step"]
st.markdown(f"**Bước {step}/3** · Thông tin cơ thể → Sức khỏe → Xác nhận")
st.progress(step / 3)
submit_btn = False
if step == 1:
    with st.container(border=True):
        st.markdown("#### 👤 Thông tin cá nhân & Thể trạng")
        col1, col2, col3 = st.columns(3)
        with col1:
            patient_code = st.text_input("Mã bệnh nhân (*)", key="input_patient_code")
            age = st.number_input(
                "Tuổi (*)", min_value=1, max_value=120, key="input_age"
            )
        with col2:
            sex_str = st.radio(
                "Giới tính (*)",
                ["Nam", "Nữ"],
                horizontal=True,
                key="input_sex",
            )
            height_cm = st.number_input(
                "Chiều cao (cm) (*)",
                min_value=50.0,
                max_value=250.0,
                step=0.5,
                key="input_height",
            )
        with col3:
            weight_kg = st.number_input(
                "Cân nặng (kg) (*)",
                min_value=2.0,
                max_value=400.0,
                step=0.5,
                key="input_weight",
            )
            activity_levels = ["sedentary", "light", "moderate", "active", "very_active"]
            activity_level = st.selectbox(
                "Mức độ vận động (*)",
                options=activity_levels,
                format_func=format_activity_level,
                key="input_activity",
            )

    if st.button("Tiếp tục: Sức khỏe", type="primary", width="stretch"):
        st.session_state["profile_step"] = 2
        st.rerun()
elif step == 2:
    with st.container(border=True):
        st.markdown("#### 🩺 Bệnh lý nền & Dị ứng thực phẩm")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            conditions = st.multiselect(
                "Bệnh lý nền (hỗ trợ điều trị):",
                options=["t2d", "htn", "gout", "obesity"],
                format_func=format_condition,
                key="input_conditions",
            )
        with col_c2:
            valid_allergens = ["seafood", "peanut", "milk", "egg", "gluten", "soy"]
            allergens = st.multiselect(
                "Dị ứng thực phẩm (loại trừ tuyệt đối):",
                options=valid_allergens,
                format_func=format_allergen,
                key="input_allergens",
            )

    with st.container(border=True):
        st.markdown("#### ⚠️ Tình trạng sức khỏe cần lưu ý")
        st.caption("Lưu ý: Ca nguy cơ cao sẽ được phát hiện và tự động chuyển hướng bác sĩ.")
        col_r1, col_r2, col_r3 = st.columns(3)
        with col_r1:
            pregnancy = st.checkbox("Đang mang thai", key="input_pregnancy")
            lactating = st.checkbox("Đang cho con bú", key="input_lactating")
        with col_r2:
            ckd_stage = st.number_input(
                "Giai đoạn suy thận mạn (CKD 0-5):",
                min_value=0,
                max_value=5,
                key="input_ckd",
            )
            dialysis = st.checkbox("Đang chạy thận nhân tạo", key="input_dialysis")
        with col_r3:
            eating_disorder = st.checkbox(
                "Tiền sử rối loạn ăn uống", key="input_eating_disorder"
            )

    back, forward = st.columns(2)
    if back.button("Quay lại", width="stretch"):
        st.session_state["profile_step"] = 1
        st.rerun()
    if forward.button("Tiếp tục: Xác nhận", type="primary", width="stretch"):
        st.session_state["profile_step"] = 3
        st.rerun()
else:
    with st.container(border=True):
        st.markdown("#### 🍽️ Kế hoạch & Sở thích ăn uống")
        col_p1, col_p2 = st.columns([1, 2])
        with col_p1:
            days = st.slider(
                "Số ngày thực đơn:",
                min_value=1,
                max_value=7,
                key="input_days",
            )
        with col_p2:
            preferences_text = st.text_area(
                "Ghi chú / Sở thích ẩm thực (tối đa 500 ký tự):",
                max_chars=500,
                placeholder="Ví dụ: Thích ăn cá, không thích thịt bò, ăn nhạt...",
                key="input_preferences",
            )

    st.markdown("#### Kiểm tra lại thông tin")
    st.write(
        f"Mã hồ sơ: {st.session_state['input_patient_code']} · "
        f"Tuổi: {st.session_state['input_age']} · Giới tính: {st.session_state['input_sex']}"
    )
    st.write(
        f"Chiều cao: {st.session_state['input_height']} cm · "
        f"Cân nặng: {st.session_state['input_weight']} kg"
    )
    conditions_summary = ", ".join(
        format_condition(c) for c in st.session_state["input_conditions"]
    )
    allergens_summary = ", ".join(format_allergen(a) for a in st.session_state["input_allergens"])
    st.write("Bệnh lý: " + (conditions_summary or "Không khai báo"))
    st.write("Dị ứng: " + (allergens_summary or "Không khai báo"))
    special = []
    for key, label in (
        ("input_pregnancy", "Đang mang thai"),
        ("input_lactating", "Đang cho con bú"),
        ("input_dialysis", "Đang chạy thận"),
        ("input_eating_disorder", "Tiền sử rối loạn ăn uống"),
    ):
        if st.session_state[key]:
            special.append(label)
    if st.session_state["input_ckd"]:
        special.append(f"Bệnh thận giai đoạn {st.session_state['input_ckd']}")
    st.write("Tình trạng cần lưu ý: " + (", ".join(special) or "Không khai báo"))
    st.write(f"Số ngày: {st.session_state['input_days']}")
    back, forward = st.columns(2)
    if back.button("Quay lại", width="stretch"):
        st.session_state["profile_step"] = 2
        st.rerun()
    submit_btn = forward.button(
        "Tạo thực đơn", type="primary", width="stretch",
        disabled=st.session_state.get("analyzing", False),
    )

if submit_btn:
    st.session_state["analyzing"] = True
    sex_code = "male" if st.session_state["input_sex"] == "Nam" else "female"

    try:
        profile = PatientProfile(
            patient_code=st.session_state["input_patient_code"].strip() or "BN-001",
            age=int(st.session_state["input_age"]),
            sex=sex_code,  # type: ignore[arg-type]
            height_cm=float(st.session_state["input_height"]),
            weight_kg=float(st.session_state["input_weight"]),
            activity_level=st.session_state["input_activity"],  # type: ignore[arg-type]
            conditions=st.session_state["input_conditions"],  # type: ignore[arg-type]
            allergens=st.session_state["input_allergens"],  # type: ignore[arg-type]
            pregnancy=st.session_state["input_pregnancy"],
            lactating=st.session_state["input_lactating"],
            ckd_stage=int(st.session_state["input_ckd"]),
            dialysis=st.session_state["input_dialysis"],
            eating_disorder=st.session_state["input_eating_disorder"],
            preferences_text=st.session_state["input_preferences"].strip(),
            days=int(st.session_state["input_days"]),
        )

        with st.status("Đang phân tích lâm sàng và xử lý hồ sơ...", expanded=True) as status_box:
            st.write("Hệ thống đang xử lý hồ sơ, vui lòng chờ.")

            result = run_request(profile=profile)
            st.session_state["current_result"] = result
            st.session_state["current_profile"] = profile.model_dump()
            status_box.update(label="Đã hoàn tất phân tích!", state="complete", expanded=False)

        st.session_state["analyzing"] = False
        st.success("Phân tích thành công! Đang chuyển đến trang Kết quả...")
        st.switch_page("pages/2_Ket_qua.py")

    except Exception as e:
        st.session_state["analyzing"] = False
        st.error(f"Đã xảy ra lỗi khi phân tích: {e}")
        for note in getattr(e, "__notes__", []):
            if note.startswith("Lượt gửi API"):
                st.caption(note)
