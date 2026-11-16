"""Cấu hình mặc định cho pytest: chạy chế độ direct, mock LLM và chống treo MCP trong sandbox."""

import os
import socket
import sys
from contextlib import suppress
from functools import lru_cache
from typing import Any

import pytest


@lru_cache(maxsize=1)
def _can_use_loopback_socketpair(timeout_sec: float = 0.25) -> bool:
    """Kiểm tra nhanh khả năng mở TCP loopback trên Windows để tránh treo socketpair vô hạn."""
    if sys.platform != "win32":
        return True
    lsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    csock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lsock.settimeout(timeout_sec)
        lsock.bind(("127.0.0.1", 0))
        lsock.listen(1)
        addr, port = lsock.getsockname()[:2]
        csock.setblocking(False)
        with suppress(BlockingIOError, InterruptedError):
            csock.connect((addr, port))
        ssock, _ = lsock.accept()
        ssock.close()
        return True
    except OSError:
        return False
    finally:
        with suppress(OSError):
            csock.close()
        with suppress(OSError):
            lsock.close()


def pytest_configure(config: Any) -> None:
    """Đặt mặc định TOOLS_MODE=direct, LLM_MODE=mock và LLM_PROVIDER=gemini trước khi nạp test."""
    _ = config
    os.environ.setdefault("TOOLS_MODE", "direct")
    os.environ.setdefault("LLM_MODE", "mock")
    os.environ.setdefault("LLM_PROVIDER", "gemini")


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    """Fail-fast thay vì treo vĩnh viễn khi chạy test @pytest.mark.mcp trong sandbox."""
    if item.get_closest_marker("mcp") and not _can_use_loopback_socketpair():
        pytest.fail(
            "Môi trường hiện tại chặn TCP loopback (127.0.0.1), khiến asyncio/socketpair "
            "của @pytest.mark.mcp bị treo vô hạn. Hãy chạy trong sandbox với "
            '-m "not slow and not mcp", và chạy riêng -m mcp ngoài sandbox (BypassSandbox: true).'
        )
