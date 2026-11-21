"""Router chạy luồng tạo thực đơn, liệt kê và xem chi tiết thực đơn."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from agent.graph import run_request
from api.schemas import (
    DailyTotalOut,
    GuardrailEventOut,
    MealItemOut,
    MealPlanDetailResponse,
    MealPlanListResponse,
    MealPlanQueueCounts,
    MealPlanRunResponse,
    MealPlanSummary,
    PatientSummaryOut,
    ReviewRecordOut,
)
from core.schemas import (
    GuidelineSnippet,
    NeedsResult,
    NutritionTargets,
    PatientProfile,
    RiskResult,
    Violation,
)
from db.models import FoodNutrient, GuardrailEvent, MealPlan, QueryLog
from db.repo import get_meal_plan_detail, list_meal_plans_for_ui
from db.session import get_engine

router = APIRouter(prefix="/meal-plans", tags=["meal-plans"])

_NO_MENU_STATUSES = frozenset({"redirect_to_doctor", "blocked"})


def build_enriched_meal_plan_detail(meal_plan_id: int) -> MealPlanDetailResponse:
    """Nạp chi tiết từ get_meal_plan_detail, bổ sung fiber/sugar & guardrail events từ session."""
    raw = get_meal_plan_detail(meal_plan_id)
    if raw is None:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy thực đơn #{meal_plan_id}.")

    mp = raw["meal_plan"]
    status = str(mp.get("status", "draft"))

    if status in _NO_MENU_STATUSES:
        items_out: list[MealItemOut] = []
        by_day_out: dict[str, dict[str, list[MealItemOut]]] = {}
        daily_totals_out: list[DailyTotalOut] = []
    else:
        raw_items = list(raw.get("items") or [])
        food_ids = sorted({int(it["food_id"]) for it in raw_items})
        nutr_map: dict[int, tuple[float, float]] = {}
        if food_ids:
            with Session(get_engine()) as sess:
                nutr_rows = sess.scalars(
                    select(FoodNutrient).where(FoodNutrient.food_id.in_(food_ids))
                ).all()
                for n in nutr_rows:
                    nutr_map[int(n.food_id)] = (float(n.fiber_g or 0.0), float(n.sugar_g or 0.0))

        items_out = []
        by_day_out = {}
        day_fiber_sugar: dict[int, list[float]] = {}

        for it in raw_items:
            fid = int(it["food_id"])
            grams = float(it.get("grams", 0.0))
            fib_100, sug_100 = nutr_map.get(fid, (0.0, 0.0))
            ratio = grams / 100.0
            item_fiber = round(fib_100 * ratio, 1)
            item_sugar = round(sug_100 * ratio, 1)

            item_obj = MealItemOut(
                id=it.get("id"),
                day=int(it["day"]),
                meal=str(it["meal"]),
                food_id=fid,
                name_vi=str(it.get("name_vi", "Món ăn")),
                grams=grams,
                kcal=float(it.get("kcal", 0.0)),
                protein_g=float(it.get("protein_g", 0.0)),
                fat_g=float(it.get("fat_g", 0.0)),
                carb_g=float(it.get("carb_g", 0.0)),
                sodium_mg=float(it.get("sodium_mg", 0.0)),
                fiber_g=item_fiber,
                sugar_g=item_sugar,
            )
            items_out.append(item_obj)
            day_key = str(item_obj.day)
            by_day_out.setdefault(day_key, {}).setdefault(item_obj.meal, []).append(item_obj)

            acc = day_fiber_sugar.setdefault(item_obj.day, [0.0, 0.0])
            acc[0] = round(acc[0] + item_fiber, 1)
            acc[1] = round(acc[1] + item_sugar, 1)

        daily_totals_out = []
        for dt in raw.get("daily_totals") or []:
            d_num = int(dt["day"])
            fib_sum, sug_sum = day_fiber_sugar.get(d_num, [0.0, 0.0])
            daily_totals_out.append(
                DailyTotalOut(
                    day=d_num,
                    kcal=float(dt.get("kcal", 0.0)),
                    protein_g=float(dt.get("protein_g", 0.0)),
                    fat_g=float(dt.get("fat_g", 0.0)),
                    carb_g=float(dt.get("carb_g", 0.0)),
                    sodium_mg=float(dt.get("sodium_mg", 0.0)),
                    fiber_g=fib_sum,
                    sugar_g=sug_sum,
                )
            )

    # Thu thập thêm GuardrailEvent liên kết qua QueryLog.session_id
    events_map: dict[int, GuardrailEventOut] = {
        int(ge["id"]): GuardrailEventOut(**ge) for ge in (raw.get("guardrail_events") or [])
    }
    with Session(get_engine()) as sess:
        q_sessions = list(
            sess.scalars(
                select(QueryLog.session_id).where(QueryLog.meal_plan_id == meal_plan_id)
            ).all()
        )
        if q_sessions:
            extra_events = sess.scalars(
                select(GuardrailEvent)
                .where(GuardrailEvent.session_id.in_(q_sessions))
                .order_by(GuardrailEvent.id.asc())
            ).all()
            for ge in extra_events:
                if ge.id not in events_map:
                    events_map[int(ge.id)] = GuardrailEventOut(
                        id=int(ge.id),
                        layer=ge.layer,
                        type=ge.type,
                        reason=ge.reason,
                        created_at=ge.created_at.isoformat() if ge.created_at else "",
                    )

    raw_risk = raw.get("risk")
    risk_out = _to_model_or_none(RiskResult, raw_risk) if raw_risk else None
    snippets_out = [
        s if isinstance(s, GuidelineSnippet) else GuidelineSnippet.model_validate(s)
        for s in (raw.get("snippets") or [])
    ]
    violations_out = [
        v if isinstance(v, Violation) else Violation.model_validate(v)
        for v in (raw.get("violations") or [])
    ]

    return MealPlanDetailResponse(
        meal_plan=mp,
        patient=raw["patient"],
        targets=raw.get("targets") or {},
        needs=raw.get("needs") or {},
        risk=risk_out,
        snippets=snippets_out,
        violations=violations_out,
        items=items_out,
        by_day=by_day_out,
        daily_totals=daily_totals_out,
        reviews=[ReviewRecordOut(**r) for r in (raw.get("reviews") or [])],
        guardrail_events=[events_map[k] for k in sorted(events_map.keys())],
    )


def _to_model_or_none(cls: type[Any], val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, cls):
        return val
    if isinstance(val, dict):
        return cls.model_validate(val)
    if hasattr(val, "model_dump"):
        return cls.model_validate(val.model_dump())
    return None


@router.post("/run", response_model=MealPlanRunResponse)
def run_meal_plan(profile: PatientProfile) -> MealPlanRunResponse:
    """Chạy luồng LangGraph qua agent.graph.run_request(profile) và trả kết quả chuẩn hóa."""
    res = run_request(profile=profile)
    status = str(res.get("status", "draft"))
    meal_plan_id = res.get("meal_plan_id")

    items_out: list[MealItemOut] = []
    daily_totals_out: list[DailyTotalOut] = []

    if status not in _NO_MENU_STATUSES:
        if meal_plan_id is not None:
            detail = build_enriched_meal_plan_detail(int(meal_plan_id))
            items_out = detail.items
            daily_totals_out = detail.daily_totals
        if not daily_totals_out and isinstance(res.get("plan_scored"), list):
            daily_totals_out = [DailyTotalOut(**d) for d in res["plan_scored"]]

    violations = [
        v if isinstance(v, Violation) else Violation.model_validate(v)
        for v in (res.get("violations") or [])
    ]
    snippets = [
        s if isinstance(s, GuidelineSnippet) else GuidelineSnippet.model_validate(s)
        for s in (res.get("snippets") or [])
    ]

    patient_summary = PatientSummaryOut(
        patient_code=profile.patient_code,
        display_name=f"Bệnh nhân {profile.patient_code}",
        age=profile.age,
        sex=profile.sex,
        height_cm=profile.height_cm,
        weight_kg=profile.weight_kg,
        conditions=list(profile.conditions),
        allergens=list(profile.allergens),
        days=profile.days,
        preferences_text=profile.preferences_text,
    )

    return MealPlanRunResponse(
        status=status,
        meal_plan_id=int(meal_plan_id) if meal_plan_id is not None else None,
        thread_id=str(res.get("thread_id", "")),
        session_id=str(res.get("session_id", "")),
        trace_id=str(res.get("trace_id", "")),
        retry_count=int(res.get("retry_count", 0)),
        input_flags=list(res.get("input_flags") or []),
        output_flags=list(res.get("output_flags") or []),
        patient=patient_summary,
        risk=_to_model_or_none(RiskResult, res.get("risk")),
        targets=_to_model_or_none(NutritionTargets, res.get("targets")),
        needs=_to_model_or_none(NeedsResult, res.get("needs")),
        items=items_out,
        daily_totals=daily_totals_out,
        violations=violations,
        snippets=snippets,
        explanation_md=str(res.get("explanation_md", "")),
        metrics=dict(res.get("metrics") or {}),
        execution=dict(res.get("execution") or {}),
        trace_notes=list(res.get("trace_notes") or []),
    )


@router.get("", response_model=MealPlanListResponse)
def list_meal_plans(
    status: Annotated[
        str | None,
        Query(description="Lọc trạng thái, phân tách bằng dấu phẩy"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> MealPlanListResponse:
    """Lấy danh sách thực đơn kèm bộ đếm từng nhóm trạng thái cho hàng đợi."""
    status_filter: list[str] | str | None = None
    if status and status.strip():
        parts = [s.strip() for s in status.split(",") if s.strip()]
        status_filter = parts[0] if len(parts) == 1 else parts

    rows = list_meal_plans_for_ui(status=status_filter, limit=limit)
    items = [MealPlanSummary(**r) for r in rows]

    with Session(get_engine()) as sess:
        grouped = sess.execute(
            select(MealPlan.status, func.count()).group_by(MealPlan.status)
        ).all()
    counts_map = {str(st): int(cnt) for st, cnt in grouped}
    counts = MealPlanQueueCounts(
        pending_review=counts_map.get("pending_review", 0),
        needs_human_review=counts_map.get("needs_human_review", 0),
        approved=counts_map.get("approved", 0),
        rejected=counts_map.get("rejected", 0),
        total=sum(counts_map.values()),
    )

    return MealPlanListResponse(counts=counts, items=items)


@router.get("/{meal_plan_id}", response_model=MealPlanDetailResponse)
def get_meal_plan(meal_plan_id: int) -> MealPlanDetailResponse:
    """Lấy chi tiết một thực đơn theo meal_plan_id."""
    return build_enriched_meal_plan_detail(meal_plan_id)
