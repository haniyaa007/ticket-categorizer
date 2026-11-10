"""Group tickets that describe the same underlying problem."""

from __future__ import annotations

import numpy as np
from sklearn.cluster import HDBSCAN, AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer

from ticketsorter.config import Settings

NOISE = -1


def cluster_embeddings(vectors: np.ndarray, settings: Settings) -> np.ndarray:
    """Return a label per row; -1 means 'does not belong to any cluster'."""
    n = len(vectors)
    size = settings.min_cluster_size
    if n < max(size * 2, 4):
        return np.full(n, NOISE, dtype=int)

    if settings.cluster_method == "agglomerative":
        model = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=settings.effective_agglomerative_distance,
            metric="cosine",
            linkage="average",
        )
        labels = model.fit_predict(vectors)
        # drop clusters smaller than min_cluster_size
        out = labels.copy()
        for lab, cnt in zip(*np.unique(labels, return_counts=True), strict=True):
            if cnt < size:
                out[labels == lab] = NOISE
        return _relabel(out)

    # HDBSCAN on unit vectors: euclidean distance is monotonic in cosine distance.
    model = HDBSCAN(
        min_cluster_size=size,
        min_samples=max(1, size - 1),
        cluster_selection_method="leaf",  # finer, more specific problem groups
        copy=True,
    )
    return _relabel(model.fit_predict(vectors))


def _relabel(labels: np.ndarray) -> np.ndarray:
    """Renumber clusters 0..k-1 by descending size."""
    valid = labels[labels != NOISE]
    if valid.size == 0:
        return labels
    ids, counts = np.unique(valid, return_counts=True)
    mapping = {int(old): new for new, old in enumerate(ids[np.argsort(-counts)])}
    return np.array([mapping.get(int(x), NOISE) for x in labels])


def top_terms(docs_by_cluster: dict[int, list[str]], n_terms: int = 4) -> dict[int, list[str]]:
    """Distinctive terms per cluster (class-based TF-IDF: each cluster is one big document)."""
    if not docs_by_cluster:
        return {}
    ids = list(docs_by_cluster)
    joined = [" ".join(docs_by_cluster[i]) for i in ids]
    vec = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", sublinear_tf=True)
    try:
        x = vec.fit_transform(joined)
    except ValueError:  # empty vocabulary
        return {i: [] for i in ids}
    vocab = np.array(vec.get_feature_names_out())
    result: dict[int, list[str]] = {}
    for row, cid in enumerate(ids):
        weights = x[row].toarray().ravel()
        chosen: list[str] = []
        for j in np.argsort(-weights):
            if weights[j] <= 0 or len(chosen) >= n_terms:
                break
            term = str(vocab[j])
            if any(term in c or c in term for c in chosen):
                continue
            chosen.append(term)
        result[cid] = chosen
    return result
