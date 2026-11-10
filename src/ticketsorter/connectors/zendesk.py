"""Minimal Zendesk connector (read tickets, optionally write back tags).

Env vars: ZENDESK_SUBDOMAIN, ZENDESK_EMAIL, ZENDESK_API_TOKEN
Docs: https://developer.zendesk.com/api-reference/ticketing/tickets/tickets/
"""

from __future__ import annotations

import os
from collections.abc import Iterator

from ticketsorter.models import Ticket, TicketResult

TIER_TAGS = {"enterprise": "enterprise", "team": "team", "pro": "pro"}


def _client():
    try:
        import httpx
    except ImportError as exc:  # pragma: no cover
        raise ImportError("Run: pip install 'ticket-categorizer[zendesk]'") from exc
    sub, email, token = (
        os.environ.get(k) for k in ("ZENDESK_SUBDOMAIN", "ZENDESK_EMAIL", "ZENDESK_API_TOKEN")
    )
    if not (sub and email and token):
        raise RuntimeError("Set ZENDESK_SUBDOMAIN, ZENDESK_EMAIL and ZENDESK_API_TOKEN")
    return httpx.Client(
        base_url=f"https://{sub}.zendesk.com/api/v2",
        auth=(f"{email}/token", token),
        timeout=30,
    )


def _to_ticket(z: dict) -> Ticket:
    tags = z.get("tags") or []
    tier = next((v for k, v in TIER_TAGS.items() if k in tags), "free")  # adapt to YOUR tagging
    return Ticket(
        id=str(z["id"]),
        subject=z.get("subject") or "",
        body=z.get("description") or "",
        customer_tier=tier,
        created_at=z.get("created_at"),
        metadata={"tags": tags, "status": z.get("status")},
    )


def fetch_open_tickets(limit: int = 500) -> Iterator[Ticket]:
    """Cursor-paginated fetch of non-solved tickets."""
    n = 0
    with _client() as c:
        url, params = "/tickets.json", {"page[size]": 100}
        while url and n < limit:
            r = c.get(url, params=params)
            r.raise_for_status()
            data = r.json()
            for z in data.get("tickets", []):
                if z.get("status") in ("solved", "closed", "deleted"):
                    continue
                yield _to_ticket(z)
                n += 1
                if n >= limit:
                    return
            url = data.get("links", {}).get("next") if data.get("meta", {}).get("has_more") else None
            params = None  # the "next" link already carries the query string


def write_back(result: TicketResult) -> None:
    """Add triage tags to the ticket (additive: existing tags are preserved)."""
    tags = [
        f"tc_cat_{result.category}",
        f"tc_tier_{result.tier.lower()}",
        f"tc_prio_{result.priority.lower()}",
    ]
    if result.possible_incident:
        tags.append("tc_possible_incident")
    with _client() as c:
        r = c.put(f"/tickets/{result.ticket_id}/tags.json", json={"tags": tags})
        r.raise_for_status()
