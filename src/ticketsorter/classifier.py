"""Taxonomy-based categorization.

Each category is described in YAML (description + keywords + examples). A ticket is scored against
every category as::

    score = max(cosine(ticket, description), cosine(ticket, each example)) + keyword_bonus

No training data needed - add or edit categories in YAML and you're done. When you later have
labelled history, swap this class for a trained classifier without touching the rest of the pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import numpy as np
import yaml
from pydantic import BaseModel, Field

from ticketsorter.embeddings import Embedder
from ticketsorter.models import CategoryMatch
from ticketsorter.utils import compile_terms, find_terms

FALLBACK = "other"


class CategoryDef(BaseModel):
    name: str
    description: str = ""
    keywords: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    default_tier: Literal["L1", "L2"] = "L1"
    base_priority: int = Field(default=3, ge=1, le=4)  # 1 = most urgent
    incident_prone: bool = False
    runbook: str | None = None  # link/text shown to agents in cluster summaries

    @property
    def profile_text(self) -> str:
        return f"{self.name.replace('_', ' ')}. {self.description}. {' '.join(self.keywords)}"


def load_categories(path: Path) -> dict[str, CategoryDef]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    cats = {c["name"]: CategoryDef(**c) for c in raw["categories"]}
    cats.setdefault(
        FALLBACK,
        CategoryDef(name=FALLBACK, description="Anything that fits no other category", default_tier="L1"),
    )
    return cats


class CategoryClassifier:
    def __init__(
        self, categories: dict[str, CategoryDef], threshold: float, keyword_weight: float = 0.12
    ) -> None:
        self.categories = categories
        self.scored = [c for c in categories.values() if c.name != FALLBACK]
        self.threshold = threshold
        self.keyword_weight = keyword_weight
        self._kw = [compile_terms(c.keywords) for c in self.scored]
        self._row_texts: list[str] = []
        self._row_cat: list[int] = []
        for i, c in enumerate(self.scored):
            self._row_texts.append(c.profile_text)
            self._row_cat.append(i)
            for ex in c.examples:
                self._row_texts.append(ex)
                self._row_cat.append(i)
        self._row_vecs: np.ndarray | None = None

    @property
    def reference_texts(self) -> list[str]:
        """Texts a fit-based embedder (TF-IDF) should include in its vocabulary."""
        return self._row_texts

    def bind(self, embedder: Embedder) -> None:
        self._row_vecs = embedder.embed(self._row_texts)

    def classify(self, texts: list[str], vectors: np.ndarray) -> list[CategoryMatch]:
        if self._row_vecs is None:
            raise RuntimeError("call bind(embedder) first")
        n, n_cat = len(texts), len(self.scored)
        sims = vectors @ self._row_vecs.T
        cat_sims = np.full((n, n_cat), -1.0, dtype=np.float32)
        for row, ci in enumerate(self._row_cat):
            cat_sims[:, ci] = np.maximum(cat_sims[:, ci], sims[:, row])

        lowered = [t.lower() for t in texts]
        hits = [[find_terms(self._kw[ci], t) for ci in range(n_cat)] for t in lowered]
        bonus = np.array([[min(len(h), 3) * self.keyword_weight for h in row] for row in hits])
        scores = cat_sims + bonus

        out: list[CategoryMatch] = []
        for i in range(n):
            order = np.argsort(-scores[i])
            top, second = int(order[0]), int(order[1]) if n_cat > 1 else int(order[0])
            score = float(scores[i, top])
            margin = float(score - scores[i, second]) if n_cat > 1 else score
            if score < self.threshold:
                category, conf = FALLBACK, "low"
            else:
                category = self.scored[top].name
                if score >= self.threshold * 1.8 and margin >= 0.05:
                    conf = "high"
                elif margin >= 0.02:
                    conf = "medium"
                else:
                    conf = "low"
            out.append(
                CategoryMatch(
                    category=category,
                    score=round(score, 4),
                    margin=round(margin, 4),
                    confidence=conf,
                    keyword_hits=hits[i][top] if category != FALLBACK else [],
                    runner_up=self.scored[second].name if n_cat > 1 else None,
                )
            )
        return out
