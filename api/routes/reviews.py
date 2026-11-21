"""Router cổng phê duyệt lâm sàng Human-in-the-Loop (dry-run & submit)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from agent.graph import resume_review
from api.routes.meal_plans import build_enriched_meal_plan_detail
from api.schemas import (
    AllowedFoodOut,
    AllowedFoodsResponse,
    DailyTotalOut,
    PreviewEditRequest,
    PreviewEditResponse,
    ReviewSubmitRequest,
    ReviewSubmitResponse,
)
from core.schemas import ScoredItem, Violation
from db.repo import (
    get_allowed_foods_for_plan,
    get_meal_plan_detail,
    preview_and_verify_edited_items,
    record_review_for_finalized_plan,
)

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("/{meal_plan_id}/allowed-foods", response_model=AllowedFoodsResponse)
def list_allowed_foods_for_review(
    meal_plan_id: int,
    q: str = "",
) -> AllowedFoodsResponse:
    """Lấy danh sách thực phẩm an toàn (đã lọc dị ứng/purin/avoid_tags) để thêm/đổi món."""
    try:
        rows = get_allowed_foods_for_plan(meal_plan_id, query=q)
    except ValueError as exc:
        msg = str(exc)
        code = 404 if "Không tìm thấy" in msg else 400
        raise HTTPException(status_code=code, detail=msg) from exc
    return AllowedFoodsResponse(foods=[AllowedFoodOut(**r) for r in rows])


@router.post("/{meal_plan_id}/preview-edit", response_model=PreviewEditResponse)
def preview_edit_meal_plan(meal_plan_id: int, payload: PreviewEditRequest) -> PreviewEditResponse:
    """Tính lại dinh dưỡng và kiểm chứng khô 11 tiêu chí (không ghi DB)."""
    edited_dicts = [it.model_dump() for it in payload.edited_items]
    try:
        res = preview_and_verify_edited_items(meal_plan_id, edited_dicts)
    except ValueError as exc:
        msg = str(exc)
        code = 404 if "Không tìm thấy" in msg else 400
        raise HTTPException(status_code=code, detail=msg) from exc

    return PreviewEditResponse(
        is_valid=bool(res.get("is_valid", False)),
        violations=[Violation.model_validate(v) for v in (res.get("violations") or [])],
        daily_totals=[DailyTotalOut(**d) for d in (res.get("daily_totals") or [])],
        scored_items=[ScoredItem.model_validate(it) for it in (res.get("scored_items") or [])],
    )


@router.post("/{meal_plan_id}/submit", response_model=ReviewSubmitResponse)
def submit_review(meal_plan_id: int, payload: ReviewSubmitRequest) -> ReviewSubmitResponse:
    """Áp dụng quyết định approve/edit/reject thông qua resume_review hoặc record_review."""
    detail = get_meal_plan_detail(meal_plan_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy thực đơn #{meal_plan_id}.")

    mp = detail["meal_plan"]
    current_status = str(mp.get("status", ""))
    thread_id = str(mp.get("thread_id", ""))
    reviewer = payload.reviewer_name.strip() or "Chuyên gia dinh dưỡng"
    note = payload.note.strip()

    if payload.decision == "reject" and not note:
        raise HTTPException(
            status_code=400,
            detail="Từ chối thực đơn bắt buộc phải nhập lý do (ghi chú chuyên môn).",
        )

    edited_dicts = (
        [it.model_dump() for it in payload.edited_items]
        if payload.edited_items is not None
        else None
    )

    violations_out: list[Violation] = []
    try:
        if current_status == "pending_review":
            res = resume_review(
                thread_id=thread_id,
                decision=payload.decision,
                note=note,
                edited_items=edited_dicts,
                reviewer_name=reviewer,
            )
            new_status = str(res.get("status", current_status))
            violations_out = [
                v if isinstance(v, Violation) else Violation.model_validate(v)
                for v in (res.get("violations") or [])
            ]
        elif current_status == "needs_human_review":
            res = record_review_for_finalized_plan(
                meal_plan_id=meal_plan_id,
                reviewer_name=reviewer,
                decision=payload.decision,
                note=note,
                edited_items=edited_dicts,
            )
            new_status = str(res.get("status", current_status))
        else:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Thực đơn #{meal_plan_id} đang ở trạng thái '{current_status}', "
                    "không nằm trong hàng đợi chờ duyệt."
                ),
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    updated_detail = build_enriched_meal_plan_detail(meal_plan_id)
    return ReviewSubmitResponse(
        meal_plan_id=meal_plan_id,
        thread_id=thread_id,
        status=new_status,
        decision=payload.decision,
        note=note,
        violations=violations_out,
        daily_totals=updated_detail.daily_totals,
        detail=updated_detail,
    )
