"""Lớp guardrail đầu vào (validation, nguy cơ cao, injection, đòi thuốc, lạc đề, SAFETY_LLM)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import httpx
import yaml
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session
from unidecode import unidecode

from config.settings import Settings, get_settings
from core.classify import (
    TextRiskAssessment,
    assess_risk,
    assess_text_risk_details,
)
from core.nutrition import calc_bmi
from core.schemas import PatientProfile, RiskResult
from db.repo import create_guardrail_event
from db.session import get_engine
from observability.tracing import trace_llm_generation

DEFAULT_GUARDRAILS_PATH = Path("config/guardrails.yaml")
DEFAULT_SAFETY_PROMPT_PATH = Path("prompts/safety_classifier.txt")

_LEET_TRANS = str.maketrans(
    {
        "0": "o",
        "1": "i",
        "3": "e",
        "4": "a",
        "5": "s",
        "7": "t",
        "@": "a",
        "$": "s",
    }
)

_FIELD_NAME_VI: dict[str, str] = {
    "patient_code": "mã bệnh nhân",
    "age": "tuổi",
    "sex": "giới tính",
    "height_cm": "chiều cao (cm)",
    "weight_kg": "cân nặng (kg)",
    "activity_level": "mức độ vận động",
    "conditions": "nhóm bệnh lý",
    "allergens": "dị nguyên",
    "ckd_stage": "giai đoạn bệnh thận",
    "preferences_text": "ghi chú sở thích",
    "days": "số ngày thực đơn",
}

SafetyLabel = Literal["OK", "INJECTION", "MEDICAL_ADVICE", "OFF_TOPIC", "HIGH_RISK"]

_SEVERITY_RANK: dict[SafetyLabel, int] = {
    "OK": 0,
    "OFF_TOPIC": 1,
    "MEDICAL_ADVICE": 2,
    "HIGH_RISK": 3,
    "INJECTION": 4,
}


class SafetyClassificationLLM(BaseModel):
    """Kết quả JSON từ prompts/safety_classifier.txt."""

    label: SafetyLabel
    reason: str = Field(default="")


@dataclass
class InputGuardrailResult:
    """Kết quả tổng hợp sau khi chạy input guardrail."""

    action: Literal["pass", "blocked", "redirect_to_doctor", "needs_human_review"]
    profile: PatientProfile | None = None
    risk: RiskResult | None = None
    flags: list[str] = field(default_factory=list)
    cleaned_preferences_text: str = ""
    notice_vi: str = ""
    blocked_message_vi: str = ""
    events: list[tuple[str, str]] = field(default_factory=list)


@lru_cache(maxsize=4)
def load_guardrails_config(path: Path = DEFAULT_GUARDRAILS_PATH) -> dict[str, Any]:
    """Đọc cấu hình mẫu guardrail từ config/guardrails.yaml."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def normalize_text(text: str) -> str:
    """Chuẩn hóa tiếng Việt có dấu sang ASCII thường, gom khoảng trắng (SPEC 10.1)."""
    if not text:
        return ""
    ascii_text = unidecode(text).lower()
    return re.sub(r"\s+", " ", ascii_text).strip()


def _normalize_leet_and_spaced(text: str) -> tuple[str, str]:
    """Tạo bản chuẩn hóa leetspeak và bản gộp ký tự đơn rời rạc để bắt lỗi cố ý."""
    norm = normalize_text(text)
    leet = norm.translate(_LEET_TRANS)
    # Gộp chuỗi nhiều ký tự đơn cách nhau bởi dấu cách, ví dụ "p r o m p t" -> "prompt"
    despaced = re.sub(r"(?<=\b[a-z])\s+(?=[a-z]\b)", "", leet)
    return leet, despaced


def _format_validation_error_vi(exc: ValidationError) -> str:
    """Chuyển lỗi Pydantic ValidationError thành thông báo tiếng Việt thân thiện."""
    parts: list[str] = []
    for err in exc.errors():
        loc = err.get("loc") or ()
        field_key = str(loc[0]) if loc else "dữ liệu"
        label = _FIELD_NAME_VI.get(field_key, field_key)
        parts.append(f"{label} ({err.get('msg', 'không hợp lệ')})")
    detail = "; ".join(parts) if parts else "thông tin đầu vào không đúng định dạng"
    return f"Thông tin hồ sơ chưa hợp lệ: {detail}. Vui lòng kiểm tra và nhập lại."


def log_guardrail_event(
    *,
    session_id: str,
    layer: str,
    event_type: str,
    reason: str,
    session: Session | None = None,
) -> None:
    """Ghi sự kiện GuardrailEvent vào SQLite; tự mở session nếu chưa truyền vào."""
    if not session_id:
        return
    if session is not None:
        create_guardrail_event(
            session,
            session_id=session_id,
            layer=layer,
            event_type=event_type,
            reason=reason,
        )
        return

    engine = get_engine()
    with Session(engine) as db_sess:
        create_guardrail_event(
            db_sess,
            session_id=session_id,
            layer=layer,
            event_type=event_type,
            reason=reason,
        )
        db_sess.commit()


def _matches_any(
    norm_text: str,
    keywords: list[str],
    regex_patterns: list[str],
    *,
    extra_texts: tuple[str, ...] = (),
) -> str | None:
    """Kiểm tra khớp keyword hoặc regex; trả về mẫu khớp đầu tiên hoặc None."""
    candidates = [norm_text, *extra_texts]
    for kw in keywords:
        kw_norm = normalize_text(kw)
        if not kw_norm:
            continue
        for cand in candidates:
            if kw_norm in cand:
                return kw
    for pat in regex_patterns:
        for cand in candidates:
            if re.search(pat, cand):
                return pat
    return None


def _assess_clinical_high_risk(
    profile: PatientProfile,
    risk_rules: dict[str, Any] | None = None,
) -> RiskResult:
    """Kiểm tra luật nguy cơ cao dựa trên các trường lâm sàng có cấu trúc (không quét text)."""
    profile_no_text = profile.model_copy(update={"preferences_text": ""})
    return assess_risk(profile_no_text, risk_rules=risk_rules)


def _assess_text_high_risk(
    text: str,
    risk_rules: dict[str, Any] | None = None,
) -> RiskResult:
    """Kiểm tra từ khóa nguy cơ cao trong preferences_text theo ngữ cảnh từng vị trí."""
    return assess_text_risk_details(text, risk_rules=risk_rules).confirmed


def _strip_clauses_matching(
    text: str,
    keywords: list[str],
    regex_patterns: list[str],
) -> tuple[str, bool, str | None]:
    """Tách mệnh đề/câu, loại bỏ phần vi phạm và giữ lại sở thích ăn uống hợp lệ."""
    if not text or not text.strip():
        return "", False, None

    clauses = [c.strip() for c in re.split(r"[.!?;,\n]+", text) if c.strip()]
    kept: list[str] = []
    matched_rule: str | None = None

    for clause in clauses:
        norm_clause = normalize_text(clause)
        hit = _matches_any(norm_clause, keywords, regex_patterns)
        if hit is not None:
            if matched_rule is None:
                matched_rule = hit
        else:
            kept.append(clause)

    return ", ".join(kept), matched_rule is not None, matched_rule


def _has_nutrition_keyword(norm_text: str, nutrition_keywords: list[str]) -> bool:
    """Kiểm tra văn bản chuẩn hóa có chứa ít nhất 1 từ khóa thuộc miền ăn uống/dinh dưỡng."""
    for kw in nutrition_keywords:
        kw_norm = normalize_text(kw)
        if not kw_norm:
            continue
        if re.search(rf"(?<![a-z0-9]){re.escape(kw_norm)}(?![a-z0-9])", norm_text):
            return True
    return False


def _render_safety_prompt(text: str, prompt_path: Path = DEFAULT_SAFETY_PROMPT_PATH) -> str:
    """Nạp prompts/safety_classifier.txt và bọc văn bản đã khử thẻ <user_data>."""
    template = prompt_path.read_text(encoding="utf-8")
    safe_text = text.replace("</user_data>", "[/user_data]").replace("<user_data>", "[user_data]")
    return template.replace("{{text}}", safe_text.strip())


def run_safety_classifier_llm(
    text: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
    prompt_path: Path = DEFAULT_SAFETY_PROMPT_PATH,
) -> SafetyClassificationLLM:
    """Phân loại an toàn tùy chọn (SAFETY_LLM=on) dùng GEMINI_LIGHT_MODEL hoặc mock."""
    if not text or not text.strip():
        return SafetyClassificationLLM(label="OK", reason="Không có ghi chú.")

    cfg_settings = settings or get_settings()
    if client is None and (
        cfg_settings.LLM_MODE == "mock" or not cfg_settings.GEMINI_API_KEY.strip()
    ):
        guard_cfg = load_guardrails_config()
        norm = normalize_text(text)
        leet, despaced = _normalize_leet_and_spaced(text)
        inj = guard_cfg.get("injection") or {}
        if _matches_any(
            norm,
            inj.get("keywords", []),
            inj.get("regex_patterns", []),
            extra_texts=(leet, despaced),
        ):
            return SafetyClassificationLLM(
                label="INJECTION",
                reason="Phát hiện mẫu can thiệp chỉ dẫn hệ thống.",
            )
        if _assess_text_high_risk(text).high_risk:
            return SafetyClassificationLLM(
                label="HIGH_RISK",
                reason="Ghi chú đề cập tình trạng nguy cơ cao.",
            )
        med = guard_cfg.get("medical_advice") or {}
        if _matches_any(norm, med.get("keywords", []), med.get("regex_patterns", [])):
            return SafetyClassificationLLM(
                label="MEDICAL_ADVICE",
                reason="Yêu cầu kê đơn hoặc chẩn đoán y khoa.",
            )
        off = guard_cfg.get("off_topic") or {}
        if _matches_any(norm, off.get("keywords", []), off.get("regex_patterns", [])):
            return SafetyClassificationLLM(
                label="OFF_TOPIC",
                reason="Nội dung không liên quan đến dinh dưỡng.",
            )
        return SafetyClassificationLLM(label="OK", reason="Ghi chú an toàn.")

    prompt = _render_safety_prompt(text, prompt_path=prompt_path)
    active_client = client or genai.Client(
        api_key=cfg_settings.GEMINI_API_KEY.strip(),
        http_options=types.HttpOptions(timeout=20_000, retry_options=None),
    )
    gen_config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=SafetyClassificationLLM,
        temperature=0.0,
    )
    try:
        with trace_llm_generation(
            name="gemini_safety_classifier",
            model=cfg_settings.GEMINI_LIGHT_MODEL,
            input_data=prompt,
            metadata={"safety_llm": "on"},
            settings=cfg_settings,
        ) as gen:
            response = active_client.models.generate_content(
                model=cfg_settings.GEMINI_LIGHT_MODEL,
                contents=prompt,
                config=gen_config,
            )
            parsed = getattr(response, "parsed", None)
            if isinstance(parsed, SafetyClassificationLLM):
                result = parsed
            elif isinstance(parsed, dict):
                result = SafetyClassificationLLM.model_validate(parsed)
            else:
                raw_text = str(getattr(response, "text", None) or "").strip()
                result = SafetyClassificationLLM.model_validate(json.loads(raw_text))
            usage_meta = getattr(response, "usage_metadata", None)
            t_in = int(getattr(usage_meta, "prompt_token_count", 0) or 0)
            t_out = int(getattr(usage_meta, "candidates_token_count", 0) or 0)
            gen.finish(output={"label": result.label}, tokens_in=t_in, tokens_out=t_out)
            return result
    except (
        genai_errors.APIError,
        TimeoutError,
        ConnectionError,
        httpx.HTTPError,
        ValidationError,
        ValueError,
    ):
        # Không làm hỏng luồng và không nới lỏng luật khi safety LLM lỗi
        return SafetyClassificationLLM(label="OK", reason="Fallback do lỗi kết nối classifier.")


def validate_profile_input(
    raw_profile: PatientProfile | dict[str, Any],
    *,
    session_id: str = "",
    guardrails_cfg: dict[str, Any] | None = None,
    session: Session | None = None,
    log_events: bool = True,
) -> tuple[PatientProfile | None, InputGuardrailResult | None]:
    """Kiểm tra Pydantic PatientProfile và BMI 10–80; trả về lỗi chặn nếu không hợp lệ."""
    cfg = guardrails_cfg or load_guardrails_config()
    disclaimer = str(cfg.get("disclaimer_vi", "")).strip()

    if isinstance(raw_profile, PatientProfile):
        profile = raw_profile
    else:
        try:
            profile = PatientProfile.model_validate(raw_profile)
        except ValidationError as exc:
            err_vi = _format_validation_error_vi(exc)
            if log_events and session_id:
                log_guardrail_event(
                    session_id=session_id,
                    layer="input",
                    event_type="validation",
                    reason=err_vi,
                    session=session,
                )
            return None, InputGuardrailResult(
                action="blocked",
                profile=None,
                flags=["validation"],
                blocked_message_vi=f"**Dữ liệu không hợp lệ:** {err_vi}\n\n---\n{disclaimer}",
                events=[("validation", err_vi)],
            )

    bounds = cfg.get("bmi_bounds") or {}
    bmi_min = float(bounds.get("min", 10.0))
    bmi_max = float(bounds.get("max", 80.0))
    bmi = calc_bmi(profile.weight_kg, profile.height_cm)
    if bmi < bmi_min or bmi > bmi_max:
        reason = (
            f"Chỉ số BMI tính được là {bmi:.1f}, nằm ngoài khoảng hợp lệ "
            f"{bmi_min:.0f}–{bmi_max:.0f}. Vui lòng kiểm tra lại chiều cao và cân nặng."
        )
        if log_events and session_id:
            log_guardrail_event(
                session_id=session_id,
                layer="input",
                event_type="validation",
                reason=reason,
                session=session,
            )
        return None, InputGuardrailResult(
            action="blocked",
            profile=profile,
            flags=["validation"],
            blocked_message_vi=f"**Dữ liệu không hợp lệ:** {reason}\n\n---\n{disclaimer}",
            events=[("validation", reason)],
        )

    return profile, None


_ALLERGEN_TERMS: dict[str, tuple[str, ...]] = {
    "peanut": ("lac", "dau phong", "peanut"),
    "seafood": ("hai san", "tom", "cua", "muc", "ngheu", "so", "oc", "seafood"),
    "milk": ("sua bo", "pho mai", "sua", "milk", "dairy"),
    "egg": ("trung", "egg"),
    "gluten": ("gluten", "lua mi", "banh mi"),
    "soy": ("dau nanh", "dau phu", "dau hu", "soy"),
}
_INCLUDE_VERB_RE = re.compile(
    r"\b(?:chon|them|dua|cho|xep|uu\s+tien|bat\s+buoc|muon\s+an|can\s+co|select|add|include|put)\b"
)
_ALLERGEN_CLAUSE_NEG_RE = re.compile(
    r"\b(?:khong|tranh|dung|bo|kieng|di\s+ung|not|no|avoid|without)\b"
)


def _detect_allergen_override(norm_text: str, allergens: list[str]) -> str | None:
    """Phát hiện chỉ dẫn yêu cầu đưa món chứa chính dị nguyên của bệnh nhân vào thực đơn."""
    if not norm_text or not allergens:
        return None
    for clause in re.split(r"[.!?;,\n]+", norm_text):
        part = clause.strip()
        if not part or _ALLERGEN_CLAUSE_NEG_RE.search(part):
            continue
        if not _INCLUDE_VERB_RE.search(part):
            continue
        for alg in allergens:
            for term in _ALLERGEN_TERMS.get(alg, ()):
                if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", part):
                    return f"allergen_override:{alg}"
    return None


def evaluate_input_guardrail(
    raw_profile: PatientProfile | dict[str, Any],
    *,
    session_id: str = "",
    existing_flags: list[str] | None = None,
    guardrails_cfg: dict[str, Any] | None = None,
    risk_rules: dict[str, Any] | None = None,
    settings: Settings | None = None,
    safety_llm_client: Any | None = None,
    session: Session | None = None,
    log_events: bool = True,
) -> InputGuardrailResult:
    """Thực thi đầy đủ lớp guardrail đầu vào theo SPEC bảng 10.1 và mục 6.4."""
    cfg = guardrails_cfg or load_guardrails_config()
    cfg_settings = settings or get_settings()
    disclaimer = str(cfg.get("disclaimer_vi", "")).strip()
    flags = list(existing_flags or [])
    events: list[tuple[str, str]] = []

    def _record(event_type: str, reason: str) -> None:
        events.append((event_type, reason))
        if log_events and session_id:
            log_guardrail_event(
                session_id=session_id,
                layer="input",
                event_type=event_type,
                reason=reason,
                session=session,
            )

    # 1. Hợp lệ dữ liệu (Pydantic + BMI 10–80)
    profile, validation_err = validate_profile_input(
        raw_profile,
        session_id=session_id,
        guardrails_cfg=cfg,
        session=session,
        log_events=log_events,
    )
    if validation_err is not None or profile is None:
        assert validation_err is not None
        return validation_err

    # 2. Nguy cơ cao từ chỉ số lâm sàng cấu trúc (luật 6.4)
    clinical_risk = _assess_clinical_high_risk(profile, risk_rules=risk_rules)
    if clinical_risk.high_risk:
        for r_code in clinical_risk.reasons:
            if r_code not in flags:
                flags.append(r_code)
        _record("high_risk", f"Nguy cơ cao lâm sàng: {','.join(clinical_risk.reasons)}")
        return InputGuardrailResult(
            action="redirect_to_doctor",
            profile=profile,
            risk=clinical_risk,
            flags=flags,
            cleaned_preferences_text="",
            blocked_message_vi=(
                f"**Khuyến nghị thăm khám trực tiếp:** {clinical_risk.message_vi}"
                f"\n\n---\n{disclaimer}"
            ),
            events=events,
        )

    raw_text = profile.preferences_text or ""
    norm_text = normalize_text(raw_text)
    leet_text, despaced_text = _normalize_leet_and_spaced(raw_text)

    # 3. Prompt injection (kể cả cờ injection truyền sẵn hoặc phát hiện từ text)
    inj_cfg = cfg.get("injection") or {}
    inj_hit = _matches_any(
        norm_text,
        inj_cfg.get("keywords", []),
        inj_cfg.get("regex_patterns", []),
        extra_texts=(leet_text, despaced_text),
    )
    if inj_hit is None:
        inj_hit = _detect_allergen_override(norm_text, list(profile.allergens))
    if "injection" in flags or inj_hit is not None:
        if "injection" not in flags:
            flags.append("injection")
        _record("injection", f"Phát hiện prompt injection (mẫu: {inj_hit or 'input_flags'}).")
        return InputGuardrailResult(
            action="blocked",
            profile=profile,
            risk=RiskResult(high_risk=False),
            flags=flags,
            cleaned_preferences_text="",
            blocked_message_vi=(
                "**Yêu cầu bị từ chối:** Phát hiện nội dung không hợp lệ hoặc cố tình "
                f"vượt qua quy tắc an toàn.\n\n---\n{disclaimer}"
            ),
            events=events,
        )

    # 4. Nguy cơ cao / cấp cứu / nghi ngờ chưa xác định qua văn bản preferences_text (RISK_TEXT)
    text_assessment: TextRiskAssessment = assess_text_risk_details(raw_text, risk_rules=risk_rules)
    text_risk = text_assessment.confirmed
    if text_risk.high_risk:
        for r_code in text_risk.reasons:
            if r_code not in flags:
                flags.append(r_code)
        _record("high_risk", f"Nguy cơ cao từ ghi chú: {','.join(text_risk.reasons)}")
        header = (
            "**CẢNH BÁO CẤP CỨU Y KHOA:**"
            if "RISK_EMERGENCY" in text_risk.reasons
            else "**Khuyến nghị thăm khám trực tiếp:**"
        )
        return InputGuardrailResult(
            action="redirect_to_doctor",
            profile=profile,
            risk=text_risk,
            flags=flags,
            cleaned_preferences_text="",
            blocked_message_vi=f"{header} {text_risk.message_vi}\n\n---\n{disclaimer}",
            events=events,
        )

    if text_assessment.ambiguous_reasons:
        for r_code in text_assessment.ambiguous_reasons:
            if r_code not in flags:
                flags.append(r_code)
        if "ambiguous_high_risk" not in flags:
            flags.append("ambiguous_high_risk")
        _record(
            "high_risk",
            "Ghi chú có dấu hiệu nguy cơ cao chưa rõ "
            f"({','.join(text_assessment.ambiguous_reasons)}), chuyển chuyên gia duyệt.",
        )
        return InputGuardrailResult(
            action="needs_human_review",
            profile=profile,
            risk=RiskResult(
                high_risk=False,
                reasons=list(text_assessment.ambiguous_reasons),
                message_vi=text_assessment.ambiguous_message_vi,
            ),
            flags=flags,
            cleaned_preferences_text="",
            blocked_message_vi=(
                f"**Cần chuyên gia xem xét trực tiếp:** {text_assessment.ambiguous_message_vi}"
                f"\n\n---\n{disclaimer}"
            ),
            events=events,
        )

    # 5. Đòi chẩn đoán / kê đơn / chỉnh liều thuốc
    working_text = raw_text
    notices: list[str] = []
    med_cfg = cfg.get("medical_advice") or {}
    working_text, med_hit, med_rule = _strip_clauses_matching(
        working_text,
        med_cfg.get("keywords", []),
        med_cfg.get("regex_patterns", []),
    )
    rule_label: SafetyLabel = "OK"
    if med_hit:
        rule_label = "MEDICAL_ADVICE"
        if "medical_advice" not in flags:
            flags.append("medical_advice")
        notices.append(
            "Lưu ý: Hệ thống chỉ hỗ trợ xây dựng khẩu phần ăn, không chẩn đoán bệnh "
            "hay kê/chỉnh liều thuốc. Phần yêu cầu về thuốc đã được bỏ qua."
        )
        _record("medical_advice", f"Lọc yêu cầu chẩn đoán/kê thuốc (mẫu: {med_rule}).")

    # 6. Lạc đề (từ khóa + độ dài thiếu từ khóa dinh dưỡng)
    off_cfg = cfg.get("off_topic") or {}
    working_text, off_kw_hit, off_rule = _strip_clauses_matching(
        working_text,
        off_cfg.get("keywords", []),
        off_cfg.get("regex_patterns", []),
    )
    off_len_hit = False
    min_len = int(off_cfg.get("min_length_for_topic_check", 80))
    if working_text and len(working_text) >= min_len:
        norm_rem = normalize_text(working_text)
        if not _has_nutrition_keyword(norm_rem, off_cfg.get("nutrition_keywords", [])):
            off_len_hit = True
            working_text = ""

    if off_kw_hit or off_len_hit:
        if _SEVERITY_RANK[rule_label] < _SEVERITY_RANK["OFF_TOPIC"]:
            rule_label = "OFF_TOPIC"
        if "off_topic" not in flags:
            flags.append("off_topic")
        reason_off = (
            f"Bỏ qua nội dung lạc đề (mẫu: {off_rule})."
            if off_kw_hit
            else "Bỏ qua đoạn văn bản dài không liên quan đến ăn uống/dinh dưỡng."
        )
        _record("off_topic", reason_off)

    # 7. Lớp tùy chọn SAFETY_LLM=on: chỉ làm chặt hơn luật, không nới lỏng
    if cfg_settings.SAFETY_LLM == "on" and raw_text.strip():
        llm_cls = run_safety_classifier_llm(
            raw_text,
            settings=cfg_settings,
            client=safety_llm_client,
        )
        if _SEVERITY_RANK[llm_cls.label] > _SEVERITY_RANK[rule_label]:
            if llm_cls.label == "INJECTION":
                if "injection" not in flags:
                    flags.append("injection")
                _record("injection", f"SAFETY_LLM chặn injection: {llm_cls.reason}")
                return InputGuardrailResult(
                    action="blocked",
                    profile=profile,
                    risk=RiskResult(high_risk=False),
                    flags=flags,
                    cleaned_preferences_text="",
                    blocked_message_vi=(
                        "**Yêu cầu bị từ chối:** Phát hiện nội dung không hợp lệ hoặc cố tình "
                        f"vượt qua quy tắc an toàn.\n\n---\n{disclaimer}"
                    ),
                    events=events,
                )
            if llm_cls.label == "HIGH_RISK":
                if "RISK_TEXT" not in flags:
                    flags.append("RISK_TEXT")
                _record("high_risk", f"SAFETY_LLM phát hiện nguy cơ cao: {llm_cls.reason}")
                msg = (
                    "Ghi chú có dấu hiệu thuộc nhóm nguy cơ cao cần bác sĩ hoặc "
                    "chuyên gia dinh dưỡng tư vấn trực tiếp."
                )
                return InputGuardrailResult(
                    action="redirect_to_doctor",
                    profile=profile,
                    risk=RiskResult(high_risk=True, reasons=["RISK_TEXT"], message_vi=msg),
                    flags=flags,
                    cleaned_preferences_text="",
                    blocked_message_vi=(
                        f"**Khuyến nghị thăm khám trực tiếp:** {msg}\n\n---\n{disclaimer}"
                    ),
                    events=events,
                )
            if llm_cls.label == "MEDICAL_ADVICE" and "medical_advice" not in flags:
                flags.append("medical_advice")
                working_text = ""
                notices.append(
                    "Lưu ý: Hệ thống chỉ hỗ trợ xây dựng khẩu phần ăn, không chẩn đoán bệnh "
                    "hay kê/chỉnh liều thuốc."
                )
                _record("medical_advice", f"SAFETY_LLM lọc đòi thuốc/chẩn đoán: {llm_cls.reason}")
            if llm_cls.label == "OFF_TOPIC" and "off_topic" not in flags:
                flags.append("off_topic")
                working_text = ""
                _record("off_topic", f"SAFETY_LLM lọc nội dung lạc đề: {llm_cls.reason}")

    cleaned_profile = profile.model_copy(update={"preferences_text": working_text})
    return InputGuardrailResult(
        action="pass",
        profile=cleaned_profile,
        risk=RiskResult(high_risk=False),
        flags=flags,
        cleaned_preferences_text=working_text,
        notice_vi=" ".join(notices),
        events=events,
    )
