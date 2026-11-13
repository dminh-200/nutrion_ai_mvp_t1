"""Test khói: kiểm tra import mọi package trong dự án."""

import importlib

import pytest

PACKAGES = [
    "config",
    "core",
    "db",
    "rag",
    "mcp_server",
    "agent",
    "guardrails",
    "observability",
    "app",
    "app.pages",
    "evals",
    "scripts",
    "tests",
]


@pytest.mark.parametrize("package_name", PACKAGES)
def test_import_project_package(package_name: str) -> None:
    """Mỗi package trong cây thư mục đều import được."""
    module = importlib.import_module(package_name)
    assert module is not None
