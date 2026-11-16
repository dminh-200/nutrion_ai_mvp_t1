"""Truy xuất đoạn hướng dẫn dinh dưỡng từ ChromaDB và lọc nội dung thuốc/lạc đề (SPEC Phần 8)."""

import re
from pathlib import Path
from typing import Any

import chromadb
from unidecode import unidecode

from config.settings import get_settings
from core.schemas import GuidelineSnippet
from rag.embeddings import get_embedder
from rag.ingest import COLLECTION_NAME

_KNOWN_DISEASES = frozenset({"t2d", "htn", "gout", "obesity"})
_E5_DEFAULT_MIN_SCORE = 0.82
_E5_OUT_OF_DOMAIN_MIN_SCORE = 0.88

_DOMAIN_QUERY_RE = re.compile(
    r"\b(?:"
    r"tieu\s+duong|dai\s+thao\s+duong|duong\s+huyet|glucose|glycemic|diabetes|"
    r"tang\s+huyet\s+ap|huyet\s+ap|hypertension|dash|"
    r"gout|gut|acid\s+uric|urate|urat|purin|"
    r"beo\s+phi|thua\s+can|obesity|weight\s+loss|giam\s+can|overweight|"
    r"dinh\s+duong|nutrition|diet|khau\s+phan|thuc\s+don|bua\s+an|meal|food|"
    r"thuc\s+pham|mon\s+an|an\s+uong|an\s+kieng|calo|kcal|energy|nang\s+luong|"
    r"calorie|glucid|carb|tinh\s+bot|protein|chat\s+dam|lipid|chat\s+beo|"
    r"cholesterol|chat\s+xo|fiber|muoi|salt|natri|sodium|kali|potassium|"
    r"duong\s+kinh|free\s+sugars|sweetened|sugar|rau\s+xanh|trai\s+cay|"
    r"ngu\s+coc|thit|hai\s+san|sua|trung|nuoc\s+loc|nuoc\s+uong|water|"
    r"ruou|bia|ethanol|di\s+ung|allergy|who|ada"
    r")\b",
    flags=re.IGNORECASE,
)

_DRUG_OR_BIBLIO_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:"
        r"insulin|metformin|glibenclamide|glimepiride|gliclazide|sitagliptin|"
        r"empagliflozin|dapagliflozin|losartan|amlodipine|valsartan|enalapril|"
        r"lisinopril|nifedipine|thiazid\w*|allopurinol|febuxostat|colchicin\w*|"
        r"probenecid|prednisolon\w*|corticoid|nsaid|atorvastatin|rosuvastatin|"
        r"statin|aspirin|warfarin|ethambutol|pyrazinamid\w*"
        r")\b"
    ),
    re.compile(
        r"\bthu\s*oc\s+(?:ti\s*em|u\s*ong|ch\s*ich|ch\s*ong\s+viem|giam\s+dau|"
        r"ha\s+acid\s+uric|ha\s+duong|ha\s+huyet\s+ap|ch\s*ong\s+lao|uc\s+che|"
        r"l\s*oi\s+ti\s*eu|khang\s+sinh|dieu\s+tri|tay\s+y)\b"
    ),
    re.compile(
        r"\b(?:mui\s+(?:ti\s*em|ch\s*ich|dieu\s+tri|thu\s*oc|ke\s+tiep|tiep\s+theo)|"
        r"cu\s+(?:ti\s*em|ch\s*ich)|li\s*eu\s+(?:ti\s*em|dieu\s+tri|thu\s*oc))\b"
    ),
    re.compile(
        r"\b(?:ng\s*ung|d\s*ung|bo|cat|thay(?:\s+the)?|tu\s+bo|tam\s+(?:dung|ng\s*ung)|"
        r"ch\s*inh|dieu\s+ch\s*inh|ke|tang|giam|nhay\s+qua|quen)\s+"
        r"(?:viec\s+)?(?:su\s+dung|u\s*ong|ti\s*em|ch\s*ich)?\s*"
        r"(?:thu\s*oc|insulin|phac\s+do|li\s*eu|mui\s+(?:ti\s*em|ch\s*ich|dieu\s+tri)|"
        r"cu\s+(?:ti\s*em|ch\s*ich)|vien\s+thu\s*oc)\b"
    ),
    re.compile(r"\b(?:ke\s+don|ke\s+toa|chinh\s+li\s*eu|dieu\s+tri\s+noi\s+khoa)\b"),
    re.compile(
        r"\b(?:li\s*eu\s+\d+\s*(?:mg|mcg|iu|ui|vien)|"
        r"\d+\s*(?:mg|mcg|iu|ui|vien)\s*/\s*(?:ngay|24\s*h))\b"
    ),
    re.compile(
        r"\b(?:nha\s+xu\s*at\s+b\s*an|giao\s+trinh\s+chuyen\s+nganh|edition\s+\d+)\b|"
        r"\b(?:pp|tr)\.\s*\d+\s*[-–]\s*\d+\b"
    ),
)

_OCR_COLLAPSE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bthu\s+oc\b"), "thuoc"),
    (re.compile(r"\bli\s+eu\b"), "lieu"),
    (re.compile(r"\bch\s+ong\b"), "chong"),
    (re.compile(r"\bng\s+ung\b"), "ngung"),
    (re.compile(r"\bu\s+ong\b"), "uong"),
    (re.compile(r"\bl\s+oi\s+ti\s+eu\b"), "loi tieu"),
    (re.compile(r"\bd\s+ung\b"), "dung"),
    (re.compile(r"\bch\s+inh\b"), "chinh"),
    (re.compile(r"\bb\s+enh\b"), "benh"),
)


def _normalize_for_match(text: str) -> str:
    """Chuẩn hóa không dấu và gộp lỗi tách dấu cách PDF phổ biến để so khớp an toàn."""
    norm = re.sub(r"\s+", " ", unidecode(text).lower()).strip()
    for pat, repl in _OCR_COLLAPSE_PATTERNS:
        norm = pat.sub(repl, norm)
    return norm


def is_nutrition_relevant_query(query: str, disease: str | None = None) -> bool:
    """Kiểm tra câu truy vấn có thuộc miền dinh dưỡng/bệnh lý dinh dưỡng hay không."""
    if disease and disease.strip().lower() in _KNOWN_DISEASES:
        return True
    if not query or not query.strip():
        return False
    norm = _normalize_for_match(query)
    return bool(_DOMAIN_QUERY_RE.search(norm))


def _is_medication_or_biblio_segment(segment: str) -> bool:
    """Kiểm tra đoạn/câu có chứa tên thuốc, chỉnh/ngừng thuốc hay mục lục trích dẫn."""
    norm = _normalize_for_match(segment)
    if not norm:
        return False
    return any(pat.search(norm) for pat in _DRUG_OR_BIBLIO_PATTERNS)


def sanitize_snippet_text(text: str) -> str:
    """Loại bỏ các câu/dòng chỉ dẫn thuốc hoặc trích dẫn thư mục khỏi đoạn RAG."""
    if not text or not text.strip():
        return ""
    kept_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", line) if s.strip()]
        kept_sents = [s for s in sentences if not _is_medication_or_biblio_segment(s)]
        if kept_sents:
            kept_lines.append(" ".join(kept_sents))
    cleaned = "\n".join(kept_lines).strip()
    return cleaned if len(cleaned) >= 15 else ""


def sanitize_guideline_snippets(
    snippets: list[GuidelineSnippet],
) -> list[GuidelineSnippet]:
    """Lọc an toàn danh sách GuidelineSnippet trước khi đưa vào prompt LLM giải thích."""
    sanitized: list[GuidelineSnippet] = []
    for snip in snippets:
        clean_text = sanitize_snippet_text(snip.text)
        if not clean_text:
            continue
        sanitized.append(snip.model_copy(update={"text": clean_text}))
    return sanitized


def retrieve(
    query: str,
    disease: str | None = None,
    k: int = 4,
    min_score: float | None = None,
    chroma_dir: Path | None = None,
    use_fake_embedder: bool = False,
) -> list[GuidelineSnippet]:
    """Truy xuất top-k đoạn hướng dẫn từ ChromaDB kèm nguồn, số trang và lọc an toàn."""
    if not query.strip() or k <= 0:
        return []

    settings = get_settings()
    threshold = settings.RAG_MIN_SCORE if min_score is None else min_score
    if min_score is not None or use_fake_embedder:
        effective_min_score = threshold
    elif is_nutrition_relevant_query(query, disease):
        effective_min_score = max(threshold, _E5_DEFAULT_MIN_SCORE)
    else:
        effective_min_score = max(threshold, _E5_OUT_OF_DOMAIN_MIN_SCORE)

    target_chroma = Path(chroma_dir or settings.CHROMA_DIR)
    if not target_chroma.exists():
        return []

    client = chromadb.PersistentClient(path=str(target_chroma))
    existing_names = [c.name for c in client.list_collections()]
    if COLLECTION_NAME not in existing_names:
        return []

    collection = client.get_collection(name=COLLECTION_NAME)
    total_count = collection.count()
    if total_count == 0:
        return []

    embedder = get_embedder(use_fake=use_fake_embedder)
    q_vec = embedder.embed_queries([query])[0]

    where_filter: dict[str, Any] | None = None
    if disease:
        clean_disease = disease.strip().lower()
        if clean_disease:
            where_filter = {
                "$or": [
                    {"disease": clean_disease},
                    {f"disease_{clean_disease}": True},
                ]
            }

    n_results = min(max(k * 4, 16), total_count)
    query_kwargs: dict[str, Any] = {
        "query_embeddings": [q_vec],
        "n_results": n_results,
        "include": ["documents", "metadatas", "distances"],
    }
    if where_filter is not None:
        query_kwargs["where"] = where_filter

    raw: dict[str, Any] = collection.query(**query_kwargs)

    docs = raw.get("documents", [[]])[0]
    metas = raw.get("metadatas", [[]])[0]
    dists = raw.get("distances", [[]])[0]

    snippets: list[GuidelineSnippet] = []
    for doc, meta, dist in zip(docs, metas, dists, strict=False):
        score = round(max(0.0, min(1.0, 1.0 - float(dist))), 4)
        if score < effective_min_score:
            continue
        clean_doc = sanitize_snippet_text(str(doc))
        if not clean_doc:
            continue
        snippets.append(
            GuidelineSnippet(
                text=clean_doc,
                source_name=str(meta.get("source_name", "")),
                year=meta.get("year", 2024),
                page=meta.get("page", 1),
                disease=str(meta.get("disease", "")),
                score=score,
            )
        )
        if len(snippets) >= k:
            break

    return snippets


retrieve_guidelines = retrieve
