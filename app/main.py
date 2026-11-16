"""Điểm vào chính của ứng dụng Streamlit nutrition-ai-mvp (M11 - R2)."""

import streamlit as st

from app.ui_helpers import (
    init_session_state,
    inject_custom_css,
    render_disclaimer,
    render_system_warnings,
    render_workflow_diagram,
)
from db.repo import ensure_db_ready

st.set_page_config(
    page_title="AI Hỗ Trợ Dinh Dưỡng Lâm Sàng",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource(show_spinner="Đang khởi tạo cơ sở dữ liệu y tế...")
def _setup_database() -> dict[str, object]:
    """Khởi tạo cấu trúc bảng, seed bệnh nhân và dữ liệu thực phẩm (chỉ chạy 1 lần)."""
    return ensure_db_ready()


def main() -> None:
    """Điều phối giao diện đa trang và phân quyền người dùng."""
    _setup_database()
    init_session_state()
    inject_custom_css()

    with st.sidebar:
        st.markdown("### 🏥 Hệ Thống Dinh Dưỡng AI")
        st.caption("Phiên bản MVP Lâm Sàng (M11)")

        role = st.selectbox(
            "Vai trò người dùng:",
            ["Bệnh nhân", "Chuyên gia dinh dưỡng", "Quản trị viên / Nhà nghiên cứu"],
            key="current_role",
        )

        show_all = st.checkbox(
            "Hiển thị toàn bộ trang (Kiểm thử)",
            key="show_all_pages",
        )

        st.divider()

    # Định nghĩa danh sách các trang
    page_1 = st.Page(
        "pages/1_Ho_so.py",
        title="Hồ sơ bệnh nhân",
        icon=":material/person:",
        default=True,
    )
    page_2 = st.Page(
        "pages/2_Ket_qua.py",
        title="Kết quả thực đơn",
        icon=":material/restaurant_menu:",
    )
    page_3 = st.Page(
        "pages/3_Chuyen_gia_duyet.py",
        title="Chuyên gia duyệt",
        icon=":material/verified_user:",
    )
    page_4 = st.Page(
        "pages/4_Dashboard.py",
        title="Bảng điều khiển",
        icon=":material/monitoring:",
    )

    if show_all or role == "Quản trị viên / Nhà nghiên cứu":
        pages = [page_1, page_2, page_3, page_4]
    elif role == "Chuyên gia dinh dưỡng":
        pages = [page_3, page_2, page_1]
    else:  # Bệnh nhân
        pages = [page_1, page_2]

    nav = st.navigation(pages)

    # Hiển thị sidebar components
    with st.sidebar:
        render_system_warnings()
        render_workflow_diagram()
        st.divider()
        render_disclaimer()

    nav.run()


if __name__ == "__main__":
    main()
