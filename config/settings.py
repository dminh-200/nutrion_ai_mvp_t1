"""Cấu hình ứng dụng đọc từ biến môi trường và file .env."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Cấu hình toàn cục cho nutrition-ai-mvp."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    GEMINI_API_KEY: str = ""
    GEMINI_PLANNER_MODEL: str = "gemini-3.8-flash"
    GEMINI_LIGHT_MODEL: str = "gemini-3.5-flash-lite"
    LLM_MODE: Literal["real", "mock"] = "mock"
    LLM_MAX_RPM: int = 8
    LLM_CACHE_DIR: str = ".cache/llm"
    TOOLS_MODE: Literal["mcp", "direct"] = "direct"

    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_BASE_URL: str = "https://cloud.langfuse.com"

    DB_URL: str = "sqlite:///db/nutrition.db"
    CHECKPOINT_DB: str = "db/checkpoints.sqlite"
    CHROMA_DIR: str = "rag/chroma"
    EMBEDDING_MODEL: str = "intfloat/multilingual-e5-small"
    APP_ENV: Literal["dev", "demo"] = "dev"

    @property
    def langfuse_enabled(self) -> bool:
        """Bật Langfuse tracing khi có đủ public và secret key."""
        return bool(self.LANGFUSE_PUBLIC_KEY.strip() and self.LANGFUSE_SECRET_KEY.strip())

    def validate_llm_config(self) -> tuple[bool, str | None]:
        """Kiểm tra cấu hình LLM; trả về (hợp_lệ, thông_báo_lỗi_nếu_có)."""
        if self.LLM_MODE == "real" and not self.GEMINI_API_KEY.strip():
            return (
                False,
                "Thiếu GEMINI_API_KEY khi LLM_MODE=real. "
                "Vui lòng bổ sung GEMINI_API_KEY trong .env hoặc chuyển sang LLM_MODE=mock.",
            )
        return True, None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Trả về instance Settings được cache."""
    return Settings()
