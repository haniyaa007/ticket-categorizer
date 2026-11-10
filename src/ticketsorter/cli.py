"""Command line interface: ``ticketsorter --help``."""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path

from ticketsorter.config import DEFAULTS_DIR, Settings


def _run(args: argparse.Namespace) -> int:
    from ticketsorter.io import load_tickets, write_outputs
    from ticketsorter.pipeline import TicketPipeline

    settings = Settings()
    if args.backend:
        settings.embedding_backend = args.backend
    pipeline = TicketPipeline(settings)
    tickets = load_tickets(args.input)
    if not tickets:
        print("No valid tickets found.", file=sys.stderr)
        return 1
    out = pipeline.run(tickets)
    files = write_outputs(out, args.output)
    s = out.stats
    print(f"\n{s['tickets']} tickets -> {s['clusters']} clusters ({s['unclustered']} unclustered)")
    print(f"tiers: {s['by_tier']}   priorities: {s['by_priority']}   incidents: {s['possible_incidents']}")
    for f in files:
        print(f"  wrote {f}")
    return 0


def _classify(args: argparse.Namespace) -> int:
    from ticketsorter.models import Ticket
    from ticketsorter.pipeline import TicketPipeline

    settings = Settings()
    if args.backend:
        settings.embedding_backend = args.backend
    ticket = Ticket(id="cli", subject=args.subject, body=args.body, customer_tier=args.tier)
    print(json.dumps(TicketPipeline(settings).classify([ticket])[0].model_dump(), indent=2))
    return 0


def _serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError:
        print("Run: pip install 'ticket-categorizer[api]'", file=sys.stderr)
        return 1
    uvicorn.run("ticketsorter.api:create_app", factory=True, host=args.host, port=args.port)
    return 0


def _init_config(args: argparse.Namespace) -> int:
    dest = Path(args.dir)
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("categories.yaml", "routing.yaml"):
        target = dest / name
        if target.exists() and not args.force:
            print(f"exists, skipping: {target} (use --force)")
            continue
        shutil.copy(DEFAULTS_DIR / name, target)
        print(f"wrote {target}")
    print("Now set TC_CATEGORIES_PATH / TC_ROUTING_PATH in .env to use them.")
    return 0


def _zendesk(args: argparse.Namespace) -> int:
    from ticketsorter.connectors.zendesk import fetch_open_tickets

    tickets = list(fetch_open_tickets(args.limit))
    Path(args.output).write_text(
        json.dumps({"tickets": [t.model_dump(mode="json") for t in tickets]}, indent=2),
        encoding="utf-8",
    )
    print(f"Saved {len(tickets)} tickets to {args.output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ticketsorter", description=__doc__)
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="categorize + cluster + route a file of tickets")
    r.add_argument("-i", "--input", required=True, help=".csv / .json / .jsonl")
    r.add_argument("-o", "--output", default="out")
    r.add_argument("--backend", choices=["sentence-transformers", "tfidf"])
    r.set_defaults(fn=_run)

    c = sub.add_parser("classify", help="classify a single ticket")
    c.add_argument("--subject", default="")
    c.add_argument("--body", default="")
    c.add_argument("--tier", default="free", help="customer plan, e.g. enterprise")
    c.add_argument("--backend", choices=["sentence-transformers", "tfidf"])
    c.set_defaults(fn=_classify)

    s = sub.add_parser("serve", help="run the HTTP API")
    s.add_argument("--host", default="0.0.0.0")  # noqa: S104
    s.add_argument("--port", type=int, default=8000)
    s.set_defaults(fn=_serve)

    i = sub.add_parser("init-config", help="copy default categories/routing YAML to edit")
    i.add_argument("--dir", default="config")
    i.add_argument("--force", action="store_true")
    i.set_defaults(fn=_init_config)

    z = sub.add_parser("zendesk", help="download open tickets from Zendesk to a JSON file")
    z.add_argument("-o", "--output", default="data/zendesk_tickets.json")
    z.add_argument("--limit", type=int, default=500)
    z.set_defaults(fn=_zendesk)

    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
