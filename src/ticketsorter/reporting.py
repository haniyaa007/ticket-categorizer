"""Human-readable triage report (L1 / L2 queues + clusters)."""

from __future__ import annotations

from ticketsorter.models import PipelineOutput


def to_markdown(o: PipelineOutput) -> str:
    s = o.stats
    lines = [
        "# Ticket triage report",
        "",
        f"- Tickets: **{s.get('tickets', 0)}**  |  Clusters: **{s.get('clusters', 0)}**  |  "
        f"Unclustered: **{s.get('unclustered', 0)}**",
        f"- By tier: {s.get('by_tier', {})}",
        f"- By priority: {s.get('by_priority', {})}",
        f"- Possible incidents: **{s.get('possible_incidents', 0)}**",
        "",
        "## Problem clusters",
        "",
        "| Cluster | Label | Category | Size | Tier | Priority | Incident? |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in o.clusters:
        lines.append(
            f"| {c.cluster_id} | {c.label} | {c.category} | {c.size} | {c.tier} | {c.priority} | "
            f"{'YES' if c.possible_incident else ''} |"
        )
    for tier in ("L2", "L1"):
        rows = sorted((r for r in o.results if r.tier == tier), key=lambda r: r.priority)
        lines += ["", f"## {tier} queue ({len(rows)})", ""]
        lines += [f"- **{r.priority}** `{r.ticket_id}` [{r.category}] {r.subject}" for r in rows[:50]]
        if len(rows) > 50:
            lines.append(f"- ... and {len(rows) - 50} more")
    return "\n".join(lines) + "\n"
