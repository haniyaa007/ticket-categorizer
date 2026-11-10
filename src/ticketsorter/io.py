"""Load tickets from CSV / JSON / JSONL and write results."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path

from pydantic import ValidationError

from ticketsorter.models import PipelineOutput, Ticket

log = logging.getLogger(__name__)

ALIASES = {
    "id": ["id", "ticket_id", "ticket id", "key"],
    "subject": ["subject", "title", "summary"],
    "body": ["body", "description", "message", "content", "text"],
    "customer_tier": ["customer_tier", "plan", "tier", "customer_plan"],
    "created_at": ["created_at", "created", "created_time", "date"],
    "reopen_count": ["reopen_count", "reopens", "reopened"],
}


def _pick(row: dict, field: str):
    lowered = {str(k).strip().lower(): v for k, v in row.items()}
    for alias in ALIASES[field]:
        if alias in lowered and lowered[alias] not in (None, ""):
            return lowered[alias]
    return None


def _row_to_ticket(row: dict, n: int) -> Ticket | None:
    data = {f: _pick(row, f) for f in ALIASES}
    data = {k: v for k, v in data.items() if v is not None}
    data.setdefault("id", f"row-{n}")
    if "reopen_count" in data:
        try:
            data["reopen_count"] = int(float(data["reopen_count"]))
        except ValueError:
            data.pop("reopen_count")
    known = {a for aliases in ALIASES.values() for a in aliases}
    data["metadata"] = {k: v for k, v in row.items() if str(k).strip().lower() not in known}
    try:
        return Ticket(**data)
    except ValidationError as exc:
        log.warning("Skipping row %s: %s", n, exc.errors()[0]["msg"])
        return None


def load_tickets(path: str | Path) -> list[Ticket]:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
    elif suffix == ".jsonl":
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    elif suffix == ".json":
        rows = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(rows, dict):
            rows = rows.get("tickets", [])
    else:
        raise ValueError(f"Unsupported file type: {suffix} (use .csv, .json or .jsonl)")
    tickets = [t for n, r in enumerate(rows, 1) if (t := _row_to_ticket(r, n))]
    log.info("Loaded %d tickets from %s", len(tickets), path)
    return tickets


def write_outputs(output: PipelineOutput, out_dir: str | Path) -> list[Path]:
    from ticketsorter.reporting import to_markdown

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = []

    p = out / "tickets_categorized.csv"
    cols = [
        "ticket_id",
        "subject",
        "category",
        "category_score",
        "confidence",
        "cluster_id",
        "cluster_label",
        "priority",
        "tier",
        "possible_incident",
        "reasons",
    ]
    with p.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in output.results:
            row = r.model_dump()
            row["reasons"] = " | ".join(row["reasons"])
            w.writerow({c: row[c] for c in cols})
    files.append(p)

    p = out / "clusters.json"
    p.write_text(json.dumps([c.model_dump() for c in output.clusters], indent=2), encoding="utf-8")
    files.append(p)

    p = out / "report.md"
    p.write_text(to_markdown(output), encoding="utf-8")
    files.append(p)
    return files
