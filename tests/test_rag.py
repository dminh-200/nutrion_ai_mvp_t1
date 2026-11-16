"""Kiểm thử pipeline RAG (ingest + retrieve + eval) với embedding giả và model thật."""

import json
from pathlib import Path

import chromadb
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import GuidelineDoc
from db.session import create_db_engine
from evals.rag_eval import evaluate_retrieval
from rag.embeddings import get_embedder
from rag.ingest import (
    COLLECTION_NAME,
    _chunk_text_with_offsets,
    _make_chunk_id,
    _normalize_diseases,
    ingest_guidelines,
)
from rag.retrieve import retrieve

FIXTURES_DIR = Path("tests/fixtures")


def test_rag_ingest_and_retrieve_fake_embedder(tmp_path: Path) -> None:
    """Test nhanh dùng FakeEmbedder với bộ fixture 4 bệnh trong tests/fixtures."""
    chroma_dir = tmp_path / "chroma"
    engine = create_db_engine(f"sqlite:///{tmp_path / 'rag.db'}")

    res = ingest_guidelines(
        guidelines_dir=FIXTURES_DIR,
        chroma_dir=chroma_dir,
        engine=engine,
        use_fake_embedder=True,
    )
    assert res["docs"] == 1
    assert res["chunks"] == 4
    assert res["error_pages"] == 0

    snippets = retrieve(
        query="người bị gout nên hạn chế thực phẩm nào",
        disease="gout",
        k=2,
        min_score=0.0,
        chroma_dir=chroma_dir,
        use_fake_embedder=True,
    )
    assert len(snippets) >= 1
    assert snippets[0].source_name == "Tài liệu mẫu 4 bệnh (Fixture)"
    assert snippets[0].page == 1
    assert "purin" in snippets[0].text.lower()


def test_rag_normalize_diseases_yaml_list_and_csv(tmp_path: Path) -> None:
    """Chuẩn hóa diseases dù viết dạng YAML list hay chuỗi CSV và lọc đúng bằng where."""
    assert _normalize_diseases(["t2d", "obesity"]) == ["t2d", "obesity"]
    assert _normalize_diseases("t2d, obesity, t2d") == ["t2d", "obesity"]
    assert _normalize_diseases(None) == []

    guidelines_dir = tmp_path / "guidelines"
    guidelines_dir.mkdir()
    (guidelines_dir / "ada.txt").write_text(
        "Hướng dẫn ADA cho tiểu đường type 2 và béo phì: kiểm soát năng lượng.",
        encoding="utf-8",
    )
    (guidelines_dir / "gout.txt").write_text(
        "Hướng dẫn bệnh gút: hạn chế purin.",
        encoding="utf-8",
    )
    (guidelines_dir / "sources.yaml").write_text(
        "- file_name: ada.txt\n"
        '  source_name: "ADA"\n'
        "  year: 2026\n"
        '  diseases: ["t2d", "obesity"]\n'
        "- file_name: gout.txt\n"
        '  source_name: "BYT Gout"\n'
        "  year: 2016\n"
        '  diseases: "gout"\n',
        encoding="utf-8",
    )

    chroma_dir = tmp_path / "chroma_norm"
    engine = create_db_engine(f"sqlite:///{tmp_path / 'rag_norm.db'}")
    ingest_guidelines(
        guidelines_dir=guidelines_dir,
        chroma_dir=chroma_dir,
        engine=engine,
        use_fake_embedder=True,
    )

    t2d_res = retrieve(
        query="tiểu đường kiểm soát năng lượng",
        disease="t2d",
        k=2,
        min_score=0.0,
        chroma_dir=chroma_dir,
        use_fake_embedder=True,
    )
    obesity_res = retrieve(
        query="béo phì kiểm soát năng lượng",
        disease="obesity",
        k=2,
        min_score=0.0,
        chroma_dir=chroma_dir,
        use_fake_embedder=True,
    )
    assert len(t2d_res) == 1
    assert t2d_res[0].source_name == "ADA"
    assert t2d_res[0].disease == "t2d,obesity"
    assert len(obesity_res) == 1
    assert obesity_res[0].source_name == "ADA"


def test_rag_deterministic_id_and_guideline_doc_sync(tmp_path: Path) -> None:
    """Nạp lại cùng tài liệu không tạo chunk trùng và đồng bộ bảng guideline_doc."""
    assert _make_chunk_id("a.pdf", 1, 0) == _make_chunk_id("a.pdf", 1, 0)
    assert _make_chunk_id("a.pdf", 1, 0) != _make_chunk_id("a.pdf", 1, 100)
    assert get_embedder(use_fake=True) is get_embedder(use_fake=True)

    guidelines_dir = tmp_path / "guidelines"
    guidelines_dir.mkdir()
    (guidelines_dir / "sample_guideline.txt").write_text(
        (FIXTURES_DIR / "sample_guideline.txt").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    sources_path = guidelines_dir / "sources.yaml"
    sources_path.write_text(
        "- file_name: sample_guideline.txt\n"
        "  source_name: Nguồn v1\n"
        "  year: 2023\n"
        "  diseases: gout,htn\n",
        encoding="utf-8",
    )

    chroma_dir = tmp_path / "chroma"
    engine = create_db_engine(f"sqlite:///{tmp_path / 'rag_sync.db'}")

    first = ingest_guidelines(
        guidelines_dir=guidelines_dir,
        chroma_dir=chroma_dir,
        engine=engine,
        use_fake_embedder=True,
    )

    sources_path.write_text(
        "- file_name: sample_guideline.txt\n"
        "  source_name: Nguồn v2\n"
        "  year: 2024\n"
        '  diseases: ["gout", "htn"]\n',
        encoding="utf-8",
    )
    second = ingest_guidelines(
        guidelines_dir=guidelines_dir,
        chroma_dir=chroma_dir,
        engine=engine,
        use_fake_embedder=True,
    )

    assert first["chunks"] == second["chunks"]
    client = chromadb.PersistentClient(path=str(chroma_dir))
    collection = client.get_collection(COLLECTION_NAME)
    assert collection.count() == first["chunks"]

    with Session(engine) as session:
        rows = session.scalars(select(GuidelineDoc)).all()
        assert len(rows) == 1
        assert rows[0].source_name == "Nguồn v2"
        assert rows[0].year == 2024
        assert rows[0].diseases == "gout,htn"


def test_rag_where_filter_min_score_and_rebuild(tmp_path: Path) -> None:
    """Kiểm tra lọc disease bằng where, ngưỡng min_score và cờ rebuild."""
    guidelines_dir = tmp_path / "guidelines"
    guidelines_dir.mkdir()
    (guidelines_dir / "gout.txt").write_text(
        "Người bệnh gout cần hạn chế nội tạng động vật giàu purin và bia rượu.",
        encoding="utf-8",
    )
    (guidelines_dir / "htn.txt").write_text(
        "Người tăng huyết áp cần giảm natri dưới 2000 mg mỗi ngày.",
        encoding="utf-8",
    )
    sources_path = guidelines_dir / "sources.yaml"
    sources_path.write_text(
        "- file_name: gout.txt\n"
        "  source_name: Tài liệu Gout\n"
        "  year: 2024\n"
        "  diseases: gout\n"
        "- file_name: htn.txt\n"
        "  source_name: Tài liệu HTN\n"
        "  year: 2024\n"
        "  diseases: htn\n",
        encoding="utf-8",
    )

    chroma_dir = tmp_path / "chroma"
    engine = create_db_engine(f"sqlite:///{tmp_path / 'rag_filter.db'}")
    ingest_guidelines(
        guidelines_dir=guidelines_dir,
        chroma_dir=chroma_dir,
        engine=engine,
        use_fake_embedder=True,
    )

    gout_res = retrieve(
        query="hạn chế purin cho người bệnh gout",
        disease="gout",
        k=4,
        min_score=0.0,
        chroma_dir=chroma_dir,
        use_fake_embedder=True,
    )
    assert len(gout_res) == 1
    assert gout_res[0].source_name == "Tài liệu Gout"

    # Bệnh không có trong tài liệu -> trả danh sách rỗng
    empty_disease = retrieve(
        query="thực đơn giảm cân",
        disease="obesity",
        k=4,
        min_score=0.0,
        chroma_dir=chroma_dir,
        use_fake_embedder=True,
    )
    assert empty_disease == []

    # Ngưỡng min_score cao hơn mọi kết quả -> trả danh sách rỗng (không bịa)
    below_threshold = retrieve(
        query="gout",
        disease="gout",
        k=4,
        min_score=0.99,
        chroma_dir=chroma_dir,
        use_fake_embedder=True,
    )
    assert below_threshold == []

    # Rebuild chỉ còn htn.txt
    sources_path.write_text(
        "- file_name: htn.txt\n"
        "  source_name: Tài liệu HTN\n"
        "  year: 2024\n"
        "  diseases: htn\n",
        encoding="utf-8",
    )
    res_rebuild = ingest_guidelines(
        guidelines_dir=guidelines_dir,
        chroma_dir=chroma_dir,
        engine=engine,
        use_fake_embedder=True,
        rebuild=True,
    )
    assert res_rebuild["docs"] == 1
    assert (
        retrieve(
            query="purin",
            disease="gout",
            k=4,
            min_score=0.0,
            chroma_dir=chroma_dir,
            use_fake_embedder=True,
        )
        == []
    )


def test_rag_chunking_respects_size_and_sentence_boundary() -> None:
    """Tách chunk trong khoảng 600-800 ký tự, có chồng lấn và giữ trọn câu khi có thể."""
    sentence = "Người bệnh cần duy trì chế độ ăn cân đối và giàu chất xơ mỗi ngày. "
    text = sentence * 28  # ~1876 ký tự
    chunks = _chunk_text_with_offsets(text, chunk_size=700, overlap=100)

    assert len(chunks) >= 3
    for idx, (offset, chunk) in enumerate(chunks):
        assert offset >= 0
        assert len(chunk) <= 800
        if idx < len(chunks) - 1:
            assert 500 <= len(chunk) <= 800
            assert chunk.endswith(".")


def test_rag_questions_distribution_and_eval_fake(tmp_path: Path) -> None:
    """Đảm bảo rag_questions.json có 20 câu (5 mỗi bệnh) và rag_eval chạy đúng trên fixture."""
    questions = json.loads(Path("evals/rag_questions.json").read_text(encoding="utf-8"))
    assert len(questions) == 20
    counts: dict[str, int] = {}
    for q in questions:
        assert q.get("query")
        assert q.get("expected_keywords")
        counts[q["disease"]] = counts.get(q["disease"], 0) + 1
    assert counts == {"t2d": 5, "htn": 5, "gout": 5, "obesity": 5}

    fixture_questions = [
        {
            "id": "F1",
            "query": "người bị gout nên hạn chế thực phẩm giàu purin",
            "disease": "gout",
            "expected_keywords": ["purin"],
        },
        {
            "id": "F2",
            "query": "tăng huyết áp giảm natri dưới 2000 mg",
            "disease": "htn",
            "expected_keywords": ["natri", "2000"],
        },
        {
            "id": "F3",
            "query": "tiểu đường type 2 ưu tiên ngũ cốc nguyên hạt chất xơ",
            "disease": "t2d",
            "expected_keywords": ["chất xơ"],
        },
        {
            "id": "F4",
            "query": "béo phì kiểm soát năng lượng 500 kcal",
            "disease": "obesity",
            "expected_keywords": ["500"],
        },
    ]
    q_path = tmp_path / "fixture_questions.json"
    q_path.write_text(json.dumps(fixture_questions, ensure_ascii=False), encoding="utf-8")

    chroma_dir = tmp_path / "chroma_eval"
    engine = create_db_engine(f"sqlite:///{tmp_path / 'rag_eval.db'}")
    ingest_guidelines(
        guidelines_dir=FIXTURES_DIR,
        chroma_dir=chroma_dir,
        engine=engine,
        use_fake_embedder=True,
    )
    res = evaluate_retrieval(
        questions_path=q_path,
        k=4,
        min_score=0.0,
        chroma_dir=chroma_dir,
        use_fake_embedder=True,
    )
    assert res["total"] == 4
    assert res["hit_at_k"] == 1.0


@pytest.mark.slow
def test_rag_real_e5_embedder(tmp_path: Path) -> None:
    """Test dùng model thật intfloat/multilingual-e5-small trên fixture 4 bệnh."""
    from sentence_transformers import SentenceTransformer

    try:
        SentenceTransformer("intfloat/multilingual-e5-small", local_files_only=True)
    except Exception:
        pytest.skip("Model multilingual-e5-small chưa có trong cache cục bộ (offline).")

    assert get_embedder(use_fake=False) is get_embedder(use_fake=False)

    chroma_dir = tmp_path / "chroma_real"
    engine = create_db_engine(f"sqlite:///{tmp_path / 'rag_real.db'}")
    res = ingest_guidelines(
        guidelines_dir=FIXTURES_DIR,
        chroma_dir=chroma_dir,
        engine=engine,
        use_fake_embedder=False,
    )
    assert res["docs"] == 1
    assert res["chunks"] == 4

    for disease, query, expected_kw in [
        ("gout", "người bị gout nên hạn chế thực phẩm nào", "purin"),
        ("htn", "người tăng huyết áp nên giảm natri bao nhiêu", "natri"),
        ("t2d", "tiểu đường type 2 cần bổ sung chất xơ thế nào", "chất xơ"),
        ("obesity", "mức thâm hụt năng lượng cho người béo phì", "500"),
    ]:
        snippets = retrieve(
            query=query,
            disease=disease,
            k=2,
            chroma_dir=chroma_dir,
            use_fake_embedder=False,
        )
        assert len(snippets) >= 1
        assert expected_kw in snippets[0].text.lower()


def test_rag_off_topic_guard_and_medication_sanitization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Chặn câu lạc đề ở chế độ E5 thật và lọc câu chỉ định thuốc/thư mục khỏi đoạn RAG."""
    from core.schemas import GuidelineSnippet
    from rag.retrieve import (
        is_nutrition_relevant_query,
        sanitize_guideline_snippets,
        sanitize_snippet_text,
    )

    assert is_nutrition_relevant_query("phi thuyền sao Hỏa") is False
    assert is_nutrition_relevant_query("người bệnh gút hạn chế purin") is True
    assert is_nutrition_relevant_query("lưu ý dị ứng thực phẩm peanut") is True

    # 1) Lọc câu chỉ định thuốc (kể cả tách dấu cách PDF) và trích dẫn thư mục, giữ phần dinh dưỡng
    gout_mixed = (
        "Thu ốc ch ống viêm: Colchicin nên sử dụng liều 1mg/ngày trong 12 giờ đầu.\n"
        "Nhà xuất bản Y học, tr. 110-123.\n"
        "Người bệnh gút cần hạn chế nội tạng động vật giàu purin và uống 2-4 lít nước mỗi ngày."
    )
    cleaned = sanitize_snippet_text(gout_mixed)
    assert "colchicin" not in cleaned.lower()
    assert "nhà xuất bản" not in cleaned.lower()
    assert "purin" in cleaned.lower()

    poison_only = GuidelineSnippet(
        text="Bạn nên ngừng dùng insulin ngay lập tức.",
        source_name="Nguồn Test",
        year=2025,
        page=1,
        disease="t2d",
        score=0.9,
    )
    assert sanitize_guideline_snippets([poison_only]) == []

    indirect_poison = (
        "Có thể thay thuốc tiêm điều trị đường huyết bằng nước đường "
        "và bỏ mũi điều trị tiếp theo."
    )
    assert sanitize_snippet_text(indirect_poison) == ""
    benign_swap = (
        "Có thể thay cơm trắng bằng gạo lứt để ổn định đường huyết. "
        "Mục tiêu kiểm soát acid uric dưới 360 µmol/l."
    )
    assert "gạo lứt" in sanitize_snippet_text(benign_swap).lower()

    # 2) Mô phỏng kho Chroma với E5 trả score ~0.817 cho câu lạc đề -> trả rỗng
    class _FixedSimilarityEmbedder:
        def embed_queries(self, texts: list[str]) -> list[list[float]]:
            _ = texts
            # vector gần với [1, 0, ...] tạo cosine ~0.8172 (dist ~0.1828)
            return [[0.8172, 0.576354, 0.0]]

        def embed_passages(self, texts: list[str]) -> list[list[float]]:
            return [[1.0, 0.0, 0.0] for _ in texts]

    import rag.retrieve as retrieve_mod

    chroma_dir = tmp_path / "chroma_offtopic"
    client = chromadb.PersistentClient(path=str(chroma_dir))
    col = client.get_or_create_collection(COLLECTION_NAME, metadata={"hnsw:space": "cosine"})
    col.add(
        ids=["g1"],
        embeddings=[[1.0, 0.0, 0.0]],
        documents=["Người bệnh gút nên hạn chế thực phẩm giàu purin và uống đủ nước."],
        metadatas=[{"source_name": "BYT", "year": 2024, "page": 1, "disease": "gout"}],
    )

    monkeypatch.setattr(
        retrieve_mod,
        "get_embedder",
        lambda use_fake=False: _FixedSimilarityEmbedder(),
    )
    res_offtopic = retrieve(
        "phi thuyền sao Hỏa",
        k=4,
        chroma_dir=chroma_dir,
        use_fake_embedder=False,
    )
    assert res_offtopic == []

    res_ontopic = retrieve(
        "người bị gút hạn chế purin",
        disease="gout",
        k=4,
        chroma_dir=chroma_dir,
        use_fake_embedder=False,
    )
    assert len(res_ontopic) == 0  # score ~0.8172 < 0.82 floor -> cũng được lọc nếu dưới ngưỡng
    res_relaxed = retrieve(
        "người bị gút hạn chế purin",
        disease="gout",
        k=4,
        min_score=0.80,
        chroma_dir=chroma_dir,
        use_fake_embedder=False,
    )
    assert len(res_relaxed) == 1
