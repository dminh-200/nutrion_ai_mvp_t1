"""Cấu hình mặc định cho pytest: cô lập DB tạm, chạy direct/mock LLM và chống treo MCP."""

import os
import shutil
import socket
import sys
import tempfile
from collections.abc import Iterator
from contextlib import suppress
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest

_PYTEST_TEMP_DIR: Path | None = None


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
    """Cô lập DB_URL/CHECKPOINT_DB vào thư mục tạm và đặt mặc định mock/direct."""
    global _PYTEST_TEMP_DIR
    _ = config
    _PYTEST_TEMP_DIR = Path(tempfile.mkdtemp(prefix="nutriai-pytest-"))
    os.environ["DB_URL"] = f"sqlite:///{(_PYTEST_TEMP_DIR / 'pytest.db').as_posix()}"
    os.environ["CHECKPOINT_DB"] = (_PYTEST_TEMP_DIR / "pytest_checkpoints.sqlite").as_posix()
    os.environ["LANGFUSE_PUBLIC_KEY"] = ""
    os.environ["LANGFUSE_SECRET_KEY"] = ""
    os.environ.setdefault("TOOLS_MODE", "direct")
    os.environ.setdefault("LLM_MODE", "mock")
    os.environ.setdefault("LLM_PROVIDER", "gemini")

    import db.session as db_session
    from config.settings import get_settings

    get_settings.cache_clear()
    if db_session._engine is not None:
        with suppress(Exception):
            db_session._engine.dispose()
    db_session._engine = None
    db_session._SessionLocal = None


def pytest_unconfigure(config: Any) -> None:
    """Dọn dẹp engine và thư mục DB tạm sau khi phiên pytest kết thúc."""
    _ = config
    import db.session as db_session

    if db_session._engine is not None:
        with suppress(Exception):
            db_session._engine.dispose()
        db_session._engine = None
        db_session._SessionLocal = None

    if _PYTEST_TEMP_DIR is not None and _PYTEST_TEMP_DIR.exists():
        shutil.rmtree(_PYTEST_TEMP_DIR, ignore_errors=True)


@pytest.fixture(scope="session", autouse=True)
def _init_isolated_pytest_db() -> Iterator[None]:
    """Khởi tạo schema, bệnh nhân mẫu và thực phẩm trên DB tạm dùng chung cho phiên test."""
    from db.repo import ensure_db_ready
    from db.session import get_engine

    ensure_db_ready(get_engine())
    yield


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item: pytest.Item) -> None:
    """Fail-fast thay vì treo vĩnh viễn khi chạy test @pytest.mark.mcp trong sandbox."""
    if item.get_closest_marker("mcp") and not _can_use_loopback_socketpair():
        pytest.fail(
            "Môi trường hiện tại chặn TCP loopback (127.0.0.1), khiến asyncio/socketpair "
            "của @pytest.mark.mcp bị treo vô hạn. Hãy chạy trong sandbox với "
            '-m "not slow and not mcp", và chạy riêng -m mcp ngoài sandbox (BypassSandbox: true).'
        )
