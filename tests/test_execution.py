"""Kiểm tra nhãn nguồn kết quả và bộ đếm tại điểm gửi API."""

from typing import Any

from agent.llm import _call_with_retry, _RateLimiter
from app.ui_helpers import execution_summary
from observability.execution import observe_execution, record_execution


def test_execution_counts_and_request_isolation() -> None:
    """Cache, mock và API được đếm riêng và không rò sang yêu cầu sau."""
    @observe_execution
    def request() -> dict[str, Any]:
        record_execution("cache")
        record_execution("mock")
        _call_with_retry(lambda: "ok", rate_limiter=_RateLimiter(), max_rpm=0)
        return {}

    result = request()
    assert result["execution"] == {"api_attempts": 1, "cache_hits": 1, "mock_calls": 1}
    assert request()["execution"] == result["execution"]
    assert "Đã gửi API mới: 1" in execution_summary(result["execution"])


def test_execution_labels_do_not_infer_from_mode() -> None:
    """Không suy đoán API từ cấu hình hay token của bản ghi cũ."""
    assert "chưa có thông tin" in execution_summary(None)
    assert "Không gửi API mới" in execution_summary({"mock_calls": 2})
    assert "Dùng cache: 1" in execution_summary({"cache_hits": 1})
    assert "quy tắc" in execution_summary({})
