"""Lớp guardrail đầu ra: lọc từ cấm, kiểm tra trích nguồn, disclaimer, dị ứng và sàn kcal."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from agent.tools_gateway import ToolsGateway
from core.allergen import check_allergen
from core.schemas import GuidelineSnippet, MealPlanLLM, NutritionTargets, PatientProfile
from guardrails.input import load_guardrails_config, log_guardrail_event, normalize_text

_CITATION_PATTERN = re.compile(r"\[([^,\[\]]+?)\s*,\s*tr\.?\s*([^\[\]]+?)\]")
_BULLET_LINE_PATTERN = re.compile(r"^\s*(?:[-•*]|\d+\.)\s+")


@dataclass
class OutputGuardrailResult:
    """Kết quả kiểm tra đầu ra trước khi chuyển duyệt chuyên gia."""

    explanation_md: str
    output_flags: list[str] = field(default_factory=list)
    status: str = "pending_review"
    events: list[tuple[str, str]] = field(default_factory=list)


def _strip_existing_disclaimer(text: str) -> str:
    """Loại bỏ dòng disclaimer hoặc gạch phân cách cuối văn bản để gắn lại bản chuẩn cố định."""
    lines = text.rstrip().splitlines()
    while lines:
        last = lines[-1].strip()
        last_norm = normalize_text(last)
        if (
            not last
            or last == "---"
            or "thuc don chi mang tinh tham khao ho tro dinh duong" in last_norm
        ):
            lines.pop()
        else:
            break
    return "\n".join(lines).rstrip()


def _is_forbidden_sentence(sentence: str, forbidden_cfg: dict[str, Any]) -> bool:
    """Kiểm tra câu có chứa nội dung y khoa bị cấm ở đầu ra hay không."""
    norm = normalize_text(sentence)
    if not norm:
        return False
    for kw in forbidden_cfg.get("keywords", []):
        if normalize_text(kw) in norm:
            return True
    for pat in forbidden_cfg.get("regex_patterns", []):
        if re.search(pat, norm):
            return True
    return False


def _remove_forbidden_sentences(
    text: str,
    forbidden_cfg: dict[str, Any],
) -> tuple[str, bool]:
    """Xóa từng câu chứa nội dung cấm trong explanation_md nhưng vẫn giữ cấu trúc dòng."""
    if not text.strip():
        return "", False

    changed = False
    out_lines: list[str] = []

    for line in text.splitlines():
        if not line.strip():
            out_lines.append("")
            continue

        bullet_prefix = ""
        body = line
        bullet_match = _BULLET_LINE_PATTERN.match(line)
        if bullet_match:
            bullet_prefix = bullet_match.group(0)
            body = line[len(bullet_prefix) :]

        sentences = [s for s in re.split(r"(?<=[.!?])\s+", body) if s.strip()]
        if not sentences:
            continue
        kept_sentences: list[str] = []
        for sent in sentences:
            if _is_forbidden_sentence(sent, forbidden_cfg):
                changed = True
            else:
                kept_sentences.append(sent)

        if kept_sentences:
            out_lines.append(f"{bullet_prefix}{' '.join(kept_sentences)}".rstrip())

    return "\n".join(out_lines).strip(), changed


def _citation_matches_snippets(
    line: str,
    snippets: list[GuidelineSnippet],
) -> bool:
    """Kiểm tra dòng gạch đầu dòng có trích dẫn [tên tài liệu, tr. X] khớp snippet đã truy xuất."""
    matches = _CITATION_PATTERN.findall(line)
    if not matches or not snippets:
        return False

    valid_pairs = {
        (normalize_text(str(s.source_name)), normalize_text(str(s.page)))
        for s in snippets
    }
    for src, page in matches:
        pair = (normalize_text(src), normalize_text(page))
        if pair in valid_pairs:
            return True
    return False


def _enforce_bullet_citations(
    text: str,
    snippets: list[GuidelineSnippet],
) -> tuple[str, bool]:
    """Xóa mọi gạch đầu dòng khuyến nghị thiếu trích dẫn hợp lệ khớp snippets."""
    if not text.strip():
        return "", False

    removed_any = False
    kept_lines: list[str] = []
    for line in text.splitlines():
        if _BULLET_LINE_PATTERN.match(line) and line.strip() != "---":
            if _citation_matches_snippets(line, snippets):
                kept_lines.append(line)
            else:
                removed_any = True
        else:
            kept_lines.append(line)

    return "\n".join(kept_lines).strip(), removed_any


def _extract_valid_food_ids(
    plan_llm: MealPlanLLM | None,
    allowed_foods: list[dict[str, Any]] | None,
) -> list[int]:
    """Lấy các food_id có trong plan_llm và tồn tại trong allowed_foods."""
    if plan_llm is None or plan_llm.cannot_plan:
        return []
    known_ids = (
        {int(f["id"]) for f in allowed_foods if "id" in f}
        if allowed_foods
        else None
    )
    ids: list[int] = []
    for day in plan_llm.days:
        for meal in day.meals:
            for item in meal.items:
                if known_ids is None or item.food_id in known_ids:
                    ids.append(item.food_id)
    return ids


def evaluate_output_guardrail(
    *,
    explanation_md: str,
    snippets: list[GuidelineSnippet] | None = None,
    profile: PatientProfile | None = None,
    targets: NutritionTargets | None = None,
    plan_llm: MealPlanLLM | None = None,
    plan_scored: list[dict[str, Any]] | None = None,
    allowed_foods: list[dict[str, Any]] | None = None,
    violations: list[Any] | None = None,
    existing_output_flags: list[str] | None = None,
    notice_vi: str = "",
    session_id: str = "",
    gateway: ToolsGateway | None = None,
    guardrails_cfg: dict[str, Any] | None = None,
    session: Session | None = None,
    log_events: bool = True,
) -> OutputGuardrailResult:
    """Thực thi lớp guardrail đầu ra theo SPEC mục 10.2."""
    cfg = guardrails_cfg or load_guardrails_config()
    disclaimer = str(cfg.get("disclaimer_vi", "")).strip()
    forbidden_cfg = cfg.get("forbidden_output") or {}

    output_flags = list(existing_output_flags or [])
    events: list[tuple[str, str]] = []

    def _record(event_type: str, reason: str) -> None:
        events.append((event_type, reason))
        if log_events and session_id:
            log_guardrail_event(
                session_id=session_id,
                layer="output",
                event_type=event_type,
                reason=reason,
                session=session,
            )

    clean_text = _strip_existing_disclaimer(explanation_md or "")

    # 1. Xóa câu chứa nội dung cấm ở đầu ra
    clean_text, has_forbidden = _remove_forbidden_sentences(clean_text, forbidden_cfg)
    if has_forbidden:
        if "forbidden_output" not in output_flags:
            output_flags.append("forbidden_output")
        _record("forbidden_output", "Đã xóa câu chứa từ ngữ/chỉ định y khoa bị cấm ở đầu ra.")

    # 2. Xóa gạch đầu dòng khuyến nghị thiếu trích nguồn hợp lệ
    clean_text, has_missing_cit = _enforce_bullet_citations(clean_text, list(snippets or []))
    if has_missing_cit:
        if "missing_citation" not in output_flags:
            output_flags.append("missing_citation")
        _record("missing_citation", "Đã xóa gạch đầu dòng khuyến nghị thiếu trích dẫn hợp lệ.")

    if notice_vi.strip() and notice_vi.strip() not in clean_text:
        clean_text = f"{clean_text}\n\n{notice_vi.strip()}".strip()

    # 3. Luôn chèn disclaimer cố định từ config (không để LLM tự viết)
    if clean_text:
        final_md = f"{clean_text}\n\n---\n{disclaimer}"
    else:
        final_md = f"---\n{disclaimer}"

    # 4. Kiểm tra phòng thủ nhiều lớp cuối cùng: dị ứng + sàn năng lượng trên plan_scored
    if profile is not None and profile.allergens and plan_llm is not None:
        food_ids = _extract_valid_food_ids(plan_llm, allowed_foods)
        if food_ids:
            try:
                if gateway is not None:
                    alg_violations = gateway.check_allergen(food_ids, list(profile.allergens))
                else:
                    alg_violations = check_allergen(
                        food_ids, list(profile.allergens), food_db=allowed_foods
                    )
            except ValueError:
                alg_violations = []
            if alg_violations:
                if "allergen" not in output_flags:
                    output_flags.append("allergen")
                _record(
                    "allergen",
                    "Phát hiện món chứa dị nguyên tại output_guardrail: "
                    + "; ".join(v.message_vi for v in alg_violations),
                )

    if targets is not None and plan_scored:
        low_days = [
            str(d.get("day"))
            for d in plan_scored
            if float(d.get("kcal", 0.0)) < targets.kcal_floor
        ]
        if low_days:
            if "energy_floor" not in output_flags:
                output_flags.append("energy_floor")
            _record(
                "energy_floor",
                f"Ngày {', '.join(low_days)} dưới sàn {targets.kcal_floor:.0f} kcal.",
            )

    unfixable = bool(violations) or ("allergen" in output_flags) or ("energy_floor" in output_flags)
    status = "needs_human_review" if unfixable else "pending_review"
    return OutputGuardrailResult(
        explanation_md=final_md,
        output_flags=output_flags,
        status=status,
        events=events,
    )
