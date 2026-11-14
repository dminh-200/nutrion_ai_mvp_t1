"""Chạy thử 3 bệnh nhân mẫu (t2d+htn, gout+dị ứng hải sản, béo phì) và in kết quả (SPEC M8)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from agent.graph import run_request  # noqa: E402
from config.settings import get_settings  # noqa: E402
from core.schemas import PatientProfile  # noqa: E402
from db.import_food import import_food_csv  # noqa: E402
from db.init_db import init_db  # noqa: E402
from db.models import Food  # noqa: E402
from db.session import get_engine  # noqa: E402

SAMPLE_PATIENTS: list[tuple[str, PatientProfile]] = [
    (
        "1. Tiểu đường T2 + Tăng huyết áp",
        PatientProfile(
            patient_code="DEMO_M8_01",
            age=55,
            sex="male",
            height_cm=168.0,
            weight_kg=72.0,
            activity_level="light",
            conditions=["t2d", "htn"],
            allergens=[],
            preferences_text="Thích ăn cơm, cá kho nhạt, rau luộc",
            days=3,
        ),
    ),
    (
        "2. Gout + Dị ứng hải sản",
        PatientProfile(
            patient_code="DEMO_M8_02",
            age=50,
            sex="male",
            height_cm=172.0,
            weight_kg=76.0,
            activity_level="moderate",
            conditions=["gout"],
            allergens=["seafood"],
            preferences_text="Không ăn hải sản, thích thịt trắng và rau xanh",
            days=3,
        ),
    ),
    (
        "3. Béo phì",
        PatientProfile(
            patient_code="DEMO_M8_03",
            age=38,
            sex="female",
            height_cm=158.0,
            weight_kg=76.0,
            activity_level="sedentary",
            conditions=["obesity"],
            allergens=[],
            preferences_text="Thích món hấp, nhiều rau, ít dầu mỡ",
            days=3,
        ),
    ),
]


def _ensure_ready_db() -> dict[int, str]:
    """Đảm bảo DB đã khởi tạo bảng và có dữ liệu thực phẩm; trả về map id -> name_vi."""
    engine = get_engine()
    init_db(engine)
    with Session(engine) as session:
        food_count = session.scalar(select(func.count()).select_from(Food)) or 0
    if food_count == 0:
        import_food_csv(engine=engine)
    with Session(engine) as session:
        rows = session.execute(select(Food.id, Food.name_vi)).all()
    return {int(r[0]): str(r[1]) for r in rows}


def _avg_kcal(plan_scored: list[dict[str, Any]]) -> float:
    if not plan_scored:
        return 0.0
    return sum(float(d.get("kcal", 0.0)) for d in plan_scored) / len(plan_scored)


def main() -> int:
    """Chạy 3 bệnh nhân mẫu qua AgentGraph và in bảng tổng hợp thực đơn + số lần sửa."""
    parser = argparse.ArgumentParser(description="Chạy thử 3 bệnh nhân mẫu (M8).")
    parser.add_argument("--days", type=int, default=3, help="Số ngày thực đơn (1..7).")
    parser.add_argument(
        "--tools-mode",
        choices=["direct", "mcp"],
        default=None,
        help="Ghi đè TOOLS_MODE (mặc định đọc từ .env/Settings).",
    )
    args = parser.parse_args()

    settings = get_settings()
    print(
        f"Cấu hình chạy: LLM_MODE={settings.LLM_MODE} | "
        f"TOOLS_MODE={args.tools_mode or settings.TOOLS_MODE} | "
        f"PLANNER={settings.GEMINI_PLANNER_MODEL} | LIGHT={settings.GEMINI_LIGHT_MODEL}"
    )

    ok_cfg, err_msg = settings.validate_llm_config()
    if not ok_cfg:
        print(f"\n[CẢNH BÁO CẤU HÌNH] {err_msg}")
        print(
            "Gợi ý chạy thử ngay không cần API key (PowerShell):\n"
            '  $env:LLM_MODE="mock"; $env:TOOLS_MODE="direct"; '
            ".venv/Scripts/python.exe scripts/try_patients.py"
        )
        return 1

    food_names = _ensure_ready_db()

    summary_rows: list[dict[str, Any]] = []
    total_llm_calls = 0
    total_tokens_in = 0
    total_tokens_out = 0

    for label, base_profile in SAMPLE_PATIENTS:
        profile = base_profile.model_copy(update={"days": max(1, min(7, args.days))})
        tid = f"try-m8-{profile.patient_code}-{uuid4().hex[:6]}"
        res = run_request(
            profile,
            thread_id=tid,
            tools_mode=args.tools_mode,
        )
        targets = res.get("targets")
        plan_scored = res.get("plan_scored") or []
        violations = res.get("violations") or []
        metrics = res.get("metrics") or {}

        avg_k = _avg_kcal(plan_scored)
        tgt_k = float(targets.target_kcal) if targets else 0.0
        err_pct = abs(avg_k - tgt_k) / tgt_k * 100.0 if tgt_k > 0 else 0.0

        llm_calls = int(metrics.get("llm_calls", 0))
        t_in = int(metrics.get("tokens_in", 0))
        t_out = int(metrics.get("tokens_out", 0))
        total_llm_calls += llm_calls
        total_tokens_in += t_in
        total_tokens_out += t_out

        summary_rows.append(
            {
                "label": label,
                "code": profile.patient_code,
                "status": res.get("status", ""),
                "retries": int(res.get("retry_count", 0)),
                "llm_calls": llm_calls,
                "tokens": f"{t_in}/{t_out}",
                "target_kcal": tgt_k,
                "avg_kcal": avg_k,
                "err_pct": err_pct,
                "violations": [v.code for v in violations],
                "res": res,
            }
        )

    print("\n=== BẢNG KẾT QUẢ 3 BỆNH NHÂN MẪU ===")
    header = (
        f"{'Bệnh nhân':<34} | {'Trạng thái':<18} | {'Sửa':>3} | {'LLM':>3} | "
        f"{'Mục tiêu':>8} | {'TB ngày':>8} | {'Lệch':>6} | {'Token (in/out)':<14}"
    )
    print(header)
    print("-" * len(header))
    for row in summary_rows:
        print(
            f"{row['label']:<34} | {row['status']:<18} | {row['retries']:>3} | "
            f"{row['llm_calls']:>3} | {row['target_kcal']:>8.0f} | {row['avg_kcal']:>8.1f} | "
            f"{row['err_pct']:>5.1f}% | {row['tokens']:<14}"
        )
        if row["violations"]:
            print(f"   -> Vi phạm còn lại: {', '.join(row['violations'])}")

    print(
        f"\nTổng kết: {len(summary_rows)} ca | Tổng số lần gọi LLM={total_llm_calls} | "
        f"Tokens in/out={total_tokens_in}/{total_tokens_out}"
    )

    for row in summary_rows:
        res = row["res"]
        print(f"\n--- Chi tiết thực đơn: {row['label']} ({row['code']}) ---")
        plan_llm = res.get("plan_llm")
        if plan_llm and not plan_llm.cannot_plan:
            for d_plan in plan_llm.days:
                day_score = next(
                    (s for s in (res.get("plan_scored") or []) if int(s["day"]) == d_plan.day),
                    None,
                )
                score_str = (
                    f" | {day_score['kcal']:.0f} kcal, "
                    f"P={day_score['protein_g']:.1f}g, F={day_score['fat_g']:.1f}g, "
                    f"C={day_score['carb_g']:.1f}g, Na={day_score['sodium_mg']:.0f}mg"
                    if day_score
                    else ""
                )
                print(f"  Ngày {d_plan.day}{score_str}:")
                for meal in d_plan.meals:
                    items_txt = ", ".join(
                        f"{food_names.get(it.food_id, f'#{it.food_id}')} ({it.grams:.0f}g)"
                        for it in meal.items
                    )
                    print(f"    - {meal.meal}: {items_txt}")
        else:
            reason = getattr(plan_llm, "reason", "") if plan_llm else ""
            print(f"  Không sinh được thực đơn: {reason}")
        expl = str(res.get("explanation_md", "")).strip().splitlines()
        if expl:
            print("  Giải thích:")
            for line in expl[:5]:
                print(f"    {line}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
