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
    LLM_PROVIDER: str = "gemini"
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "qwen/qwen3.8-27b"
    ALIBABA_API_KEY: str = ""
    ALIBABA_BASE_URL: str = (
        "https://ws-rkodq3wgmou33rdz.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"
    )
    ALIBABA_MODEL: str = "qwen3.8-flash"
    ALIBABA_CHAT_API_KEY: str = ""
    ALIBABA_CHAT_BASE_URL: str = ""
    ALIBABA_CHAT_MODEL: str = ""
    LLM_MODE: Literal["real", "mock"] = "mock"
    LLM_MAX_RPM: int = 8
    LLM_CACHE_DIR: str = ".cache/llm"
    TOOLS_MODE: Literal["mcp", "direct"] = "direct"
    SAFETY_LLM: Literal["on", "off"] = "off"

    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_BASE_URL: str = "https://cloud.langfuse.com"

    DB_URL: str = "sqlite:///db/nutrition.db"
    CHECKPOINT_DB: str = "db/checkpoints.sqlite"
    CHROMA_DIR: str = "rag/chroma"
    EMBEDDING_MODEL: str = "intfloat/multilingual-e5-small"
    RAG_MIN_SCORE: float = 0.2
    APP_ENV: Literal["dev", "demo"] = "dev"

    @property
    def langfuse_enabled(self) -> bool:
        """Bật Langfuse tracing khi có đủ public và secret key."""
        return bool(self.LANGFUSE_PUBLIC_KEY.strip() and self.LANGFUSE_SECRET_KEY.strip())

    @property
    def chat_uses_dedicated_key(self) -> bool:
        """Trả về True nếu Chatbot đang cấu hình ALIBABA_CHAT_API_KEY riêng."""
        return bool(self.ALIBABA_CHAT_API_KEY.strip())

    def resolve_chat_alibaba_config(self) -> tuple[str, str, str]:
        """Trả về (api_key, model, base_url) cho Chatbot, tự fallback về cấu hình Alibaba chính."""
        api_key = self.ALIBABA_CHAT_API_KEY.strip() or self.ALIBABA_API_KEY.strip()
        model = self.ALIBABA_CHAT_MODEL.strip() or self.ALIBABA_MODEL.strip()
        base_url = self.ALIBABA_CHAT_BASE_URL.strip() or self.ALIBABA_BASE_URL.strip()
        return api_key, model, base_url

    def validate_llm_config(self) -> tuple[bool, str | None]:
        """Kiểm tra cấu hình LLM; trả về (hợp_lệ, thông_báo_lỗi_nếu_có)."""
        if self.LLM_MODE == "real":
            provider = self.LLM_PROVIDER.lower().strip()
            if provider == "groq" and not self.GROQ_API_KEY.strip():
                return (
                    False,
                    "Thiếu GROQ_API_KEY khi LLM_MODE=real và LLM_PROVIDER=groq. "
                    "Vui lòng bổ sung GROQ_API_KEY trong .env hoặc chuyển sang LLM_MODE=mock.",
                )
            if provider == "alibaba" and not self.ALIBABA_API_KEY.strip():
                return (
                    False,
                    "Thiếu ALIBABA_API_KEY khi LLM_MODE=real và LLM_PROVIDER=alibaba. "
                    "Vui lòng bổ sung ALIBABA_API_KEY trong .env hoặc chuyển sang LLM_MODE=mock.",
                )
            if provider == "gemini" and not self.GEMINI_API_KEY.strip():
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
