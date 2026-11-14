"""Wrapper embedding cho multilingual-e5-small và chế độ giả lập cho CI."""

import hashlib
import math
from functools import lru_cache
from typing import Any, Protocol

from config.settings import get_settings


class Embedder(Protocol):
    """Giao diện chung cho bộ tạo vector embedding."""

    def embed_queries(self, texts: list[str]) -> list[list[float]]:
        """Tạo embedding cho danh sách câu truy vấn (tiền tố query:)."""

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        """Tạo embedding cho danh sách đoạn văn bản (tiền tố passage:)."""


class FakeEmbedder:
    """Embedding giả lập tất định dựa trên hash từ khóa (không tải model)."""

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def _encode_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = [t.strip(".,;:!?()[]").lower() for t in text.split() if t.strip()]
        for tok in tokens:
            digest = hashlib.sha256(tok.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dim
            vec[idx] += 1.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def embed_queries(self, texts: list[str]) -> list[list[float]]:
        return [self._encode_one(f"query: {t}") for t in texts]

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [self._encode_one(f"passage: {t}") for t in texts]


@lru_cache(maxsize=4)
def _load_sentence_transformer(model_name: str) -> Any:
    """Tải và cache singleton SentenceTransformer theo tên model."""
    from sentence_transformers import SentenceTransformer

    try:
        return SentenceTransformer(model_name, local_files_only=True)
    except Exception:
        return SentenceTransformer(model_name)


class E5Embedder:
    """Embedding thật dùng sentence-transformers (intfloat/multilingual-e5-small)."""

    def __init__(self, model_name: str | None = None) -> None:
        name = model_name or get_settings().EMBEDDING_MODEL
        self._model = _load_sentence_transformer(name)

    def embed_queries(self, texts: list[str]) -> list[list[float]]:
        prefixed = [f"query: {t}" for t in texts]
        vectors = self._model.encode(prefixed, normalize_embeddings=True)
        return [v.tolist() for v in vectors]

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        prefixed = [f"passage: {t}" for t in texts]
        vectors = self._model.encode(prefixed, normalize_embeddings=True)
        return [v.tolist() for v in vectors]


@lru_cache(maxsize=4)
def _get_cached_e5_embedder(model_name: str) -> E5Embedder:
    return E5Embedder(model_name=model_name)


@lru_cache(maxsize=1)
def _get_cached_fake_embedder() -> FakeEmbedder:
    return FakeEmbedder()


def get_embedder(use_fake: bool = False) -> Embedder:
    """Trả về FakeEmbedder nếu use_fake=True, ngược lại trả về E5Embedder (singleton)."""
    if use_fake:
        return _get_cached_fake_embedder()
    model_name = get_settings().EMBEDDING_MODEL
    return _get_cached_e5_embedder(model_name)
