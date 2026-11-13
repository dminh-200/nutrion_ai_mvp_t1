"""Kiểm thử cấu hình đọc từ biến môi trường."""

from config.settings import Settings, get_settings


def test_settings_defaults(monkeypatch) -> None:
    """Đảm bảo Settings đọc đúng giá trị mặc định và biến môi trường."""
    monkeypatch.setenv("LLM_MODE", "mock")
    monkeypatch.setenv("TOOLS_MODE", "direct")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "")

    settings = Settings(_env_file=None)
    assert settings.LLM_MODE == "mock"
    assert settings.TOOLS_MODE == "direct"
    assert settings.GEMINI_PLANNER_MODEL == "gemini-3.8-flash"
    assert settings.GEMINI_LIGHT_MODEL == "gemini-3.5-flash-lite"
    assert settings.LLM_MAX_RPM == 8
    assert settings.langfuse_enabled is False

    ok, err = settings.validate_llm_config()
    assert ok is True
    assert err is None


def test_settings_real_mode_without_key(monkeypatch) -> None:
    """Báo lỗi rõ ràng khi LLM_MODE=real nhưng thiếu GEMINI_API_KEY."""
    monkeypatch.setenv("LLM_MODE", "real")
    monkeypatch.setenv("GEMINI_API_KEY", "")

    settings = Settings(_env_file=None)
    ok, err = settings.validate_llm_config()
    assert ok is False
    assert err is not None
    assert "GEMINI_API_KEY" in err


def test_get_settings_cached() -> None:
    """get_settings trả về instance Settings hợp lệ."""
    get_settings.cache_clear()
    settings = get_settings()
    assert isinstance(settings, Settings)
