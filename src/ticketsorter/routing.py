"""L1 / L2 routing and priority.

Design: category sets a *baseline* (tier + priority); signals in the ticket and its cluster
escalate it. Every decision records human-readable ``reasons`` so agents can see *why* a ticket
was escalated (important for trust and for tuning the rules).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from ticketsorter.classifier import CategoryDef
from ticketsorter.models import Ticket
from ticketsorter.utils import compile_terms, find_terms


class RoutingConfig(BaseModel):
    p1_keywords: list[str] = Field(default_factory=list)
    p2_keywords: list[str] = Field(default_factory=list)
    l2_keywords: list[str] = Field(default_factory=list)
    frustration_keywords: list[str] = Field(default_factory=list)
    priority_customer_tiers: list[str] = Field(default_factory=lambda: ["enterprise"])
    reopen_escalation: int = 2
    incident_cluster_size: int = 5
    incident_window_minutes: int = 60


def load_routing(path: Path) -> RoutingConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return RoutingConfig(**raw)


@dataclass
class RouteDecision:
    tier: str
    priority: int
    reasons: list[str] = field(default_factory=list)

    @property
    def priority_label(self) -> str:
        return f"P{self.priority}"


class Router:
    def __init__(self, cfg: RoutingConfig, categories: dict[str, CategoryDef]) -> None:
        self.cfg = cfg
        self.categories = categories
        self._p1 = compile_terms(cfg.p1_keywords)
        self._p2 = compile_terms(cfg.p2_keywords)
        self._l2 = compile_terms(cfg.l2_keywords)
        self._frus = compile_terms(cfg.frustration_keywords)

    def route(
        self, ticket: Ticket, text: str, category: str, possible_incident: bool = False
    ) -> RouteDecision:
        cat = self.categories[category]
        text = text.lower()
        tier, prio = cat.default_tier, cat.base_priority
        reasons = [f"category={category} (default {tier}/P{prio})"]

        if hits := find_terms(self._p1, text):
            prio = 1
            reasons.append(f"critical wording: {', '.join(hits[:3])}")
        elif hits := find_terms(self._p2, text):
            prio = min(prio, 2)
            reasons.append(f"urgent wording: {', '.join(hits[:3])}")

        if hits := find_terms(self._frus, text):
            prio = max(1, prio - 1)
            reasons.append(f"customer frustration: {', '.join(hits[:2])}")

        if ticket.customer_tier in self.cfg.priority_customer_tiers:
            prio = max(1, prio - 1)
            reasons.append(f"{ticket.customer_tier} customer")

        if hits := find_terms(self._l2, text):
            tier = "L2"
            reasons.append(f"technical depth: {', '.join(hits[:3])}")

        if ticket.reopen_count >= self.cfg.reopen_escalation:
            tier = "L2"
            reasons.append(f"reopened {ticket.reopen_count}x")

        if possible_incident:
            tier, prio = "L2", min(prio, 2)
            reasons.append("part of a cluster that looks like an active incident")

        if prio == 1:
            tier = "L2"
        return RouteDecision(tier=tier, priority=prio, reasons=reasons)
