"""Lắp ghép LangGraph 11 node với SqliteSaver checkpointer và API công khai (SPEC 9.1–9.2)."""

import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from agent.nodes import (
    await_review,
    classify,
    explain,
    finalize,
    input_guardrail,
    intake,
    output_guardrail,
    plan,
    portion_adjust,
    retrieve,
    verify,
)
from agent.state import AgentState
from agent.tools_gateway import ToolsGateway
from config.settings import get_settings
from core.schemas import PatientProfile

MAX_RETRIES = 2


def _route_after_input_guardrail(state: AgentState) -> str:
    """Rẽ nhánh sau input_guardrail: nguy cơ cao hoặc bị chặn -> finalize; hợp lệ -> classify."""
    risk = state.get("risk")
    if (risk and risk.high_risk) or state.get("status") in ("redirect_to_doctor", "blocked"):
        return "finalize"
    return "classify"


def _route_after_plan(state: AgentState) -> str:
    """Rẽ nhánh sau plan: nếu cannot_plan -> finalize; ngược lại -> portion_adjust."""
    plan_llm = state.get("plan_llm")
    if plan_llm is None or plan_llm.cannot_plan:
        return "finalize"
    return "portion_adjust"


def _route_after_verify(state: AgentState) -> str:
    """Rẽ nhánh sau verify: đạt -> explain; còn lượt sửa -> plan; hết lượt -> finalize."""
    violations = state.get("violations") or []
    retry_count = int(state.get("retry_count", 0))
    if not violations:
        return "explain"
    if retry_count < MAX_RETRIES:
        return "plan"
    return "finalize"


def _route_after_output_guardrail(state: AgentState) -> str:
    """Rẽ nhánh sau output_guardrail: vi phạm không tự sửa được -> finalize; đạt -> await_review."""
    if state.get("status") == "needs_human_review":
        return "finalize"
    return "await_review"


def build_graph(gateway: ToolsGateway, checkpointer: Any = None) -> Any:
    """Xây dựng và compile StateGraph đủ 11 node theo SPEC mục 9.1–9.2."""
    builder = StateGraph(AgentState)

    builder.add_node("intake", intake)
    builder.add_node("input_guardrail", input_guardrail)
    builder.add_node("classify", lambda s: classify(s, gateway))
    builder.add_node("retrieve", lambda s: retrieve(s, gateway))
    builder.add_node("plan", lambda s: plan(s, gateway))
    builder.add_node("portion_adjust", portion_adjust)
    builder.add_node("verify", lambda s: verify(s, gateway))
    builder.add_node("explain", explain)
    builder.add_node("output_guardrail", output_guardrail)
    builder.add_node("await_review", lambda s: await_review(s, gateway))
    builder.add_node("finalize", lambda s: finalize(s, gateway))

    builder.add_edge(START, "intake")
    builder.add_edge("intake", "input_guardrail")
    builder.add_conditional_edges(
        "input_guardrail",
        _route_after_input_guardrail,
        {"finalize": "finalize", "classify": "classify"},
    )
    builder.add_edge("classify", "retrieve")
    builder.add_edge("retrieve", "plan")
    builder.add_conditional_edges(
        "plan",
        _route_after_plan,
        {"finalize": "finalize", "portion_adjust": "portion_adjust"},
    )
    builder.add_edge("portion_adjust", "verify")
    builder.add_conditional_edges(
        "verify",
        _route_after_verify,
        {"explain": "explain", "plan": "plan", "finalize": "finalize"},
    )
    builder.add_edge("explain", "output_guardrail")
    builder.add_conditional_edges(
        "output_guardrail",
        _route_after_output_guardrail,
        {"await_review": "await_review", "finalize": "finalize"},
    )
    builder.add_edge("await_review", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile(checkpointer=checkpointer)


def get_graph_mermaid() -> str:
    """Xuất chuỗi sơ đồ Mermaid của AgentGraph."""
    with ToolsGateway(mode="direct") as gw:
        graph = build_graph(gw)
        return str(graph.get_graph().draw_mermaid())


def run_request(
    profile: PatientProfile | dict[str, Any],
    *,
    thread_id: str | None = None,
    session_id: str | None = None,
    checkpoint_db: str | None = None,
    tools_mode: str | None = None,
    mock_force_violation: bool | str = False,
    input_flags: list[str] | None = None,
) -> dict[str, Any]:
    """Chạy luồng từ đầu đến khi gặp interrupt (await_review) hoặc kết thúc (finalize)."""
    db_path = checkpoint_db or get_settings().CHECKPOINT_DB
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    resolved_thread_id = thread_id or f"thread-{uuid4().hex[:12]}"
    resolved_session_id = session_id or f"sess-{uuid4().hex[:12]}"
    valid_profile = (
        profile
        if isinstance(profile, PatientProfile)
        else PatientProfile.model_validate(profile)
    )

    initial_state: AgentState = {
        "session_id": resolved_session_id,
        "thread_id": resolved_thread_id,
        "profile": valid_profile,
        "retry_count": 0,
        "input_flags": list(input_flags or []),
        "output_flags": [],
        "trace_notes": [],
        "mock_force_violation": mock_force_violation,
    }
    config = {"configurable": {"thread_id": resolved_thread_id}}

    t0 = time.perf_counter()
    with ToolsGateway(mode=tools_mode) as gw, SqliteSaver.from_conn_string(db_path) as checkpointer:
        graph = build_graph(gw, checkpointer=checkpointer)
        raw_result = graph.invoke(initial_state, config=config)
        result = dict(raw_result)

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    metrics = dict(result.get("metrics") or {})
    metrics["latency_ms"] = elapsed_ms
    result["metrics"] = metrics

    if "__interrupt__" in result and result.get("meal_plan_id") is None:
        interrupts = result["__interrupt__"]
        if interrupts:
            first_val = getattr(interrupts[0], "value", None)
            if isinstance(first_val, dict) and "meal_plan_id" in first_val:
                result["meal_plan_id"] = first_val["meal_plan_id"]

    return result


def resume_review(
    thread_id: str,
    decision: str | dict[str, Any] = "approve",
    note: str = "",
    edited_items: list[dict[str, Any]] | None = None,
    *,
    reviewer_name: str = "Chuyên gia dinh dưỡng",
    checkpoint_db: str | None = None,
    tools_mode: str | None = None,
) -> dict[str, Any]:
    """Tiếp tục luồng sau interrupt (await_review) bằng Command(resume=...)."""
    db_path = checkpoint_db or get_settings().CHECKPOINT_DB
    config = {"configurable": {"thread_id": thread_id}}

    if isinstance(decision, dict):
        review_payload: dict[str, Any] = dict(decision)
        review_payload.setdefault("decision", "approve")
        review_payload.setdefault("note", note)
        review_payload.setdefault("edited_items", list(edited_items or []))
        review_payload.setdefault("reviewer_name", reviewer_name)
    else:
        review_payload = {
            "decision": decision,
            "note": note,
            "edited_items": list(edited_items or []),
            "reviewer_name": reviewer_name,
        }

    with ToolsGateway(mode=tools_mode) as gw, SqliteSaver.from_conn_string(db_path) as checkpointer:
        graph = build_graph(gw, checkpointer=checkpointer)
        raw_result = graph.invoke(Command(resume=review_payload), config=config)
        return dict(raw_result)
