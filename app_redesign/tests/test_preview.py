"""Kiểm thử bản mới độc lập với dữ liệu gốc và API thật."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from streamlit.testing.v1 import AppTest

from app_redesign.main import _sidebar_action, require_preview
from app_redesign.run import preview_environment


def test_sidebar_navigation_is_checked_against_demo_role(monkeypatch: pytest.MonkeyPatch) -> None:
    """Giữ quyền điều hướng theo vai trò khi nhận sự kiện từ trình duyệt."""
    state: dict[str, Any] = {
        "role": "Người bệnh",
        "nutri-sidebar": {"action": {"page": "Bàn duyệt"}},
    }
    monkeypatch.setattr("app_redesign.main.st.session_state", state)
    _sidebar_action()
    assert "next_page" not in state
    state["nutri-sidebar"]["action"] = {"role": "Chuyên gia"}
    _sidebar_action()
    state["nutri-sidebar"]["action"] = {"page": "Bàn duyệt"}
    _sidebar_action()
    assert state["next_page"] == "Bàn duyệt"


def test_launcher_disables_external_models(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Các biến môi trường thật không được rò sang tiến trình thử."""
    monkeypatch.setenv("LLM_MODE", "real")
    monkeypatch.setenv("ALIBABA_API_KEY", "synthetic-secret")
    env = preview_environment(tmp_path)
    assert env["LLM_MODE"] == "mock"
    assert env["SAFETY_LLM"] == "off"
    assert env["LANGFUSE_SECRET_KEY"] == ""
    assert env["ALIBABA_API_KEY"] == ""
    assert Path(env["CHECKPOINT_DB"]).parent == tmp_path


def test_direct_launch_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Chạy nhầm file main không được mở DB thật."""
    monkeypatch.delenv("REDESIGN_PREVIEW_ROOT", raising=False)
    assert not require_preview()


@pytest.mark.parametrize("unsafe", ["real", "outside", "key", "telemetry", "safety"])
def test_preview_guard_rejects_unsafe_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    unsafe: str,
) -> None:
    """Chặn model thật, khóa thật và đường dẫn dữ liệu ngoài vùng thử."""
    monkeypatch.setenv("REDESIGN_PREVIEW_ROOT", str(tmp_path))
    settings = SimpleNamespace(
        DB_URL="sqlite:///" + str(tmp_path / "db.sqlite"),
        CHECKPOINT_DB=str(tmp_path / "checkpoint"),
        CHROMA_DIR=str(tmp_path / "chroma"),
        LLM_CACHE_DIR=str(tmp_path / "cache"),
        LLM_MODE="mock",
        SAFETY_LLM="off",
        TOOLS_MODE="direct",
        langfuse_enabled=False,
        GEMINI_API_KEY="",
        GROQ_API_KEY="",
        ALIBABA_API_KEY="",
    )
    monkeypatch.setattr("config.settings.get_settings", lambda: settings)
    assert require_preview()
    if unsafe == "real":
        settings.LLM_MODE = "real"
    elif unsafe == "outside":
        settings.DB_URL = "sqlite:///" + str(tmp_path.parent / "original.db")
    elif unsafe == "key":
        settings.ALIBABA_API_KEY = "synthetic"
    elif unsafe == "telemetry":
        settings.langfuse_enabled = True
    else:
        settings.SAFETY_LLM = "on"
    assert not require_preview()


def test_profile_roundtrip_preserves_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    """Đổi bước và đổi mẫu phải cập nhật dữ liệu gửi tới agent."""
    from app_redesign.pages.profile import DEFAULTS

    sample = {
        **DEFAULTS,
        "patient_code": "SYNTHETIC-02",
        "age": 57,
        "conditions": ["htn"],
        "allergens": ["peanut"],
    }
    monkeypatch.setattr("db.repo.load_sample_patients", lambda: [sample])
    app = AppTest.from_string("from app_redesign.pages.profile import render\nrender()")
    app.run()
    app.selectbox(key="sample").select(1).run()
    assert app.session_state["draft"]["patient_code"] == DEFAULTS["patient_code"]
    next(button for button in app.button if button.label == "Nạp hồ sơ đã chọn").click().run()
    assert app.session_state["draft"]["patient_code"] == "SYNTHETIC-02"
    assert app.session_state["draft"]["conditions"] == ["htn"]
    next(button for button in app.button if button.label == "Tiếp tục →").click().run()
    assert app.session_state["step"] == 1
    assert app.multiselect[1].value == ["peanut"]
    app.checkbox[0].check()
    next(button for button in app.button if button.label == "Tiếp tục →").click().run()
    assert app.session_state["draft"]["pregnancy"]
    next(button for button in app.button if button.label == "Quay lại").click().run()
    assert app.checkbox[0].value
    assert not app.exception


def _detail(status: str, empty: bool = False) -> dict[str, Any]:
    """Tạo dữ liệu kết quả giả lập, không ghi SQLite."""
    return {
        "meal_plan": {"status": status, "thread_id": "synthetic", "explanation_md": ""},
        "reviews": [],
        "targets": {"target_kcal": 1500},
        "items": []
        if empty
        else [dict(day=1, meal="breakfast", food_id=1, name_vi="Món thử", grams=100)],
        "daily_totals": []
        if empty
        else [dict(day=1, kcal=1500, protein_g=60, fat_g=50, carb_g=200)],
        "patient": dict(
            code="TEST", age=45, height_cm=170, weight_kg=70, conditions=[], allergens=[]
        ),
    }


@pytest.mark.parametrize("status", ["blocked", "redirect_to_doctor", "rejected"])
def test_result_does_not_send_unavailable_menu_to_frontend(
    monkeypatch: pytest.MonkeyPatch,
    status: str,
) -> None:
    """Ngay cả khi DB còn món, ca bị chặn hoặc từ chối không gửi khẩu phần xuống React."""
    sent: list[dict[str, Any]] = []
    monkeypatch.setattr("db.repo.get_meal_plan_detail", lambda _: _detail(status))
    monkeypatch.setattr("app_redesign.meal_studio.render", sent.append)
    app = AppTest.from_string("from app_redesign.pages.results import render\nrender()")
    app.session_state["result"] = {"meal_plan_id": 1, "status": status}
    app.run()
    assert not app.exception
    [model] = sent
    assert model["status"] == status
    assert not model["days"] and "goals" not in model


def test_review_of_empty_menu_is_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Không thể phê duyệt ca rỗng từ giao diện mới."""
    monkeypatch.setattr(
        "db.repo.list_meal_plans_for_ui",
        lambda **_: [dict(id=1, patient_code="TEST", status="needs_human_review")],
    )
    monkeypatch.setattr(
        "db.repo.get_meal_plan_detail", lambda _: _detail("needs_human_review", True)
    )
    app = AppTest.from_string(
        "from app_redesign.pages.review import render\nrender()", default_timeout=15
    )
    app.run()
    assert not app.exception
    assert next(
        button for button in app.button if button.label == "Duyệt bản đã kiểm chứng"
    ).disabled


def test_result_discards_stale_fiber_after_edited_portions() -> None:
    """Chỉ số chất xơ trước khi chỉnh khẩu phần không dùng cho bản đã duyệt."""
    from app_redesign.meal_studio import build_model

    detail = _detail("approved")
    result = {"plan_scored": {"daily_totals": [{"day": 1, "fiber_g": 24.3}]}}
    latest = build_model(1, detail, result, "Người bệnh")["days"][0]
    assert latest["metrics"]["fiber_g"] == 24.3
    detail["reviews"] = [{"decision": "edit", "note": "Ghi chú giả lập"}]
    edited = build_model(1, detail, result, "Người bệnh")["days"][0]
    assert edited["metrics"]["fiber_g"] is None


def test_preview_from_other_plan_cannot_enable_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    """Đổi ca không được tái sử dụng lần kiểm chứng hợp lệ trước đó."""
    monkeypatch.setattr(
        "db.repo.list_meal_plans_for_ui",
        lambda **_: [dict(id=1, patient_code="TEST", status="needs_human_review")],
    )
    monkeypatch.setattr("db.repo.get_meal_plan_detail", lambda _: _detail("needs_human_review"))
    app = AppTest.from_string(
        "from app_redesign.pages.review import render\nrender()", default_timeout=15
    )
    app.session_state["owned_threads"] = ["synthetic"]
    app.session_state["review_preview"] = {
        "stamp": "another-plan",
        "result": {"is_valid": True},
    }
    app.run()
    assert not app.exception
    button = next(button for button in app.button if button.label == "Duyệt bản đã kiểm chứng")
    assert button.disabled
    assert "review_preview" not in app.session_state


def test_missing_nutrition_stays_distinct_from_a_measured_zero() -> None:
    """Giữ tổng ngày từ DB, giữ riêng dữ liệu thiếu và số 0 ghi nhận được."""
    from app_redesign.meal_studio import build_model

    detail = _detail("pending_review")
    detail["daily_totals"][0].pop("fat_g")
    detail["daily_totals"][0]["sodium_mg"] = 0
    [day] = build_model(1, detail, {}, "Người bệnh")["days"]
    assert day["metrics"]["kcal"] == 1500
    assert day["metrics"]["fat_g"] is None
    assert day["metrics"]["sodium_mg"] == 0
    assert day["meals"][0]["kcal"] is None


def test_explanation_uses_structured_needs_and_groups_sources() -> None:
    """Nhu cầu bằng tiếng Việt, nguồn trùng được gom và đoạn gốc dành cho chuyên gia."""
    from app_redesign.meal_studio import build_model

    detail = _detail("pending_review")
    detail["needs"] = {"needs": ["giam_natri"]}
    snippet = {"source_name": "Tài liệu thử", "page": 3, "text": "Trích đoạn mẫu"}
    result = {"snippets": [snippet, snippet]}
    patient = build_model(1, detail, result, "Người bệnh")
    expert = build_model(1, detail, result, "Chuyên gia")
    assert patient["needs"] == ["Giảm natri"]
    assert patient["sources"] == [{"name": "Tài liệu thử", "page": "3", "excerpts": []}]
    assert expert["sources"][0]["excerpts"] == ["Trích đoạn mẫu"]


def test_html_escapes_untrusted_values() -> None:
    """Tên và nội dung động không được biến thành HTML thực thi."""
    app = AppTest.from_string(
        "from app_redesign.ui import hero\nhero('<script>', '<img>', '<iframe>')"
    ).run()
    assert not app.exception
    html = app.get("html")[0].proto.body
    assert "&lt;script&gt;" in html
    assert "<iframe>" not in html
