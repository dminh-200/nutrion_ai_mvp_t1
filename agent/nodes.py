"""Các node xử lý trong LangGraph (đủ 11 node theo SPEC mục 9.1–9.2 và 3.2)."""

import json
from typing import Annotated, Any, Literal
from uuid import uuid4

from langgraph.types import interrupt
from pydantic import BaseModel, BeforeValidator, ConfigDict, field_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from agent.llm import (
    call_explain_llm,
    call_planner_llm,
    get_llm_error_types,
    resolve_active_model_name,
)
from agent.state import AgentState
from agent.tools_gateway import ToolsGateway
from agent.verifier import verify_meal_plan
from config.settings import get_settings
from core.nutrition import load_rules
from core.portion import adjust_portions
from core.schemas import (
    DayPlan,
    GuidelineSnippet,
    Meal,
    MealPlanLLM,
    PatientProfile,
    PlannedItem,
)
from db.init_db import ALLERGENS, CONDITIONS
from db.models import (
    Allergen,
    Condition,
    HealthProfile,
    MealPlan,
    MealPlanItem,
    Patient,
    ProfileAllergen,
    ProfileCondition,
)
from db.repo import (
    create_meal_plan,
    create_review,
    get_meal_plan_by_thread,
    update_meal_plan_status,
)
from db.session import get_engine
from guardrails.input import evaluate_input_guardrail, load_guardrails_config
from guardrails.output import evaluate_output_guardrail
from observability.querylog import estimate_cost_usd, upsert_query_log
from rag.retrieve import sanitize_guideline_snippets

DISCLAIMER_VI = f"\n\n---\n{str(load_guardrails_config()['disclaimer_vi']).strip()}"

NEED_QUERY_MAP: dict[str, tuple[str, str | None]] = {
    "kiem_soat_duong_huyet": ("dinh dưỡng kiểm soát đường huyết tiểu đường type 2", "t2d"),
    "giam_natri": ("dinh dưỡng giảm muối natri tăng huyết áp", "htn"),
    "han_che_purin": ("dinh dưỡng hạn chế purin bệnh gout", "gout"),
    "giam_can": ("dinh dưỡng giảm cân kiểm soát năng lượng béo phì", "obesity"),
    "duy_tri_can_bang": ("chế độ dinh dưỡng cân bằng hợp lý", None),
}


def _diversify_foods(candidates: list[dict[str, Any]], limit: int = 120) -> list[dict[str, Any]]:
    """Sắp xếp round-robin theo food_group để ưu tiên đa dạng nhóm thực phẩm."""
    by_group: dict[str, list[dict[str, Any]]] = {}
    for item in candidates:
        grp = str(item.get("food_group", "khac"))
        by_group.setdefault(grp, []).append(item)

    diversified: list[dict[str, Any]] = []
    groups = sorted(by_group.keys())
    idx = 0
    while len(diversified) < limit:
        added = False
        for grp in groups:
            if idx < len(by_group[grp]):
                diversified.append(by_group[grp][idx])
                added = True
                if len(diversified) >= limit:
                    break
        if not added:
            break
        idx += 1
    return diversified


def _health_profile_matches(
    session: Session, hp: HealthProfile, profile: PatientProfile
) -> bool:
    """Kiểm tra bản ghi HealthProfile hiện có trùng khớp chỉ số, bệnh và dị ứng hay không."""
    scalar_match = (
        hp.age == profile.age
        and hp.sex == profile.sex
        and abs(hp.height_cm - profile.height_cm) < 1e-6
        and abs(hp.weight_kg - profile.weight_kg) < 1e-6
        and hp.activity_level == profile.activity_level
        and hp.pregnancy == profile.pregnancy
        and hp.lactating == profile.lactating
        and hp.ckd_stage == profile.ckd_stage
        and hp.dialysis == profile.dialysis
        and hp.eating_disorder == profile.eating_disorder
        and hp.preferences_text == profile.preferences_text
        and hp.days == profile.days
    )
    if not scalar_match:
        return False

    db_conditions = set(
        session.scalars(
            select(Condition.code)
            .join(ProfileCondition, Condition.id == ProfileCondition.condition_id)
            .where(ProfileCondition.profile_id == hp.id)
        ).all()
    )
    if db_conditions != set(profile.conditions):
        return False

    db_allergens = set(
        session.scalars(
            select(Allergen.code)
            .join(ProfileAllergen, Allergen.id == ProfileAllergen.allergen_id)
            .where(ProfileAllergen.profile_id == hp.id)
        ).all()
    )
    return db_allergens == set(profile.allergens)


def _get_or_create_health_profile(session: Session, profile: PatientProfile) -> HealthProfile:
    """Tìm hoặc tạo mới Patient + HealthProfile (kèm bệnh, dị ứng) khi chỉ số hồ sơ thay đổi."""
    patient = session.scalar(select(Patient).where(Patient.code == profile.patient_code))
    if patient is None:
        patient = Patient(
            code=profile.patient_code,
            display_name=f"Bệnh nhân {profile.patient_code}",
            is_synthetic=True,
        )
        session.add(patient)
        session.flush()

    hp = session.scalar(
        select(HealthProfile)
        .where(HealthProfile.patient_id == patient.id)
        .order_by(HealthProfile.id.desc())
    )
    if hp is not None and _health_profile_matches(session, hp, profile):
        return hp

    new_hp = HealthProfile(
        patient_id=patient.id,
        age=profile.age,
        sex=profile.sex,
        height_cm=profile.height_cm,
        weight_kg=profile.weight_kg,
        activity_level=profile.activity_level,
        pregnancy=profile.pregnancy,
        lactating=profile.lactating,
        ckd_stage=profile.ckd_stage,
        dialysis=profile.dialysis,
        eating_disorder=profile.eating_disorder,
        preferences_text=profile.preferences_text,
        days=profile.days,
    )
    session.add(new_hp)
    session.flush()

    cond_defaults = dict(CONDITIONS)
    cond_map = {c.code: c.id for c in session.scalars(select(Condition)).all()}
    for c_code in dict.fromkeys(profile.conditions):
        if c_code not in cond_map:
            row = Condition(code=c_code, name_vi=cond_defaults.get(c_code, c_code))
            session.add(row)
            session.flush()
            cond_map[c_code] = row.id
        session.add(ProfileCondition(profile_id=new_hp.id, condition_id=cond_map[c_code]))

    alg_defaults = dict(ALLERGENS)
    alg_map = {a.code: a.id for a in session.scalars(select(Allergen)).all()}
    for a_code in dict.fromkeys(profile.allergens):
        if a_code not in alg_map:
            row_a = Allergen(code=a_code, name_vi=alg_defaults.get(a_code, a_code))
            session.add(row_a)
            session.flush()
            alg_map[a_code] = row_a.id
        session.add(ProfileAllergen(profile_id=new_hp.id, allergen_id=alg_map[a_code]))

    session.flush()
    return new_hp


def _save_plan_items(
    session: Session,
    meal_plan_id: int,
    plan_llm: MealPlanLLM,
    gateway: ToolsGateway,
) -> None:
    """Tính dinh dưỡng qua gateway.score_menu và lưu danh sách MealPlanItem."""
    session.execute(delete(MealPlanItem).where(MealPlanItem.meal_plan_id == meal_plan_id))
    scored = gateway.score_menu(plan_llm)
    item_idx = 0
    for day_plan in plan_llm.days:
        for meal in day_plan.meals:
            for _ in meal.items:
                s_item = scored["items"][item_idx]
                item_idx += 1
                session.add(
                    MealPlanItem(
                        meal_plan_id=meal_plan_id,
                        day=day_plan.day,
                        meal=meal.meal,
                        food_id=s_item.food_id,
                        grams=s_item.grams,
                        kcal=s_item.kcal,
                        protein_g=s_item.protein_g,
                        fat_g=s_item.fat_g,
                        carb_g=s_item.carb_g,
                        sodium_mg=s_item.sodium_mg,
                    )
                )


def _persist_meal_plan(
    state: AgentState,
    gateway: ToolsGateway,
    *,
    status_override: str | None = None,
    save_items: bool = True,
) -> int:
    """Lưu hoặc cập nhật MealPlan (kèm MealPlanItem nếu có) vào SQLite, trả về meal_plan_id."""
    profile = state["profile"]
    thread_id = state["thread_id"]
    status = status_override or state.get("status", "draft")
    targets = state.get("targets")
    needs = state.get("needs")
    risk = state.get("risk")
    snippets = state.get("snippets") or []
    explanation_md = state.get("explanation_md", "")
    retry_count = int(state.get("retry_count", 0))
    violations = state.get("violations", [])
    risk_json = risk.model_dump_json() if risk else "{}"
    snippets_json = json.dumps(
        [s.model_dump() if hasattr(s, "model_dump") else dict(s) for s in snippets],
        ensure_ascii=False,
    )
    violations_json = json.dumps(
        [v.model_dump() if hasattr(v, "model_dump") else dict(v) for v in violations],
        ensure_ascii=False,
    )
    passed_first_try = retry_count == 0 and not violations and status in (
        "pending_review",
        "approved",
    )

    engine = get_engine()
    with Session(engine) as session:
        existing: MealPlan | None = get_meal_plan_by_thread(session, thread_id)
        if existing is not None:
            existing_hp = session.get(HealthProfile, existing.profile_id)
            existing_patient = (
                session.get(Patient, existing_hp.patient_id)
                if existing_hp is not None
                else None
            )
            if (
                existing_hp is None
                or existing_patient is None
                or existing_patient.code != profile.patient_code
            ):
                raise ValueError(
                    f"thread_id={thread_id!r} đã thuộc về hồ sơ khác "
                    f"(meal_plan_id={existing.id}), từ chối ghi đè."
                )
            if existing.status != "pending_review":
                raise ValueError(
                    f"thread_id={thread_id!r} (meal_plan_id={existing.id}) đã ở trạng thái "
                    f"{existing.status!r}, không thể ghi đè."
                )
            if _health_profile_matches(session, existing_hp, profile):
                hp = existing_hp
            else:
                raise ValueError(
                    f"thread_id={thread_id!r} (meal_plan_id={existing.id}) không khớp hồ sơ "
                    "đã lưu trước đó, từ chối ghi đè."
                )
            plan_row = update_meal_plan_status(
                session,
                existing.id,
                status=status,
                explanation_md=explanation_md,
                retry_count=retry_count,
                verifier_passed_first_try=passed_first_try,
                risk_json=risk_json,
                snippets_json=snippets_json,
                violations_json=violations_json,
            )
            assert plan_row is not None
            plan_llm = state.get("plan_llm")
            if save_items and plan_llm is not None and not plan_llm.cannot_plan and plan_llm.days:
                _save_plan_items(session, plan_row.id, plan_llm, gateway)
        else:
            hp = _get_or_create_health_profile(session, profile)
            plan_row = create_meal_plan(
                session,
                profile_id=hp.id,
                thread_id=thread_id,
                status=status,
                targets_json=targets.model_dump_json() if targets else "{}",
                needs_json=needs.model_dump_json() if needs else "{}",
                risk_json=risk_json,
                snippets_json=snippets_json,
                violations_json=violations_json,
                explanation_md=explanation_md,
                retry_count=retry_count,
                verifier_passed_first_try=passed_first_try,
            )
            plan_llm = state.get("plan_llm")
            if save_items and plan_llm is not None and not plan_llm.cannot_plan and plan_llm.days:
                _save_plan_items(session, plan_row.id, plan_llm, gateway)

        session.commit()
        return int(plan_row.id)


def _apply_edited_items(
    plan: MealPlanLLM,
    edited_items: list[dict[str, Any]],
) -> MealPlanLLM:
    """Áp dụng danh sách chỉnh sửa (grams hoặc xóa món) của chuyên gia lên MealPlanLLM."""
    if not edited_items:
        return plan.model_copy(deep=True)

    # Nếu edited_items có đầy đủ cấu trúc day + meal + food_id: thay thế toàn bộ danh sách món
    if all("day" in it and "meal" in it and "food_id" in it for it in edited_items):
        by_day_meal: dict[tuple[int, str], list[PlannedItem]] = {}
        extra_meals_by_day: dict[int, list[str]] = {}
        for it in edited_items:
            day_num = int(it["day"])
            meal_name = str(it["meal"])
            if meal_name not in extra_meals_by_day.setdefault(day_num, []):
                extra_meals_by_day[day_num].append(meal_name)
            grams = float(it.get("grams", 0.0))
            if grams <= 0:
                continue
            key = (day_num, meal_name)
            by_day_meal.setdefault(key, []).append(
                PlannedItem.model_construct(food_id=int(it["food_id"]), grams=grams)
            )

        existing_days = {dp.day: dp for dp in plan.days}
        ordered_days = [dp.day for dp in plan.days]
        for day_num in sorted(extra_meals_by_day):
            if day_num not in existing_days:
                ordered_days.append(day_num)

        new_days: list[DayPlan] = []
        for day_num in ordered_days:
            dp = existing_days.get(day_num)
            meal_names: list[str] = [m.meal for m in dp.meals] if dp else []
            for m_name in extra_meals_by_day.get(day_num, []):
                if m_name not in meal_names:
                    meal_names.append(m_name)
            new_meals = [
                Meal.model_construct(meal=m_name, items=by_day_meal.get((day_num, m_name), []))
                for m_name in meal_names
            ]
            new_days.append(DayPlan.model_construct(day=day_num, meals=new_meals))
        return MealPlanLLM.model_construct(days=new_days, cannot_plan=False, reason="")

    # Nếu edited_items chỉ truyền {food_id, grams} để cập nhật khối lượng món tương ứng
    overrides = {int(it["food_id"]): float(it["grams"]) for it in edited_items if "food_id" in it}
    updated = plan.model_copy(deep=True)
    for day_plan in updated.days:
        for meal in day_plan.meals:
            kept_items: list[PlannedItem] = []
            for item in meal.items:
                if item.food_id in overrides:
                    new_g = overrides[item.food_id]
                    if new_g > 0:
                        kept_items.append(
                            PlannedItem.model_construct(food_id=item.food_id, grams=new_g)
                        )
                else:
                    kept_items.append(item)
            meal.items = kept_items
    return updated


def _accumulate_llm_metrics(
    metrics_in: dict[str, Any] | None,
    *,
    model_name: str,
    usage: dict[str, int],
) -> dict[str, Any]:
    """Cộng dồn số lần gọi LLM, token tổng và token chi tiết theo từng model."""
    metrics = dict(metrics_in or {})
    metrics["llm_calls"] = int(metrics.get("llm_calls", 0)) + 1
    metrics["tokens_in"] = int(metrics.get("tokens_in", 0)) + int(usage.get("tokens_in", 0))
    metrics["tokens_out"] = int(metrics.get("tokens_out", 0)) + int(usage.get("tokens_out", 0))

    raw_mu = dict(metrics.get("model_usage") or {})
    cur = dict(raw_mu.get(model_name) or {})
    cur["calls"] = int(cur.get("calls", 0)) + 1
    cur["tokens_in"] = int(cur.get("tokens_in", 0)) + int(usage.get("tokens_in", 0))
    cur["tokens_out"] = int(cur.get("tokens_out", 0)) + int(usage.get("tokens_out", 0))
    raw_mu[model_name] = cur
    metrics["model_usage"] = raw_mu
    return metrics


# ==============================================================================
# 11 NODE THEO SPEC MỤC 9.1
# ==============================================================================


def intake(state: AgentState) -> dict[str, Any]:
    """Node 1 (intake): Chuẩn hóa hồ sơ, tạo session_id, thread_id, bắt đầu trace."""
    raw_profile = state["profile"]
    profile = (
        raw_profile
        if isinstance(raw_profile, PatientProfile)
        else PatientProfile.model_validate(raw_profile)
    )
    session_id = state.get("session_id") or f"sess-{uuid4().hex[:12]}"
    thread_id = state.get("thread_id") or f"thread-{uuid4().hex[:12]}"
    trace_id = state.get("trace_id") or ""
    metrics = dict(state.get("metrics") or {})
    metrics.setdefault("llm_calls", 0)
    metrics.setdefault("tokens_in", 0)
    metrics.setdefault("tokens_out", 0)
    metrics.setdefault("latency_ms", 0.0)
    metrics.setdefault("model_usage", {})
    trace_notes = list(state.get("trace_notes") or [])
    trace_notes.append(f"intake: nhận hồ sơ {profile.patient_code}")

    return {
        "profile": profile,
        "session_id": session_id,
        "thread_id": thread_id,
        "trace_id": trace_id,
        "retry_count": int(state.get("retry_count", 0)),
        "input_flags": list(state.get("input_flags") or []),
        "output_flags": list(state.get("output_flags") or []),
        "violations": list(state.get("violations") or []),
        "snippets": list(state.get("snippets") or []),
        "allowed_foods": list(state.get("allowed_foods") or []),
        "explanation_md": state.get("explanation_md", ""),
        "metrics": metrics,
        "trace_notes": trace_notes,
        "status": "draft",
    }


def input_guardrail(state: AgentState) -> dict[str, Any]:
    """Node 2 (input_guardrail): Kiểm tra hợp lệ, nguy cơ cao, injection, đòi thuốc, lạc đề."""
    profile = state["profile"]
    session_id = str(state.get("session_id", ""))
    flags = list(state.get("input_flags") or [])
    trace_notes = list(state.get("trace_notes") or [])

    result = evaluate_input_guardrail(
        profile,
        session_id=session_id,
        existing_flags=flags,
        log_events=bool(session_id),
    )

    if result.action == "redirect_to_doctor":
        reasons_txt = ",".join(result.risk.reasons) if result.risk else "RISK_TEXT"
        trace_notes.append(f"input_guardrail: chuyển hướng bác sĩ ({reasons_txt})")
        return {
            "risk": result.risk,
            "input_flags": result.flags,
            "status": "redirect_to_doctor",
            "explanation_md": result.blocked_message_vi,
            "trace_notes": trace_notes,
        }

    if result.action == "blocked":
        trace_notes.append(
            f"input_guardrail: chặn yêu cầu ({','.join(result.flags) or 'blocked'})"
        )
        return {
            "risk": result.risk,
            "input_flags": result.flags,
            "status": "blocked",
            "explanation_md": result.blocked_message_vi,
            "trace_notes": trace_notes,
        }

    if result.action == "needs_human_review":
        trace_notes.append(
            f"input_guardrail: chuyển chuyên gia xem xét ({','.join(result.flags) or 'ambiguous'})"
        )
        return {
            "risk": result.risk,
            "input_flags": result.flags,
            "status": "needs_human_review",
            "explanation_md": result.blocked_message_vi,
            "trace_notes": trace_notes,
        }

    out: dict[str, Any] = {
        "risk": result.risk,
        "input_flags": result.flags,
        "status": "draft",
        "trace_notes": trace_notes,
    }
    if result.profile is not None:
        out["profile"] = result.profile
    if result.events:
        ev_names = ",".join(ev_type for ev_type, _ in result.events)
        trace_notes.append(f"input_guardrail: lọc/cảnh báo [{ev_names}]")
    else:
        trace_notes.append("input_guardrail: hồ sơ hợp lệ")
    return out


def classify(state: AgentState, gateway: ToolsGateway) -> dict[str, Any]:
    """Node 3 (classify): Tính mục tiêu và nhu cầu dinh dưỡng qua tool calc_targets."""
    profile = state["profile"]
    res = gateway.calc_targets(profile)
    targets = res["targets"]
    needs = res["needs"]
    trace_notes = list(state.get("trace_notes") or [])
    trace_notes.append(
        f"classify: target_kcal={targets.target_kcal:.0f}, needs={','.join(needs.needs)}"
    )
    return {
        "targets": targets,
        "needs": needs,
        "trace_notes": trace_notes,
    }


def retrieve(state: AgentState, gateway: ToolsGateway) -> dict[str, Any]:
    """Node 4 (retrieve): Truy vấn hướng dẫn theo từng nhu cầu, gộp, khử trùng, tối đa 8 đoạn."""
    needs = state.get("needs")
    need_list = needs.needs if needs and needs.needs else ["duy_tri_can_bang"]

    merged: list[GuidelineSnippet] = []
    seen_keys: set[tuple[str, str, str]] = set()

    for need_name in need_list:
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

    sanitized = sanitize_guideline_snippets(merged)[:8]
    trace_notes = list(state.get("trace_notes") or [])
    if sanitized:
        trace_notes.append(f"retrieve: truy xuất {len(sanitized)} đoạn hướng dẫn")
    else:
        trace_notes.append("retrieve: không tìm thấy đoạn tài liệu dinh dưỡng phù hợp")
    return {
        "snippets": sanitized,
        "trace_notes": trace_notes,
    }


def plan(state: AgentState, gateway: ToolsGateway) -> dict[str, Any]:
    """Node 5 (plan): Lấy danh sách món qua tool search_food và gọi LLM sinh thực đơn."""
    profile = state["profile"]
    targets = state["targets"]
    needs = state["needs"]
    assert targets is not None and needs is not None

    cfg = load_rules()
    exclude_tags: list[str] = ["nguyen_lieu_song"]
    max_purine_level: str | None = None
    for need_name in needs.needs:
        need_cfg = cfg["needs"].get(need_name, {})
        exclude_tags.extend(need_cfg.get("avoid_tags", []))
        if "max_purine_level" in need_cfg:
            max_purine_level = str(need_cfg["max_purine_level"])

    candidates = gateway.search_food(
        query="",
        exclude_allergens=list(profile.allergens),
        exclude_tags=exclude_tags,
        max_purine_level=max_purine_level,
        limit=200,
    )
    allowed_foods = _diversify_foods(candidates, limit=120)

    prev_violations = state.get("violations") or []
    retry_count = int(state.get("retry_count", 0))
    if prev_violations:
        retry_count += 1

    fv_flag = state.get("mock_force_violation", False)
    if fv_flag == "always":
        force_violation = True
    elif fv_flag in (True, "once"):
        force_violation = retry_count == 0
    else:
        force_violation = False

    error_notice = ""
    try:
        plan_llm, usage = call_planner_llm(
            days=profile.days,
            allowed_foods=allowed_foods,
            targets=targets,
            profile=profile,
            needs=needs,
            violations=prev_violations,
            force_violation=force_violation,
        )
    except get_llm_error_types() as exc:
        error_notice = str(exc)
        plan_llm = MealPlanLLM(days=[], cannot_plan=True, reason=error_notice)
        usage = {"tokens_in": 0, "tokens_out": 0}

    metrics = _accumulate_llm_metrics(
        state.get("metrics"),
        model_name=resolve_active_model_name("planner", settings=get_settings()),
        usage=usage,
    )

    trace_notes = list(state.get("trace_notes") or [])
    trace_notes.append(
        f"plan: lập thực đơn (retry={retry_count}, cannot_plan={plan_llm.cannot_plan})"
    )

    out: dict[str, Any] = {
        "allowed_foods": allowed_foods,
        "plan_llm": plan_llm,
        "retry_count": retry_count,
        "metrics": metrics,
        "trace_notes": trace_notes,
    }
    if plan_llm.cannot_plan:
        out["status"] = "needs_human_review"
        if error_notice:
            out["explanation_md"] = f"**Thông báo cấu hình/mô hình:** {error_notice}{DISCLAIMER_VI}"
    return out


def portion_adjust(state: AgentState) -> dict[str, Any]:
    """Node 6 (portion_adjust): Cân chỉnh khẩu phần bằng code theo SPEC 6.5."""
    plan_llm = state.get("plan_llm")
    targets = state.get("targets")
    if plan_llm is None or plan_llm.cannot_plan or targets is None:
        return {}

    adjusted, notes = adjust_portions(plan_llm, targets)
    trace_notes = list(state.get("trace_notes") or []) + notes
    return {
        "plan_llm": adjusted,
        "trace_notes": trace_notes,
    }


def verify(state: AgentState, gateway: ToolsGateway) -> dict[str, Any]:
    """Node 7 (verify): Kiểm chứng thực đơn qua tool score_menu, check_allergen và verifier."""
    plan_llm = state.get("plan_llm")
    targets = state.get("targets")
    profile = state["profile"]
    retry_count = int(state.get("retry_count", 0))
    assert plan_llm is not None and targets is not None

    violations, daily_totals = verify_meal_plan(
        plan=plan_llm,
        profile=profile,
        targets=targets,
        gateway=gateway,
        needs=state.get("needs"),
        allowed_foods=state.get("allowed_foods"),
    )

    trace_notes = list(state.get("trace_notes") or [])
    if violations:
        codes = ",".join(v.code for v in violations)
        trace_notes.append(f"verify: phát hiện vi phạm [{codes}] ở retry={retry_count}")
    else:
        trace_notes.append(f"verify: đạt kiểm chứng ở retry={retry_count}")

    out: dict[str, Any] = {
        "plan_scored": daily_totals,
        "violations": violations,
        "retry_count": retry_count,
        "trace_notes": trace_notes,
    }
    if violations and retry_count >= 2:
        out["status"] = "needs_human_review"
    return out


def explain(state: AgentState) -> dict[str, Any]:
    """Node 8 (explain): Viết giải thích cho người bệnh có trích nguồn (model nhẹ ở chế độ real)."""
    targets = state.get("targets")
    needs = state.get("needs")
    raw_snippets = state.get("snippets") or []
    snippets = sanitize_guideline_snippets(raw_snippets)
    assert targets is not None and needs is not None

    food_name_map = {
        int(f["id"]): str(f.get("name_vi", ""))
        for f in (state.get("allowed_foods") or [])
        if "id" in f
    }

    trace_notes = list(state.get("trace_notes") or [])
    if len(snippets) < len(raw_snippets):
        trace_notes.append("explain: đã lọc nội dung thuốc/thư mục khỏi đoạn RAG")
    if not snippets:
        trace_notes.append("explain: không đủ tài liệu dinh dưỡng phù hợp để trích dẫn trực tiếp")

    try:
        text, usage = call_explain_llm(
            needs=needs,
            targets=targets,
            snippets=snippets,
            plan_scored=state.get("plan_scored"),
            plan_llm=state.get("plan_llm"),
            food_name_map=food_name_map,
        )
        trace_notes.append("explain: đã tạo giải thích thực đơn")
    except get_llm_error_types() as exc:
        text, usage = call_explain_llm(
            needs=needs,
            targets=targets,
            snippets=snippets,
            mode="mock",
        )
        text = f"{text}\n\n*Ghi chú: Đã dùng giải thích tóm tắt dự phòng ({exc}).*"
        trace_notes.append(f"explain: dùng tóm tắt dự phòng do lỗi LLM ({exc})")

    if not snippets and "không đủ tài liệu" not in text.lower():
        text = (
            f"{text}\n\n*Lưu ý tài liệu: Không đủ tài liệu hướng dẫn dinh dưỡng phù hợp "
            "để trích dẫn trực tiếp.*"
        ).strip()

    metrics = _accumulate_llm_metrics(
        state.get("metrics"),
        model_name=resolve_active_model_name("light", settings=get_settings()),
        usage=usage,
    )

    return {
        "explanation_md": text,
        "metrics": metrics,
        "trace_notes": trace_notes,
    }


def output_guardrail(state: AgentState, gateway: ToolsGateway | None = None) -> dict[str, Any]:
    """Node 9 (output_guardrail): Lọc từ cấm, trích nguồn, disclaimer, dị ứng và sàn kcal."""
    input_flags = state.get("input_flags") or []
    notice_vi = (
        "*Nhắc nhở an toàn: Hệ thống chỉ hỗ trợ xây dựng thực đơn dinh dưỡng, "
        "không chẩn đoán bệnh hay kê/chỉnh liều thuốc.*"
        if "medical_advice" in input_flags
        else ""
    )

    result = evaluate_output_guardrail(
        explanation_md=state.get("explanation_md", ""),
        snippets=state.get("snippets") or [],
        profile=state.get("profile"),
        targets=state.get("targets"),
        plan_llm=state.get("plan_llm"),
        plan_scored=state.get("plan_scored") or [],
        allowed_foods=state.get("allowed_foods") or [],
        violations=state.get("violations") or [],
        existing_output_flags=state.get("output_flags") or [],
        notice_vi=notice_vi,
        session_id=str(state.get("session_id", "")),
        gateway=gateway,
        log_events=bool(state.get("session_id")),
    )

    trace_notes = list(state.get("trace_notes") or [])
    trace_notes.append(f"output_guardrail: status={result.status}")
    return {
        "explanation_md": result.explanation_md,
        "output_flags": result.output_flags,
        "status": result.status,
        "trace_notes": trace_notes,
    }


VALID_REVIEW_DECISIONS: tuple[str, ...] = ("approve", "edit", "reject")


def validate_review_decision(raw_decision: Any) -> Literal["approve", "edit", "reject"]:
    """Xác thực quyết định duyệt của chuyên gia; chỉ chấp nhận approve, edit hoặc reject."""
    if not isinstance(raw_decision, str):
        raise ValueError(
            "Thiếu hoặc sai kiểu quyết định duyệt. Chỉ chấp nhận: approve, edit, reject."
        )
    cleaned = raw_decision.strip()
    if cleaned not in VALID_REVIEW_DECISIONS:
        raise ValueError(
            f"Quyết định duyệt không hợp lệ: {raw_decision!r}. "
            "Chỉ chấp nhận: approve, edit, reject."
        )
    return cleaned  # type: ignore[return-value]


def _coerce_review_resume_payload(value: Any) -> Any:
    """Chuẩn hóa dữ liệu resume thành dict có khóa decision trước khi Pydantic xác thực."""
    if isinstance(value, str):
        return {"decision": value}
    if isinstance(value, dict) and "decision" not in value:
        return {**value, "decision": None}
    return value


class ReviewResumePayload(BaseModel):
    """Schema xác thực phản hồi HITL ngay tại interrupt() để không lưu giá trị sai."""

    model_config = ConfigDict(extra="allow")

    decision: Literal["approve", "edit", "reject"]
    note: str = ""
    edited_items: list[dict[str, Any]] | None = None

    @field_validator("decision", mode="before")
    @classmethod
    def _validate_decision(cls, value: Any) -> str:
        return validate_review_decision(value)

    @field_validator("edited_items", mode="before")
    @classmethod
    def _validate_edited_items(cls, value: Any) -> Any:
        if value is not None and not isinstance(value, list):
            raise ValueError("Trường edited_items phải là danh sách khi decision='edit'.")
        return value


ReviewResumeInput = Annotated[
    ReviewResumePayload,
    BeforeValidator(_coerce_review_resume_payload),
]


def await_review(state: AgentState, gateway: ToolsGateway) -> dict[str, Any]:
    """Node 10 (await_review): Lưu meal_plan status=pending_review rồi gọi interrupt() chờ duyệt."""
    meal_plan_id = _persist_meal_plan(
        state,
        gateway,
        status_override="pending_review",
        save_items=True,
    )

    payload = {
        "thread_id": state.get("thread_id", ""),
        "meal_plan_id": meal_plan_id,
        "status": "pending_review",
        "plan_scored": state.get("plan_scored") or [],
        "violations": [v.model_dump() for v in state.get("violations") or []],
        "explanation_md": state.get("explanation_md", ""),
    }

    decision_data = interrupt(payload, response_schema=ReviewResumeInput)
    if isinstance(decision_data, ReviewResumePayload):
        review_dict = decision_data.model_dump()
    elif isinstance(decision_data, dict):
        review_dict = dict(decision_data)
    elif isinstance(decision_data, str):
        review_dict = {"decision": decision_data}
    else:
        raise ValueError(
            "Dữ liệu phản hồi duyệt phải là dict hoặc chuỗi hợp lệ (approve, edit, reject)."
        )

    decision = validate_review_decision(review_dict.get("decision"))
    review_dict["decision"] = decision
    trace_notes = list(state.get("trace_notes") or [])

    plan_llm = state.get("plan_llm")
    targets = state.get("targets")
    profile = state["profile"]
    updated_scored = state.get("plan_scored")
    updated_violations = list(state.get("violations") or [])

    if decision == "reject":
        new_status = "rejected"
        trace_notes.append("await_review: chuyên gia từ chối thực đơn")
    elif decision == "edit":
        raw_edited = review_dict.get("edited_items")
        if raw_edited is not None and not isinstance(raw_edited, list):
            raise ValueError("Trường edited_items phải là danh sách khi decision='edit'.")
        if raw_edited is not None and len(raw_edited) == 0:
            new_status = "needs_human_review"
            trace_notes.append("await_review: danh sách món sau sửa rỗng -> needs_human_review")
        else:
            edited_items = list(raw_edited or [])
            if plan_llm is not None and targets is not None:
                plan_llm = _apply_edited_items(plan_llm, edited_items)
                has_positive_items = any(
                    it.grams > 0 for d in plan_llm.days for m in d.meals for it in m.items
                )
                updated_violations, updated_scored = verify_meal_plan(
                    plan=plan_llm,
                    profile=profile,
                    targets=targets,
                    gateway=gateway,
                    needs=state.get("needs"),
                    allowed_foods=state.get("allowed_foods"),
                )
                if updated_violations or not has_positive_items:
                    new_status = "needs_human_review"
                    trace_notes.append(
                        "await_review: bản sửa của chuyên gia rỗng hoặc còn vi phạm verifier"
                    )
                else:
                    new_status = "approved"
                    trace_notes.append("await_review: chuyên gia sửa và đạt verifier -> approved")
            else:
                new_status = "needs_human_review"
                trace_notes.append(
                    "await_review: thiếu thực đơn/mục tiêu để kiểm chứng bản sửa -> "
                    "needs_human_review"
                )
    elif decision == "approve":
        new_status = "approved"
        trace_notes.append("await_review: chuyên gia duyệt -> approved")
    else:  # pragma: no cover - phòng thủ bổ sung
        raise ValueError(f"Quyết định duyệt không hợp lệ: {decision!r}.")

    return {
        "review": review_dict,
        "status": new_status,
        "plan_llm": plan_llm,
        "plan_scored": updated_scored,
        "violations": updated_violations,
        "meal_plan_id": meal_plan_id,
        "trace_notes": trace_notes,
    }


def finalize(state: AgentState, gateway: ToolsGateway) -> dict[str, Any]:
    """Node 11 (finalize): Ghi trạng thái cuối, MealPlan/MealPlanItem, Review và QueryLog."""
    final_status = state.get("status") or "needs_human_review"
    explanation_md = state.get("explanation_md", "")
    if final_status == "needs_human_review" and not explanation_md:
        explanation_md = (
            "Hệ thống chưa thể tự động hoàn tất thực đơn đạt mọi ngưỡng kiểm chứng. "
            f"Hồ sơ đã được chuyển cho chuyên gia dinh dưỡng xem xét.{DISCLAIMER_VI}"
        )

    # Theo SPEC 3.2: khi hết lượt sửa, redirect_to_doctor hoặc blocked thì không lưu thực đơn
    save_items = final_status in ("approved", "pending_review")
    updated_state = dict(state)
    updated_state["explanation_md"] = explanation_md

    meal_plan_id = _persist_meal_plan(
        updated_state,  # type: ignore[arg-type]
        gateway,
        status_override=final_status,
        save_items=save_items,
    )

    review = state.get("review")
    metrics = state.get("metrics") or {}
    violations = state.get("violations") or []
    profile = state["profile"]
    trace_id = str(state.get("trace_id", ""))
    recorded_cost, _ = estimate_cost_usd(
        tokens_in=int(metrics.get("tokens_in", 0)),
        tokens_out=int(metrics.get("tokens_out", 0)),
        model_usage=metrics.get("model_usage"),
    )

    engine = get_engine()
    with Session(engine) as session:
        if review:
            create_review(
                session,
                meal_plan_id=meal_plan_id,
                reviewer_name=str(review.get("reviewer_name", "Chuyên gia dinh dưỡng")),
                decision=str(review.get("decision", "")),
                note=str(review.get("note", "")),
                edited_items_json=json.dumps(
                    review.get("edited_items") or [], ensure_ascii=False
                ),
            )

        upsert_query_log(
            session_id=state.get("session_id", "sess-default"),
            patient_code=profile.patient_code,
            status=final_status,
            meal_plan_id=meal_plan_id,
            latency_ms=float(metrics.get("latency_ms", 0.0)),
            llm_calls=int(metrics.get("llm_calls", 0)),
            tokens_in=int(metrics.get("tokens_in", 0)),
            tokens_out=int(metrics.get("tokens_out", 0)),
            est_cost_usd=recorded_cost,
            retry_count=int(state.get("retry_count", 0)),
            violation_codes=",".join(v.code for v in violations),
            trace_id=trace_id,
            model_usage=metrics.get("model_usage"),
            session=session,
        )
        session.commit()

    trace_notes = list(state.get("trace_notes") or [])
    trace_notes.append(f"finalize: hoàn tất với status={final_status}, meal_plan_id={meal_plan_id}")
    return {
        "status": final_status,
        "meal_plan_id": meal_plan_id,
        "explanation_md": explanation_md,
        "trace_notes": trace_notes,
    }
