"""Các hàm hỗ trợ UI, CSS styling, components và định dạng tiếng Việt cho Streamlit (M11)."""

from typing import Any

import streamlit as st
import yaml

from db.repo import get_system_warnings

CONDITIONS_MAP = {
    "t2d": "Đái tháo đường T2",
    "htn": "Tăng huyết áp",
    "gout": "Gout",
    "obesity": "Béo phì",
}

ALLERGENS_MAP = {
    "seafood": "Hải sản",
    "peanut": "Đậu phộng",
    "milk": "Sữa",
    "egg": "Trứng",
    "gluten": "Gluten",
    "soy": "Đậu nành",
}

ACTIVITY_MAP = {
    "sedentary": "Ít vận động (văn phòng, tĩnh tại)",
    "light": "Vận động nhẹ (1-3 buổi/tuần)",
    "moderate": "Vận động vừa phải (3-5 buổi/tuần)",
    "active": "Vận động nhiều (6-7 buổi/tuần)",
    "very_active": "Vận động rất nhiều (lao động nặng/thể thao)",
}

MEAL_MAP = {
    "breakfast": "Bữa sáng",
    "lunch": "Bữa trưa",
    "dinner": "Bữa tối",
    "snack": "Bữa phụ",
}

STATUS_MAP = {
    "approved": "Đã duyệt",
    "pending_review": "Chờ duyệt",
    "needs_human_review": "Cần chuyên gia xem",
    "blocked": "Bị chặn",
    "rejected": "Đã từ chối",
    "redirect_to_doctor": "Chuyển hướng bác sĩ",
    "draft": "Bản nháp",
}

RISK_REASON_MAP = {
    "RISK_PREG": "Đang mang thai",
    "RISK_LACT": "Đang cho con bú",
    "RISK_MINOR": "Chưa đủ tuổi trưởng thành",
    "RISK_CKD": "Bệnh thận mạn hoặc đang chạy thận",
    "RISK_ED": "Có tiền sử rối loạn ăn uống",
    "RISK_BMI_LOW": "Chỉ số BMI dưới mức an toàn",
    "RISK_TEXT": "Ghi chú sức khỏe cần bác sĩ đánh giá",
}


def format_risk_reason(code: str) -> str:
    """Đổi mã nguy cơ nội bộ thành lời giải thích cho người dùng."""
    return RISK_REASON_MAP.get(code, "Tình trạng sức khỏe cần tư vấn trực tiếp")


def format_condition(code: str) -> str:
    """Chuyển mã bệnh lý sang tiếng Việt thân thiện."""
    return CONDITIONS_MAP.get(code.lower().strip(), code)


def format_allergen(code: str) -> str:
    """Chuyển mã dị nguyên sang tiếng Việt thân thiện."""
    return ALLERGENS_MAP.get(code.lower().strip(), code)


def format_activity_level(code: str) -> str:
    """Chuyển mã mức độ vận động sang tiếng Việt thân thiện."""
    return ACTIVITY_MAP.get(code.lower().strip(), code)


def format_meal_name(meal: str) -> str:
    """Chuyển mã bữa ăn sang tên tiếng Việt chuẩn."""
    return MEAL_MAP.get(meal.lower().strip(), meal.capitalize())


def format_status(status: str) -> str:
    """Chuyển mã trạng thái sang tiếng Việt chuẩn."""
    return STATUS_MAP.get(status.lower().strip(), status)


def execution_summary(execution: dict[str, Any] | None) -> str:
    """Mô tả nguồn kết quả dựa trên các sự kiện thực thi đã ghi nhận."""
    if execution is None:
        return "Nguồn kết quả: Bản ghi cũ chưa có thông tin lượt gửi API."
    api = int(execution.get("api_attempts", 0))
    cache = int(execution.get("cache_hits", 0))
    mock = int(execution.get("mock_calls", 0))
    parts = [f"Đã gửi API mới: {api} lượt" if api else "Không gửi API mới"]
    if cache:
        parts.append(f"Dùng cache: {cache} lượt")
    if mock:
        parts.append(f"Giả lập: {mock} lượt")
    if not (api or cache or mock):
        parts.append("Xử lý bằng quy tắc, chưa chạy mô hình")
    return "Nguồn kết quả: " + " · ".join(parts)


def init_session_state() -> None:
    """Khởi tạo các khóa cần thiết trong st.session_state."""
    defaults: dict[str, Any] = {
        "current_result": None,
        "selected_patient_code": None,
        "review_selected_plan_id": None,
        "edit_preview_result": None,
        "current_role": "Bệnh nhân",
        "show_all_pages": False,
        "analyzing": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def inject_custom_css() -> None:
    """Tiêm CSS tùy biến theo chuẩn Health-Tech / Clinical Dashboard hiện đại."""
    css = """
    <style>
    .stApp {
        background: #F5F7FB;
    }
    [data-testid="stMainBlockContainer"] {
        max-width: 1180px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }
    [data-testid="stSidebar"] {
        background: #EFF8F7;
        border-right: 1px solid #D7E9E7;
    }
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: #FFFFFF;
        box-shadow: 0 4px 18px rgba(15, 118, 110, 0.045);
    }
    [data-testid="stButton"] button[kind="primary"] {
        background: #0D9488;
        border-color: #0D9488;
        border-radius: 10px;
        font-weight: 650;
        min-height: 2.8rem;
    }
    [data-testid="stButton"] button[kind="primary"]:hover {
        background: #0F766E;
        border-color: #0F766E;
    }
    [data-testid="stMain"] h4 {
        color: #0F766E;
        letter-spacing: -0.015em;
    }
    [data-testid="stMain"] p, [data-testid="stMain"] label {
        font-size: 1rem;
        line-height: 1.55;
    }
    [data-testid="stAlert"] { border-radius: 14px; }
    [data-testid="stVerticalBlockBorderWrapper"] > div {
        border-radius: 16px !important;
    }
    @media (max-width: 760px) {
        [data-testid="stMainBlockContainer"] { padding: 1rem; }
        .hero-banner { padding: 20px !important; }
    }
    /* Hero Banner Gradient Teal */
    .hero-banner {
        background: radial-gradient(circle at 93% 4%, rgba(255,255,255,.24) 0 9%, transparent 9.3%),
                    radial-gradient(circle at 87% 118%, rgba(99,220,213,.3) 0 19%,
                                    transparent 19.3%),
                    linear-gradient(120deg, #075F61 0%, #0D9488 64%, #2563A6 100%);
        border-radius: 20px;
        padding: 30px 34px;
        color: #FFFFFF;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.08), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
        margin-bottom: 24px;
    }
    .hero-banner h1, .hero-banner h2 {
        color: #FFFFFF !important;
        margin: 0 0 8px 0 !important;
        font-weight: 700;
        font-size: 1.85rem;
    }
    .hero-banner p {
        color: #CCFBF1 !important;
        margin: 0 !important;
        font-size: 0.95rem;
        line-height: 1.5;
    }

    /* Modern KPI Cards */
    [data-testid="stMetric"] {
        background-color: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-left: 4px solid #0D9488 !important;
        border-radius: 12px !important;
        padding: 14px 18px !important;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05) !important;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.08) !important;
    }
    [data-testid="stMetricLabel"] {
        color: #64748B !important;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
    }
    [data-testid="stMetricValue"] {
        color: #0F172A !important;
        font-weight: 700 !important;
    }
    [data-testid="stMetricValue"] > div {
        font-size: clamp(1.45rem, 2.1vw, 2rem) !important;
        letter-spacing: -0.04em;
    }
    [data-testid="stHorizontalBlock"] > div:nth-child(4n+2) [data-testid="stMetric"] {
        border-left-color: #2563EB !important;
        background: #F5F8FF !important;
    }
    [data-testid="stHorizontalBlock"] > div:nth-child(4n+3) [data-testid="stMetric"] {
        border-left-color: #7C3AED !important;
        background: #FAF7FF !important;
    }
    [data-testid="stHorizontalBlock"] > div:nth-child(4n+4) [data-testid="stMetric"] {
        border-left-color: #EA580C !important;
        background: #FFF8F2 !important;
    }

    /* Pill Badges */
    .pill-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 12px;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.82rem;
        letter-spacing: 0.02em;
    }
    .badge-approved {
        background-color: #D1FAE5;
        color: #065F46;
        border: 1px solid #A7F3D0;
    }
    .badge-pending {
        background-color: #FEF3C7;
        color: #92400E;
        border: 1px solid #FDE68A;
    }
    .badge-needs-review {
        background-color: #FEF3C7;
        color: #92400E;
        border: 1px solid #FDE68A;
    }
    .badge-blocked {
        background-color: #FEE2E2;
        color: #991B1B;
        border: 1px solid #FECACA;
    }
    .badge-rejected {
        background-color: #FEE2E2;
        color: #991B1B;
        border: 1px solid #FECACA;
    }
    .badge-redirect {
        background-color: #DBEAFE;
        color: #1E40AF;
        border: 1px solid #BFDBFE;
    }
    .badge-default {
        background-color: #F1F5F9;
        color: #475569;
        border: 1px solid #CBD5E1;
    }

    /* Container Card Enhancements */
    [data-testid="stVerticalBlockBorderWrapper"] > div {
        border-radius: 12px !important;
        border-color: #E2E8F0 !important;
    }

    /* Medical Disclaimer Footer Banner */
    .medical-disclaimer-box {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-left: 4px solid #64748B;
        border-radius: 8px;
        padding: 12px 16px;
        color: #475569;
        font-size: 0.85rem;
        margin-top: 24px;
        margin-bottom: 12px;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def render_hero_banner(title: str, subtitle: str, icon: str = "🩺") -> None:
    """Hiển thị Hero Banner chuẩn phong cách y tế hiện đại."""
    html = f"""
    <div class="hero-banner">
        <h2>{icon} {title}</h2>
        <p>{subtitle}</p>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def get_status_badge_html(status: str) -> str:
    """Trả về chuỗi HTML định dạng pill badge cho trạng thái."""
    s = (status or "").lower().strip()
    if s == "approved":
        return '<span class="pill-badge badge-approved">✓ Đã duyệt</span>'
    elif s == "pending_review":
        return '<span class="pill-badge badge-pending">⏳ Chờ duyệt</span>'
    elif s == "needs_human_review":
        return '<span class="pill-badge badge-needs-review">⚠️ Cần chuyên gia xem</span>'
    elif s == "blocked":
        return '<span class="pill-badge badge-blocked">🚫 Bị chặn</span>'
    elif s == "rejected":
        return '<span class="pill-badge badge-rejected">✕ Từ chối</span>'
    elif s == "redirect_to_doctor":
        return '<span class="pill-badge badge-redirect">🩺 Chuyển hướng bác sĩ</span>'
    return f'<span class="pill-badge badge-default">{status}</span>'


def render_status_badge(status: str) -> None:
    """Hiển thị huy hiệu dạng viên thuốc (pill badge) trực quan."""
    st.markdown(get_status_badge_html(status), unsafe_allow_html=True)


def get_disclaimer_text() -> str:
    """Đọc câu tuyên bố miễn trừ y tế từ config/guardrails.yaml."""
    from pathlib import Path

    guardrails_path = Path("config/guardrails.yaml")
    if guardrails_path.exists():
        try:
            data = yaml.safe_load(guardrails_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "disclaimer_vi" in data:
                return str(data["disclaimer_vi"]).strip()
        except Exception:
            pass
    return (
        "*Lưu ý: Thực đơn chỉ mang tính tham khảo hỗ trợ dinh dưỡng, "
        "không thay thế chẩn đoán hoặc chỉ định điều trị của bác sĩ.*"
    )


def render_disclaimer() -> None:
    """Hiển thị tuyên bố miễn trừ y tế bất biến."""
    disclaimer = get_disclaimer_text()
    html = f"""
    <div class="medical-disclaimer-box">
        {disclaimer}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_system_warnings(warnings_data: dict[str, Any] | None = None) -> None:
    """Hiển thị cảnh báo hệ thống (TODO_VERIFY, SAMPLE_DATA, LLM key) trên sidebar."""
    data = warnings_data if warnings_data is not None else get_system_warnings()
    if not data or not data.get("has_warnings"):
        return

    with st.sidebar:
        with st.expander("⚠️ Cảnh báo hệ thống", expanded=False):
            for w in data.get("warnings", []):
                st.warning(w)
            if data.get("todo_verify_items"):
                st.caption("Chi tiết TODO_VERIFY:")
                for it in data["todo_verify_items"][:5]:
                    st.code(it, language="text")


def render_workflow_diagram() -> None:
    """Hiển thị sơ đồ Mermaid của AgentGraph trong hộp expander."""
    from agent.graph import get_graph_mermaid

    with st.expander("🔍 Xem sơ đồ luồng tác tử LangGraph (11 Nodes)"):
        try:
            mermaid_str = get_graph_mermaid()
            st.code(mermaid_str, language="mermaid")
        except Exception as e:
            st.info(f"Không thể tạo sơ đồ Mermaid: {e}")
