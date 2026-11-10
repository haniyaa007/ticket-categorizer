# Contributing

1. Fork + clone, then `python -m venv .venv && source .venv/bin/activate`
2. `make install` (or `pip install -e ".[dev]"`)
3. Make your change, add/adjust tests in `tests/`
4. `make format && make lint && make test` must pass
5. Open a PR describing the problem and the fix

**Good first contributions:** new connectors (Freshdesk, Intercom, Jira Service Management, HubSpot),
more taxonomy presets, multilingual support, evaluation scripts.

**Never** include real customer tickets in issues, tests or sample data.
