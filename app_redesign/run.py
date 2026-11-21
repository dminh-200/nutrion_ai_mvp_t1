"""Khởi động bản thử độc lập trên dữ liệu tạm và không gọi API."""

import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def preview_environment(folder: Path) -> dict[str, str]:
    """Tạo môi trường riêng cho tiến trình Streamlit."""
    env = os.environ.copy()
    env.update(
        {
            "DB_URL": "sqlite:///" + (folder / "nutrition.db").as_posix(),
            "CHECKPOINT_DB": str(folder / "checkpoints.sqlite"),
            "CHROMA_DIR": str(folder / "chroma"),
            "LLM_CACHE_DIR": str(folder / "llm_cache"),
            "REDESIGN_PREVIEW_ROOT": str(folder),
            "LLM_MODE": "mock",
            "TOOLS_MODE": "direct",
            "SAFETY_LLM": "off",
            "LANGFUSE_PUBLIC_KEY": "",
            "LANGFUSE_SECRET_KEY": "",
            "GEMINI_API_KEY": "",
            "GROQ_API_KEY": "",
            "ALIBABA_API_KEY": "",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "ANONYMIZED_TELEMETRY": "False",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": os.pathsep.join([str(ROOT), env.get("PYTHONPATH", "")]),
        }
    )
    return env


def main() -> None:
    """Chạy cổng 8502 và dọn bản sao sau khi dừng ứng dụng."""
    with tempfile.TemporaryDirectory(prefix="nutrition-redesign-") as temp:
        folder = Path(temp)
        source = ROOT / "db" / "nutrition.db"
        if source.exists():
            # immutable ngăn SQLite tạo journal/shm trong thư mục dữ liệu gốc.
            uri = source.as_uri() + "?mode=ro&immutable=1"
            with (
                closing(sqlite3.connect(uri, uri=True)) as original,
                closing(sqlite3.connect(folder / "nutrition.db")) as copied,
            ):
                original.backup(copied)
        chroma = ROOT / "rag" / "chroma"
        if chroma.exists():
            shutil.copytree(chroma, folder / "chroma")
        command = [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "app_redesign/main.py",
            "--server.port",
            "8502",
            "--server.address",
            "127.0.0.1",
            "--server.enableCORS",
            "true",
            "--server.headless",
            "true",
            "--browser.gatherUsageStats",
            "false",
            "--client.toolbarMode",
            "minimal",
            "--theme.base",
            "light",
            "--theme.primaryColor",
            "#1E5E49",
            "--theme.backgroundColor",
            "#F4F7F3",
            "--theme.secondaryBackgroundColor",
            "#FFFFFF",
            "--theme.textColor",
            "#182D26",
        ]
        print("Bản thiết kế mới: http://localhost:8502", flush=True)
        print("Dữ liệu tạm · Mô hình giả lập · Không gọi API thật", flush=True)
        child = subprocess.Popen(command, cwd=ROOT, env=preview_environment(folder))
        try:
            code = child.wait()
        except KeyboardInterrupt:
            child.terminate()
            code = 0
        finally:
            if child.poll() is None:
                child.terminate()
            child.wait()
        if code:
            raise SystemExit(code)


if __name__ == "__main__":
    main()
