"""Sinh tất định 200 bản ghi QueryLog giả lập và GuardrailEvent trong 14 ngày (M11 - R1)."""

import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import Engine, delete  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from db.init_db import init_db  # noqa: E402
from db.models import GuardrailEvent, QueryLog  # noqa: E402
from db.session import get_engine  # noqa: E402
from observability.querylog import estimate_cost_usd  # noqa: E402

PATIENT_CODES_NORMAL = [f"P{i:04d}" for i in range(1, 26)]
PATIENT_CODES_HIGH_RISK = [f"P{i:04d}" for i in range(26, 31)]


def seed_logs(engine: Engine | None = None, count: int = 200, seed: int = 42) -> int:
    """Sinh tất định 200 bản ghi QueryLog và GuardrailEvent rải đều trong 14 ngày."""
    target_engine = engine or get_engine()
    init_db(target_engine)

    rng = random.Random(seed)
    now = datetime.now(UTC)

    with Session(target_engine) as session:
        # Xóa bản ghi giả lập cũ để bảo đảm tính bất biến (idempotent)
        session.execute(
            delete(GuardrailEvent).where(GuardrailEvent.session_id.like("synth-sess-%"))
        )
        session.execute(
            delete(QueryLog).where(QueryLog.is_synthetic_log == True)  # noqa: E712
        )
        session.commit()

    # Phân bổ 200 ca theo tỷ lệ thực tế
    # approved: 90 ca (~45%)
    # pending_review: 40 ca (~20%)
    # needs_human_review: 20 ca (~10%)
    # redirect_to_doctor: 30 ca (~15%)
    # blocked: 20 ca (~10%)
    categories = (
        ["approved"] * 90
        + ["pending_review"] * 40
        + ["needs_human_review"] * 20
        + ["redirect_to_doctor"] * 30
        + ["blocked"] * 20
    )
    rng.shuffle(categories)

    logs_to_insert: list[QueryLog] = []
    events_to_insert: list[GuardrailEvent] = []

    for idx, status in enumerate(categories, start=1):
        sess_id = f"synth-sess-{idx:04d}"
        trace_id = f"trace-synth-{idx:04d}"

        # Phân bổ thời gian trong 14 ngày qua
        offset_days = rng.uniform(0.05, 13.95)
        created_at = now - timedelta(days=offset_days)

        if status == "approved":
            pcode = rng.choice(PATIENT_CODES_NORMAL)
            latency = rng.uniform(2200.0, 6800.0)
            llm_calls = rng.randint(2, 3)
            tokens_in = rng.randint(1200, 2800)
            tokens_out = rng.randint(600, 1400)
            _, cost = estimate_cost_usd(tokens_in=tokens_in, tokens_out=tokens_out)
            retry_count = 1 if rng.random() < 0.2 else 0
            violation_codes = ""

        elif status == "pending_review":
            pcode = rng.choice(PATIENT_CODES_NORMAL)
            latency = rng.uniform(3200.0, 7800.0)
            llm_calls = rng.randint(2, 4)
            tokens_in = rng.randint(1500, 3200)
            tokens_out = rng.randint(700, 1500)
            _, cost = estimate_cost_usd(tokens_in=tokens_in, tokens_out=tokens_out)
            retry_count = rng.randint(1, 2)
            violation_codes = rng.choice(
                ["KCAL_OUT_OF_RANGE", "SODIUM_EXCEEDED", "MACRO_OUT_OF_RANGE"]
            )

        elif status == "needs_human_review":
            pcode = rng.choice(PATIENT_CODES_NORMAL)
            latency = rng.uniform(4500.0, 9200.0)
            llm_calls = rng.randint(3, 4)
            tokens_in = rng.randint(2000, 3600)
            tokens_out = rng.randint(800, 1600)
            _, cost = estimate_cost_usd(tokens_in=tokens_in, tokens_out=tokens_out)
            retry_count = 2
            violation_codes = rng.choice(["GRAMS_OUT_OF_RANGE", "ALLERGEN", "BELOW_FLOOR"])
            events_to_insert.append(
                GuardrailEvent(
                    session_id=sess_id,
                    layer="output",
                    type="boundary_case",
                    reason="Vượt quá ngưỡng tự điều chỉnh hoặc cần chuyên gia kiểm duyệt.",
                    created_at=created_at,
                )
            )

        elif status == "redirect_to_doctor":
            pcode = rng.choice(PATIENT_CODES_HIGH_RISK)
            latency = rng.uniform(120.0, 420.0)
            llm_calls = 0
            tokens_in = 0
            tokens_out = 0
            cost = 0.0
            retry_count = 0
            violation_codes = "HIGH_RISK"
            events_to_insert.append(
                GuardrailEvent(
                    session_id=sess_id,
                    layer="input",
                    type="high_risk",
                    reason="Bệnh nhân thuộc nhóm nguy cơ cao (thai kỳ/suy thận/ăn uống).",
                    created_at=created_at,
                )
            )

        else:  # blocked
            pcode = rng.choice(PATIENT_CODES_NORMAL + PATIENT_CODES_HIGH_RISK)
            latency = rng.uniform(50.0, 190.0)
            llm_calls = 0
            tokens_in = 0
            tokens_out = 0
            cost = 0.0
            retry_count = 0
            violation_codes = "SAFETY_BLOCK"
            ev_type = rng.choice(["injection", "off_topic", "medical_advice"])
            events_to_insert.append(
                GuardrailEvent(
                    session_id=sess_id,
                    layer="input",
                    type=ev_type,
                    reason=f"Phát hiện vi phạm an toàn loại: {ev_type}.",
                    created_at=created_at,
                )
            )

        log = QueryLog(
            session_id=sess_id,
            patient_code=pcode,
            status=status,
            latency_ms=latency,
            llm_calls=llm_calls,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            est_cost_usd=cost,
            retry_count=retry_count,
            violation_codes=violation_codes,
            trace_id=trace_id,
            is_synthetic_log=True,
            created_at=created_at,
        )
        logs_to_insert.append(log)

    with Session(target_engine) as session:
        session.add_all(logs_to_insert)
        session.add_all(events_to_insert)
        session.commit()

    return len(logs_to_insert)


if __name__ == "__main__":
    inserted = seed_logs()
    print(f"Đã seed thành công {inserted} QueryLog giả lập và các GuardrailEvent tương ứng.")
