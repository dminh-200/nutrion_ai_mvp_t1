"""Sinh bộ ca đánh giá có đáp án kỳ vọng từ evals/cases_raw.json bằng core/ (SPEC 13.1)."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from core.classify import assess_risk, classify_needs
from core.nutrition import build_targets
from core.schemas import PatientProfile
from guardrails.input import evaluate_input_guardrail

DEFAULT_RAW_PATH = Path("evals/cases_raw.json")
DEFAULT_OUT_PATH = Path("evals/cases.json")


def build_eval_cases(
    raw_path: Path = DEFAULT_RAW_PATH,
    out_path: Path = DEFAULT_OUT_PATH,
) -> list[dict[str, Any]]:
    """Đọc cases_raw.json, tính đáp án kỳ vọng bằng core/ và ghi ra cases.json."""
    raw_items = json.loads(raw_path.read_text(encoding="utf-8"))
    built_cases: list[dict[str, Any]] = []

    for item in raw_items:
        profile = PatientProfile.model_validate(item["profile"])
        risk = assess_risk(profile)
        needs = classify_needs(profile)
        targets = build_targets(profile, needs)

        guard_res = evaluate_input_guardrail(
            profile,
            session_id="",
            log_events=False,
        )
        if risk.high_risk or guard_res.action == "redirect_to_doctor":
            expected_action = "redirect_to_doctor"
        elif guard_res.action == "blocked":
            expected_action = "blocked"
        else:
            expected_action = "plan"

        built_cases.append(
            {
                "id": str(item["id"]),
                "category": str(item["category"]),
                "description": str(item.get("description", "")),
                "profile": profile.model_dump(),
                "expected": {
                    "action": expected_action,
                    "high_risk": risk.high_risk,
                    "risk_reasons": list(risk.reasons),
                    "needs": list(needs.needs),
                    "rule_refs": list(needs.rule_refs),
                    "bmi": targets.bmi,
                    "bmr": targets.bmr,
                    "tdee": targets.tdee,
                    "target_kcal": targets.target_kcal,
                    "protein_g": targets.protein_g,
                    "fat_g": targets.fat_g,
                    "carb_g": targets.carb_g,
                    "fiber_min_g": targets.fiber_min_g,
                    "sodium_max_mg": targets.sodium_max_mg,
                    "sugar_max_g": targets.sugar_max_g,
                    "kcal_floor": targets.kcal_floor,
                },
            }
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(built_cases, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return built_cases


def main() -> int:
    """Điểm vào CLI sinh evals/cases.json từ evals/cases_raw.json."""
    parser = argparse.ArgumentParser(description="Sinh đáp án kỳ vọng cho bộ ca evals.")
    parser.add_argument("--input", type=Path, default=DEFAULT_RAW_PATH, help="File cases_raw.json")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT_PATH, help="File cases.json")
    args = parser.parse_args()

    cases = build_eval_cases(raw_path=args.input, out_path=args.output)
    counts = Counter(c["category"] for c in cases)
    actions = Counter(c["expected"]["action"] for c in cases)
    print(f"Đã sinh {len(cases)} ca -> {args.output}")
    print(f"Phân bố nhóm: {dict(counts)}")
    print(f"Phân bố hành động kỳ vọng: {dict(actions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
