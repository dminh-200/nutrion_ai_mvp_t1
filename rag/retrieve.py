"""Truy xuất đoạn hướng dẫn dinh dưỡng từ ChromaDB theo SPEC Phần 8."""

from pathlib import Path
from typing import Any

import chromadb

from config.settings import get_settings
from core.schemas import GuidelineSnippet
from rag.embeddings import get_embedder
from rag.ingest import COLLECTION_NAME


def retrieve(
    query: str,
    disease: str | None = None,
    k: int = 4,
    min_score: float | None = None,
    chroma_dir: Path | None = None,
    use_fake_embedder: bool = False,
) -> list[GuidelineSnippet]:
    """Truy xuất top-k đoạn hướng dẫn từ ChromaDB kèm nguồn và số trang."""
    if not query.strip() or k <= 0:
        return []

    settings = get_settings()
    threshold = settings.RAG_MIN_SCORE if min_score is None else min_score
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

    n_results = min(k, total_count)
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
        if score < threshold:
            continue
        snippets.append(
            GuidelineSnippet(
                text=doc,
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
