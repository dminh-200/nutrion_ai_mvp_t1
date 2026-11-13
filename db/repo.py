"""Các hàm CRUD tối thiểu cho meal_plan, review, query_log, guardrail_event."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import GuardrailEvent, MealPlan, QueryLog, Review


def create_meal_plan(
    session: Session,
    *,
    profile_id: int,
    thread_id: str,
    status: str = "draft",
    targets_json: str = "{}",
    needs_json: str = "{}",
    explanation_md: str = "",
    retry_count: int = 0,
    verifier_passed_first_try: bool = False,
) -> MealPlan:
    """Tạo mới một bản ghi meal_plan."""
    plan = MealPlan(
        profile_id=profile_id,
        thread_id=thread_id,
        status=status,
        targets_json=targets_json,
        needs_json=needs_json,
        explanation_md=explanation_md,
        retry_count=retry_count,
        verifier_passed_first_try=verifier_passed_first_try,
    )
    session.add(plan)
    session.flush()
    return plan


def get_meal_plan_by_thread(session: Session, thread_id: str) -> MealPlan | None:
    """Tìm meal_plan theo thread_id."""
    return session.scalar(select(MealPlan).where(MealPlan.thread_id == thread_id))


def update_meal_plan_status(
    session: Session,
    meal_plan_id: int,
    *,
    status: str,
    explanation_md: str | None = None,
    retry_count: int | None = None,
    verifier_passed_first_try: bool | None = None,
) -> MealPlan | None:
    """Cập nhật trạng thái và thông tin liên quan của meal_plan."""
    plan = session.get(MealPlan, meal_plan_id)
    if plan is None:
        return None
    plan.status = status
    if explanation_md is not None:
        plan.explanation_md = explanation_md
    if retry_count is not None:
        plan.retry_count = retry_count
    if verifier_passed_first_try is not None:
        plan.verifier_passed_first_try = verifier_passed_first_try
    session.flush()
    return plan


def create_review(
    session: Session,
    *,
    meal_plan_id: int,
    reviewer_name: str,
    decision: str,
    note: str = "",
    edited_items_json: str = "[]",
) -> Review:
    """Lưu quyết định duyệt của chuyên gia."""
    review = Review(
        meal_plan_id=meal_plan_id,
        reviewer_name=reviewer_name,
        decision=decision,
        note=note,
        edited_items_json=edited_items_json,
    )
    session.add(review)
    session.flush()
    return review


def list_reviews_for_plan(session: Session, meal_plan_id: int) -> list[Review]:
    """Lấy danh sách review của một meal_plan."""
    return list(session.scalars(select(Review).where(Review.meal_plan_id == meal_plan_id)).all())


def create_query_log(
    session: Session,
    *,
    session_id: str,
    patient_code: str,
    status: str,
    meal_plan_id: int | None = None,
    latency_ms: float = 0.0,
    llm_calls: int = 0,
    tokens_in: int = 0,
    tokens_out: int = 0,
    est_cost_usd: float = 0.0,
    retry_count: int = 0,
    violation_codes: str = "",
    trace_id: str = "",
    is_synthetic_log: bool = False,
) -> QueryLog:
    """Ghi một dòng nhật ký truy vấn."""
    log = QueryLog(
        meal_plan_id=meal_plan_id,
        session_id=session_id,
        patient_code=patient_code,
        status=status,
        latency_ms=latency_ms,
        llm_calls=llm_calls,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        est_cost_usd=est_cost_usd,
        retry_count=retry_count,
        violation_codes=violation_codes,
        trace_id=trace_id,
        is_synthetic_log=is_synthetic_log,
    )
    session.add(log)
    session.flush()
    return log


def list_query_logs(session: Session, limit: int = 100) -> list[QueryLog]:
    """Lấy danh sách query_log mới nhất."""
    return list(
        session.scalars(select(QueryLog).order_by(QueryLog.id.desc()).limit(limit)).all()
    )


def create_guardrail_event(
    session: Session,
    *,
    session_id: str,
    layer: str,
    event_type: str,
    reason: str = "",
) -> GuardrailEvent:
    """Ghi một sự kiện chặn hoặc cảnh báo từ guardrails."""
    ev = GuardrailEvent(
        session_id=session_id,
        layer=layer,
        type=event_type,
        reason=reason,
    )
    session.add(ev)
    session.flush()
    return ev


def list_guardrail_events(session: Session, session_id: str | None = None) -> list[GuardrailEvent]:
    """Lấy danh sách sự kiện guardrails."""
    stmt = select(GuardrailEvent)
    if session_id is not None:
        stmt = stmt.where(GuardrailEvent.session_id == session_id)
    return list(session.scalars(stmt.order_by(GuardrailEvent.id.desc())).all())
