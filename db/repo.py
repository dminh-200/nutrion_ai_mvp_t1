"""Các hàm DAL cho meal_plan, review, query_log, guardrail_event và giao diện Streamlit (M11)."""

import csv
import io
import json
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session

from db.models import (
    Allergen,
    Condition,
    Food,
    GuardrailEvent,
    HealthProfile,
    MealPlan,
    MealPlanItem,
    Patient,
    ProfileAllergen,
    ProfileCondition,
    QueryLog,
    Review,
)


def create_meal_plan(
    session: Session,
    *,
    profile_id: int,
    thread_id: str,
    status: str = "draft",
    targets_json: str = "{}",
    needs_json: str = "{}",
    risk_json: str = "{}",
    snippets_json: str = "[]",
    violations_json: str = "[]",
    draft_plan_json: str = "{}",
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
        risk_json=risk_json,
        snippets_json=snippets_json,
        violations_json=violations_json,
        draft_plan_json=draft_plan_json,
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
    risk_json: str | None = None,
    snippets_json: str | None = None,
    violations_json: str | None = None,
    draft_plan_json: str | None = None,
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
    if risk_json is not None:
        plan.risk_json = risk_json
    if snippets_json is not None:
        plan.snippets_json = snippets_json
    if violations_json is not None:
        plan.violations_json = violations_json
    if draft_plan_json is not None:
        plan.draft_plan_json = draft_plan_json
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


# ==============================================================================
# HÀM BỔ SUNG CHO GIAO DIỆN STREAMLIT & BẢNG ĐIỀU KHIỂN (M11 - REQUIREMENT R1)
# ==============================================================================


def ensure_db_ready(engine: Engine | None = None) -> dict[str, Any]:
    """Tự động khởi tạo DB, seed 30 bệnh nhân mẫu và import thực phẩm nếu DB trống."""
    from db.import_food import import_food_csv, resolve_food_csv
    from db.init_db import init_db
    from db.seed_patients import seed_patients
    from db.session import get_engine

    target_engine = engine or get_engine()
    init_db(target_engine)

    seeded = False
    imported = False
    with Session(target_engine) as session:
        patient_count = session.scalar(select(func.count()).select_from(Patient)) or 0
        food_count = session.scalar(select(func.count()).select_from(Food)) or 0

    if patient_count == 0:
        seed_patients(engine=target_engine)
        seeded = True
        with Session(target_engine) as session:
            patient_count = session.scalar(select(func.count()).select_from(Patient)) or 0

    if food_count == 0:
        import_food_csv(engine=target_engine)
        imported = True
        with Session(target_engine) as session:
            food_count = session.scalar(select(func.count()).select_from(Food)) or 0

    _, is_sample = resolve_food_csv()
    return {
        "ready": True,
        "patient_count": int(patient_count),
        "food_count": int(food_count),
        "is_sample_food": bool(is_sample or (food_count <= 30)),
        "seeded": seeded,
        "imported": imported,
    }


def load_sample_patients(
    json_path: Path | str = Path("data/patients_seed.json"),
    session: Session | None = None,
) -> list[dict[str, Any]]:
    """Nạp 30 bệnh nhân mẫu từ data/patients_seed.json hoặc truy vấn SQLite fallback."""
    p_path = Path(json_path)
    if p_path.exists():
        try:
            data = json.loads(p_path.read_text(encoding="utf-8"))
            if isinstance(data, list) and len(data) > 0:
                return data
        except Exception:
            pass

    from db.session import get_session

    def _query(sess: Session) -> list[dict[str, Any]]:
        rows = sess.execute(
            select(Patient, HealthProfile)
            .join(HealthProfile, Patient.id == HealthProfile.patient_id)
            .order_by(Patient.id.asc())
        ).all()
        result: list[dict[str, Any]] = []
        for pat, prof in rows:
            cond_rows = sess.scalars(
                select(Condition.code)
                .join(ProfileCondition, Condition.id == ProfileCondition.condition_id)
                .where(ProfileCondition.profile_id == prof.id)
            ).all()
            allergen_rows = sess.scalars(
                select(Allergen.code)
                .join(ProfileAllergen, Allergen.id == ProfileAllergen.allergen_id)
                .where(ProfileAllergen.profile_id == prof.id)
            ).all()
            result.append(
                {
                    "patient_code": pat.code,
                    "display_name": pat.display_name,
                    "age": prof.age,
                    "sex": prof.sex,
                    "height_cm": prof.height_cm,
                    "weight_kg": prof.weight_kg,
                    "activity_level": prof.activity_level,
                    "conditions": list(cond_rows),
                    "allergens": list(allergen_rows),
                    "pregnancy": prof.pregnancy,
                    "lactating": prof.lactating,
                    "ckd_stage": prof.ckd_stage,
                    "dialysis": prof.dialysis,
                    "eating_disorder": prof.eating_disorder,
                    "preferences_text": prof.preferences_text,
                    "days": prof.days,
                }
            )
        return result

    if session is not None:
        return _query(session)
    with get_session() as sess:
        return _query(sess)


def get_system_warnings(session: Session | None = None) -> dict[str, Any]:
    """Trả về danh sách cảnh báo TODO_VERIFY, SAMPLE_DATA và kiểm tra cấu hình khóa LLM."""
    import yaml

    from config.settings import get_settings
    from db.import_food import resolve_food_csv
    from db.session import get_session
    from scripts.check_rules import CONFIG_FILES, find_todo_verify

    todo_verify_items: list[str] = []
    for path in CONFIG_FILES:
        if path.exists():
            try:
                content = yaml.safe_load(path.read_text(encoding="utf-8"))
                todo_verify_items.extend(find_todo_verify(content, str(path)))
            except Exception:
                pass

    _, is_sample_file = resolve_food_csv()

    def _check_food_count(sess: Session) -> int:
        return sess.scalar(select(func.count()).select_from(Food)) or 0

    if session is not None:
        food_count = _check_food_count(session)
    else:
        with get_session() as sess:
            food_count = _check_food_count(sess)

    is_sample_food = bool(is_sample_file or (food_count <= 30))
    settings = get_settings()
    llm_valid, llm_msg = settings.validate_llm_config()

    warnings: list[str] = []
    if todo_verify_items:
        warnings.append(
            f"Còn {len(todo_verify_items)} giá trị quy tắc y khoa chưa kiểm chứng (TODO_VERIFY)."
        )
    if is_sample_food:
        warnings.append(
            "Cơ sở dữ liệu thực phẩm đang sử dụng tập dữ liệu mẫu (SAMPLE_DATA), "
            "cần cập nhật đầy đủ trước khi triển khai lâm sàng."
        )
    if not llm_valid and llm_msg:
        warnings.append(llm_msg)

    return {
        "has_warnings": len(warnings) > 0,
        "todo_verify_count": len(todo_verify_items),
        "todo_verify_items": todo_verify_items,
        "is_sample_food": is_sample_food,
        "sample_food_warning": (
            "Dữ liệu thực phẩm đang ở chế độ mẫu (food_sample.csv)." if is_sample_food else None
        ),
        "llm_warning": llm_msg,
        "warnings": warnings,
    }


def list_meal_plans_for_ui(
    session: Session | None = None,
    status: str | list[str] | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Truy vấn danh sách thực đơn lọc theo trạng thái cho màn hình duyệt."""
    from db.session import get_session

    def _query(sess: Session) -> list[dict[str, Any]]:
        stmt = (
            select(MealPlan, HealthProfile, Patient)
            .join(HealthProfile, MealPlan.profile_id == HealthProfile.id)
            .join(Patient, HealthProfile.patient_id == Patient.id)
        )
        if status is not None:
            if isinstance(status, str):
                stmt = stmt.where(MealPlan.status == status)
            elif isinstance(status, (list, tuple, set)):
                stmt = stmt.where(MealPlan.status.in_(list(status)))

        stmt = stmt.order_by(MealPlan.id.desc()).limit(limit)
        rows = sess.execute(stmt).all()

        results: list[dict[str, Any]] = []
        for plan, prof, pat in rows:
            cond_codes = sess.scalars(
                select(Condition.code)
                .join(ProfileCondition, Condition.id == ProfileCondition.condition_id)
                .where(ProfileCondition.profile_id == prof.id)
            ).all()

            results.append(
                {
                    "id": plan.id,
                    "thread_id": plan.thread_id,
                    "status": plan.status,
                    "patient_code": pat.code,
                    "display_name": pat.display_name,
                    "conditions": list(cond_codes),
                    "retry_count": plan.retry_count,
                    "verifier_passed_first_try": plan.verifier_passed_first_try,
                    "created_at": plan.created_at.isoformat() if plan.created_at else "",
                }
            )
        return results

    if session is not None:
        return _query(session)
    with get_session() as sess:
        return _query(sess)


def _parse_draft_plan_json(raw_json: str | None) -> Any | None:
    """Đọc MealPlanLLM bản nháp từ draft_plan_json nếu hợp lệ và có ngày ăn."""
    if not raw_json or not raw_json.strip():
        return None
    try:
        data = json.loads(raw_json)
        if not isinstance(data, dict) or data.get("cannot_plan") or not data.get("days"):
            return None
        from core.schemas import MealPlanLLM

        plan_obj = MealPlanLLM.model_validate(data)
        return plan_obj if (not plan_obj.cannot_plan and plan_obj.days) else None
    except Exception:
        return None


def _build_approved_explanation_md(
    plan: MealPlan,
    verification: dict[str, Any],
    *,
    note: str = "",
    session: Session | None = None,
) -> str:
    """Tạo nội dung giải thích có trích nguồn chuẩn khi ca needs_human_review được duyệt."""
    from agent.llm import call_explain_llm
    from core.food import load_food_db_from_sqlite
    from core.schemas import GuidelineSnippet, MealPlanLLM, NeedsResult, NutritionTargets
    from guardrails.output import evaluate_output_guardrail

    try:
        targets = NutritionTargets(**json.loads(plan.targets_json or "{}"))
        needs = NeedsResult(**json.loads(plan.needs_json or "{}"))
        raw_snips = json.loads(getattr(plan, "snippets_json", "[]") or "[]")
        snippets = [
            GuidelineSnippet.model_validate(s) for s in raw_snips if isinstance(s, dict)
        ]
        verified_plan = MealPlanLLM.model_validate(verification.get("plan_llm") or {"days": []})
        food_db = load_food_db_from_sqlite(session=session)
        food_name_map = {int(f["id"]): str(f.get("name_vi", "")) for f in food_db if "id" in f}

        text, _ = call_explain_llm(
            needs=needs,
            targets=targets,
            snippets=snippets,
            plan_scored=verification.get("daily_totals") or [],
            plan_llm=verified_plan,
            food_name_map=food_name_map,
            mode="mock",
        )
        notice_vi = (
            f"*Ghi chú thẩm định chuyên gia: {note.strip()}*" if note and note.strip() else ""
        )
        out = evaluate_output_guardrail(
            explanation_md=text,
            snippets=snippets,
            targets=targets,
            plan_llm=verified_plan,
            plan_scored=verification.get("daily_totals") or [],
            allowed_foods=food_db,
            violations=[],
            notice_vi=notice_vi,
            log_events=False,
        )
        return out.explanation_md
    except Exception:
        from guardrails.input import load_guardrails_config

        disclaimer = str(load_guardrails_config().get("disclaimer_vi", "")).strip()
        note_line = f"\n\n*Ghi chú chuyên gia: {note.strip()}*" if note and note.strip() else ""
        return (
            "Thực đơn đã được chuyên gia dinh dưỡng điều chỉnh định lượng và phê duyệt "
            f"đạt chuẩn kiểm chứng lâm sàng.{note_line}\n\n---\n{disclaimer}"
        )


def get_allowed_foods_for_plan(
    meal_plan_id: int,
    query: str = "",
    session: Session | None = None,
) -> list[dict[str, Any]]:
    """Trả về danh sách thực phẩm an toàn cho hồ sơ của meal_plan để chuyên gia thêm/đổi món."""
    from unidecode import unidecode

    from core.classify import classify_needs
    from core.food import get_allowed_foods, load_food_db_from_sqlite
    from core.schemas import NeedsResult, PatientProfile
    from db.session import get_session

    def _query(sess: Session) -> list[dict[str, Any]]:
        plan = sess.get(MealPlan, meal_plan_id)
        if plan is None:
            raise ValueError(f"Không tìm thấy meal_plan có id={meal_plan_id}")
        prof = sess.get(HealthProfile, plan.profile_id)
        if prof is None:
            raise ValueError(f"Không tìm thấy health_profile cho meal_plan={meal_plan_id}")
        pat = sess.get(Patient, prof.patient_id)

        cond_codes = list(
            sess.scalars(
                select(Condition.code)
                .join(ProfileCondition, Condition.id == ProfileCondition.condition_id)
                .where(ProfileCondition.profile_id == prof.id)
            ).all()
        )
        allergen_codes = list(
            sess.scalars(
                select(Allergen.code)
                .join(ProfileAllergen, Allergen.id == ProfileAllergen.allergen_id)
                .where(ProfileAllergen.profile_id == prof.id)
            ).all()
        )

        needs_obj: NeedsResult | None = None
        try:
            needs_dict = json.loads(plan.needs_json or "{}")
            if isinstance(needs_dict, dict) and needs_dict.get("needs"):
                needs_obj = NeedsResult(**needs_dict)
        except Exception:
            needs_obj = None

        if needs_obj is None:
            p_obj = PatientProfile(
                patient_code=pat.code if pat else "P_EDIT",
                age=prof.age,
                sex=prof.sex,  # type: ignore[arg-type]
                height_cm=prof.height_cm,
                weight_kg=prof.weight_kg,
                activity_level=prof.activity_level,  # type: ignore[arg-type]
                conditions=cond_codes,  # type: ignore[arg-type]
                allergens=allergen_codes,  # type: ignore[arg-type]
                pregnancy=prof.pregnancy,
                lactating=prof.lactating,
                ckd_stage=prof.ckd_stage,
                dialysis=prof.dialysis,
                eating_disorder=prof.eating_disorder,
                preferences_text=prof.preferences_text,
                days=prof.days,
            )
            needs_obj = classify_needs(p_obj)

        food_db = load_food_db_from_sqlite(session=sess)
        allowed = get_allowed_foods(
            needs=needs_obj,
            allergens=allergen_codes,
            limit=250,
            food_db=food_db,
        )
        q_norm = unidecode(query).strip().lower() if query else ""
        results: list[dict[str, Any]] = []
        for f in allowed:
            if q_norm:
                hay = unidecode(f"{f.get('name_vi', '')} {f.get('food_group', '')}").lower()
                if q_norm not in hay:
                    continue
            results.append(
                {
                    "id": int(f["id"]),
                    "code": str(f.get("code", "")),
                    "name_vi": str(f.get("name_vi", "")),
                    "food_group": str(f.get("food_group", "khac")),
                    "unit_default_g": float(f.get("unit_default_g") or 100.0),
                    "kcal": round(float(f.get("kcal") or 0.0), 1),
                    "protein_g": round(float(f.get("protein_g") or 0.0), 1),
                    "fat_g": round(float(f.get("fat_g") or 0.0), 1),
                    "carb_g": round(float(f.get("carb_g") or 0.0), 1),
                    "fiber_g": round(float(f.get("fiber_g") or 0.0), 1),
                    "sugar_g": round(float(f.get("sugar_g") or 0.0), 1),
                    "sodium_mg": round(float(f.get("sodium_mg") or 0.0), 1),
                    "purine_level": str(f.get("purine_level", "low")),
                }
            )
        return results

    if session is not None:
        return _query(session)
    with get_session() as sess:
        return _query(sess)


def get_meal_plan_detail(
    meal_plan_id: int,
    session: Session | None = None,
) -> dict[str, Any] | None:
    """Lấy chi tiết thực đơn gồm hồ sơ, nhu cầu, mục tiêu, món ăn, tổng ngày và đánh giá."""
    from db.session import get_session

    def _query(sess: Session) -> dict[str, Any] | None:
        plan = sess.get(MealPlan, meal_plan_id)
        if plan is None:
            return None

        prof = sess.get(HealthProfile, plan.profile_id)
        pat = sess.get(Patient, prof.patient_id) if prof else None

        cond_codes: list[str] = []
        allergen_codes: list[str] = []
        if prof:
            cond_codes = list(
                sess.scalars(
                    select(Condition.code)
                    .join(ProfileCondition, Condition.id == ProfileCondition.condition_id)
                    .where(ProfileCondition.profile_id == prof.id)
                ).all()
            )
            allergen_codes = list(
                sess.scalars(
                    select(Allergen.code)
                    .join(ProfileAllergen, Allergen.id == ProfileAllergen.allergen_id)
                    .where(ProfileAllergen.profile_id == prof.id)
                ).all()
            )

        try:
            targets_dict = json.loads(plan.targets_json)
        except Exception:
            targets_dict = {}
        try:
            needs_dict = json.loads(plan.needs_json)
        except Exception:
            needs_dict = {}
        try:
            risk_dict = json.loads(getattr(plan, "risk_json", "{}") or "{}")
            if not isinstance(risk_dict, dict):
                risk_dict = {}
        except Exception:
            risk_dict = {}
        try:
            snippets_list = json.loads(getattr(plan, "snippets_json", "[]") or "[]")
            if not isinstance(snippets_list, list):
                snippets_list = []
        except Exception:
            snippets_list = []
        try:
            violations_list = json.loads(getattr(plan, "violations_json", "[]") or "[]")
            if not isinstance(violations_list, list):
                violations_list = []
        except Exception:
            violations_list = []

        if not risk_dict and plan.status == "redirect_to_doctor" and prof is not None:
            from core.classify import assess_risk
            from core.schemas import PatientProfile

            try:
                p_obj = PatientProfile(
                    patient_code=pat.code if pat else "ANON",
                    age=prof.age,
                    sex=prof.sex,  # type: ignore[arg-type]
                    height_cm=prof.height_cm,
                    weight_kg=prof.weight_kg,
                    activity_level=prof.activity_level,  # type: ignore[arg-type]
                    conditions=cond_codes,  # type: ignore[arg-type]
                    allergens=allergen_codes,  # type: ignore[arg-type]
                    pregnancy=prof.pregnancy,
                    lactating=prof.lactating,
                    ckd_stage=prof.ckd_stage,
                    dialysis=prof.dialysis,
                    eating_disorder=prof.eating_disorder,
                    preferences_text=prof.preferences_text,
                    days=prof.days,
                )
                risk_dict = assess_risk(p_obj).model_dump()
            except Exception:
                risk_dict = {}

        item_rows = sess.execute(
            select(MealPlanItem, Food)
            .join(Food, MealPlanItem.food_id == Food.id)
            .where(MealPlanItem.meal_plan_id == meal_plan_id)
            .order_by(MealPlanItem.day.asc(), MealPlanItem.id.asc())
        ).all()

        items_list: list[dict[str, Any]] = []
        by_day: dict[int, dict[str, list[dict[str, Any]]]] = {}
        day_accum: dict[int, dict[str, float]] = {}

        for it, f in item_rows:
            item_dict = {
                "id": it.id,
                "day": it.day,
                "meal": it.meal,
                "food_id": it.food_id,
                "name_vi": f.name_vi,
                "grams": it.grams,
                "kcal": round(it.kcal, 1),
                "protein_g": round(it.protein_g, 1),
                "fat_g": round(it.fat_g, 1),
                "carb_g": round(it.carb_g, 1),
                "sodium_mg": round(it.sodium_mg, 1),
            }
            items_list.append(item_dict)
            by_day.setdefault(it.day, {}).setdefault(it.meal, []).append(item_dict)

            if it.day not in day_accum:
                day_accum[it.day] = {
                    "day": it.day,
                    "kcal": 0.0,
                    "protein_g": 0.0,
                    "fat_g": 0.0,
                    "carb_g": 0.0,
                    "sodium_mg": 0.0,
                }
            day_accum[it.day]["kcal"] += it.kcal
            day_accum[it.day]["protein_g"] += it.protein_g
            day_accum[it.day]["fat_g"] += it.fat_g
            day_accum[it.day]["carb_g"] += it.carb_g
            day_accum[it.day]["sodium_mg"] += it.sodium_mg

        if not items_list and plan.status not in ("redirect_to_doctor", "blocked"):
            draft_plan = _parse_draft_plan_json(getattr(plan, "draft_plan_json", "{}"))
            if draft_plan is not None:
                from db.models import FoodNutrient

                food_rows = sess.execute(
                    select(Food, FoodNutrient).join(
                        FoodNutrient, Food.id == FoodNutrient.food_id
                    )
                ).all()
                food_map = {int(f_row.id): (f_row, n_row) for f_row, n_row in food_rows}
                synthetic_id = 1
                for day_plan in draft_plan.days:
                    d_num = int(day_plan.day)
                    for meal_obj in day_plan.meals:
                        m_name = str(meal_obj.meal)
                        for p_item in meal_obj.items:
                            fid = int(p_item.food_id)
                            pair = food_map.get(fid)
                            if pair is None:
                                continue
                            f_row, n_row = pair
                            grams = float(p_item.grams)
                            ratio = grams / 100.0
                            kcal = round(float(n_row.kcal or 0.0) * ratio, 1)
                            prot = round(float(n_row.protein_g or 0.0) * ratio, 1)
                            fat = round(float(n_row.fat_g or 0.0) * ratio, 1)
                            carb = round(float(n_row.carb_g or 0.0) * ratio, 1)
                            sod = round(float(n_row.sodium_mg or 0.0) * ratio, 1)
                            item_dict = {
                                "id": synthetic_id,
                                "day": d_num,
                                "meal": m_name,
                                "food_id": fid,
                                "name_vi": f_row.name_vi,
                                "grams": grams,
                                "kcal": kcal,
                                "protein_g": prot,
                                "fat_g": fat,
                                "carb_g": carb,
                                "sodium_mg": sod,
                            }
                            synthetic_id += 1
                            items_list.append(item_dict)
                            by_day.setdefault(d_num, {}).setdefault(m_name, []).append(item_dict)
                            if d_num not in day_accum:
                                day_accum[d_num] = {
                                    "day": d_num,
                                    "kcal": 0.0,
                                    "protein_g": 0.0,
                                    "fat_g": 0.0,
                                    "carb_g": 0.0,
                                    "sodium_mg": 0.0,
                                }
                            day_accum[d_num]["kcal"] += kcal
                            day_accum[d_num]["protein_g"] += prot
                            day_accum[d_num]["fat_g"] += fat
                            day_accum[d_num]["carb_g"] += carb
                            day_accum[d_num]["sodium_mg"] += sod

        daily_totals = [
            {
                "day": d,
                "kcal": round(v["kcal"], 1),
                "protein_g": round(v["protein_g"], 1),
                "fat_g": round(v["fat_g"], 1),
                "carb_g": round(v["carb_g"], 1),
                "sodium_mg": round(v["sodium_mg"], 1),
            }
            for d, v in sorted(day_accum.items())
        ]

        reviews = sess.scalars(
            select(Review).where(Review.meal_plan_id == meal_plan_id).order_by(Review.id.asc())
        ).all()
        reviews_list = [
            {
                "id": r.id,
                "reviewer_name": r.reviewer_name,
                "decision": r.decision,
                "note": r.note,
                "created_at": r.created_at.isoformat() if r.created_at else "",
            }
            for r in reviews
        ]

        q_sessions = list(
            sess.scalars(
                select(QueryLog.session_id).where(QueryLog.meal_plan_id == meal_plan_id)
            ).all()
        )
        candidate_sids = list(dict.fromkeys([plan.thread_id, *q_sessions]))
        guardrail_events = sess.scalars(
            select(GuardrailEvent)
            .where(GuardrailEvent.session_id.in_(candidate_sids))
            .order_by(GuardrailEvent.id.asc())
        ).all()
        guardrails_list = [
            {
                "id": ge.id,
                "layer": ge.layer,
                "type": ge.type,
                "reason": ge.reason,
                "created_at": ge.created_at.isoformat() if ge.created_at else "",
            }
            for ge in guardrail_events
        ]

        return {
            "meal_plan": {
                "id": plan.id,
                "thread_id": plan.thread_id,
                "status": plan.status,
                "explanation_md": plan.explanation_md,
                "retry_count": plan.retry_count,
                "verifier_passed_first_try": plan.verifier_passed_first_try,
                "created_at": plan.created_at.isoformat() if plan.created_at else "",
            },
            "patient": {
                "code": pat.code if pat else "",
                "display_name": pat.display_name if pat else "",
                "age": prof.age if prof else 0,
                "sex": prof.sex if prof else "male",
                "height_cm": prof.height_cm if prof else 0.0,
                "weight_kg": prof.weight_kg if prof else 0.0,
                "activity_level": prof.activity_level if prof else "sedentary",
                "conditions": cond_codes,
                "allergens": allergen_codes,
                "pregnancy": prof.pregnancy if prof else False,
                "lactating": prof.lactating if prof else False,
                "ckd_stage": prof.ckd_stage if prof else 0,
                "dialysis": prof.dialysis if prof else False,
                "eating_disorder": prof.eating_disorder if prof else False,
                "preferences_text": prof.preferences_text if prof else "",
                "days": prof.days if prof else 3,
            },
            "targets": targets_dict,
            "needs": needs_dict,
            "risk": risk_dict or None,
            "snippets": snippets_list,
            "violations": violations_list,
            "items": items_list,
            "by_day": by_day,
            "daily_totals": daily_totals,
            "reviews": reviews_list,
            "guardrail_events": guardrails_list,
        }

    if session is not None:
        return _query(session)
    with get_session() as sess:
        return _query(sess)


def preview_and_verify_edited_items(
    meal_plan_id: int,
    edited_items: list[dict[str, Any]],
    session: Session | None = None,
) -> dict[str, Any]:
    """Tính toán lại dinh dưỡng và kiểm chứng lâm sàng bản sửa tạm (không ghi DB)."""
    from agent.nodes import _apply_edited_items
    from agent.tools_gateway import ToolsGateway
    from agent.verifier import verify_meal_plan
    from core.food import load_food_db_from_sqlite
    from core.schemas import (
        DayPlan,
        Meal,
        MealPlanLLM,
        NeedsResult,
        NutritionTargets,
        PatientProfile,
        PlannedItem,
    )
    from core.scoring import score_menu
    from db.session import get_session

    def _execute(sess: Session) -> dict[str, Any]:
        plan = sess.get(MealPlan, meal_plan_id)
        if plan is None:
            raise ValueError(f"Không tìm thấy meal_plan có id={meal_plan_id}")

        prof = sess.get(HealthProfile, plan.profile_id)
        if prof is None:
            raise ValueError(f"Không tìm thấy health_profile cho meal_plan={meal_plan_id}")
        pat = sess.get(Patient, prof.patient_id)

        cond_codes = list(
            sess.scalars(
                select(Condition.code)
                .join(ProfileCondition, Condition.id == ProfileCondition.condition_id)
                .where(ProfileCondition.profile_id == prof.id)
            ).all()
        )
        allergen_codes = list(
            sess.scalars(
                select(Allergen.code)
                .join(ProfileAllergen, Allergen.id == ProfileAllergen.allergen_id)
                .where(ProfileAllergen.profile_id == prof.id)
            ).all()
        )

        profile = PatientProfile(
            patient_code=pat.code if pat else "P_EDIT",
            age=prof.age,
            sex=prof.sex,  # type: ignore[arg-type]
            height_cm=prof.height_cm,
            weight_kg=prof.weight_kg,
            activity_level=prof.activity_level,  # type: ignore[arg-type]
            conditions=cond_codes,  # type: ignore[arg-type]
            allergens=allergen_codes,  # type: ignore[arg-type]
            pregnancy=prof.pregnancy,
            lactating=prof.lactating,
            ckd_stage=prof.ckd_stage,
            dialysis=prof.dialysis,
            eating_disorder=prof.eating_disorder,
            preferences_text=prof.preferences_text,
            days=prof.days,
        )

        targets_dict = json.loads(plan.targets_json)
        targets = NutritionTargets(**targets_dict)

        needs_dict = json.loads(plan.needs_json)
        needs = NeedsResult(**needs_dict)

        item_rows = sess.scalars(
            select(MealPlanItem)
            .where(MealPlanItem.meal_plan_id == meal_plan_id)
            .order_by(MealPlanItem.day.asc(), MealPlanItem.id.asc())
        ).all()

        by_day_meal: dict[tuple[int, str], list[PlannedItem]] = {}
        for it in item_rows:
            by_day_meal.setdefault((it.day, it.meal), []).append(
                PlannedItem(food_id=it.food_id, grams=it.grams)
            )
        if not by_day_meal:
            draft_plan = _parse_draft_plan_json(getattr(plan, "draft_plan_json", "{}"))
            if draft_plan is not None:
                for dp in draft_plan.days:
                    for ml in dp.meals:
                        for pit in ml.items:
                            by_day_meal.setdefault((int(dp.day), str(ml.meal)), []).append(
                                PlannedItem(food_id=int(pit.food_id), grams=float(pit.grams))
                            )

        days_list: list[DayPlan] = []
        for d in range(1, prof.days + 1):
            meals_list: list[Meal] = []
            for m in ("breakfast", "lunch", "dinner", "snack"):
                items_in_m = by_day_meal.get((d, m), [])
                if items_in_m:
                    meals_list.append(Meal(meal=m, items=items_in_m))  # type: ignore[arg-type]
            days_list.append(DayPlan(day=d, meals=meals_list))

        base_plan = MealPlanLLM(days=days_list, cannot_plan=False, reason="")
        if not edited_items:
            empty_viol = [
                {
                    "code": "DAY_COUNT",
                    "message_vi": "Thực đơn chỉnh sửa không có món ăn nào.",
                    "day": None,
                    "meal": None,
                    "food_id": None,
                }
            ]
            return {
                "is_valid": False,
                "violations": empty_viol,
                "daily_totals": [],
                "scored_items": [],
                "plan_llm": MealPlanLLM(days=[], cannot_plan=False, reason="").model_dump(),
            }

        new_plan = _apply_edited_items(base_plan, edited_items)

        food_db = load_food_db_from_sqlite(session=sess)
        scoring_res = score_menu(new_plan, food_db=food_db)

        with ToolsGateway(mode="direct") as gw:
            violations, _ = verify_meal_plan(
                plan=new_plan,
                profile=profile,
                targets=targets,
                gateway=gw,
                needs=needs,
                food_db=food_db,
            )

        has_positive_items = any(
            it.grams > 0 for d in new_plan.days for m in d.meals for it in m.items
        )
        return {
            "is_valid": len(violations) == 0 and has_positive_items and bool(scoring_res["items"]),
            "violations": [v.model_dump() for v in violations],
            "daily_totals": scoring_res["daily_totals"],
            "scored_items": [it.model_dump() for it in scoring_res["items"]],
            "plan_llm": new_plan.model_dump(),
        }

    if session is not None:
        return _execute(session)
    with get_session() as sess:
        return _execute(sess)


def record_review_for_finalized_plan(
    meal_plan_id: int,
    reviewer_name: str,
    decision: str,
    note: str = "",
    edited_items: list[dict[str, Any]] | None = None,
    session: Session | None = None,
) -> dict[str, Any]:
    """Ghi nhận quyết định phê duyệt/từ chối của chuyên gia cho ca needs_human_review."""
    decision_clean = decision.lower().strip()
    if decision_clean not in ("approve", "reject", "edit"):
        raise ValueError(f"Quyết định không hợp lệ: {decision}. Cho phép: approve, reject, edit")

    if decision_clean == "reject" and not note.strip():
        raise ValueError("Từ chối thực đơn bắt buộc phải có lý do (note).")

    from db.session import get_session

    def _execute(sess: Session) -> dict[str, Any]:
        plan = sess.get(MealPlan, meal_plan_id)
        if plan is None:
            raise ValueError(f"Không tìm thấy meal_plan có id={meal_plan_id}")

        if plan.status != "needs_human_review":
            raise ValueError("Chỉ ca cần chuyên gia xem mới được xử lý ngoài luồng duyệt.")

        verification: dict[str, Any] | None = None
        if decision_clean in ("approve", "edit"):
            current_rows = list(
                sess.scalars(
                    select(MealPlanItem).where(MealPlanItem.meal_plan_id == meal_plan_id)
                ).all()
            )
            current_items: list[dict[str, Any]] = [
                {
                    "day": item.day,
                    "meal": item.meal,
                    "food_id": item.food_id,
                    "grams": item.grams,
                }
                for item in current_rows
            ]
            if not current_items:
                draft_plan = _parse_draft_plan_json(getattr(plan, "draft_plan_json", "{}"))
                if draft_plan is not None:
                    for dp in draft_plan.days:
                        for ml in dp.meals:
                            for pit in ml.items:
                                current_items.append(
                                    {
                                        "day": int(dp.day),
                                        "meal": str(ml.meal),
                                        "food_id": int(pit.food_id),
                                        "grams": float(pit.grams),
                                    }
                                )
            if decision_clean == "edit":
                if edited_items is None:
                    raise ValueError("Cần danh sách món chỉnh sửa hợp lệ khi chọn sửa thực đơn.")
                if not current_items and not edited_items:
                    raise ValueError("Không thể duyệt thực đơn chưa có món ăn.")
                candidate_items = edited_items
            else:
                if not current_items:
                    raise ValueError("Không thể duyệt thực đơn chưa có món ăn.")
                candidate_items = current_items

            verification = preview_and_verify_edited_items(
                meal_plan_id, candidate_items or [], session=sess
            )
            if not verification["is_valid"] or not verification.get("scored_items"):
                raise ValueError("Thực đơn còn vi phạm kiểm chứng; chỉ có thể từ chối.")

        new_status = "approved" if decision_clean in ("approve", "edit") else "rejected"
        plan.status = new_status
        if new_status == "approved":
            plan.violations_json = "[]"

        if new_status == "approved" and verification is not None:
            sess.execute(delete(MealPlanItem).where(MealPlanItem.meal_plan_id == meal_plan_id))
            sess.flush()

            verified_plan = verification.get("plan_llm") or {}
            plan.draft_plan_json = json.dumps(verified_plan, ensure_ascii=False)
            scored_list = list(verification.get("scored_items") or [])
            scored_idx = 0
            for day_obj in verified_plan.get("days", []):
                day_num = int(day_obj["day"])
                for meal_obj in day_obj.get("meals", []):
                    meal_name = str(meal_obj["meal"])
                    for _ in meal_obj.get("items", []):
                        s_item = scored_list[scored_idx]
                        scored_idx += 1
                        sess.add(
                            MealPlanItem(
                                meal_plan_id=meal_plan_id,
                                day=day_num,
                                meal=meal_name,
                                food_id=int(s_item["food_id"]),
                                grams=float(s_item["grams"]),
                                kcal=float(s_item["kcal"]),
                                protein_g=float(s_item["protein_g"]),
                                fat_g=float(s_item["fat_g"]),
                                carb_g=float(s_item["carb_g"]),
                                sodium_mg=float(s_item["sodium_mg"]),
                            )
                        )
            cur_exp = (plan.explanation_md or "").strip()
            if (
                not cur_exp
                or "Hệ thống chưa thể tự động hoàn tất thực đơn" in cur_exp
                or "Nội dung giải thích tự động đã bị ẩn" in cur_exp
            ):
                plan.explanation_md = _build_approved_explanation_md(
                    plan,
                    verification,
                    note=note,
                    session=sess,
                )

        edited_json = json.dumps(edited_items or [], ensure_ascii=False)
        rev = Review(
            meal_plan_id=meal_plan_id,
            reviewer_name=reviewer_name,
            decision=decision_clean,
            note=note,
            edited_items_json=edited_json,
        )
        sess.add(rev)

        qlog = sess.scalar(
            select(QueryLog)
            .where(QueryLog.meal_plan_id == meal_plan_id)
            .order_by(QueryLog.id.desc())
        )
        if qlog:
            qlog.status = new_status

        sess.commit()
        return {
            "meal_plan_id": meal_plan_id,
            "status": new_status,
            "decision": decision_clean,
            "note": note,
        }

    if session is not None:
        return _execute(session)
    with get_session() as sess:
        return _execute(sess)


def get_dashboard_dataset(
    session: Session | None = None,
    start_date: datetime | date | None = None,
    end_date: datetime | date | None = None,
    condition: str | None = None,
    include_synthetic: bool = True,
) -> dict[str, Any]:
    """Tổng hợp chỉ số KPI, 4 biểu đồ Plotly và danh sách QueryLog (hỗ trợ xuất CSV)."""
    from config.settings import get_settings
    from db.session import get_session

    def _execute(sess: Session) -> dict[str, Any]:
        stmt = select(QueryLog)
        if not include_synthetic:
            stmt = stmt.where(QueryLog.is_synthetic_log == False)  # noqa: E712

        dt_start: datetime | None = None
        if start_date is not None:
            if isinstance(start_date, date) and not isinstance(start_date, datetime):
                dt_start = datetime.combine(start_date, time.min)
            else:
                dt_start = start_date
            stmt = stmt.where(QueryLog.created_at >= dt_start)

        dt_end: datetime | None = None
        if end_date is not None:
            if isinstance(end_date, date) and not isinstance(end_date, datetime):
                dt_end = datetime.combine(end_date, time.max)
            else:
                dt_end = end_date
            stmt = stmt.where(QueryLog.created_at <= dt_end)

        all_logs = list(sess.scalars(stmt.order_by(QueryLog.created_at.desc())).all())

        if condition:
            cond_clean = condition.strip().lower()
            matched_mp_ids = set(
                sess.scalars(
                    select(MealPlan.id)
                    .join(HealthProfile, MealPlan.profile_id == HealthProfile.id)
                    .join(ProfileCondition, HealthProfile.id == ProfileCondition.profile_id)
                    .join(Condition, ProfileCondition.condition_id == Condition.id)
                    .where(Condition.code == cond_clean)
                ).all()
            )
            mp_id_set = {log.meal_plan_id for log in all_logs if log.meal_plan_id is not None}
            existing_mp_ids_all = (
                set(sess.scalars(select(MealPlan.id).where(MealPlan.id.in_(mp_id_set))).all())
                if mp_id_set
                else set()
            )
            matched_patient_codes = set(
                sess.scalars(
                    select(Patient.code)
                    .join(HealthProfile, Patient.id == HealthProfile.patient_id)
                    .join(ProfileCondition, HealthProfile.id == ProfileCondition.profile_id)
                    .join(Condition, ProfileCondition.condition_id == Condition.id)
                    .where(Condition.code == cond_clean)
                ).all()
            )
            all_logs = [
                log
                for log in all_logs
                if (
                    log.meal_plan_id in matched_mp_ids
                    if (log.meal_plan_id is not None and log.meal_plan_id in existing_mp_ids_all)
                    else log.patient_code in matched_patient_codes
                )
            ]

        total_requests = len(all_logs)
        approved_count = sum(1 for log in all_logs if log.status == "approved")
        pending_count = sum(
            1 for log in all_logs if log.status in ("pending_review", "needs_human_review")
        )
        redirect_count = sum(1 for log in all_logs if log.status == "redirect_to_doctor")
        blocked_count = sum(1 for log in all_logs if log.status == "blocked")

        approval_rate_pct = (
            round((approved_count / total_requests * 100), 1) if total_requests > 0 else 0.0
        )
        redirect_rate_pct = (
            round((redirect_count / total_requests * 100), 1) if total_requests > 0 else 0.0
        )
        blocked_rate_pct = (
            round((blocked_count / total_requests * 100), 1) if total_requests > 0 else 0.0
        )

        eval_logs = [
            log
            for log in all_logs
            if log.status in ("approved", "pending_review", "needs_human_review")
        ]
        first_pass_count = sum(1 for log in eval_logs if log.retry_count == 0)
        first_pass_rate_pct = (
            round((first_pass_count / len(eval_logs) * 100), 1) if eval_logs else 0.0
        )

        latencies = [log.latency_ms for log in all_logs if log.latency_ms > 0]
        avg_latency_ms = round(sum(latencies) / len(latencies), 1) if latencies else 0.0
        p95_latency_ms = 0.0
        if latencies:
            sorted_lat = sorted(latencies)
            idx = int(0.95 * len(sorted_lat))
            p95_latency_ms = round(sorted_lat[min(idx, len(sorted_lat) - 1)], 1)

        total_tokens = sum(log.tokens_in + log.tokens_out for log in all_logs)
        est_cost_usd = round(sum(log.est_cost_usd for log in all_logs), 4)

        sess_ids = {log.session_id for log in all_logs if log.session_id}
        events_by_id: dict[int, GuardrailEvent] = {}
        if sess_ids:
            for ge in sess.scalars(
                select(GuardrailEvent).where(GuardrailEvent.session_id.in_(sess_ids))
            ).all():
                events_by_id[int(ge.id)] = ge

        # Bổ sung GuardrailEvent của Chatbot và API validation không có dòng QueryLog
        if not condition:
            extra_ge_stmt = select(GuardrailEvent).where(
                GuardrailEvent.layer.in_(("chat_input", "chat_output"))
                | (GuardrailEvent.type == "validation")
            )
            if dt_start is not None:
                extra_ge_stmt = extra_ge_stmt.where(GuardrailEvent.created_at >= dt_start)
            if dt_end is not None:
                extra_ge_stmt = extra_ge_stmt.where(GuardrailEvent.created_at <= dt_end)
            for ge in sess.scalars(extra_ge_stmt).all():
                events_by_id[int(ge.id)] = ge

        guardrail_events = list(events_by_id.values())
        guardrail_trigger_count = len(guardrail_events)

        kpis = {
            "total_requests": total_requests,
            "approved_count": approved_count,
            "approval_rate_pct": approval_rate_pct,
            "pending_count": pending_count,
            "redirect_count": redirect_count,
            "redirect_rate_pct": redirect_rate_pct,
            "blocked_count": blocked_count,
            "blocked_rate_pct": blocked_rate_pct,
            "first_pass_verifier_rate_pct": first_pass_rate_pct,
            "avg_latency_ms": avg_latency_ms,
            "p95_latency_ms": p95_latency_ms,
            "total_tokens": total_tokens,
            "est_cost_usd": est_cost_usd,
            "guardrail_trigger_count": guardrail_trigger_count,
        }

        by_date: dict[str, dict[str, int]] = {}
        for log in all_logs:
            d_str = log.created_at.strftime("%Y-%m-%d") if log.created_at else "Unknown"
            if d_str not in by_date:
                by_date[d_str] = {
                    "date": d_str,
                    "approved": 0,
                    "pending": 0,
                    "redirect": 0,
                    "blocked": 0,
                    "total": 0,
                }
            by_date[d_str]["total"] += 1
            if log.status == "approved":
                by_date[d_str]["approved"] += 1
            elif log.status in ("pending_review", "needs_human_review"):
                by_date[d_str]["pending"] += 1
            elif log.status == "redirect_to_doctor":
                by_date[d_str]["redirect"] += 1
            elif log.status == "blocked":
                by_date[d_str]["blocked"] += 1
        trend_by_date = [by_date[k] for k in sorted(by_date.keys())]

        cond_counter: dict[str, int] = {"t2d": 0, "htn": 0, "gout": 0, "obesity": 0}
        mp_ids = {log.meal_plan_id for log in all_logs if log.meal_plan_id is not None}
        existing_mp_ids: set[int] = set()
        mp_cond_map: dict[int, set[str]] = {}
        if mp_ids:
            existing_mp_ids = {
                int(mid)
                for mid in sess.scalars(select(MealPlan.id).where(MealPlan.id.in_(mp_ids))).all()
            }
            mp_rows = sess.execute(
                select(MealPlan.id, Condition.code)
                .join(HealthProfile, MealPlan.profile_id == HealthProfile.id)
                .join(ProfileCondition, HealthProfile.id == ProfileCondition.profile_id)
                .join(Condition, ProfileCondition.condition_id == Condition.id)
                .where(MealPlan.id.in_(mp_ids))
            ).all()
            for mp_id, ccode in mp_rows:
                mp_cond_map.setdefault(int(mp_id), set()).add(ccode)

        p_rows = sess.execute(
            select(Patient.code, Condition.code)
            .join(HealthProfile, Patient.id == HealthProfile.patient_id)
            .join(ProfileCondition, HealthProfile.id == ProfileCondition.profile_id)
            .join(Condition, ProfileCondition.condition_id == Condition.id)
            .distinct()
        ).all()
        p_cond_map: dict[str, set[str]] = {}
        for pcode, ccode in p_rows:
            p_cond_map.setdefault(pcode, set()).add(ccode)

        for log in all_logs:
            if log.meal_plan_id is not None and log.meal_plan_id in existing_mp_ids:
                p_conds = mp_cond_map.get(log.meal_plan_id, set())
            else:
                p_conds = p_cond_map.get(log.patient_code, set())
            for c in p_conds:
                if c in cond_counter:
                    cond_counter[c] += 1
        condition_chart = {
            "labels": ["Đái tháo đường T2", "Tăng huyết áp", "Gout", "Béo phì"],
            "codes": ["t2d", "htn", "gout", "obesity"],
            "values": [
                cond_counter["t2d"],
                cond_counter["htn"],
                cond_counter["gout"],
                cond_counter["obesity"],
            ],
        }

        gr_type_counts: dict[str, int] = {}
        for ge in guardrail_events:
            t = ge.type or "other"
            gr_type_counts[t] = gr_type_counts.get(t, 0) + 1
        guardrail_chart = {
            "labels": list(gr_type_counts.keys()) or ["Không có"],
            "counts": list(gr_type_counts.values()) or [0],
        }

        latency_chart = {
            "latencies": latencies,
            "avg": avg_latency_ms,
            "p95": p95_latency_ms,
        }

        charts = {
            "trend_by_date": trend_by_date,
            "condition_distribution": condition_chart,
            "guardrails_by_type": guardrail_chart,
            "latency_distribution": latency_chart,
        }

        langfuse_base = get_settings().LANGFUSE_BASE_URL.rstrip("/")
        logs_data: list[dict[str, Any]] = []
        for log in all_logs:
            trace_url = ""
            if log.trace_id:
                trace_url = f"{langfuse_base}/trace/{log.trace_id}"
            logs_data.append(
                {
                    "id": log.id,
                    "created_at": (
                        log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else ""
                    ),
                    "session_id": log.session_id,
                    "patient_code": log.patient_code,
                    "status": log.status,
                    "latency_ms": round(log.latency_ms, 1),
                    "llm_calls": log.llm_calls,
                    "tokens_in": log.tokens_in,
                    "tokens_out": log.tokens_out,
                    "est_cost_usd": round(log.est_cost_usd, 5),
                    "retry_count": log.retry_count,
                    "violation_codes": log.violation_codes,
                    "trace_id": log.trace_id,
                    "trace_url": trace_url,
                    "is_synthetic_log": log.is_synthetic_log,
                }
            )

        csv_buffer = io.StringIO()
        if logs_data:
            writer = csv.DictWriter(csv_buffer, fieldnames=list(logs_data[0].keys()))
            writer.writeheader()
            writer.writerows(logs_data)
        csv_string = csv_buffer.getvalue()

        return {
            "kpis": kpis,
            "charts": charts,
            "logs": logs_data,
            "csv_data": csv_string,
        }

    if session is not None:
        return _execute(session)
    with get_session() as sess:
        return _execute(sess)
