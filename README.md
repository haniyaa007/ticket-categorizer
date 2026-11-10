# ticket-categorizer

[![CI](https://github.com/YOUR_GITHUB_USERNAME/ticket-categorizer/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_GITHUB_USERNAME/ticket-categorizer/actions)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Automated support-ticket **categorization, problem clustering and L1/L2 routing**, built for AI / LLM API SaaS
products (rate limits, hallucinations, latency, fine-tuning, API keys, outages, privacy...).

- **Categorize** each ticket against an editable taxonomy (YAML, no training data needed)
- **Cluster** tickets that describe the *same underlying problem*, with a readable label per cluster
- **Route** to **L1** (frontline) or **L2** (engineering/specialist) with a priority (P1-P4) and
  **human-readable reasons** ("enterprise customer", "mentions SAML", "reopened 3x"...)
- **Detect possible incidents**: many similar tickets inside a short window raises a flag
- Runs as a **CLI**, a **Python library**, or a **FastAPI service** (webhook-friendly), with Docker support
- **Privacy-first**: embeddings run locally; optional LLM labeling only sees *redacted* subjects

## How it works

```
ticket -> clean + redact -> embed -> ┬─ taxonomy match (semantic + keyword) ─> category
                                     └─ HDBSCAN clustering ─────────────────> problem cluster + label
                                                   │
        category + signals (urgency, plan, reopens, cluster burst) ──> tier (L1/L2) + priority + reasons
```

| Module | Role |
|---|---|
| `preprocess.py` | strips quotes/signatures, masks secrets, emails, URLs, IPs, IDs |
| `embeddings.py` | `sentence-transformers` (production) or `tfidf` (offline/tests) |
| `classifier.py` | taxonomy scoring: embeddings similarity + keyword bonus, with "other" fallback |
| `clustering.py` | HDBSCAN (or agglomerative) + distinctive-term labels |
| `routing.py` | L1/L2 + priority rules driven by `routing.yaml` |
| `labeling.py` | optional Anthropic-powered titles / summaries / suggested actions |
| `api.py`, `cli.py` | FastAPI service and CLI |
| `connectors/zendesk.py` | fetch tickets / write back tags |

## Quickstart

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/ticket-categorizer.git
cd ticket-categorizer
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[ml,api]"                              # add ,llm for AI cluster summaries
cp .env.example .env

ticketsorter run -i data/sample_tickets.csv -o out      # outputs: out/report.md, clusters.json, tickets_categorized.csv
```

No GPU or model download? Use `--backend tfidf` (lower quality on paraphrases, great for trying it out).

### Input format
CSV, JSON (`{"tickets": [...]}` or a list) or JSONL. Column names are matched flexibly:

| Field | Accepted names | Required |
|---|---|---|
| id | `id`, `ticket_id` | no (auto) |
| subject | `subject`, `title` | one of subject/body |
| body | `body`, `description`, `message` | one of subject/body |
| plan | `customer_tier`, `plan`, `tier` (e.g. free/pro/team/enterprise) | no |
| time | `created_at`, `created` (ISO-8601) | no (needed for time-window incident detection) |
| reopens | `reopen_count` | no |

### Output
- `tickets_categorized.csv` - category, confidence, cluster, **tier**, **priority**, `reasons`
- `clusters.json` - problem groups with size, label, tier, priority, incident flag, sample subjects
- `report.md` - L2 / L1 queues and cluster table, ready to paste into Slack or a wiki

## HTTP API

```bash
ticketsorter serve --port 8000        # docs at http://localhost:8000/docs
```

```bash
curl -X POST http://localhost:8000/v1/classify \
  -H "X-API-Key: $TC_API_KEY" -H "Content-Type: application/json" \
  -d '{"id":"123","subject":"429 errors in prod","body":"Rate limit exceeded far below our quota","customer_tier":"enterprise"}'
```

| Endpoint | Use |
|---|---|
| `POST /v1/classify` | one ticket, real-time (point your helpdesk webhook/trigger here) |
| `POST /v1/classify/batch` | many tickets, classification only |
| `POST /v1/cluster` | many tickets -> clusters + results (use ~20+ tickets for useful clusters) |
| `GET /healthz` | health check |

## Make it yours

```bash
ticketsorter init-config --dir config
# edit config/categories.yaml and config/routing.yaml, then in .env:
# TC_CATEGORIES_PATH=config/categories.yaml
# TC_ROUTING_PATH=config/routing.yaml
```

- **categories.yaml**: names, descriptions, keywords, optional real (anonymised) examples, default tier/priority,
  `incident_prone`, and a `runbook` hint for agents. Adding 3-5 real examples per category is the cheapest accuracy win.
- **routing.yaml**: urgency/frustration/technical keywords, which plans get a priority bump, reopen threshold,
  and incident size/time-window.

## Optional: AI cluster summaries

`TC_LLM_LABELING=true` + `ANTHROPIC_API_KEY` adds a title, one-line summary and suggested action per cluster.
Only redacted subjects are sent; failures fall back silently to term-based labels. Default model is configurable via
`TC_LLM_MODEL`.

## Zendesk

```bash
pip install -e ".[zendesk]"
export ZENDESK_SUBDOMAIN=acme ZENDESK_EMAIL=agent@acme.com ZENDESK_API_TOKEN=...
ticketsorter zendesk -o data/zendesk_tickets.json --limit 500
ticketsorter run -i data/zendesk_tickets.json -o out
```
Plan detection in `connectors/zendesk.py` is tag-based (`enterprise`, `team`, `pro`) - adapt to your setup.
`write_back()` adds `tc_cat_*`, `tc_tier_*`, `tc_prio_*` tags. Verify against your Zendesk configuration before using it in production.

## Development

```bash
pip install -e ".[dev]"
make test lint
```
Tests run offline with the TF-IDF backend. `scripts/generate_sample_data.py` regenerates the synthetic sample set.

## Honest limitations

- The bundled sample data is **synthetic** and the default taxonomy was written alongside it, so the accuracy
  numbers in tests (>=85%) are a smoke test, **not** a benchmark. Measure on your own labelled tickets before trusting it.
- The `tfidf` backend clusters on shared words; `sentence-transformers` groups paraphrases much better.
- English only by default. For other languages set `TC_EMBEDDING_MODEL` to a multilingual model.
- Routing is rule-based by design (explainable and easy to audit). Treat output as **triage assistance**; keep a human
  in the loop for P1 and security/privacy tickets.
- Real-time `/v1/classify` does not cluster; clustering is a batch job (e.g. hourly cron over open tickets).

## Roadmap ideas
Freshdesk/Intercom/Jira connectors - trained classifier from labelled history - duplicate-ticket detection -
multilingual presets - Prometheus metrics - feedback loop to learn from agent re-categorizations.

## License
MIT - see [LICENSE](LICENSE).
