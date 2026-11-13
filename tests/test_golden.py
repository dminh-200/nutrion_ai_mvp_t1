"""Kiểm thử ca vàng từ evals/golden_cases.json (skip khi chưa có dữ liệu)."""

import json
from pathlib import Path

import pytest

GOLDEN_PATH = Path("evals/golden_cases.json")


def test_golden_cases() -> None:
    """Đọc evals/golden_cases.json; bỏ qua nếu danh sách rỗng."""
    if not GOLDEN_PATH.exists():
        pytest.skip("Chưa có evals/golden_cases.json")
    cases = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    if not cases:
        pytest.skip("evals/golden_cases.json đang rỗng (chờ M12)")
    assert isinstance(cases, list)
