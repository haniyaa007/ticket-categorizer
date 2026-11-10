"""Data models shared by the pipeline, CLI and API."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class Ticket(BaseModel):
    id: str
    subject: str = Field(default="", max_length=1000)
    body: str = Field(default="", max_length=20000)
    customer_tier: str = "free"  # free | pro | team | enterprise (free text, lower-cased)
    created_at: datetime | None = None
    reopen_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id", mode="before")
    @classmethod
    def _id_to_str(cls, v: Any) -> str:
        return str(v)

    @field_validator("customer_tier", mode="before")
    @classmethod
    def _norm_tier(cls, v: Any) -> str:
        return str(v).strip().lower() if v else "free"

    @field_validator("created_at", mode="after")
    @classmethod
    def _utc(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    @model_validator(mode="after")
    def _non_empty(self) -> Ticket:
        if not (self.subject.strip() or self.body.strip()):
            raise ValueError("ticket needs a subject or a body")
        return self

    @property
    def text(self) -> str:
        return f"{self.subject}\n{self.body}".strip()


class CategoryMatch(BaseModel):
    category: str
    score: float
    margin: float
    confidence: str  # high | medium | low
    keyword_hits: list[str] = Field(default_factory=list)
    runner_up: str | None = None


class TicketResult(BaseModel):
    ticket_id: str
    subject: str
    category: str
    category_score: float
    confidence: str
    cluster_id: int | None = None
    cluster_label: str | None = None
    priority: str  # P1 (highest) .. P4
    tier: str  # L1 | L2
    possible_incident: bool = False
    reasons: list[str] = Field(default_factory=list)


class ClusterSummary(BaseModel):
    cluster_id: int
    label: str
    category: str
    size: int
    tier: str
    priority: str
    possible_incident: bool = False
    top_terms: list[str] = Field(default_factory=list)
    ticket_ids: list[str] = Field(default_factory=list)
    sample_subjects: list[str] = Field(default_factory=list)
    summary: str | None = None
    suggested_action: str | None = None


class PipelineOutput(BaseModel):
    results: list[TicketResult]
    clusters: list[ClusterSummary]
    stats: dict[str, Any] = Field(default_factory=dict)
