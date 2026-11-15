"""Ghi nhật ký truy vấn QueryLog và ước tính chi phí token theo cấu hình (SPEC Phần 11)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import QueryLog
from db.repo import create_query_log
from db.session import get_engine

DEFAULT_PRICING_PATH = Path("config/pricing.yaml")


@lru_cache(maxsize=4)
def load_pricing_config(path: Path = DEFAULT_PRICING_PATH) -> dict[str, Any]:
    """Đọc bảng giá token cấu hình từ config/pricing.yaml."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _calc_model_paid_usd(
    model_name: str,
    tokens_in: int,
    tokens_out: int,
    models_cfg: dict[str, Any],
) -> float:
    """Tính chi phí giả định (USD) cho 1 model từ số token in/out."""
    rates = models_cfg.get(model_name) or models_cfg.get("default") or {}
    in_rate = float(rates.get("input_per_1m_usd", 0.15))
    out_rate = float(rates.get("output_per_1m_usd", 0.60))
    return (max(0, tokens_in) / 1_000_000.0) * in_rate + (
        max(0, tokens_out) / 1_000_000.0
    ) * out_rate


def estimate_cost_usd(
    *,
    tokens_in: int = 0,
    tokens_out: int = 0,
    model: str | None = None,
    model_usage: dict[str, dict[str, int]] | None = None,
    billing_tier: str | None = None,
    pricing_cfg: dict[str, Any] | None = None,
) -> tuple[float, float]:
    """Tính (recorded_cost_usd, est_cost_if_paid_usd) theo SPEC 11.

    Gói miễn phí (billing_tier='free') trả về recorded_cost_usd=0.0 nhưng vẫn trả về
    est_cost_if_paid_usd > 0 khi có token sử dụng.
    """
    cfg = pricing_cfg or load_pricing_config()
    tier = (billing_tier or str(cfg.get("billing_tier", "free"))).strip().lower()
    models_cfg = cfg.get("models") or {}

    if model_usage:
        paid_total = sum(
            _calc_model_paid_usd(
                m_name,
                int(usage.get("tokens_in", 0)),
                int(usage.get("tokens_out", 0)),
                models_cfg,
            )
            for m_name, usage in model_usage.items()
        )
    else:
        paid_total = _calc_model_paid_usd(
            model or "default",
            int(tokens_in),
            int(tokens_out),
            models_cfg,
        )

    paid_rounded = round(paid_total, 8)
    recorded = 0.0 if tier == "free" else paid_rounded
    return recorded, paid_rounded


def upsert_query_log(
    *,
    session_id: str,
    patient_code: str,
    status: str,
    meal_plan_id: int | None = None,
    latency_ms: float = 0.0,
    llm_calls: int = 0,
    tokens_in: int = 0,
    tokens_out: int = 0,
    est_cost_usd: float | None = None,
    retry_count: int = 0,
    violation_codes: str = "",
    trace_id: str = "",
    model_usage: dict[str, dict[str, int]] | None = None,
    billing_tier: str | None = None,
    is_synthetic_log: bool = False,
    session: Session | None = None,
) -> int:
    """Ghi mới hoặc cập nhật QueryLog theo trace_id cho mọi request (kể cả khi bị chặn)."""
    if est_cost_usd is None:
        recorded_cost, _ = estimate_cost_usd(
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            model_usage=model_usage,
            billing_tier=billing_tier,
        )
    else:
        recorded_cost = float(est_cost_usd)

    def _apply(db_sess: Session) -> int:
        existing: QueryLog | None = None
        if trace_id:
            existing = db_sess.scalar(
                select(QueryLog)
                .where(QueryLog.trace_id == trace_id)
                .order_by(QueryLog.id.desc())
            )
        if existing is not None:
            existing.status = status
            if meal_plan_id is not None:
                existing.meal_plan_id = meal_plan_id
            if latency_ms > 0.0:
                existing.latency_ms = float(latency_ms)
            existing.llm_calls = max(existing.llm_calls, int(llm_calls))
            existing.tokens_in = max(existing.tokens_in, int(tokens_in))
            existing.tokens_out = max(existing.tokens_out, int(tokens_out))
            existing.est_cost_usd = recorded_cost
            existing.retry_count = max(existing.retry_count, int(retry_count))
            existing.violation_codes = violation_codes
            db_sess.flush()
            return int(existing.id)

        log = create_query_log(
            db_sess,
            session_id=session_id,
            patient_code=patient_code,
            status=status,
            meal_plan_id=meal_plan_id,
            latency_ms=float(latency_ms),
            llm_calls=int(llm_calls),
            tokens_in=int(tokens_in),
            tokens_out=int(tokens_out),
            est_cost_usd=recorded_cost,
            retry_count=int(retry_count),
            violation_codes=violation_codes,
            trace_id=trace_id,
            is_synthetic_log=is_synthetic_log,
        )
        return int(log.id)

    if session is not None:
        return _apply(session)

    engine = get_engine()
    with Session(engine) as db_sess:
        log_id = _apply(db_sess)
        db_sess.commit()
        return log_id
