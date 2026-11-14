"""Các node xử lý trong LangGraph (đủ 11 node theo SPEC mục 9.1–9.2 và 3.2)."""

import json
from typing import Any
from uuid import uuid4

import httpx
from google.genai import errors as genai_errors
from langgraph.types import interrupt
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from unidecode import unidecode

from agent.llm import LLMConfigError, call_explain_llm, call_planner_llm
from agent.state import AgentState
from agent.tools_gateway import ToolsGateway
from agent.verifier import verify_meal_plan
from core.classify import assess_risk
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
    create_query_log,
    create_review,
    get_meal_plan_by_thread,
    update_meal_plan_status,
)
from db.session import get_engine

DISCLAIMER_VI = (
    "\n\n---\n*Lưu ý: Thực đơn chỉ mang tính tham khảo hỗ trợ dinh dưỡng, "
    "không thay thế chẩn đoán hoặc chỉ định điều trị của bác sĩ.*"
)

INJECTION_PATTERNS = (
    "bo qua huong dan",
    "bo qua moi huong dan",
    "ignore previous",
    "ignore all instructions",
    "system prompt",
    "ban la admin",
    "tiet lo prompt",
    "jailbreak",
    "developer mode",
)

NEED_QUERY_MAP: dict[str, tuple[str, str | None]] = {
    "kiem_soat_duong_huyet": ("dinh dưỡng kiểm soát đường huyết tiểu đường type 2", "t2d"),
    "giam_natri": ("dinh dưỡng giảm muối natri tăng huyết áp", "htn"),
    "han_che_purin": ("dinh dưỡng hạn chế purin bệnh gout", "gout"),
    "giam_can": ("dinh dưỡng giảm cân kiểm soát năng lượng béo phì", "obesity"),
    "duy_tri_can_bang": ("chế độ dinh dưỡng cân bằng hợp lý", None),
}


def _detect_injection(text: str) -> bool:
    """Phát hiện mẫu prompt injection cơ bản trong văn bản người dùng."""
    if not text or not text.strip():
        return False
    norm = unidecode(text).lower()
    return any(pat in norm for pat in INJECTION_PATTERNS)


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
    explanation_md = state.get("explanation_md", "")
    retry_count = int(state.get("retry_count", 0))
    violations = state.get("violations", [])
    passed_first_try = retry_count == 0 and not violations and status in (
        "pending_review",
        "approved",
    )

    engine = get_engine()
    with Session(engine) as session:
        hp = _get_or_create_health_profile(session, profile)
        existing: MealPlan | None = get_meal_plan_by_thread(session, thread_id)
        if existing is None:
            plan_row = create_meal_plan(
                session,
                profile_id=hp.id,
                thread_id=thread_id,
                status=status,
                targets_json=targets.model_dump_json() if targets else "{}",
                needs_json=needs.model_dump_json() if needs else "{}",
                explanation_md=explanation_md,
                retry_count=retry_count,
                verifier_passed_first_try=passed_first_try,
            )
            plan_llm = state.get("plan_llm")
            if save_items and plan_llm is not None and not plan_llm.cannot_plan and plan_llm.days:
                _save_plan_items(session, plan_row.id, plan_llm, gateway)
        else:
            plan_row = update_meal_plan_status(
                session,
                existing.id,
                status=status,
                explanation_md=explanation_md,
                retry_count=retry_count,
                verifier_passed_first_try=passed_first_try,
            )
            assert plan_row is not None
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

    # Nếu edited_items có đầy đủ cấu trúc day + meal + food_id + grams
    if all("day" in it and "meal" in it and "food_id" in it for it in edited_items):
        by_day_meal: dict[tuple[int, str], list[PlannedItem]] = {}
        for it in edited_items:
            grams = float(it.get("grams", 0.0))
            if grams <= 0:
                continue
            key = (int(it["day"]), str(it["meal"]))
            by_day_meal.setdefault(key, []).append(
                PlannedItem.model_construct(food_id=int(it["food_id"]), grams=grams)
            )

        new_days: list[DayPlan] = []
        for day_plan in plan.days:
            new_meals: list[Meal] = []
            for meal in day_plan.meals:
                key = (day_plan.day, meal.meal)
                if key in by_day_meal:
                    new_meals.append(
                        Meal.model_construct(meal=meal.meal, items=by_day_meal[key])
                    )
                else:
                    new_meals.append(meal.model_copy(deep=True))
            new_days.append(DayPlan.model_construct(day=day_plan.day, meals=new_meals))
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
    metrics = dict(state.get("metrics") or {})
    metrics.setdefault("llm_calls", 0)
    metrics.setdefault("tokens_in", 0)
    metrics.setdefault("tokens_out", 0)
    metrics.setdefault("latency_ms", 0.0)
    trace_notes = list(state.get("trace_notes") or [])
    trace_notes.append(f"intake: nhận hồ sơ {profile.patient_code}")

    return {
        "profile": profile,
        "session_id": session_id,
        "thread_id": thread_id,
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
    """Node 2 (input_guardrail): Kiểm tra hợp lệ, luật nguy cơ cao, chống prompt injection."""
    profile = state["profile"]
    risk = assess_risk(profile)
    flags = list(state.get("input_flags") or [])
    trace_notes = list(state.get("trace_notes") or [])

    if risk.high_risk:
        for r_code in risk.reasons:
            if r_code not in flags:
                flags.append(r_code)
        trace_notes.append(f"input_guardrail: chuyển hướng bác sĩ ({','.join(risk.reasons)})")
        return {
            "risk": risk,
            "input_flags": flags,
            "status": "redirect_to_doctor",
            "explanation_md": (
                f"**Khuyến nghị thăm khám trực tiếp:** {risk.message_vi}{DISCLAIMER_VI}"
            ),
            "trace_notes": trace_notes,
        }

    if "injection" in flags or _detect_injection(profile.preferences_text):
        if "injection" not in flags:
            flags.append("injection")
        trace_notes.append("input_guardrail: chặn yêu cầu do phát hiện prompt injection")
        return {
            "risk": risk,
            "input_flags": flags,
            "status": "blocked",
            "explanation_md": (
                "**Yêu cầu bị từ chối:** Phát hiện nội dung không hợp lệ hoặc cố tình "
                f"vượt qua quy tắc an toàn.{DISCLAIMER_VI}"
            ),
            "trace_notes": trace_notes,
        }

    trace_notes.append("input_guardrail: hồ sơ hợp lệ")
    return {
        "risk": risk,
        "input_flags": flags,
        "status": "draft",
        "trace_notes": trace_notes,
    }


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

    trace_notes = list(state.get("trace_notes") or [])
    trace_notes.append(f"retrieve: truy xuất {len(merged)} đoạn hướng dẫn")
    return {
        "snippets": merged[:8],
        "trace_notes": trace_notes,
    }


def plan(state: AgentState, gateway: ToolsGateway) -> dict[str, Any]:
    """Node 5 (plan): Lấy danh sách món qua tool search_food và gọi LLM sinh thực đơn."""
    profile = state["profile"]
    targets = state["targets"]
    needs = state["needs"]
    assert targets is not None and needs is not None

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
    except (
        LLMConfigError,
        genai_errors.APIError,
        TimeoutError,
        ConnectionError,
        httpx.HTTPError,
    ) as exc:
        error_notice = str(exc)
        plan_llm = MealPlanLLM(days=[], cannot_plan=True, reason=error_notice)
        usage = {"tokens_in": 0, "tokens_out": 0}

    metrics = dict(state.get("metrics") or {})
    metrics["llm_calls"] = int(metrics.get("llm_calls", 0)) + 1
    metrics["tokens_in"] = int(metrics.get("tokens_in", 0)) + usage["tokens_in"]
    metrics["tokens_out"] = int(metrics.get("tokens_out", 0)) + usage["tokens_out"]

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
    snippets = state.get("snippets") or []
    assert targets is not None and needs is not None

    food_name_map = {
        int(f["id"]): str(f.get("name_vi", ""))
        for f in (state.get("allowed_foods") or [])
        if "id" in f
    }

    trace_notes = list(state.get("trace_notes") or [])
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
    except (
        LLMConfigError,
        genai_errors.APIError,
        TimeoutError,
        ConnectionError,
        httpx.HTTPError,
    ) as exc:
        text, usage = call_explain_llm(
            needs=needs,
            targets=targets,
            snippets=snippets,
            mode="mock",
        )
        text = f"{text}\n\n*Ghi chú: Đã dùng giải thích tóm tắt dự phòng ({exc}).*"
        trace_notes.append(f"explain: dùng tóm tắt dự phòng do lỗi LLM ({exc})")

    metrics = dict(state.get("metrics") or {})
    metrics["llm_calls"] = int(metrics.get("llm_calls", 0)) + 1
    metrics["tokens_in"] = int(metrics.get("tokens_in", 0)) + usage["tokens_in"]
    metrics["tokens_out"] = int(metrics.get("tokens_out", 0)) + usage["tokens_out"]

    return {
        "explanation_md": text,
        "metrics": metrics,
        "trace_notes": trace_notes,
    }


def output_guardrail(state: AgentState) -> dict[str, Any]:
    """Node 9 (output_guardrail): Kiểm tra đầu ra, sàn năng lượng và gắn disclaimer bắt buộc."""
    explanation = state.get("explanation_md", "")
    if "tham khảo" not in explanation.lower():
        explanation = f"{explanation}{DISCLAIMER_VI}"

    output_flags = list(state.get("output_flags") or [])
    targets = state.get("targets")
    plan_scored = state.get("plan_scored") or []

    if targets is not None:
        for day_tot in plan_scored:
            if float(day_tot.get("kcal", 0.0)) < targets.kcal_floor:
                if "energy_floor" not in output_flags:
                    output_flags.append("energy_floor")

    unfixable = bool(state.get("violations")) or (
        "energy_floor" in output_flags or "allergen" in output_flags
    )
    status = "needs_human_review" if unfixable else "pending_review"

    trace_notes = list(state.get("trace_notes") or [])
    trace_notes.append(f"output_guardrail: status={status}")
    return {
        "explanation_md": explanation,
        "output_flags": output_flags,
        "status": status,
        "trace_notes": trace_notes,
    }


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

    decision_data = interrupt(payload)
    review_dict: dict[str, Any] = (
        dict(decision_data)
        if isinstance(decision_data, dict)
        else {"decision": str(decision_data)}
    )
    decision = str(review_dict.get("decision", "approve"))
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
        edited_items = list(review_dict.get("edited_items") or [])
        if plan_llm is not None and targets is not None:
            plan_llm = _apply_edited_items(plan_llm, edited_items)
            updated_violations, updated_scored = verify_meal_plan(
                plan=plan_llm,
                profile=profile,
                targets=targets,
                gateway=gateway,
                needs=state.get("needs"),
                allowed_foods=state.get("allowed_foods"),
            )
            if updated_violations:
                new_status = "needs_human_review"
                trace_notes.append("await_review: bản sửa của chuyên gia còn vi phạm verifier")
            else:
                new_status = "approved"
                trace_notes.append("await_review: chuyên gia sửa và đạt verifier -> approved")
        else:
            new_status = "approved"
    else:
        new_status = "approved"
        trace_notes.append("await_review: chuyên gia duyệt -> approved")

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
    final_status = state.get("status", "approved")
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

    engine = get_engine()
    with Session(engine) as session:
        if review:
            create_review(
                session,
                meal_plan_id=meal_plan_id,
                reviewer_name=str(review.get("reviewer_name", "Chuyên gia dinh dưỡng")),
                decision=str(review.get("decision", "approve")),
                note=str(review.get("note", "")),
                edited_items_json=json.dumps(
                    review.get("edited_items") or [], ensure_ascii=False
                ),
            )

        create_query_log(
            session,
            session_id=state.get("session_id", "sess-default"),
            patient_code=profile.patient_code,
            status=final_status,
            meal_plan_id=meal_plan_id,
            latency_ms=float(metrics.get("latency_ms", 0.0)),
            llm_calls=int(metrics.get("llm_calls", 0)),
            tokens_in=int(metrics.get("tokens_in", 0)),
            tokens_out=int(metrics.get("tokens_out", 0)),
            retry_count=int(state.get("retry_count", 0)),
            violation_codes=",".join(v.code for v in violations),
            is_synthetic_log=False,
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
