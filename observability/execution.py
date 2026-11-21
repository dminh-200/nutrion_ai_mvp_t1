"""Ghi nhận nguồn kết quả thực tế theo từng yêu cầu, không chứa dữ liệu bệnh nhân."""

from collections.abc import Callable
from contextvars import ContextVar
from functools import wraps
from typing import Any

_events: ContextVar[list[str] | None] = ContextVar("llm_execution_events", default=None)


def record_execution(source: str) -> None:
    """Ghi nhận lượt gửi API, đọc cache hoặc chạy giả lập trong yêu cầu hiện tại."""
    events = _events.get()
    if events is not None:
        events.append(source)


def observe_execution[**P](fn: Callable[P, dict[str, Any]]) -> Callable[P, dict[str, Any]]:
    """Bổ sung thống kê thực thi vào kết quả, cô lập giữa các yêu cầu đồng thời."""
    @wraps(fn)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> dict[str, Any]:
        events: list[str] = []
        token = _events.set(events)
        try:
            result = fn(*args, **kwargs)
            result["execution"] = {
                "api_attempts": events.count("api"),
                "cache_hits": events.count("cache"),
                "mock_calls": events.count("mock"),
            }
            return result
        except Exception as exc:
            exc.add_note(f"Lượt gửi API trong yêu cầu: {events.count('api')}")
            raise
        finally:
            _events.reset(token)

    return wrapped
