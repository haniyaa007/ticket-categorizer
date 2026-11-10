"""Embedding backends. All return L2-normalised float32 matrices (cosine == dot product)."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Sequence

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from ticketsorter.config import Settings

log = logging.getLogger(__name__)


class Embedder(ABC):
    requires_fit = False

    def fit(self, texts: Sequence[str]) -> Embedder:
        return self

    @abstractmethod
    def embed(self, texts: Sequence[str]) -> np.ndarray: ...


class TfidfEmbedder(Embedder):
    """Dependency-light lexical embedder. Fast and offline; weaker on paraphrases."""

    requires_fit = True

    def __init__(self, svd_components: int = 128, max_features: int = 20000) -> None:
        self.svd_components = svd_components
        self.max_features = max_features
        self._vec: TfidfVectorizer | None = None
        self._svd: TruncatedSVD | None = None

    def fit(self, texts: Sequence[str]) -> TfidfEmbedder:
        self._vec = TfidfVectorizer(
            ngram_range=(1, 2),
            sublinear_tf=True,
            stop_words="english",
            max_features=self.max_features,
        )
        x = self._vec.fit_transform(texts)
        n_docs, n_feat = x.shape
        self._svd = None
        if min(n_docs, n_feat) > self.svd_components + 1:
            self._svd = TruncatedSVD(self.svd_components, random_state=42).fit(x)
        return self

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        if self._vec is None:
            raise RuntimeError("TfidfEmbedder must be fit() before embed()")
        x = self._vec.transform(texts)
        arr = self._svd.transform(x) if self._svd is not None else x.toarray()
        return normalize(arr).astype(np.float32)


class SentenceTransformerEmbedder(Embedder):
    def __init__(self, model_name: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "sentence-transformers is not installed. Run: pip install 'ticket-categorizer[ml]' "
                "or set TC_EMBEDDING_BACKEND=tfidf"
            ) from exc
        log.info("Loading embedding model %s", model_name)
        self._model = SentenceTransformer(model_name)

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        vecs = self._model.encode(
            list(texts), batch_size=64, normalize_embeddings=True, show_progress_bar=False
        )
        return np.asarray(vecs, dtype=np.float32)


_ST_CACHE: dict[str, SentenceTransformerEmbedder] = {}


def get_embedder(settings: Settings) -> Embedder:
    """Return an embedder. Heavy models are cached; TF-IDF is always a fresh, unfitted instance."""
    if settings.embedding_backend == "tfidf":
        return TfidfEmbedder()
    name = settings.embedding_model
    if name not in _ST_CACHE:
        _ST_CACHE[name] = SentenceTransformerEmbedder(name)
    return _ST_CACHE[name]
