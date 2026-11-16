"""Phân loại nhu cầu dinh dưỡng và sàng lọc nguy cơ cao theo SPEC mục 6.3–6.4."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from unidecode import unidecode

from core.nutrition import calc_bmi, load_rules
from core.schemas import NeedsResult, PatientProfile, RiskResult

DEFAULT_RISK_RULES_PATH = Path("config/risk_rules.yaml")

_CLAUSE_SPLIT_RE = re.compile(
    r"(?:[.!?;:\n\r()\[\]{}\"“”'…–—]+|,(?=\s|$)|"
    r"\s+(?:nhưng mà|nhung ma|tuy nhiên|tuy nhien|nhưng|nhung|mà|ngoài ra|ngoai ra|"
    r"kèm theo|kem theo|bởi vì|boi vi|tại vì|cho nên|cho nen|mặc dù|mac du|"
    r"vì|và|chứ|nên|tuy|hoặc(?!\s+(?:không|chưa)))\s+)",
    flags=re.IGNORECASE,
)

_NEGATION_TAIL_RE = re.compile(
    r"(?:^|\b)(?:"
    r"khong he|khong phai la|khong phai|khong con|khong co|khong dang|khong bi|khong mac|"
    r"khong can|khong|chua he|chua tung|chua bao gio|chua phai|chua co|chua bi|chua|het|da het"
    r")(?:\s+(?:co|dang|mang|bi|mac|phai|con|tung|la|nham|thuoc|can|sap|duoc)){0,2}$"
)

_UNCERTAINTY_BEFORE_RE = re.compile(
    r"(?:^|\b)(?:"
    r"khong ro|chua ro|khong chac|chua chac|khong biet|chua biet|"
    r"nghi ngo|nghi la|kha nang|ban khoan|thac mac|hinh nhu|co ve|lieu|nghe noi|"
    r"tre kinh|cham kinh|thu thai|que thu"
    r")\b"
)

_UNCERTAINTY_AFTER_RE = re.compile(
    r"^(?:hay khong|hay chua|hoac khong|khong nhi|chua nhi|u|vay)\b"
)

_QUESTION_PARTICLE_AFTER_RE = re.compile(
    r"^(?:khong|chua)(?:\s+(?:nhi|a|ha|vay|chu|dau|sao))?\s*$"
)

_BAU_BEFORE_BENIGN = frozenset(
    {
        "canh",
        "bi",
        "qua",
        "trai",
        "mon",
        "luoc",
        "xao",
        "ham",
        "kho",
        "nau",
        "an",
        "hat",
        "hoa",
        "nu",
        "dot",
        "ngon",
        "rau",
        "muop",
        "ruot",
        "vo",
        "nam",
        "cui",
        "xat",
        "lat",
        "mieng",
        "goi",
        "nom",
        "xay",
        "ep",
        "trong",
        "mua",
        "ban",
        "got",
        "bo",
        "chao",
        "sup",
        "nuoc",
        "ung",
        "cuoc",
        "phieu",
        "di",
        "chon",
    }
)

_BAU_BEFORE_BENIGN_BIGRAMS = frozenset(
    {
        ("bo", "phieu"),
        ("ung", "cu"),
        ("tong", "thong"),
        ("dai", "bieu"),
    }
)

_BAU_AFTER_BENIGN_SINGLE = frozenset(
    {
        "luoc",
        "xao",
        "kho",
        "ham",
        "nau",
        "duc",
        "non",
        "gia",
        "sao",
        "xay",
        "nuong",
        "hap",
        "chien",
        "lat",
        "mieng",
        "giong",
        "dat",
        "cu",
        "troi",
        "ban",
        "chon",
        "len",
    }
)

_BAU_AFTER_BENIGN_BIGRAMS = frozenset(
    {
        ("khong", "khi"),
        ("tam", "su"),
        ("nhiet", "huyet"),
        ("bi", "thu"),
    }
)

_BAU_UNACCENTED_CLEAR_BEFORE = frozenset(
    {"dang", "co", "mang", "ba", "me", "nguoi", "can", "toi", "minh", "vo"}
)
_BAU_UNACCENTED_CLEAR_AFTER = frozenset({"bi", "thai", "nghen", "thang", "tuan"})

_PREVENTABLE_EMERGENCY_KWS = frozenset(
    {"tut duong huyet", "duong huyet tut", "ha duong huyet nang", "ha duong huyet qua thap"}
)
_PREVENTION_BEFORE_RE = re.compile(
    r"(?:^|\b)(?:tranh|phong|phong tranh|phong ngua|ngan ngua|ngua|so|lo)(?:\s+(?:bi|mac|con))?$"
)


@dataclass
class TextRiskAssessment:
    """Kết quả đánh giá nguy cơ cao trên văn bản theo ngữ cảnh từng vị trí."""

    confirmed: RiskResult
    ambiguous_reasons: list[str] = field(default_factory=list)
    ambiguous_message_vi: str = ""


def normalize_vietnamese_ascii(text: str) -> str:
    """Chuẩn hóa văn bản tiếng Việt sang chữ thường không dấu, gom khoảng trắng."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", unidecode(text).lower()).strip()


@lru_cache(maxsize=4)
def load_risk_rules(path: Path = DEFAULT_RISK_RULES_PATH) -> dict[str, Any]:
    """Đọc cấu hình luật nguy cơ cao từ config/risk_rules.yaml."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def classify_needs(
    profile: PatientProfile,
    rules: dict[str, Any] | None = None,
) -> NeedsResult:
    """Phân loại nhu cầu dinh dưỡng từ hồ sơ bệnh nhân theo SPEC mục 6.3."""
    cfg = rules or load_rules()
    needs: list[str] = []
    rule_refs: list[str] = []

    if "t2d" in profile.conditions:
        needs.append("kiem_soat_duong_huyet")
        rule_refs.append("NEED_T2D")
    if "htn" in profile.conditions:
        needs.append("giam_natri")
        rule_refs.append("NEED_HTN")
    if "gout" in profile.conditions:
        needs.append("han_che_purin")
        rule_refs.append("NEED_GOUT")

    bmi = calc_bmi(profile.weight_kg, profile.height_cm)
    bmi_threshold = float(cfg["needs"]["giam_can"]["bmi_threshold"]["value"])
    if "obesity" in profile.conditions or bmi >= bmi_threshold:
        needs.append("giam_can")
        rule_refs.append("NEED_WEIGHT")

    if profile.allergens:
        for allergen in profile.allergens:
            needs.append(f"tranh_di_ung:{allergen}")
        rule_refs.append("NEED_ALLERGY")

    if not needs:
        needs.append("duy_tri_can_bang")
        rule_refs.append("NEED_DEFAULT")

    return NeedsResult(needs=needs, rule_refs=rule_refs)


def _is_benign_bau_occurrence(
    before_raw: str,
    before_words: list[str],
    after_words: list[str],
) -> bool:
    """Kiểm tra vị trí khớp 'bầu'/'bau' có phải món ăn hay thành ngữ vô hại."""
    if before_words and before_words[-1] in _BAU_BEFORE_BENIGN:
        return True
    # Phân biệt "thái bầu" (món ăn, có dấu sắc) với "thai bầu" (thai kỳ)
    raw_before_tokens = re.findall(r"[0-9a-zA-ZÀ-ỹ]+", before_raw.lower())
    if raw_before_tokens and raw_before_tokens[-1] == "thái":
        return True
    if (
        len(before_words) >= 2
        and (before_words[-2], before_words[-1]) in _BAU_BEFORE_BENIGN_BIGRAMS
    ):
        return True
    if after_words and after_words[0] in _BAU_AFTER_BENIGN_SINGLE:
        return True
    if len(after_words) >= 2 and (after_words[0], after_words[1]) in _BAU_AFTER_BENIGN_BIGRAMS:
        return True
    return False


def _has_local_uncertainty(
    before_raw: str,
    before_words: list[str],
    after_words: list[str],
    clause_raw: str,
) -> bool:
    """Phát hiện ngữ cảnh nghi vấn/chưa chắc chắn quanh vị trí khớp."""
    before_window = " ".join(before_words[-7:])
    if _UNCERTAINTY_BEFORE_RE.search(before_window):
        return True
    # Phân biệt "có thể" (khả năng) với "cơ thể" (cơ thể người) bằng chữ có dấu khi có mặt
    before_raw_lower = before_raw.lower()
    if "có thể" in before_raw_lower or (
        "co the" in before_window and "cơ thể" not in before_raw_lower
    ):
        return True
    # Chỉ coi "nghi" đơn lẻ là nghi ngờ khi đứng như động từ nghi ngờ (trước đó không phải "nghỉ")
    if re.search(r"\bnghi\b", before_raw_lower):
        return True

    after_window = " ".join(after_words[:4])
    if _UNCERTAINTY_AFTER_RE.search(after_window):
        return True
    if _QUESTION_PARTICLE_AFTER_RE.match(after_window):
        return True
    if clause_raw.rstrip().endswith("?") and re.search(
        r"\b(?:co phai|phai khong|co\s+(?:mang|co|dang)|lieu)\b",
        normalize_vietnamese_ascii(clause_raw),
    ):
        return True
    return False


def _evaluate_match_occurrence(
    *,
    clause_raw: str,
    before_raw: str,
    after_raw: str,
    kw_norm: str,
    rule_code: str,
    is_unaccented_bau: bool,
) -> Literal["skip", "ambiguous", "confirmed"]:
    """Đánh giá một vị trí khớp duy nhất: bỏ qua, mơ hồ (cần duyệt), hay xác nhận nguy cơ cao."""
    before_norm = normalize_vietnamese_ascii(before_raw)
    after_norm = normalize_vietnamese_ascii(after_raw)
    before_words = before_norm.split()
    after_words = after_norm.split()

    if kw_norm == "bau" and _is_benign_bau_occurrence(before_raw, before_words, after_words):
        return "skip"

    if rule_code == "RISK_EMERGENCY" and kw_norm in _PREVENTABLE_EMERGENCY_KWS:
        if _PREVENTION_BEFORE_RE.search(before_norm):
            return "skip"

    if _has_local_uncertainty(before_raw, before_words, after_words, clause_raw):
        return "ambiguous"

    if _NEGATION_TAIL_RE.search(before_norm):
        return "skip"

    if kw_norm == "co em be":
        has_household = (
            "nha" in before_words[-3:]
            or "trong" in before_words[-2:]
            or "cho" in before_words[-2:]
            or ("gia" in before_words[-4:] and "dinh" in before_words[-3:])
        )
        has_baby_age_after = bool(
            re.match(r"^(?:\d+\s+)?(?:thang|tuoi|an dam|o nha)\b", " ".join(after_words[:4]))
        )
        has_self_or_preg_marker = any(
            w in {"dang", "sap", "toi", "minh", "vo", "em"} for w in before_words[-4:]
        )
        if has_household or has_baby_age_after or not has_self_or_preg_marker:
            return "ambiguous"

    if is_unaccented_bau:
        has_clear_before = bool(before_words and before_words[-1] in _BAU_UNACCENTED_CLEAR_BEFORE)
        has_clear_after = bool(
            after_words
            and (
                after_words[0] in _BAU_UNACCENTED_CLEAR_AFTER
                or after_words[0].isdigit()
            )
        )
        if not (has_clear_before or has_clear_after):
            return "ambiguous"

    return "confirmed"


def assess_text_risk_details(
    text: str,
    risk_rules: dict[str, Any] | None = None,
) -> TextRiskAssessment:
    """Sàng lọc nguy cơ cao trên preferences_text theo từng vị trí khớp và mệnh đề."""
    if not text or not text.strip():
        return TextRiskAssessment(confirmed=RiskResult(high_risk=False))

    cfg = risk_rules or load_risk_rules()
    rules_cfg = cfg["rules"]

    confirmed_reasons: list[str] = []
    confirmed_messages: list[str] = []
    ambiguous_reasons: list[str] = []

    def _add_confirmed(code: str) -> None:
        if code not in confirmed_reasons:
            confirmed_reasons.append(code)
            confirmed_messages.append(rules_cfg[code]["message_vi"])

    clauses = [seg.strip() for seg in _CLAUSE_SPLIT_RE.split(text) if seg and seg.strip()]

    for clause_raw in clauses:
        clause_raw_lower = clause_raw.lower()
        clause_norm = normalize_vietnamese_ascii(clause_raw)
        if not clause_norm:
            continue

        # Xây dựng map vị trí norm -> vị trí gần đúng trong raw bằng tách theo token
        for code, rule_data in rules_cfg.items():
            keywords = sorted(rule_data.get("keywords", []), key=len, reverse=True)
            for kw in keywords:
                kw_lower = kw.lower().strip()
                kw_norm = normalize_vietnamese_ascii(kw)
                if not kw_norm:
                    continue

                if kw_norm == "bau":
                    # 1) Quét chữ "bầu" có dấu trên văn bản gốc trước
                    has_accented_bau = False
                    accented_pat = re.compile(r"(?<![0-9a-zA-ZÀ-ỹ])bầu(?![0-9a-zA-ZÀ-ỹ])")
                    for m in accented_pat.finditer(clause_raw_lower):
                        has_accented_bau = True
                        verdict = _evaluate_match_occurrence(
                            clause_raw=clause_raw,
                            before_raw=clause_raw[: m.start()],
                            after_raw=clause_raw[m.end() :],
                            kw_norm="bau",
                            rule_code=code,
                            is_unaccented_bau=False,
                        )
                        if verdict == "confirmed":
                            _add_confirmed(code)
                        elif verdict == "ambiguous" and code not in ambiguous_reasons:
                            ambiguous_reasons.append(code)

                    # 2) Quét "bau" không dấu khi không có chữ "bầu" có dấu trong mệnh đề
                    if not has_accented_bau:
                        unaccented_pat = re.compile(r"(?<![a-z0-9])bau(?![a-z0-9])")
                        for m in unaccented_pat.finditer(clause_norm):
                            verdict = _evaluate_match_occurrence(
                                clause_raw=clause_raw,
                                before_raw=clause_norm[: m.start()],
                                after_raw=clause_norm[m.end() :],
                                kw_norm="bau",
                                rule_code=code,
                                is_unaccented_bau=True,
                            )
                            if verdict == "confirmed":
                                _add_confirmed(code)
                            elif verdict == "ambiguous" and code not in ambiguous_reasons:
                                ambiguous_reasons.append(code)
                    continue

                # Ưu tiên khớp có dấu trước để bảo toàn ngữ nghĩa ("có thể"/"thái")
                raw_pat = re.compile(
                    rf"(?<![0-9a-zA-ZÀ-ỹ]){re.escape(kw_lower)}(?![0-9a-zA-ZÀ-ỹ])"
                )
                raw_matches = list(raw_pat.finditer(clause_raw_lower))
                if raw_matches:
                    for rm in raw_matches:
                        verdict = _evaluate_match_occurrence(
                            clause_raw=clause_raw,
                            before_raw=clause_raw[: rm.start()],
                            after_raw=clause_raw[rm.end() :],
                            kw_norm=kw_norm,
                            rule_code=code,
                            is_unaccented_bau=False,
                        )
                        if verdict == "confirmed":
                            _add_confirmed(code)
                        elif verdict == "ambiguous" and code not in ambiguous_reasons:
                            ambiguous_reasons.append(code)
                    continue

                pat = re.compile(rf"(?<![a-z0-9]){re.escape(kw_norm)}(?![a-z0-9])")
                for m in pat.finditer(clause_norm):
                    verdict = _evaluate_match_occurrence(
                        clause_raw=clause_raw,
                        before_raw=clause_norm[: m.start()],
                        after_raw=clause_norm[m.end() :],
                        kw_norm=kw_norm,
                        rule_code=code,
                        is_unaccented_bau=False,
                    )
                    if verdict == "confirmed":
                        _add_confirmed(code)
                    elif verdict == "ambiguous" and code not in ambiguous_reasons:
                        ambiguous_reasons.append(code)

        # Kiểm tra cụm "em bé" rời rạc chưa rõ ngữ cảnh (vd: "nấu cho em bé", "nhà có em bé")
        if "RISK_PREG" in rules_cfg and "RISK_PREG" not in confirmed_reasons:
            em_be_pat = re.compile(r"(?<![a-z0-9])em\s+be(?![a-z0-9])")
            for m in em_be_pat.finditer(clause_norm):
                before_s = clause_norm[: m.start()]
                if _NEGATION_TAIL_RE.search(before_s.strip()):
                    continue
                if "RISK_PREG" not in ambiguous_reasons:
                    ambiguous_reasons.append("RISK_PREG")

    # Chỉ giữ ambiguous những mã chưa được xác nhận chắc chắn
    remaining_ambiguous = [c for c in ambiguous_reasons if c not in confirmed_reasons]
    ambiguous_msg = (
        "Ghi chú có thông tin liên quan đến tình trạng nguy cơ cao hoặc đối tượng nhạy cảm "
        "chưa thể tự động xác nhận rõ (ví dụ mang thai/em bé/dấu hiệu nghi ngờ). "
        "Hệ thống tạm dừng lập thực đơn để chuyên gia dinh dưỡng rà soát trực tiếp."
        if remaining_ambiguous
        else ""
    )

    return TextRiskAssessment(
        confirmed=RiskResult(
            high_risk=bool(confirmed_reasons),
            reasons=confirmed_reasons,
            message_vi=" ".join(confirmed_messages),
        ),
        ambiguous_reasons=remaining_ambiguous,
        ambiguous_message_vi=ambiguous_msg,
    )


def assess_risk(
    profile: PatientProfile,
    risk_rules: dict[str, Any] | None = None,
) -> RiskResult:
    """Sàng lọc ca nguy cơ cao theo SPEC mục 6.4; trả về RiskResult."""
    cfg = risk_rules or load_risk_rules()
    thresholds = cfg["thresholds"]
    rules_cfg = cfg["rules"]

    reasons: list[str] = []
    messages: list[str] = []

    def _add(code: str) -> None:
        if code not in reasons:
            reasons.append(code)
            messages.append(rules_cfg[code]["message_vi"])

    if profile.pregnancy:
        _add("RISK_PREG")
    if profile.lactating:
        _add("RISK_LACT")
    if profile.age < int(thresholds["minor_age"]):
        _add("RISK_MINOR")
    if profile.ckd_stage >= int(thresholds["ckd_stage_min"]) or profile.dialysis:
        _add("RISK_CKD")
    if profile.eating_disorder:
        _add("RISK_ED")

    bmi = calc_bmi(profile.weight_kg, profile.height_cm)
    bmi_low = float(thresholds["bmi_low"]["value"])
    if bmi < bmi_low:
        _add("RISK_BMI_LOW")

    text_res = assess_text_risk_details(profile.preferences_text, risk_rules=cfg).confirmed
    for code in text_res.reasons:
        _add(code)

    return RiskResult(
        high_risk=bool(reasons),
        reasons=reasons,
        message_vi=" ".join(messages),
    )
