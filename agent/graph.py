"""Lắp ghép LangGraph 11 node với SqliteSaver checkpointer và API công khai (SPEC 9.1–9.2)."""

import sqlite3
import time
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from pydantic import ValidationError
from sqlalchemy.orm import Session

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
    validate_review_decision,
    verify,
)
from agent.state import AgentState
from agent.tools_gateway import ToolsGateway
from config.settings import get_settings
from core.schemas import PatientProfile
from db.repo import get_meal_plan_by_thread
from db.session import get_engine
from guardrails.input import validate_profile_input
from observability.querylog import estimate_cost_usd, upsert_query_log
from observability.tracing import (
    create_request_trace_id,
    get_langfuse_client,
    record_trace_scores,
    safe_flush,
    trace_node,
    trace_request,
)

MAX_RETRIES = 2

CHECKPOINT_ALLOWED_MSGPACK_MODULES: tuple[tuple[str, str], ...] = (
    ("core.schemas", "PatientProfile"),
    ("core.schemas", "NutritionTargets"),
    ("core.schemas", "NeedsResult"),
    ("core.schemas", "RiskResult"),
    ("core.schemas", "GuidelineSnippet"),
    ("core.schemas", "MealPlanLLM"),
    ("core.schemas", "DayPlan"),
    ("core.schemas", "Meal"),
    ("core.schemas", "PlannedItem"),
    ("core.schemas", "ScoredItem"),
    ("core.schemas", "Violation"),
    ("core.schemas", "ExplainOutput"),
)


@contextmanager
def open_checkpointer(db_path: str) -> Iterator[SqliteSaver]:
    """Mở SqliteSaver qua sqlite3.connect kèm JsonPlusSerializer allowlist và đóng kết nối."""
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    serde = JsonPlusSerializer(allowed_msgpack_modules=CHECKPOINT_ALLOWED_MSGPACK_MODULES)
    with closing(sqlite3.connect(db_path, check_same_thread=False)) as conn:
        saver = SqliteSaver(conn, serde=serde)
        saver.setup()
        yield saver


def _assert_new_thread_id(thread_id: str, db_path: str) -> None:
    """Chặn dùng lại thread_id đã tồn tại trong SQLite (MealPlan) hoặc checkpoint."""
    with Session(get_engine()) as session:
        existing_plan = get_meal_plan_by_thread(session, thread_id)
        if existing_plan is not None:
            raise ValueError(
                f"thread_id={thread_id!r} đã tồn tại (meal_plan_id={existing_plan.id}, "
                f"status={existing_plan.status!r}). Mọi yêu cầu run_request mới phải dùng "
                "thread_id chưa từng tồn tại; thread_id cũ chỉ dùng cho resume_review."
            )
    if db_path != ":memory:" and Path(db_path).exists():
        with open_checkpointer(db_path) as ckpt:
            if ckpt.get_tuple({"configurable": {"thread_id": thread_id}}) is not None:
                raise ValueError(
                    f"thread_id={thread_id!r} đã có checkpoint trước đó. Mọi yêu cầu "
                    "run_request mới phải dùng thread_id chưa từng tồn tại; "
                    "thread_id cũ chỉ dùng cho resume_review."
                )


def _route_after_input_guardrail(state: AgentState) -> str:
    """Rẽ nhánh sau input_guardrail: nguy cơ cao/chặn/cần duyệt -> finalize; đạt -> classify."""
    risk = state.get("risk")
    if (risk and risk.high_risk) or state.get("status") in (
        "redirect_to_doctor",
        "blocked",
        "needs_human_review",
    ):
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


def _summarize_state_for_trace(state: AgentState) -> dict[str, Any]:
    """Tóm tắt state an toàn (không chứa display_name hay preferences_text gốc) cho span."""
    profile = state.get("profile")
    p_code = profile.patient_code if isinstance(profile, PatientProfile) else ""
    pref_len = len(profile.preferences_text) if isinstance(profile, PatientProfile) else 0
    return {
        "patient_code": p_code,
        "status": state.get("status", "draft"),
        "retry_count": int(state.get("retry_count", 0)),
        "input_flags": list(state.get("input_flags") or []),
        "output_flags": list(state.get("output_flags") or []),
        "preferences_length": pref_len,
    }


def _summarize_output_for_trace(out: dict[str, Any] | None) -> dict[str, Any]:
    """Tóm tắt đầu ra node an toàn (chỉ lấy metadata/trạng thái) cho span Langfuse."""
    if not out:
        return {}
    summary: dict[str, Any] = {}
    for key in ("status", "retry_count", "input_flags", "output_flags", "meal_plan_id"):
        if key in out:
            summary[key] = out[key]
    if "violations" in out and out["violations"] is not None:
        summary["violation_codes"] = [getattr(v, "code", str(v)) for v in out["violations"]]
    if "snippets" in out and out["snippets"] is not None:
        summary["snippets_count"] = len(out["snippets"])
    if "allowed_foods" in out and out["allowed_foods"] is not None:
        summary["allowed_foods_count"] = len(out["allowed_foods"])
    if "plan_scored" in out and out["plan_scored"] is not None:
        summary["days_scored"] = len(out["plan_scored"])
    return summary


def _traced_node(
    node_name: str,
    fn: Callable[[AgentState], dict[str, Any]],
) -> Callable[[AgentState], dict[str, Any]]:
    """Bọc một node LangGraph để tự động mở span con trên trace Langfuse hiện tại."""

    def _wrapped(state: AgentState) -> dict[str, Any]:
        with trace_node(node_name, input_summary=_summarize_state_for_trace(state)) as span:
            out = fn(state)
            span.update(output=_summarize_output_for_trace(out))
            return out

    return _wrapped


def build_graph(gateway: ToolsGateway, checkpointer: Any = None) -> Any:
    """Xây dựng và compile StateGraph đủ 11 node theo SPEC mục 9.1–9.2."""
    builder = StateGraph(AgentState)

    builder.add_node("intake", _traced_node("intake", intake))
    builder.add_node("input_guardrail", _traced_node("input_guardrail", input_guardrail))
    builder.add_node("classify", _traced_node("classify", lambda s: classify(s, gateway)))
    builder.add_node("retrieve", _traced_node("retrieve", lambda s: retrieve(s, gateway)))
    builder.add_node("plan", _traced_node("plan", lambda s: plan(s, gateway)))
    builder.add_node("portion_adjust", _traced_node("portion_adjust", portion_adjust))
    builder.add_node("verify", _traced_node("verify", lambda s: verify(s, gateway)))
    builder.add_node("explain", _traced_node("explain", explain))
    builder.add_node(
        "output_guardrail", _traced_node("output_guardrail", lambda s: output_guardrail(s, gateway))
    )
    builder.add_node(
        "await_review", _traced_node("await_review", lambda s: await_review(s, gateway))
    )
    builder.add_node("finalize", _traced_node("finalize", lambda s: finalize(s, gateway)))

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


def _extract_safe_trace_context(
    raw_profile: Any,
    valid_profile: PatientProfile | None = None,
) -> tuple[str, str, str, list[str], int | str | None]:
    """Trích xuất an toàn metadata hồ sơ phục vụ tracing trước/sau khi kiểm tra kiểu."""
    if valid_profile is not None:
        raw_display_name = ""
        if isinstance(raw_profile, dict):
            dname = raw_profile.get("display_name")
            raw_display_name = dname if isinstance(dname, str) else ""
        return (
            valid_profile.patient_code,
            raw_display_name,
            valid_profile.preferences_text,
            list(valid_profile.conditions),
            valid_profile.days,
        )

    if not isinstance(raw_profile, dict):
        return "UNKNOWN", "", "", [], None

    pcode = raw_profile.get("patient_code")
    patient_code = str(pcode) if isinstance(pcode, str) and pcode.strip() else "UNKNOWN"
    dname = raw_profile.get("display_name")
    raw_display_name = dname if isinstance(dname, str) else ""
    pref = raw_profile.get("preferences_text")
    raw_pref_text = pref if isinstance(pref, str) else ""

    cond = raw_profile.get("conditions")
    if isinstance(cond, (list, tuple, set)):
        raw_conditions = [str(c) for c in cond]
    elif cond is None:
        raw_conditions = []
    else:
        raw_conditions = [str(cond)]

    days_val = raw_profile.get("days", 3)
    if isinstance(days_val, bool) or days_val is None:
        raw_days: int | str | None = str(days_val) if days_val is not None else None
    elif isinstance(days_val, int):
        raw_days = days_val
    elif isinstance(days_val, str):
        stripped = days_val.strip()
        raw_days = int(stripped) if stripped.lstrip("+-").isdigit() else days_val
    else:
        raw_days = str(days_val)

    return patient_code, raw_display_name, raw_pref_text, raw_conditions, raw_days


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
    cfg_settings = get_settings()
    db_path = checkpoint_db or cfg_settings.CHECKPOINT_DB
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    resolved_thread_id = thread_id or f"thread-{uuid4().hex[:12]}"
    _assert_new_thread_id(resolved_thread_id, db_path)
    resolved_session_id = session_id or f"sess-{uuid4().hex[:12]}"
    resolved_trace_id = create_request_trace_id(resolved_thread_id)
    effective_tools_mode = tools_mode or cfg_settings.TOOLS_MODE
    effective_llm_mode = cfg_settings.LLM_MODE

    t0 = time.perf_counter()

    # Xác thực hồ sơ trước khi tạo dữ liệu trace/ép kiểu nhằm chặn sạch đầu vào sai kiểu
    if isinstance(profile, PatientProfile):
        valid_profile: PatientProfile | None = profile
        validation_err = None
    else:
        try:
            valid_profile = PatientProfile.model_validate(profile)
            validation_err = None
        except ValidationError:
            valid_profile = None
            _, validation_err = validate_profile_input(
                profile,
                session_id=resolved_session_id,
                log_events=True,
            )

    patient_code, raw_display_name, raw_pref_text, raw_conditions, raw_days = (
        _extract_safe_trace_context(profile, valid_profile=valid_profile)
    )

    with trace_request(
        trace_id=resolved_trace_id,
        session_id=resolved_session_id,
        patient_code=patient_code,
        input_summary={
            "patient_code": patient_code,
            "conditions": raw_conditions,
            "days": raw_days,
            "preferences_length": len(raw_pref_text),
            "input_flags": list(input_flags or []),
        },
        metadata={
            "tools_mode": effective_tools_mode,
            "llm_mode": effective_llm_mode,
            "thread_id": resolved_thread_id,
        },
        display_name=raw_display_name,
        preferences_text=raw_pref_text,
        settings=cfg_settings,
    ) as root_span:
        if valid_profile is None and validation_err is not None:
            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            blocked_res: dict[str, Any] = {
                "session_id": resolved_session_id,
                "thread_id": resolved_thread_id,
                "trace_id": resolved_trace_id,
                "status": "blocked",
                "input_flags": list(validation_err.flags),
                "output_flags": [],
                "violations": [],
                "retry_count": 0,
                "explanation_md": validation_err.blocked_message_vi,
                "meal_plan_id": None,
                "metrics": {
                    "llm_calls": 0,
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "est_cost_usd": 0.0,
                    "est_cost_if_paid_usd": 0.0,
                    "latency_ms": elapsed_ms,
                },
                "trace_notes": [f"input_guardrail: {validation_err.events[0][1]}"],
            }
            root_span.update(
                output={"status": "blocked", "input_flags": list(validation_err.flags)},
                metadata={
                    "retry_count": 0,
                    "violation_codes": [],
                    "tools_mode": effective_tools_mode,
                    "llm_mode": effective_llm_mode,
                    "status": "blocked",
                },
            )
            record_trace_scores(
                trace_id=resolved_trace_id,
                status="blocked",
                retry_count=0,
                settings=cfg_settings,
            )
            upsert_query_log(
                session_id=resolved_session_id,
                patient_code=patient_code,
                status="blocked",
                meal_plan_id=None,
                latency_ms=elapsed_ms,
                llm_calls=0,
                tokens_in=0,
                tokens_out=0,
                est_cost_usd=0.0,
                retry_count=0,
                violation_codes="",
                trace_id=resolved_trace_id,
            )
            safe_flush(get_langfuse_client(cfg_settings))
            return blocked_res

        assert valid_profile is not None
        initial_state: AgentState = {
            "session_id": resolved_session_id,
            "thread_id": resolved_thread_id,
            "trace_id": resolved_trace_id,
            "profile": valid_profile,
            "retry_count": 0,
            "input_flags": list(input_flags or []),
            "output_flags": [],
            "trace_notes": [],
            "mock_force_violation": mock_force_violation,
        }
        config = {"configurable": {"thread_id": resolved_thread_id}}

        with ToolsGateway(mode=tools_mode) as gw, open_checkpointer(db_path) as ckpt:
            graph = build_graph(gw, checkpointer=ckpt)
            raw_result = graph.invoke(initial_state, config=config)
            result = dict(raw_result)

        if "__interrupt__" in result and result.get("meal_plan_id") is None:
            interrupts = result["__interrupt__"]
            if interrupts:
                first_val = getattr(interrupts[0], "value", None)
                if isinstance(first_val, dict) and "meal_plan_id" in first_val:
                    result["meal_plan_id"] = first_val["meal_plan_id"]

        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        metrics = dict(result.get("metrics") or {})
        tokens_in = int(metrics.get("tokens_in", 0))
        tokens_out = int(metrics.get("tokens_out", 0))
        recorded_cost, paid_est = estimate_cost_usd(
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            model_usage=metrics.get("model_usage"),
        )
        metrics["latency_ms"] = elapsed_ms
        metrics["est_cost_usd"] = recorded_cost
        metrics["est_cost_if_paid_usd"] = paid_est
        result["metrics"] = metrics
        result["trace_id"] = resolved_trace_id

        final_status = str(result.get("status", "draft"))
        violations = result.get("violations") or []
        violation_codes_list = [getattr(v, "code", str(v)) for v in violations]
        retry_count = int(result.get("retry_count", 0))

        root_span.update(
            output={
                "status": final_status,
                "meal_plan_id": result.get("meal_plan_id"),
                "input_flags": list(result.get("input_flags") or []),
                "output_flags": list(result.get("output_flags") or []),
                "violation_codes": violation_codes_list,
            },
            metadata={
                "retry_count": retry_count,
                "violation_codes": violation_codes_list,
                "tools_mode": effective_tools_mode,
                "llm_mode": effective_llm_mode,
                "status": final_status,
                "est_cost_if_paid_usd": paid_est,
            },
        )
        record_trace_scores(
            trace_id=resolved_trace_id,
            status=final_status,
            violations=violations,
            retry_count=retry_count,
            targets=result.get("targets"),
            plan_scored=result.get("plan_scored"),
            settings=cfg_settings,
        )
        upsert_query_log(
            session_id=resolved_session_id,
            patient_code=valid_profile.patient_code,
            status=final_status,
            meal_plan_id=result.get("meal_plan_id"),
            latency_ms=elapsed_ms,
            llm_calls=int(metrics.get("llm_calls", 0)),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            est_cost_usd=recorded_cost,
            retry_count=retry_count,
            violation_codes=",".join(violation_codes_list),
            trace_id=resolved_trace_id,
            model_usage=metrics.get("model_usage"),
        )

    safe_flush(get_langfuse_client(cfg_settings))
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
    cfg_settings = get_settings()
    db_path = checkpoint_db or cfg_settings.CHECKPOINT_DB
    config = {"configurable": {"thread_id": thread_id}}
    effective_tools_mode = tools_mode or cfg_settings.TOOLS_MODE
    effective_llm_mode = cfg_settings.LLM_MODE

    if isinstance(decision, dict):
        review_payload: dict[str, Any] = dict(decision)
        review_payload.setdefault("note", note)
        review_payload.setdefault("edited_items", list(edited_items or []))
        review_payload.setdefault("reviewer_name", reviewer_name)
    elif isinstance(decision, str):
        review_payload = {
            "decision": decision,
            "note": note,
            "edited_items": list(edited_items or []),
            "reviewer_name": reviewer_name,
        }
    else:
        raise ValueError(
            "Thiếu hoặc sai kiểu quyết định duyệt. Chỉ chấp nhận: approve, edit, reject."
        )

    validated_decision = validate_review_decision(review_payload.get("decision"))
    review_payload["decision"] = validated_decision
    if validated_decision == "edit":
        raw_edited = review_payload.get("edited_items")
        if raw_edited is not None and not isinstance(raw_edited, list):
            raise ValueError("Trường edited_items phải là danh sách khi decision='edit'.")

    t0 = time.perf_counter()
    resolved_trace_id = create_request_trace_id(thread_id)
    session_id = f"sess-{thread_id}"
    patient_code = "UNKNOWN"
    raw_pref_text = ""

    with Session(get_engine()) as db_sess:
        existing_plan = get_meal_plan_by_thread(db_sess, thread_id)
        db_status = existing_plan.status if existing_plan is not None else None
        db_plan_id = existing_plan.id if existing_plan is not None else None

    with ToolsGateway(mode=tools_mode) as gw, open_checkpointer(db_path) as checkpointer:
        graph = build_graph(gw, checkpointer=checkpointer)
        snapshot = graph.get_state(config)
        snap_vals = snapshot.values if snapshot and isinstance(snapshot.values, dict) else {}
        next_nodes = tuple(snapshot.next or ()) if snapshot else ()
        if not snap_vals and existing_plan is None:
            raise ValueError(
                f"Không tìm thấy luồng chờ duyệt cho thread_id={thread_id!r}."
            )
        current_status = db_status or str(snap_vals.get("status") or "unknown")
        if "await_review" not in next_nodes or db_status != "pending_review":
            raise ValueError(
                f"Luồng {thread_id!r} không còn ở trạng thái chờ duyệt "
                f"(status={current_status!r}, next={next_nodes!r}, meal_plan_id={db_plan_id}), "
                f"không thể áp dụng quyết định {validated_decision!r}."
            )

        if snap_vals.get("trace_id"):
            resolved_trace_id = str(snap_vals["trace_id"])
        if snap_vals.get("session_id"):
            session_id = str(snap_vals["session_id"])
        snap_profile = snap_vals.get("profile")
        if isinstance(snap_profile, PatientProfile):
            patient_code = snap_profile.patient_code
            raw_pref_text = snap_profile.preferences_text

        with trace_request(
            trace_id=resolved_trace_id,
            session_id=session_id,
            patient_code=patient_code,
            input_summary={"phase": "resume_review", "decision": review_payload.get("decision")},
            metadata={
                "tools_mode": effective_tools_mode,
                "llm_mode": effective_llm_mode,
                "thread_id": thread_id,
            },
            preferences_text=raw_pref_text,
            settings=cfg_settings,
        ) as root_span:
            raw_result = graph.invoke(Command(resume=review_payload), config=config)
            result = dict(raw_result)
            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            metrics = dict(result.get("metrics") or {})
            metrics["latency_ms"] = round(float(metrics.get("latency_ms", 0.0)) + elapsed_ms, 2)
            result["metrics"] = metrics
            result["trace_id"] = resolved_trace_id

            final_status = str(result.get("status") or "pending_review")
            violations = result.get("violations") or []
            v_codes = [getattr(v, "code", str(v)) for v in violations]
            retry_count = int(result.get("retry_count", 0))

            root_span.update(
                output={"status": final_status, "meal_plan_id": result.get("meal_plan_id")},
                metadata={
                    "retry_count": retry_count,
                    "violation_codes": v_codes,
                    "tools_mode": effective_tools_mode,
                    "llm_mode": effective_llm_mode,
                    "status": final_status,
                },
            )
            record_trace_scores(
                trace_id=resolved_trace_id,
                status=final_status,
                violations=violations,
                retry_count=retry_count,
                targets=result.get("targets"),
                plan_scored=result.get("plan_scored"),
                review_decision=validated_decision,
                settings=cfg_settings,
            )

    res_profile = result.get("profile")
    res_pcode = (
        res_profile.patient_code if isinstance(res_profile, PatientProfile) else patient_code
    )
    upsert_query_log(
        session_id=str(result.get("session_id", session_id)),
        patient_code=res_pcode,
        status=final_status,
        meal_plan_id=result.get("meal_plan_id"),
        latency_ms=float((result.get("metrics") or {}).get("latency_ms", elapsed_ms)),
        llm_calls=int((result.get("metrics") or {}).get("llm_calls", 0)),
        tokens_in=int((result.get("metrics") or {}).get("tokens_in", 0)),
        tokens_out=int((result.get("metrics") or {}).get("tokens_out", 0)),
        retry_count=int(result.get("retry_count", 0)),
        violation_codes=",".join(
            getattr(v, "code", str(v)) for v in (result.get("violations") or [])
        ),
        trace_id=resolved_trace_id,
        model_usage=(result.get("metrics") or {}).get("model_usage"),
    )
    safe_flush(get_langfuse_client(cfg_settings))
    return result
