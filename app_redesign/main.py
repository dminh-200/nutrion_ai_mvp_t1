"""Điểm vào của bản giao diện desktop độc lập."""

import os
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app_redesign import meal_studio, ui  # noqa: E402

ROLE_PAGES = {
    "Người bệnh": ("Hồ sơ", "Thực đơn"),
    "Chuyên gia": ("Hồ sơ", "Thực đơn", "Bàn duyệt"),
    "Quản trị": ("Hồ sơ", "Thực đơn", "Bàn duyệt", "Tổng quan vận hành"),
}


def _sidebar_action() -> None:
    """Xác nhận lựa chọn điều hướng theo vai trò demo hiện tại."""
    value = st.session_state.get("nutri-sidebar", {}).get("action")
    if not isinstance(value, dict):
        return
    role = value.get("role")
    page = value.get("page")
    if isinstance(role, str) and role in ROLE_PAGES:
        st.session_state["role"] = role
    current_role = st.session_state.get("role", "Người bệnh")
    if isinstance(page, str) and page in ROLE_PAGES[current_role]:
        st.session_state["next_page"] = page


def require_preview() -> bool:
    """Từ chối chạy với dữ liệu hoặc mô hình chưa được cô lập."""
    from config.settings import get_settings

    folder = os.environ.get("REDESIGN_PREVIEW_ROOT")
    if not folder:
        return False
    root = Path(folder).resolve()
    settings = get_settings()
    paths = [settings.CHECKPOINT_DB, settings.CHROMA_DIR, settings.LLM_CACHE_DIR]
    if not settings.DB_URL.startswith("sqlite:///"):
        return False
    paths.append(settings.DB_URL.removeprefix("sqlite:///"))
    return (
        all(Path(path).resolve().is_relative_to(root) for path in paths)
        and settings.LLM_MODE == "mock"
        and settings.SAFETY_LLM == "off"
        and settings.TOOLS_MODE == "direct"
        and not settings.langfuse_enabled
        and not any([settings.GEMINI_API_KEY, settings.GROQ_API_KEY, settings.ALIBABA_API_KEY])
    )


@st.cache_resource
def setup() -> None:
    """Khởi tạo bản sao DB bằng hàm backend gốc."""
    from db.repo import ensure_db_ready

    ensure_db_ready()


def main() -> None:
    """Điều phối bốn màn hình trong tiến trình Streamlit riêng."""
    st.set_page_config(
        page_title="Nutri AI · Cổng dinh dưỡng",
        page_icon=":material/nutrition:",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    ui.theme()
    if not require_preview():
        st.error("Hãy khởi động bằng python app_redesign/run.py để dùng dữ liệu tạm an toàn.")
        st.stop()
    setup()
    from app_redesign.pages import dashboard, profile, results, review
    from db.repo import get_system_warnings

    renderers = {
        "Hồ sơ": profile.render,
        "Thực đơn": results.render,
        "Bàn duyệt": review.render,
        "Tổng quan vận hành": dashboard.render,
    }

    def render_selected_page() -> None:
        """Giữ định danh trang ổn định khi đổi widget sidebar."""
        renderers[st.session_state["nav"]]()

    navigation = st.navigation(
        [st.Page(render_selected_page, title="Nutri AI", default=True)], position="hidden"
    )
    role = st.session_state.setdefault("role", "Người bệnh")
    options = ROLE_PAGES[role]
    requested = st.session_state.pop("next_page", st.session_state.get("nav"))
    st.session_state["nav"] = requested if requested in options else options[0]
    try:
        sidebar = meal_studio.component_asset("sidebar", "nutri-sidebar-root")
        st.html(f"<style>{meal_studio.font_styles()}</style>")
    except FileNotFoundError:
        st.error("Chưa có bản build giao diện. Chạy npm run build trong app_redesign/frontend.")
        st.stop()
    with st.sidebar, st.container(key="nutri-app-sidebar"):
        warnings = get_system_warnings()
        sidebar(
            key="nutri-sidebar",
            data={
                "page": st.session_state["nav"],
                "pages": options,
                "role": role,
                "roles": list(ROLE_PAGES),
                "warningCount": warnings["todo_verify_count"],
                "sampleFood": warnings["is_sample_food"],
                "warnings": warnings["todo_verify_items"],
            },
            on_action_change=_sidebar_action,
        )
    navigation.run()
    ui.footer()


if __name__ == "__main__":
    main()
