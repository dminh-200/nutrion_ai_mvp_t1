"""Router Dashboard vận hành: KPI, 4 biểu đồ, QueryLog và xuất CSV."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from api.schemas import DashboardResponse
from db.repo import get_dashboard_dataset

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_VALID_CONDITIONS = frozenset({"t2d", "htn", "gout", "obesity"})


def _normalize_condition(condition: str | None) -> str | None:
    if condition is None or not condition.strip():
        return None
    cleaned = condition.strip().lower()
    if cleaned not in _VALID_CONDITIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Mã bệnh lý không hợp lệ: {condition!r}. "
                "Chỉ chấp nhận t2d, htn, gout, obesity."
            ),
        )
    return cleaned


@router.get("", response_model=DashboardResponse)
def get_dashboard(
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
    condition: Annotated[str | None, Query()] = None,
    include_synthetic: Annotated[bool, Query()] = True,
) -> DashboardResponse:
    """Trả về KPI, dữ liệu 4 biểu đồ và bảng QueryLog từ db.repo.get_dashboard_dataset."""
    cond = _normalize_condition(condition)
    data = get_dashboard_dataset(
        start_date=start_date,
        end_date=end_date,
        condition=cond,
        include_synthetic=include_synthetic,
    )
    return DashboardResponse(
        kpis=data["kpis"],
        charts=data["charts"],
        logs=data["logs"],
        is_synthetic_included=include_synthetic,
    )


@router.get("/export.csv")
def export_dashboard_csv(
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
    condition: Annotated[str | None, Query()] = None,
    include_synthetic: Annotated[bool, Query()] = True,
) -> Response:
    """Xuất tệp CSV nhật ký truy vấn QueryLog khớp bộ lọc."""
    cond = _normalize_condition(condition)
    data = get_dashboard_dataset(
        start_date=start_date,
        end_date=end_date,
        condition=cond,
        include_synthetic=include_synthetic,
    )
    csv_text = data.get("csv_data") or ""
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="query_logs_export.csv"'},
    )
