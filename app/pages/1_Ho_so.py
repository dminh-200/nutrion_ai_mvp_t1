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

selected_idx = st.selectbox(
    "💡 Chọn nhanh bệnh nhân mẫu để điền tự động (30 ca theo chuẩn SPEC 7.2):",
    options=range(len(sample_options)),
    format_func=lambda i: sample_options[i],
    key="sample_selector_idx",
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

with st.container(border=True):
    st.markdown("#### 👤 Thông tin cá nhân & Thể trạng")
    col1, col2, col3 = st.columns(3)
    with col1:
        patient_code = st.text_input("Mã bệnh nhân (*)", value=def_code, key="input_patient_code")
        age = st.number_input(
            "Tuổi (*)", min_value=1, max_value=120, value=def_age, key="input_age"
        )
    with col2:
        sex_str = st.radio(
            "Giới tính (*)",
            ["Nam", "Nữ"],
            index=0 if def_sex == "Nam" else 1,
            horizontal=True,
            key="input_sex",
        )
        height_cm = st.number_input(
            "Chiều cao (cm) (*)",
            min_value=50.0,
            max_value=250.0,
            value=def_height,
            step=0.5,
            key="input_height",
        )
    with col3:
        weight_kg = st.number_input(
            "Cân nặng (kg) (*)",
            min_value=2.0,
            max_value=400.0,
            value=def_weight,
            step=0.5,
            key="input_weight",
        )
        activity_levels = ["sedentary", "light", "moderate", "active", "very_active"]
        act_idx = activity_levels.index(def_act) if def_act in activity_levels else 0
        activity_level = st.selectbox(
            "Mức độ vận động (*)",
            options=activity_levels,
            index=act_idx,
            format_func=format_activity_level,
            key="input_activity",
        )

with st.container(border=True):
    st.markdown("#### 🩺 Bệnh lý nền & Dị ứng thực phẩm")
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        conditions = st.multiselect(
            "Bệnh lý nền (hỗ trợ điều trị):",
            options=["t2d", "htn", "gout", "obesity"],
            default=[c for c in def_conds if c in ["t2d", "htn", "gout", "obesity"]],
            format_func=format_condition,
            key="input_conditions",
        )
    with col_c2:
        valid_allergens = ["seafood", "peanut", "milk", "egg", "gluten", "soy"]
        allergens = st.multiselect(
            "Dị ứng thực phẩm (loại trừ tuyệt đối):",
            options=valid_allergens,
            default=[a for a in def_allergens if a in valid_allergens],
            format_func=format_allergen,
            key="input_allergens",
        )

with st.container(border=True):
    st.markdown("#### ⚠️ Tình trạng đặc biệt (Sàng lọc nguy cơ cao SPEC 6.4)")
    st.caption("Lưu ý: Ca nguy cơ cao sẽ được phát hiện và tự động chuyển hướng bác sĩ.")
    col_r1, col_r2, col_r3 = st.columns(3)
    with col_r1:
        pregnancy = st.checkbox("Đang mang thai", value=def_preg, key="input_pregnancy")
        lactating = st.checkbox("Đang cho con bú", value=def_lact, key="input_lactating")
    with col_r2:
        ckd_stage = st.number_input(
            "Giai đoạn suy thận mạn (CKD 0-5):",
            min_value=0,
            max_value=5,
            value=def_ckd,
            key="input_ckd",
        )
        dialysis = st.checkbox("Đang chạy thận nhân tạo", value=def_dialysis, key="input_dialysis")
    with col_r3:
        eating_disorder = st.checkbox(
            "Tiền sử rối loạn ăn uống", value=def_ed, key="input_eating_disorder"
        )

with st.container(border=True):
    st.markdown("#### 🍽️ Kế hoạch & Sở thích ăn uống")
    col_p1, col_p2 = st.columns([1, 2])
    with col_p1:
        days = st.slider(
            "Số ngày thực đơn:",
            min_value=1,
            max_value=7,
            value=def_days,
            key="input_days",
        )
    with col_p2:
        preferences_text = st.text_area(
            "Ghi chú / Sở thích ẩm thực (tối đa 500 ký tự):",
            value=def_pref,
            max_chars=500,
            placeholder="Ví dụ: Thích ăn cá, không thích thịt bò, ăn nhạt...",
            key="input_preferences",
        )

st.markdown("<br>", unsafe_allow_html=True)
is_analyzing = st.session_state.get("analyzing", False)
submit_btn = st.button(
    "🚀 Phân tích & Tạo thực đơn dinh dưỡng",
    type="primary",
    use_container_width=True,
    disabled=is_analyzing,
    key="submit_profile_btn",
)

if submit_btn:
    st.session_state["analyzing"] = True
    sex_code = "male" if sex_str == "Nam" else "female"

    try:
        profile = PatientProfile(
            patient_code=patient_code.strip() or "BN-001",
            age=int(age),
            sex=sex_code,  # type: ignore[arg-type]
            height_cm=float(height_cm),
            weight_kg=float(weight_kg),
            activity_level=activity_level,  # type: ignore[arg-type]
            conditions=conditions,  # type: ignore[arg-type]
            allergens=allergens,  # type: ignore[arg-type]
            pregnancy=pregnancy,
            lactating=lactating,
            ckd_stage=int(ckd_stage),
            dialysis=dialysis,
            eating_disorder=eating_disorder,
            preferences_text=preferences_text.strip(),
            days=int(days),
        )

        with st.status("Đang phân tích lâm sàng và xử lý hồ sơ...", expanded=True) as status_box:
            st.write("🔍 **Bước 1/4:** Sàng lọc an toàn guardrail & phát hiện nguy cơ cao...")
            st.write("📊 **Bước 2/4:** Phân loại nhu cầu & tính toán mục tiêu năng lượng...")
            st.write("🥗 **Bước 3/4:** Xây dựng khẩu phần & điều chỉnh định lượng...")
            st.write("🛡️ **Bước 4/4:** Kiểm chứng lâm sàng đa tầng 11 tiêu chí...")

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
