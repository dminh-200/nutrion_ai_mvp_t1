"""Router hệ thống: health check, trạng thái cấu hình/cảnh báo và sơ đồ Mermaid."""

from __future__ import annotations

from fastapi import APIRouter

from agent.graph import get_graph_mermaid
from agent.llm import resolve_active_model_name
from api.schemas import (
    GraphMermaidResponse,
    HealthResponse,
    SystemStatusResponse,
    SystemWarningsOut,
)
from config.settings import get_settings
from db.repo import ensure_db_ready, get_system_warnings
from guardrails.input import load_guardrails_config

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Kiểm tra trạng thái dịch vụ API và sẵn sàng của SQLite."""
    info = ensure_db_ready()
    return HealthResponse(
        ok=bool(info.get("ready", False)),
        db_ready=bool(info.get("ready", False)),
        patient_count=int(info.get("patient_count", 0)),
        food_count=int(info.get("food_count", 0)),
    )


@router.get("/system/status", response_model=SystemStatusResponse)
def system_status() -> SystemStatusResponse:
    """Trả về thông số vận hành (LLM_MODE, TOOLS_MODE, cảnh báo TODO_VERIFY) và disclaimer."""
    settings = get_settings()
    warnings_raw = get_system_warnings()
    guard_cfg = load_guardrails_config()
    disclaimer = str(guard_cfg.get("disclaimer_vi", "")).strip()
    active_model = resolve_active_model_name("planner", settings=settings)
    _, chat_model, _ = settings.resolve_chat_alibaba_config()

    return SystemStatusResponse(
        llm_mode=settings.LLM_MODE,
        llm_provider=settings.LLM_PROVIDER,
        active_model=active_model,
        chat_model=chat_model,
        chat_uses_dedicated_key=settings.chat_uses_dedicated_key,
        tools_mode=settings.TOOLS_MODE,
        safety_llm=settings.SAFETY_LLM,
        langfuse_enabled=settings.langfuse_enabled,
        disclaimer_vi=disclaimer,
        warnings=SystemWarningsOut(**warnings_raw),
    )


@router.get("/system/graph-mermaid", response_model=GraphMermaidResponse)
def system_graph_mermaid() -> GraphMermaidResponse:
    """Trả về chuỗi sơ đồ Mermaid của LangGraph 11 nodes."""
    return GraphMermaidResponse(mermaid=get_graph_mermaid())
