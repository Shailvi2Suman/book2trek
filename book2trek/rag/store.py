"""
Retrieval store for RAG.

Two embedders behind one interface:
  * OpenAIEmbedder  — text-embedding-3-small (used when a key is present).
  * LocalEmbedder   — TF-IDF vectors (scikit-learn), the offline default so the
                      package retrieves sensibly and tests run with no key.

Both feed the same cosine-similarity VectorStore, so switching embedders never
changes the retrieval interface. This is a deliberate seam: prod quality from
OpenAI embeddings, zero-dependency determinism for CI.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .. import config as C


@dataclass
class Doc:
    id: str
    text: str
    meta: dict = field(default_factory=dict)


class LocalEmbedder:
    """TF-IDF embedder — deterministic, offline, good enough for retrieval."""

    def __init__(self) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer
        # char n-grams so morphology matches ("pack" ~ "packing", "cancel" ~
        # "cancellation") — far more robust for short spoken queries than
        # exact word matching, and still fully deterministic/offline.
        self._vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5),
                                    lowercase=True)
        self._fitted = False

    def fit(self, texts: list[str]) -> None:
        self._vec.fit(texts)
        self._fitted = True

    def embed(self, texts: list[str]) -> np.ndarray:
        if not self._fitted:
            self.fit(texts)
        return self._vec.transform(texts).toarray().astype(np.float32)


class OpenAIEmbedder:  # pragma: no cover - exercised only with a live key
    """Embeddings via OpenAI; used when OPENAI_API_KEY is set."""

    def __init__(self) -> None:
        from openai import OpenAI
        self._client = OpenAI(api_key=C.OPENAI_API_KEY)
        self._model = C.EMBED_MODEL

    def fit(self, texts: list[str]) -> None:
        return None

    def embed(self, texts: list[str]) -> np.ndarray:
        resp = self._client.embeddings.create(model=self._model, input=texts)
        return np.array([d.embedding for d in resp.data], dtype=np.float32)


def default_embedder():
    return OpenAIEmbedder() if C.have_openai() else LocalEmbedder()


def _cosine(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    an = a / (np.linalg.norm(a) + 1e-9)
    bn = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-9)
    return bn @ an


class VectorStore:
    """Fit on a set of docs, then retrieve top-k by cosine similarity."""

    def __init__(self, embedder=None) -> None:
        self.embedder = embedder or default_embedder()
        self.docs: list[Doc] = []
        self._matrix: np.ndarray | None = None

    def index(self, docs: list[Doc]) -> "VectorStore":
        self.docs = docs
        texts = [d.text for d in docs]
        if hasattr(self.embedder, "fit"):
            self.embedder.fit(texts)
        self._matrix = self.embedder.embed(texts)
        return self

    def query(self, text: str, k: int = 3) -> list[tuple[Doc, float]]:
        if self._matrix is None or not self.docs:
            return []
        qv = self.embedder.embed([text])[0]
        # align dims for TF-IDF (query transformed by fitted vocab already)
        sims = _cosine(qv, self._matrix)
        top = np.argsort(sims)[::-1][:k]
        return [(self.docs[i], float(sims[i])) for i in top]
