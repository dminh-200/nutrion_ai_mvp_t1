"""Nạp tài liệu hướng dẫn (PDF/TXT) vào ChromaDB và đồng bộ bảng guideline_doc."""

import argparse
import hashlib
import re
from pathlib import Path
from typing import Any

import chromadb
import yaml
from pypdf import PdfReader
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from config.settings import get_settings
from db.init_db import init_db
from db.models import GuidelineDoc
from db.session import get_engine
from rag.embeddings import get_embedder

COLLECTION_NAME = "guidelines"
DEFAULT_CHUNK_SIZE = 700
DEFAULT_CHUNK_OVERLAP = 100
MAX_CHUNK_SIZE = 800
_SENTENCE_BOUNDARY_RE = re.compile(r"(?:\n\s*\n|(?<=[.!?…])\s+|\n)")


def _make_chunk_id(file_name: str, page: int, offset: int) -> str:
    """Tạo ID chunk tất định từ hash(file_name, page, offset)."""
    raw = f"{file_name}::{page}::{offset}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _normalize_diseases(raw_diseases: Any) -> list[str]:
    """Chuẩn hóa trường diseases từ YAML list hoặc chuỗi CSV thành list mã bệnh sạch."""
    if raw_diseases is None:
        return []
    items: list[str] = []
    if isinstance(raw_diseases, (list, tuple, set)):
        for elem in raw_diseases:
            items.extend(str(elem).split(","))
    else:
        cleaned = str(raw_diseases).strip().strip("[]")
        items.extend(cleaned.split(","))

    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        code = item.strip().strip("'\"").lower()
        if code and code not in seen:
            seen.add(code)
            result.append(code)
    return result


def _extract_pages(file_path: Path) -> tuple[list[tuple[int, str]], int]:
    """Trích xuất danh sách (số_trang, nội_dung) và đếm số trang lỗi từ PDF hoặc TXT."""
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        try:
            reader = PdfReader(str(file_path))
        except Exception:
            return [], 1

        pages: list[tuple[int, str]] = []
        error_pages = 0
        for idx, page in enumerate(reader.pages, start=1):
            try:
                text = (page.extract_text() or "").strip()
            except Exception:
                error_pages += 1
                continue
            if text:
                pages.append((idx, text))
        return pages, error_pages

    try:
        raw = file_path.read_text(encoding="utf-8")
    except Exception:
        return [], 1

    parts = re.split(r"---PAGE\s+(\d+)---", raw)
    if len(parts) > 1:
        pages = []
        for i in range(1, len(parts), 2):
            page_num = int(parts[i])
            content = parts[i + 1].strip()
            if content:
                pages.append((page_num, content))
        return pages, 0

    cleaned = raw.strip()
    if not cleaned:
        return [], 0
    return [(1, cleaned)], 0


def _find_split_end(text: str, start: int, chunk_size: int, max_size: int) -> int:
    """Tìm vị trí kết thúc chunk ưu tiên ranh giới câu/đoạn trong khoảng cho phép."""
    n = len(text)
    if n - start <= max_size:
        return n

    window_end = min(n, start + max_size)
    target = min(n, start + chunk_size)
    soft_min = start + max(1, int(chunk_size * 0.75))

    segment = text[start:window_end]
    candidates = [start + m.end() for m in _SENTENCE_BOUNDARY_RE.finditer(segment)]

    in_preferred = [pos for pos in candidates if soft_min <= pos <= window_end]
    if in_preferred:
        # Ưu tiên ranh giới gần chunk_size (600-800 ký tự)
        return min(in_preferred, key=lambda pos: abs(pos - target))

    fallback = [pos for pos in candidates if start + int(chunk_size * 0.4) <= pos <= window_end]
    if fallback:
        return fallback[-1]

    # Không có ranh giới câu: tránh cắt giữa từ nếu có khoảng trắng gần target
    ws_pos = text.rfind(" ", soft_min, window_end)
    if ws_pos > start:
        return ws_pos + 1

    return target


def _chunk_text_with_offsets(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[tuple[int, str]]:
    """Chia văn bản thành (offset, chunk) dài ~600-800 ký tự, chồng lấn 100, giữ trọn câu."""
    cleaned = text.strip()
    if not cleaned:
        return []

    max_size = max(chunk_size, MAX_CHUNK_SIZE) if chunk_size <= MAX_CHUNK_SIZE else chunk_size
    if len(cleaned) <= max_size:
        return [(0, cleaned)]

    chunks: list[tuple[int, str]] = []
    start = 0
    n = len(cleaned)
    while start < n:
        end = _find_split_end(cleaned, start, chunk_size=chunk_size, max_size=max_size)
        piece = cleaned[start:end].strip()
        if piece:
            chunks.append((start, piece))
        if end >= n:
            break
        next_start = max(start + 1, end - overlap)
        while next_start < end and cleaned[next_start].isspace():
            next_start += 1
        if next_start <= start:
            next_start = start + 1
        start = next_start
    return chunks


def _chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Chia đoạn văn bản thành các chunk có chồng lấp."""
    return [chunk for _, chunk in _chunk_text_with_offsets(text, chunk_size, overlap)]


def ingest_guidelines(
    guidelines_dir: Path = Path("data/guidelines"),
    chroma_dir: Path | None = None,
    engine: Engine | None = None,
    use_fake_embedder: bool = False,
    rebuild: bool = False,
) -> dict[str, int]:
    """Đọc sources.yaml, nạp chunk vào ChromaDB và đồng bộ bảng guideline_doc."""
    sources_path = guidelines_dir / "sources.yaml"
    if not sources_path.exists():
        raise FileNotFoundError(f"Không tìm thấy {sources_path}")

    sources: list[dict[str, Any]] = yaml.safe_load(sources_path.read_text(encoding="utf-8")) or []
    target_chroma = str(chroma_dir or get_settings().CHROMA_DIR)
    Path(target_chroma).mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=target_chroma)
    if rebuild:
        existing_cols = [c.name for c in client.list_collections()]
        if COLLECTION_NAME in existing_cols:
            client.delete_collection(name=COLLECTION_NAME)

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    embedder = get_embedder(use_fake=use_fake_embedder)

    target_engine = engine or get_engine()
    init_db(target_engine)

    total_docs = 0
    total_chunks = 0
    total_error_pages = 0

    with Session(target_engine) as session:
        existing = {d.file_name: d for d in session.scalars(select(GuidelineDoc)).all()}
        active_files: set[str] = set()

        for src in sources:
            file_name = src["file_name"]
            file_path = guidelines_dir / file_name
            if not file_path.exists():
                continue

            active_files.add(file_name)
            disease_list = _normalize_diseases(src.get("diseases"))
            diseases_str = ",".join(disease_list)

            if file_name in existing:
                doc_row = existing[file_name]
                doc_row.source_name = src.get("source_name", file_name)
                doc_row.organization = src.get("organization", "")
                doc_row.year = int(src.get("year", 2024))
                doc_row.url = src.get("url", "")
                doc_row.diseases = diseases_str
                doc_row.license_note = src.get("license_note", "")
            else:
                session.add(
                    GuidelineDoc(
                        file_name=file_name,
                        source_name=src.get("source_name", file_name),
                        organization=src.get("organization", ""),
                        year=int(src.get("year", 2024)),
                        url=src.get("url", ""),
                        diseases=diseases_str,
                        license_note=src.get("license_note", ""),
                    )
                )
            total_docs += 1

            pages, error_pages = _extract_pages(file_path)
            total_error_pages += error_pages

            ids: list[str] = []
            docs: list[str] = []
            metas: list[dict[str, Any]] = []
            for page_num, page_text in pages:
                for offset, chunk in _chunk_text_with_offsets(page_text):
                    chunk_id = _make_chunk_id(file_name, page_num, offset)
                    meta: dict[str, Any] = {
                        "file_name": file_name,
                        "source_name": src.get("source_name", file_name),
                        "year": int(src.get("year", 2024)),
                        "page": page_num,
                        "disease": diseases_str,
                    }
                    for d in disease_list:
                        meta[f"disease_{d}"] = True
                    ids.append(chunk_id)
                    docs.append(chunk)
                    metas.append(meta)

            if ids:
                embeddings = embedder.embed_passages(docs)
                collection.upsert(
                    ids=ids,
                    documents=docs,
                    metadatas=metas,
                    embeddings=embeddings,
                )
                total_chunks += len(ids)

        if rebuild:
            for fname, doc_row in existing.items():
                if fname not in active_files:
                    session.delete(doc_row)

        session.commit()

    return {"docs": total_docs, "chunks": total_chunks, "error_pages": total_error_pages}


def main() -> None:
    """Điểm vào CLI cho lệnh nạp tài liệu RAG."""
    parser = argparse.ArgumentParser(description="Nạp tài liệu hướng dẫn vào ChromaDB.")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Xóa collection cũ và nạp lại toàn bộ tài liệu từ đầu.",
    )
    parser.add_argument(
        "--fake",
        action="store_true",
        help="Dùng FakeEmbedder thay cho mô hình local (phục vụ kiểm thử offline).",
    )
    args = parser.parse_args()
    res = ingest_guidelines(rebuild=args.rebuild, use_fake_embedder=args.fake)
    print(
        f"Đã nạp {res['docs']} tài liệu, {res['chunks']} chunk, "
        f"{res['error_pages']} trang lỗi vào ChromaDB."
    )


if __name__ == "__main__":
    main()
