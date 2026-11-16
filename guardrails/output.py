"""Lớp guardrail đầu ra: lọc từ cấm, kiểm tra trích nguồn, disclaimer, dị ứng và sàn kcal."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from agent.tools_gateway import ToolsGateway
from core.allergen import check_allergen
from core.schemas import GuidelineSnippet, MealPlanLLM, NutritionTargets, PatientProfile
from guardrails.input import load_guardrails_config, log_guardrail_event, normalize_text

logger = logging.getLogger(__name__)

_CITATION_PATTERN = re.compile(r"\[([^,\[\]]+?)\s*,\s*tr\.?\s*([^\[\]]+?)\]")
_BULLET_LINE_PATTERN = re.compile(r"^\s*(?:[-•*]|\d+\.)\s+")
_BLOCK_PREFIX_PATTERN = re.compile(r"^\s*(?:[-•*]|\d+\.|#{1,6}|>+)\s+")
_NON_SPLIT_DOT_PREFIX_RE = re.compile(
    r"(?:^|\b)(?:tr|vd|bs|ts|ths|pgs|gs)$",
    flags=re.IGNORECASE,
)


def _split_sentences(text: str, *, split_semicolon: bool = False) -> list[str]:
    """Tách câu văn xuôi mà không cắt ngang [...] trích dẫn hay viết tắt như tr. 12."""
    delimiters = {".", "!", "?"}
    if split_semicolon:
        delimiters.add(";")

    sentences: list[str] = []
    bracket_depth = 0
    paren_depth = 0
    start = 0
    n = len(text)
    i = 0
    while i < n:
        ch = text[i]
        if ch == "[":
            bracket_depth += 1
        elif ch == "]" and bracket_depth > 0:
            bracket_depth -= 1
        elif ch == "(":
            paren_depth += 1
        elif ch == ")" and paren_depth > 0:
            paren_depth -= 1
        elif (
            ch in delimiters
            and bracket_depth == 0
            and paren_depth == 0
            and i + 1 < n
            and text[i + 1].isspace()
        ):
            prefix = text[start:i]
            if ch == "." and _NON_SPLIT_DOT_PREFIX_RE.search(prefix):
                i += 1
                continue
            segment = text[start : i + 1].strip()
            if segment:
                sentences.append(segment)
            j = i + 1
            while j < n and text[j].isspace():
                j += 1
            start = j
            i = j
            continue
        i += 1

    tail = text[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences

_PROSE_RECOMMENDATION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:ban|quy\s+vi|nguoi\s+benh|benh\s+nhan)\s+"
        r"(?:nen|can|hay|phai|khong\s+nen|khong\s+duoc|tranh)\b"
    ),
    re.compile(
        r"^(?:nen|hay|can|tranh|han\s+che|kieng|tang\s+cuong|bo\s+sung|uu\s+tien|"
        r"cat\s+giam|chia\s+nho|duy\s+tri)\s+"
    ),
    re.compile(
        r"\b(?:khuyen\s+nghi|khuyen\s+cao|khong\s+nen\s+an|nen\s+an|nen\s+uong|"
        r"hay\s+an|hay\s+uong|tranh\s+an|han\s+che\s+an|kieng\s+an|bo\s+sung\s+them|"
        r"tang\s+cuong\s+an|cat\s+giam|chia\s+nho\s+bua)\b"
    ),
    re.compile(
        r"\b(?:giup\s+(?:ha|giam|kiem\s+soat|on\s+dinh|cai\s+thien|phong)|"
        r"co\s+tac\s+dung|rat\s+tot\s+cho|lam\s+tang|gay\s+tang|ngan\s+ngua)\b"
    ),
    re.compile(
        r"\btheo\s+(?:huong\s+dan|tai\s+lieu|khuyen\s+cao|nghien\s+cuu|chuyen\s+gia|bac\s+si)\b"
    ),
)


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
    """Xóa từng câu chứa nội dung y khoa cấm trên mọi cấu trúc văn bản (đoạn văn, bullet, bảng)."""
    if not text.strip():
        return "", False

    changed = False
    out_lines: list[str] = []

    for line in text.splitlines():
        if not line.strip():
            out_lines.append("")
            continue

        stripped = line.lstrip()
        if stripped.startswith("|") and stripped.endswith("|"):
            # Hàng bảng markdown: bỏ cả hàng nếu bất kỳ ô nào chứa nội dung cấm
            if _is_forbidden_sentence(stripped, forbidden_cfg):
                changed = True
                continue
            out_lines.append(line)
            continue

        prefix = ""
        body = line
        prefix_match = _BLOCK_PREFIX_PATTERN.match(line)
        if prefix_match:
            prefix = prefix_match.group(0)
            body = line[len(prefix) :]

        sentences = [s for s in _split_sentences(body, split_semicolon=True) if s.strip()]
        if not sentences:
            continue
        kept_sentences: list[str] = []
        for sent in sentences:
            if _is_forbidden_sentence(sent, forbidden_cfg):
                changed = True
            else:
                kept_sentences.append(sent)

        if kept_sentences:
            joined = " ".join(kept_sentences).strip()
            meaningful = _CITATION_PATTERN.sub("", joined).strip(" .,;:-•*")
            if meaningful:
                out_lines.append(f"{prefix}{joined}".rstrip())
            else:
                changed = True

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


def _is_prose_recommendation_sentence(sentence: str) -> bool:
    """Phát hiện câu khuyến nghị lâm sàng/dinh dưỡng viết dạng đoạn văn xuôi."""
    stripped = sentence.strip()
    if not stripped:
        return False
    # Bỏ qua tiêu đề mục ngắn kết thúc bằng dấu ':' (ví dụ: "Khuyến nghị chính:")
    if stripped.endswith(":") and len(stripped) <= 80 and "." not in stripped:
        return False
    norm = normalize_text(stripped)
    if not norm:
        return False
    return any(pat.search(norm) for pat in _PROSE_RECOMMENDATION_PATTERNS)


def _enforce_citations(
    text: str,
    snippets: list[GuidelineSnippet],
) -> tuple[str, bool]:
    """Xóa gạch đầu dòng hoặc câu khuyến nghị văn xuôi thiếu trích dẫn hợp lệ khớp snippets."""
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
            continue

        if not line.strip() or line.strip() == "---":
            kept_lines.append(line)
            continue

        prefix = ""
        body = line
        prefix_match = _BLOCK_PREFIX_PATTERN.match(line)
        if prefix_match:
            prefix = prefix_match.group(0)
            body = line[len(prefix) :]

        sentences = [s for s in _split_sentences(body, split_semicolon=False) if s.strip()]
        if not sentences:
            continue

        kept_sentences: list[str] = []
        for sent in sentences:
            has_cit_tag = bool(_CITATION_PATTERN.search(sent))
            if has_cit_tag:
                if _citation_matches_snippets(sent, snippets):
                    kept_sentences.append(sent)
                else:
                    removed_any = True
            elif _is_prose_recommendation_sentence(sent):
                removed_any = True
            else:
                kept_sentences.append(sent)

        if kept_sentences:
            kept_lines.append(f"{prefix}{' '.join(kept_sentences)}".rstrip())

    return "\n".join(kept_lines).strip(), removed_any


def _extract_plan_food_ids(plan_llm: MealPlanLLM | None) -> list[int]:
    """Lấy toàn bộ food_id duy nhất có trong plan_llm để kiểm tra dị ứng fail-closed."""
    if plan_llm is None or plan_llm.cannot_plan:
        return []
    ids: list[int] = []
    seen: set[int] = set()
    for day in plan_llm.days:
        for meal in day.meals:
            for item in meal.items:
                if item.food_id not in seen:
                    seen.add(item.food_id)
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

    # 2. Xóa khuyến nghị (bullet và văn xuôi) thiếu trích nguồn hợp lệ hoặc bịa nguồn
    clean_text, has_missing_cit = _enforce_citations(clean_text, list(snippets or []))
    if has_missing_cit:
        if "missing_citation" not in output_flags:
            output_flags.append("missing_citation")
        _record("missing_citation", "Đã xóa nội dung khuyến nghị thiếu trích dẫn hợp lệ.")

    wiped_empty = (not clean_text.strip()) and (has_forbidden or has_missing_cit)
    if wiped_empty:
        clean_text = (
            "**Lưu ý:** Nội dung giải thích tự động đã bị ẩn do vi phạm quy tắc an toàn y khoa "
            "hoặc thiếu nguồn trích dẫn hợp lệ. Hồ sơ cần chuyên gia dinh dưỡng xem xét trực tiếp."
        )

    if notice_vi.strip() and notice_vi.strip() not in clean_text:
        clean_text = f"{clean_text}\n\n{notice_vi.strip()}".strip()

    # 3. Phòng thủ nhiều lớp cuối: dị ứng (fail-closed) + sàn năng lượng trên plan_scored
    if profile is not None and profile.allergens and plan_llm is not None:
        food_ids = _extract_plan_food_ids(plan_llm)
        if food_ids:
            try:
                if gateway is not None:
                    alg_violations = gateway.check_allergen(food_ids, list(profile.allergens))
                else:
                    alg_violations = check_allergen(
                        food_ids, list(profile.allergens), food_db=allowed_foods
                    )
            except Exception as exc:
                logger.exception("Kiểm tra dị ứng thất bại tại output_guardrail: %s", exc)
                if "allergen_check_failed" not in output_flags:
                    output_flags.append("allergen_check_failed")
                _record(
                    "allergen",
                    "Không xác minh được dị nguyên do lỗi hệ thống kiểm tra "
                    f"({type(exc).__name__}): {exc}",
                )
                warn_msg = (
                    "**CẢNH BÁO AN TOÀN:** Hệ thống không thể xác minh thành phần gây dị ứng "
                    "cho thực đơn này do lỗi kiểm tra dị nguyên. Cần chuyên gia rà soát thủ công."
                )
                clean_text = f"{clean_text}\n\n{warn_msg}".strip() if clean_text else warn_msg
            else:
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

    # 4. Luôn chèn disclaimer cố định từ config (không để LLM tự viết)
    if clean_text:
        final_md = f"{clean_text}\n\n---\n{disclaimer}"
    else:
        final_md = f"---\n{disclaimer}"

    unfixable = (
        bool(violations)
        or ("allergen" in output_flags)
        or ("allergen_check_failed" in output_flags)
        or ("energy_floor" in output_flags)
        or wiped_empty
    )
    status = "needs_human_review" if unfixable else "pending_review"
    return OutputGuardrailResult(
        explanation_md=final_md,
        output_flags=output_flags,
        status=status,
        events=events,
    )
