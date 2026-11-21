"""Router Chatbot Trợ lý Dinh dưỡng."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException

from agent.chat import run_chat
from agent.llm import LLMConfigError
from api.schemas import (
    ChatCitationOut,
    ChatContextSummaryOut,
    ChatFoodSuggestionOut,
    ChatRequest,
    ChatResponse,
)

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def post_chat(payload: ChatRequest) -> ChatResponse:
    """Xử lý câu hỏi hội thoại về thực đơn, đổi món, chế biến và kiến thức dinh dưỡng."""
    clean_msg = payload.message.strip()
    if not clean_msg:
        raise HTTPException(status_code=422, detail="Tin nhắn không được để trống.")

    history_dicts = [
        {"role": item.role, "content": item.content}
        for item in payload.history[-10:]
    ]
    try:
        res = run_chat(
            message=clean_msg,
            history=history_dicts,
            meal_plan_id=payload.meal_plan_id,
            session_id=payload.session_id,
        )
    except LLMConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return ChatResponse(
        session_id=res.session_id,
        reply_md=res.reply_md,
        guardrail_tier=res.guardrail_tier,
        flags=res.flags,
        citations=[ChatCitationOut(**asdict(c)) for c in res.citations],
        suggested_foods=[ChatFoodSuggestionOut(**asdict(f)) for f in res.suggested_foods],
        context_summary=ChatContextSummaryOut(**asdict(res.context_summary)),
        disclaimer_vi=res.disclaimer_vi,
        latency_ms=res.latency_ms,
    )
