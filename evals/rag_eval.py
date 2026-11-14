"""Đánh giá khả năng truy xuất RAG bằng chỉ số retrieval_hit@4."""

import argparse
import json
from pathlib import Path
from typing import Any

from core.schemas import GuidelineSnippet
from rag.retrieve import retrieve

QUESTIONS_PATH = Path("evals/rag_questions.json")


def _snippet_matches(
    snippet: GuidelineSnippet,
    expected_disease: str | None,
    expected_keywords: list[str],
) -> bool:
    """Kiểm tra 1 đoạn trích có đúng disease và chứa ít nhất 1 từ khóa kỳ vọng."""
    if expected_disease:
        snippet_diseases = [d.strip() for d in snippet.disease.split(",") if d.strip()]
        if expected_disease not in snippet_diseases:
            return False
    text_lower = snippet.text.lower()
    return any(kw.lower() in text_lower for kw in expected_keywords)


def evaluate_retrieval(
    questions_path: Path = QUESTIONS_PATH,
    k: int = 4,
    min_score: float | None = None,
    chroma_dir: Path | None = None,
    use_fake_embedder: bool = False,
) -> dict[str, Any]:
    """Tính tỷ lệ retrieval_hit@k trên bộ câu hỏi đánh giá (tổng thể và theo bệnh)."""
    questions = json.loads(questions_path.read_text(encoding="utf-8"))
    if not questions:
        return {"total": 0, "hits": 0, "hit_at_k": 0.0, "by_disease": {}, "missed": []}

    hits = 0
    by_disease: dict[str, dict[str, int]] = {}
    missed: list[str] = []

    for q in questions:
        disease = q.get("disease")
        d_key = str(disease or "unknown")
        if d_key not in by_disease:
            by_disease[d_key] = {"total": 0, "hits": 0}
        by_disease[d_key]["total"] += 1

        snippets = retrieve(
            query=q["query"],
            disease=disease,
            k=k,
            min_score=min_score,
            chroma_dir=chroma_dir,
            use_fake_embedder=use_fake_embedder,
        )
        expected = list(q.get("expected_keywords", []))
        if any(_snippet_matches(s, disease, expected) for s in snippets):
            hits += 1
            by_disease[d_key]["hits"] += 1
        else:
            missed.append(str(q.get("id", q["query"])))

    total = len(questions)
    return {
        "total": total,
        "hits": hits,
        "hit_at_k": round(hits / total, 4) if total else 0.0,
        "by_disease": by_disease,
        "missed": missed,
    }


def main() -> None:
    """Điểm vào CLI cho script đánh giá retrieval_hit@k."""
    parser = argparse.ArgumentParser(description="Đánh giá RAG bằng retrieval_hit@4.")
    parser.add_argument("--k", type=int, default=4, help="Số đoạn truy xuất tối đa (mặc định 4).")
    parser.add_argument(
        "--min-score",
        type=float,
        default=None,
        help="Ngưỡng điểm tối thiểu (mặc định đọc từ Settings.RAG_MIN_SCORE).",
    )
    parser.add_argument(
        "--use-fake",
        action="store_true",
        help="Dùng FakeEmbedder (chỉ dùng cho kiểm thử offline).",
    )
    args = parser.parse_args()

    res = evaluate_retrieval(
        k=args.k,
        min_score=args.min_score,
        use_fake_embedder=args.use_fake,
    )
    print(f"retrieval_hit@{args.k}: {res['hits']}/{res['total']} ({res['hit_at_k'] * 100:.1f}%)")
    for disease, stats in res["by_disease"].items():
        rate = (stats["hits"] / stats["total"] * 100) if stats["total"] else 0.0
        print(f"  - {disease}: {stats['hits']}/{stats['total']} ({rate:.1f}%)")
    if res["missed"]:
        print(f"Chưa đạt: {', '.join(res['missed'])}")


if __name__ == "__main__":
    main()
