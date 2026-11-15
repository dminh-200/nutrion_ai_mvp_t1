"""Cấu hình mặc định cho pytest: chạy chế độ direct và mock LLM (SPEC 3.2, 13.6)."""

import os
from typing import Any


def pytest_configure(config: Any) -> None:
    """Đặt mặc định TOOLS_MODE=direct, LLM_MODE=mock và LLM_PROVIDER=gemini trước khi nạp test."""
    _ = config
    os.environ.setdefault("TOOLS_MODE", "direct")
    os.environ.setdefault("LLM_MODE", "mock")
    os.environ.setdefault("LLM_PROVIDER", "gemini")
