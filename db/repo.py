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
    FoodNutrient,
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

        guardrail_events = sess.scalars(
            select(GuardrailEvent)
            .where(GuardrailEvent.session_id == plan.thread_id)
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

        days_list: list[DayPlan] = []
        for d in range(1, prof.days + 1):
            meals_list: list[Meal] = []
            for m in ("breakfast", "lunch", "dinner", "snack"):
                items_in_m = by_day_meal.get((d, m), [])
                if items_in_m:
                    meals_list.append(Meal(meal=m, items=items_in_m))  # type: ignore[arg-type]
            days_list.append(DayPlan(day=d, meals=meals_list))

        base_plan = MealPlanLLM(days=days_list, cannot_plan=False, reason="")
        new_plan = _apply_edited_items(base_plan, edited_items)

        food_db = load_food_db_from_sqlite()
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

        return {
            "is_valid": len(violations) == 0,
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

        new_status = "approved" if decision_clean in ("approve", "edit") else "rejected"
        plan.status = new_status

        if decision_clean == "edit" and edited_items:
            sess.execute(delete(MealPlanItem).where(MealPlanItem.meal_plan_id == meal_plan_id))
            sess.flush()

            food_ids = [
                int(it["food_id"])
                for it in edited_items
                if "food_id" in it and float(it.get("grams", 0)) > 0
            ]
            nutrients = (
                sess.scalars(select(FoodNutrient).where(FoodNutrient.food_id.in_(food_ids))).all()
                if food_ids
                else []
            )
            nutr_map = {n.food_id: n for n in nutrients}

            for it in edited_items:
                g = float(it.get("grams", 0.0))
                if g <= 0:
                    continue
                fid = int(it["food_id"])
                n = nutr_map.get(fid)
                factor = g / 100.0
                kcal = (n.kcal * factor) if n else 0.0
                protein_g = (n.protein_g * factor) if n else 0.0
                fat_g = (n.fat_g * factor) if n else 0.0
                carb_g = (n.carb_g * factor) if n else 0.0
                sodium_mg = (n.sodium_mg * factor) if n else 0.0

                sess.add(
                    MealPlanItem(
                        meal_plan_id=meal_plan_id,
                        day=int(it.get("day", 1)),
                        meal=str(it.get("meal", "breakfast")),
                        food_id=fid,
                        grams=g,
                        kcal=kcal,
                        protein_g=protein_g,
                        fat_g=fat_g,
                        carb_g=carb_g,
                        sodium_mg=sodium_mg,
                    )
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

        if start_date is not None:
            if isinstance(start_date, date) and not isinstance(start_date, datetime):
                dt_start = datetime.combine(start_date, time.min)
            else:
                dt_start = start_date
            stmt = stmt.where(QueryLog.created_at >= dt_start)

        if end_date is not None:
            if isinstance(end_date, date) and not isinstance(end_date, datetime):
                dt_end = datetime.combine(end_date, time.max)
            else:
                dt_end = end_date
            stmt = stmt.where(QueryLog.created_at <= dt_end)

        all_logs = list(sess.scalars(stmt.order_by(QueryLog.created_at.desc())).all())

        if condition:
            cond_clean = condition.strip().lower()
            matched_patient_codes = set(
                sess.scalars(
                    select(Patient.code)
                    .join(HealthProfile, Patient.id == HealthProfile.patient_id)
                    .join(ProfileCondition, HealthProfile.id == ProfileCondition.profile_id)
                    .join(Condition, ProfileCondition.condition_id == Condition.id)
                    .where(Condition.code == cond_clean)
                ).all()
            )
            all_logs = [log for log in all_logs if log.patient_code in matched_patient_codes]

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
        guardrail_events = []
        if sess_ids:
            guardrail_events = list(
                sess.scalars(
                    select(GuardrailEvent).where(GuardrailEvent.session_id.in_(sess_ids))
                ).all()
            )
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
        p_rows = sess.execute(
            select(Patient.code, Condition.code)
            .join(HealthProfile, Patient.id == HealthProfile.patient_id)
            .join(ProfileCondition, HealthProfile.id == ProfileCondition.profile_id)
            .join(Condition, ProfileCondition.condition_id == Condition.id)
        ).all()
        p_cond_map: dict[str, list[str]] = {}
        for pcode, ccode in p_rows:
            p_cond_map.setdefault(pcode, []).append(ccode)

        for log in all_logs:
            p_conds = p_cond_map.get(log.patient_code, [])
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
