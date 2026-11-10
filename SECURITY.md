# Security policy

## Reporting a vulnerability
Please do **not** open a public issue. Email **security@YOUR_DOMAIN.com** (TODO: replace) with details
and reproduction steps. We aim to acknowledge within 3 business days.

## Handling of customer data
- Tickets contain personal data. Run this service inside your own infrastructure.
- Embeddings are computed locally (sentence-transformers); no ticket text leaves your network by default.
- If `TC_LLM_LABELING=true`, only **redacted subjects** (secrets, emails, URLs, IPs, IDs, long numbers
  masked) are sent to the Anthropic API. Review `preprocess.py` against your own data before enabling.
- Always set `TC_API_KEY` and put the service behind HTTPS.
