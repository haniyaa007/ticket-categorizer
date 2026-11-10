"""End-to-end pipeline: clean -> embed -> categorize -> cluster -> route."""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import timedelta

import numpy as np

from ticketsorter.classifier import CategoryClassifier, load_categories
from ticketsorter.clustering import NOISE, cluster_embeddings, top_terms
from ticketsorter.config import Settings
from ticketsorter.embeddings import Embedder, get_embedder
from ticketsorter.labeling import LLMLabeler
from ticketsorter.models import (
    CategoryMatch,
    ClusterSummary,
    PipelineOutput,
    Ticket,
    TicketResult,
)
from ticketsorter.preprocess import clean_for_embedding, redact_for_llm
from ticketsorter.routing import Router, load_routing

log = logging.getLogger(__name__)


class TicketPipeline:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.categories = load_categories(self.settings.categories_file)
        self.router = Router(load_routing(self.settings.routing_file), self.categories)
        self._labeler: LLMLabeler | None = None
        if self.settings.llm_labeling:
            self._labeler = LLMLabeler(self.settings.anthropic_api_key, self.settings.llm_model)
        # Long-lived classifier used for real-time single-ticket calls (API).
        self._rt_embedder, self._rt_classifier = self._build_classifier(None)

    # ------------------------------------------------------------------ helpers
    def _new_classifier(self) -> CategoryClassifier:
        return CategoryClassifier(
            self.categories, self.settings.effective_threshold, self.settings.keyword_weight
        )

    def _build_classifier(self, corpus: list[str] | None) -> tuple[Embedder, CategoryClassifier]:
        embedder = get_embedder(self.settings)
        clf = self._new_classifier()
        if embedder.requires_fit:
            embedder.fit(clf.reference_texts + (corpus or []))
        clf.bind(embedder)
        return embedder, clf

    # ------------------------------------------------------------------ real-time (no clustering)
    def classify(self, tickets: list[Ticket]) -> list[TicketResult]:
        """Categorize + route tickets individually. Low latency; used by the API."""
        texts = [clean_for_embedding(t.text) for t in tickets]
        vectors = self._rt_embedder.embed(texts)
        matches = self._rt_classifier.classify(texts, vectors)
        return [
            self._result(t, tx, m, None, None, False)
            for t, tx, m in zip(tickets, texts, matches, strict=True)
        ]

    # ------------------------------------------------------------------ batch
    def run(self, tickets: list[Ticket]) -> PipelineOutput:
        if not tickets:
            return PipelineOutput(results=[], clusters=[], stats={"tickets": 0})

        texts = [clean_for_embedding(t.text) for t in tickets]
        embedder, clf = self._build_classifier(texts)
        vectors = embedder.embed(texts)
        matches = clf.classify(texts, vectors)
        labels = cluster_embeddings(vectors, self.settings)

        members: dict[int, list[int]] = defaultdict(list)
        for idx, lab in enumerate(labels):
            if lab != NOISE:
                members[int(lab)].append(idx)

        terms = top_terms({c: [texts[i] for i in ix] for c, ix in members.items()})
        cluster_meta: dict[int, dict] = {}
        for cid, ix in members.items():
            cat = Counter(matches[i].category for i in ix).most_common(1)[0][0]
            incident = self._is_incident(cat, [tickets[i] for i in ix])
            label = f"{cat}: {', '.join(terms.get(cid, [])[:3])}".rstrip(": ")
            extra: dict[str, str] = {}
            if self._labeler:
                samples = [redact_for_llm(tickets[i].subject or tickets[i].body) for i in ix[:6]]
                extra = self._labeler.label(cat, samples)
                label = extra.get("title", label)
            cluster_meta[cid] = {
                "category": cat,
                "incident": incident,
                "label": label,
                "extra": extra,
            }

        results: list[TicketResult] = []
        for i, (t, tx, m) in enumerate(zip(tickets, texts, matches, strict=True)):
            cid = int(labels[i])
            meta = cluster_meta.get(cid)
            results.append(
                self._result(
                    t,
                    tx,
                    m,
                    cid if meta else None,
                    meta["label"] if meta else None,
                    bool(meta and meta["incident"]),
                )
            )

        clusters = self._summaries(tickets, results, members, cluster_meta, terms)
        stats = {
            "tickets": len(tickets),
            "clusters": len(clusters),
            "unclustered": int(sum(1 for lab in labels if lab == NOISE)),
            "by_category": dict(Counter(r.category for r in results)),
            "by_tier": dict(Counter(r.tier for r in results)),
            "by_priority": dict(sorted(Counter(r.priority for r in results).items())),
            "possible_incidents": sum(1 for c in clusters if c.possible_incident),
            "embedding_backend": self.settings.embedding_backend,
        }
        return PipelineOutput(results=results, clusters=clusters, stats=stats)

    # ------------------------------------------------------------------ internals
    def _result(
        self,
        t: Ticket,
        text: str,
        m: CategoryMatch,
        cid: int | None,
        label: str | None,
        incident: bool,
    ) -> TicketResult:
        d = self.router.route(t, f"{t.subject} {t.body}", m.category, incident)
        return TicketResult(
            ticket_id=t.id,
            subject=t.subject,
            category=m.category,
            category_score=m.score,
            confidence=m.confidence,
            cluster_id=cid,
            cluster_label=label,
            priority=d.priority_label,
            tier=d.tier,
            possible_incident=incident,
            reasons=d.reasons,
        )

    def _is_incident(self, category: str, members: list[Ticket]) -> bool:
        cfg = self.router.cfg
        if not self.categories[category].incident_prone or len(members) < cfg.incident_cluster_size:
            return False
        times = sorted(t.created_at for t in members if t.created_at)
        if len(times) < cfg.incident_cluster_size:  # no usable timestamps -> size only
            return True
        window, need = timedelta(minutes=cfg.incident_window_minutes), cfg.incident_cluster_size
        return any(times[i + need - 1] - times[i] <= window for i in range(len(times) - need + 1))

    def _summaries(self, tickets, results, members, meta, terms) -> list[ClusterSummary]:
        out: list[ClusterSummary] = []
        for cid, ix in sorted(members.items()):
            rs = [results[i] for i in ix]
            tier = "L2" if sum(r.tier == "L2" for r in rs) * 2 >= len(rs) else "L1"
            prios = [int(r.priority[1]) for r in rs]
            # Incidents surface at their most severe level; otherwise use the typical (modal) priority
            # so a single enterprise ticket does not make a whole cluster look urgent.
            prio = min(prios) if m_incident(meta[cid]) else Counter(sorted(prios)).most_common(1)[0][0]
            m = meta[cid]
            cat = self.categories[m["category"]]
            out.append(
                ClusterSummary(
                    cluster_id=cid,
                    label=m["label"],
                    category=m["category"],
                    size=len(ix),
                    tier="L2" if m["incident"] else tier,
                    priority=f"P{prio}",
                    possible_incident=m["incident"],
                    top_terms=terms.get(cid, []),
                    ticket_ids=[tickets[i].id for i in ix],
                    sample_subjects=[tickets[i].subject for i in ix[:3]],
                    summary=m["extra"].get("summary"),
                    suggested_action=m["extra"].get("suggested_action") or cat.runbook,
                )
            )
        return sorted(out, key=lambda c: (c.priority, -c.size))


def m_incident(meta: dict) -> bool:
    return bool(meta["incident"])


def accuracy(results: list[TicketResult], truth: dict[str, str]) -> float:
    """Helper for evaluating against labelled data: fraction of tickets with the right category."""
    scored = [r for r in results if r.ticket_id in truth]
    return float(np.mean([r.category == truth[r.ticket_id] for r in scored])) if scored else 0.0
