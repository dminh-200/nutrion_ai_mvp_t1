"""Chạy đánh giá 3 cấu hình ablation (llm_only, llm_rag, full) và xuất báo cáo (SPEC 13.2–13.4)."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from agent.llm import (
    call_explain_llm,
    call_planner_llm,
    get_llm_error_types,
    resolve_active_model_name,
)
from agent.nodes import NEED_QUERY_MAP, _diversify_foods
from agent.tools_gateway import ToolsGateway
from agent.verifier import verify_meal_plan
from config.settings import Settings, get_settings
from core.nutrition import load_rules
from core.portion import adjust_portions
from core.schemas import GuidelineSnippet, MealPlanLLM, PatientProfile
from db.import_food import import_food_csv
from db.init_db import init_db
from db.models import Food
from db.session import get_engine
from evals.build_cases import DEFAULT_OUT_PATH as DEFAULT_CASES_PATH
from evals.build_cases import DEFAULT_RAW_PATH, build_eval_cases
from evals.metrics import (
    CONFIG_ORDER,
    aggregate_config_metrics,
    build_summary_markdown,
    evaluate_redteam,
    export_results_csv,
    plot_ablation_chart,
)
from evals.rag_eval import evaluate_retrieval
from guardrails.input import evaluate_input_guardrail
from guardrails.output import evaluate_output_guardrail
from rag.retrieve import sanitize_guideline_snippets

DEFAULT_OUT_DIR = Path("evals/out")
DEFAULT_SUMMARY_PATH = Path("evals/summary.md")
DEFAULT_CSV_PATH = Path("evals/results.csv")
DEFAULT_CHART_PATH = Path("evals/ablation.png")


def _ensure_food_db() -> None:
    """Đảm bảo SQLite đã khởi tạo bảng và có dữ liệu thực phẩm."""
    engine = get_engine()
    init_db(engine)
    with Session(engine) as session:
        count = session.scalar(select(func.count()).select_from(Food)) or 0
    if count == 0:
        import_food_csv(engine=engine)


def _retrieve_snippets(
    needs_list: list[str],
    gateway: ToolsGateway,
) -> list[GuidelineSnippet]:
    """Truy vấn hướng dẫn theo từng nhu cầu, gộp và khử trùng tối đa 8 đoạn."""
    merged: list[GuidelineSnippet] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for need_name in needs_list:
        if need_name.startswith("tranh_di_ung:"):
            allergen_code = need_name.split(":", 1)[-1]
            query, disease = f"lưu ý dị ứng thực phẩm {allergen_code}", None
        else:
            query, disease = NEED_QUERY_MAP.get(
                need_name, (f"hướng dẫn dinh dưỡng {need_name}", None)
            )
        fetched = gateway.get_guideline(query=query, disease=disease, k=4)
        for snip in fetched:
            dedup_key = (snip.source_name, str(snip.page), snip.text)
            if dedup_key not in seen_keys:
                seen_keys.add(dedup_key)
                merged.append(snip)
                if len(merged) >= 8:
                    break
        if len(merged) >= 8:
            break
    return sanitize_guideline_snippets(merged)[:8]


def _count_plan_items(plan_llm: MealPlanLLM | None) -> int:
    """Đếm tổng số lượt món trong thực đơn."""
    if plan_llm is None or plan_llm.cannot_plan:
        return 0
    return sum(len(meal.items) for day in plan_llm.days for meal in day.meals)


def run_single_case(
    case: dict[str, Any],
    *,
    config_name: str,
    llm_mode: str,
    use_cache: bool,
    gateway: ToolsGateway,
    settings: Settings,
) -> dict[str, Any]:
    """Chạy 1 ca đánh giá theo cấu hình ablation (llm_only | llm_rag | full)."""
    t0 = time.perf_counter()
    profile = PatientProfile.model_validate(case["profile"])
    use_rag = config_name in ("llm_rag", "full")
    use_portion_adjust = config_name == "full"
    max_retries = 2 if config_name == "full" else 0

    metrics: dict[str, Any] = {
        "llm_calls": 0,
        "tokens_in": 0,
        "tokens_out": 0,
        "latency_ms": 0.0,
    }

    guard_in = evaluate_input_guardrail(profile, session_id="", log_events=False)
    if guard_in.action in ("redirect_to_doctor", "blocked", "needs_human_review"):
        metrics["latency_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        return {
            "config": config_name,
            "case_id": case["id"],
            "category": case["category"],
            "profile": case["profile"],
            "expected": case["expected"],
            "llm_mode": llm_mode,
            "status": guard_in.action,
            "actual_needs": [],
            "snippets": [],
            "plan_scored": [],
            "violation_codes": [],
            "retry_count": 0,
            "cannot_plan": False,
            "explanation_md": guard_in.blocked_message_vi,
            "input_flags": list(guard_in.flags),
            "output_flags": [],
            "data_missing_items": 0,
            "total_items": 0,
            "metrics": metrics,
        }

    active_profile = guard_in.profile or profile
    calc_res = gateway.calc_targets(active_profile)
    targets = calc_res["targets"]
    needs = calc_res["needs"]

    snippets: list[GuidelineSnippet] = []
    if use_rag:
        snippets = _retrieve_snippets(list(needs.needs), gateway)

    cfg = load_rules()
    exclude_tags: list[str] = []
    max_purine_level: str | None = None
    for need_name in needs.needs:
        need_cfg = cfg["needs"].get(need_name, {})
        exclude_tags.extend(need_cfg.get("avoid_tags", []))
        if "max_purine_level" in need_cfg:
            max_purine_level = str(need_cfg["max_purine_level"])

    candidates = gateway.search_food(
        query="",
        exclude_allergens=list(active_profile.allergens),
        exclude_tags=exclude_tags,
        max_purine_level=max_purine_level,
        limit=200,
    )
    allowed_foods = _diversify_foods(candidates, limit=120)

    prev_violations: list[Any] = []
    plan_llm: MealPlanLLM | None = None
    daily_totals: list[dict[str, Any]] = []
    violations: list[Any] = []
    retry_count = 0

    for attempt in range(max_retries + 1):
        retry_count = attempt
        try:
            plan_llm, usage = call_planner_llm(
                days=active_profile.days,
                allowed_foods=allowed_foods,
                targets=targets,
                profile=active_profile,
                needs=needs,
                violations=prev_violations,
                snippets=snippets if use_rag else None,
                mode=llm_mode,
                use_cache=use_cache,
                settings=settings,
            )
            metrics["llm_calls"] += 1
            metrics["tokens_in"] += int(usage.get("tokens_in", 0))
            metrics["tokens_out"] += int(usage.get("tokens_out", 0))
        except get_llm_error_types() as exc:
            plan_llm = MealPlanLLM(days=[], cannot_plan=True, reason=str(exc))
            break

        if plan_llm.cannot_plan:
            break

        if use_portion_adjust:
            plan_llm, _ = adjust_portions(plan_llm, targets)

        violations, daily_totals = verify_meal_plan(
            plan=plan_llm,
            profile=active_profile,
            targets=targets,
            gateway=gateway,
            needs=needs,
            allowed_foods=allowed_foods,
        )
        if not violations:
            break
        prev_violations = violations

    explanation_md = ""
    output_flags: list[str] = []
    final_status = "needs_human_review"

    if plan_llm is not None and not plan_llm.cannot_plan:
        food_name_map = {
            int(f["id"]): str(f.get("name_vi", ""))
            for f in allowed_foods
            if "id" in f
        }
        try:
            explanation_md, ex_usage = call_explain_llm(
                needs=needs,
                targets=targets,
                snippets=snippets,
                plan_scored=daily_totals,
                plan_llm=plan_llm,
                food_name_map=food_name_map,
                mode=llm_mode,
                use_cache=use_cache,
                settings=settings,
            )
            metrics["llm_calls"] += 1
            metrics["tokens_in"] += int(ex_usage.get("tokens_in", 0))
            metrics["tokens_out"] += int(ex_usage.get("tokens_out", 0))
        except get_llm_error_types():
            explanation_md, _ = call_explain_llm(
                needs=needs,
                targets=targets,
                snippets=snippets,
                mode="mock",
                settings=settings,
            )

        out_guard = evaluate_output_guardrail(
            explanation_md=explanation_md,
            snippets=snippets,
            profile=active_profile,
            targets=targets,
            plan_llm=plan_llm,
            plan_scored=daily_totals,
            allowed_foods=allowed_foods,
            violations=violations,
            session_id="",
            gateway=gateway,
            log_events=False,
        )
        explanation_md = out_guard.explanation_md
        output_flags = list(out_guard.output_flags)
        final_status = out_guard.status

    metrics["latency_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
    v_codes = [v.code for v in violations]
    data_missing_items = sum(1 for v in violations if v.code == "DATA_MISSING")

    return {
        "config": config_name,
        "case_id": case["id"],
        "category": case["category"],
        "profile": case["profile"],
        "expected": case["expected"],
        "llm_mode": llm_mode,
        "status": final_status,
        "actual_needs": list(needs.needs),
        "snippets": [s.model_dump() for s in snippets],
        "plan_scored": daily_totals,
        "violation_codes": v_codes,
        "retry_count": retry_count,
        "cannot_plan": bool(plan_llm.cannot_plan) if plan_llm else True,
        "explanation_md": explanation_md,
        "input_flags": list(guard_in.flags),
        "output_flags": output_flags,
        "data_missing_items": data_missing_items,
        "total_items": _count_plan_items(plan_llm),
        "metrics": metrics,
    }


def run_eval_config(
    *,
    config_name: str,
    llm_mode: str,
    use_cache: bool,
    limit: int | None = None,
    cases_path: Path = DEFAULT_CASES_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
    tools_mode: str = "direct",
    force: bool = False,
) -> list[dict[str, Any]]:
    """Chạy eval tuần tự cho 1 cấu hình và lưu từng ca vào evals/out/<config>/."""
    if not cases_path.exists():
        build_eval_cases(raw_path=DEFAULT_RAW_PATH, out_path=cases_path)

    _ensure_food_db()
    all_cases = json.loads(cases_path.read_text(encoding="utf-8"))
    selected_cases = all_cases[:limit] if limit and limit > 0 else all_cases

    cfg_dir = out_dir / config_name
    cfg_dir.mkdir(parents=True, exist_ok=True)

    settings = get_settings().model_copy(update={"LLM_MODE": llm_mode})
    meta_path = cfg_dir / "_meta.json"
    meta_payload = {
        "config": config_name,
        "llm_mode": llm_mode,
        "llm_provider": settings.LLM_PROVIDER,
        "planner_model": resolve_active_model_name("planner", settings=settings),
        "light_model": resolve_active_model_name("light", settings=settings),
        "cache": "on" if use_cache else "off",
        "limit": len(selected_cases),
        "total_raw_cases": len(all_cases),
    }
    meta_path.write_text(json.dumps(meta_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    results: list[dict[str, Any]] = []
    with ToolsGateway(mode=tools_mode) as gw:
        for idx, case in enumerate(selected_cases, start=1):
            case_file = cfg_dir / f"{case['id']}.json"
            if case_file.exists() and not force:
                existing = json.loads(case_file.read_text(encoding="utf-8"))
                if existing.get("llm_mode") == llm_mode:
                    results.append(existing)
                    print(
                        f"[{config_name}] ({idx}/{len(selected_cases)}) "
                        f"{case['id']} -> resume (cached file)"
                    )
                    continue

            record = run_single_case(
                case,
                config_name=config_name,
                llm_mode=llm_mode,
                use_cache=use_cache,
                gateway=gw,
                settings=settings,
            )
            case_file.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            results.append(record)
            m = record["metrics"]
            print(
                f"[{config_name}] ({idx}/{len(selected_cases)}) {case['id']} "
                f"status={record['status']} calls={m['llm_calls']} "
                f"viol={record['violation_codes']} {m['latency_ms']:.0f}ms"
            )

    return results


def generate_eval_report(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary_path: Path = DEFAULT_SUMMARY_PATH,
    csv_path: Path = DEFAULT_CSV_PATH,
    chart_path: Path = DEFAULT_CHART_PATH,
    use_fake_embedder: bool = False,
) -> dict[str, dict[str, Any]]:
    """Tổng hợp các cấu hình trong evals/out/ và xuất summary.md, results.csv, ablation.png."""
    if not out_dir.exists():
        raise FileNotFoundError(f"Chưa có thư mục kết quả eval: {out_dir}")

    redteam_stats = evaluate_redteam()
    rag_stats = evaluate_retrieval(use_fake_embedder=use_fake_embedder)

    summaries: dict[str, dict[str, Any]] = {}
    meta_by_config: dict[str, dict[str, Any]] = {}
    all_records: list[dict[str, Any]] = []

    found_dirs = [d.name for d in out_dir.iterdir() if d.is_dir()]
    ordered = [c for c in CONFIG_ORDER if c in found_dirs] + [
        c for c in sorted(found_dirs) if c not in CONFIG_ORDER
    ]

    for cfg_name in ordered:
        cfg_dir = out_dir / cfg_name
        meta_file = cfg_dir / "_meta.json"
        if meta_file.exists():
            meta_by_config[cfg_name] = json.loads(meta_file.read_text(encoding="utf-8"))

        case_files = sorted(p for p in cfg_dir.glob("*.json") if p.name != "_meta.json")
        if not case_files:
            continue
        records = [json.loads(p.read_text(encoding="utf-8")) for p in case_files]
        all_records.extend(records)
        summaries[cfg_name] = aggregate_config_metrics(
            records,
            config_name=cfg_name,
            redteam_stats=redteam_stats,
            rag_stats=rag_stats,
        )

    if not summaries:
        raise ValueError(f"Không tìm thấy kết quả eval nào trong {out_dir}")

    summary_md = build_summary_markdown(
        summaries,
        meta_by_config=meta_by_config,
        redteam_stats=redteam_stats,
        rag_stats=rag_stats,
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(summary_md, encoding="utf-8")

    export_results_csv(all_records, csv_path)

    first_meta = next(iter(meta_by_config.values()), {})
    limit_n = first_meta.get("limit")
    total_n = first_meta.get("total_raw_cases", 40)
    provider = first_meta.get("llm_provider", "")
    model = first_meta.get("planner_model", "")
    subtitle = f"{limit_n}/{total_n} ca đại diện | {provider}/{model}" if limit_n else ""
    plot_ablation_chart(summaries, chart_path, subtitle=subtitle)
    return summaries


def main() -> int:
    """Điểm vào CLI chạy evals hoặc xuất báo cáo tổng hợp."""
    parser = argparse.ArgumentParser(description="Chạy evals ablation và xuất báo cáo (M12).")
    parser.add_argument(
        "--config",
        choices=["llm_only", "llm_rag", "full"],
        default="full",
        help="Cấu hình ablation cần chạy.",
    )
    parser.add_argument(
        "--cache",
        choices=["on", "off"],
        default="on",
        help="Bật/tắt cache đĩa cho LLM.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Giới hạn số ca đầu tiên cần chạy (vd: 3 hoặc 6).",
    )
    parser.add_argument(
        "--llm",
        choices=["real", "mock"],
        default=None,
        help="Ghi đè LLM_MODE (mặc định đọc từ Settings/.env).",
    )
    parser.add_argument(
        "--tools-mode",
        choices=["direct", "mcp"],
        default="direct",
        help="Chế độ gọi tool (mặc định direct để chạy eval nhanh).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Thư mục lưu kết quả từng ca (mặc định evals/out).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Chạy lại cả các ca đã có file kết quả trong evals/out/.",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Tổng hợp kết quả từ evals/out/ ra summary.md, results.csv, ablation.png.",
    )
    parser.add_argument(
        "--use-fake-embedder",
        action="store_true",
        help="Dùng FakeEmbedder khi tính retrieval_hit@4 trong --report.",
    )
    args = parser.parse_args()

    if args.report:
        summaries = generate_eval_report(
            out_dir=args.out_dir,
            use_fake_embedder=args.use_fake_embedder,
        )
        print(f"Đã xuất báo cáo cho {len(summaries)} cấu hình: {', '.join(summaries.keys())}")
        print(f"  - {DEFAULT_SUMMARY_PATH}")
        print(f"  - {DEFAULT_CSV_PATH}")
        print(f"  - {DEFAULT_CHART_PATH}")
        return 0

    llm_mode = args.llm or os.environ.get("LLM_MODE") or get_settings().LLM_MODE
    use_cache = args.cache == "on"
    run_eval_config(
        config_name=args.config,
        llm_mode=llm_mode,
        use_cache=use_cache,
        limit=args.limit,
        out_dir=args.out_dir,
        tools_mode=args.tools_mode,
        force=args.force,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
