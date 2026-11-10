"""Generate data/sample_tickets.csv (synthetic, no real customer data)."""

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

G = {
    "api_errors": [
        (
            "Getting 500 errors on /v1/completions",
            "Since this morning our requests to /v1/completions return HTTP 500 internal server error intermittently. Request id req_8f3a. About 20% of calls fail.",
        ),
        (
            "502 bad gateway from the API",
            "We see 502 bad gateway responses when sending long prompts. Retrying sometimes works. Is there a known issue with the API gateway?",
        ),
        (
            "Invalid request error: messages must be array",
            "Our payload worked yesterday but now the API returns invalid_request_error 400, messages must be an array. We did not change the client code.",
        ),
        (
            "Streaming responses cut off mid-way",
            "With stream=true the SSE connection drops after a few seconds with an unexpected EOF and we receive a truncated completion.",
        ),
        (
            "Timeout errors calling the chat endpoint",
            "Our server gets a read timeout after 60 seconds on the chat endpoint for requests with large context. We also see 504 gateway timeout in the logs.",
        ),
    ],
    "rate_limits_quota": [
        (
            "429 Too Many Requests on production",
            "We keep hitting 429 rate limit exceeded errors although we are far below the documented requests per minute limit.",
        ),
        (
            "Need higher tokens per minute limit",
            "We launch next week and need our TPM limit raised to 2M tokens per minute. How do we request a quota increase?",
        ),
        (
            "Monthly quota exhausted early",
            "Our monthly token quota was used up on the 12th. Can you show a usage breakdown or increase the quota?",
        ),
        (
            "Rate limit headers missing on batch requests",
            "The x-ratelimit-remaining header is not returned for batch requests so we cannot back off properly. Is that expected with rate limits?",
        ),
        (
            "Concurrency limit reached",
            "We get a concurrent request limit reached message when running 20 parallel workers. What is the max concurrency for the Pro plan?",
        ),
    ],
    "latency_performance": [
        (
            "Responses became very slow since Monday",
            "Average latency jumped from 1.5s to 9s for the same prompts. Time to first token is also much slower. Nothing changed on our side.",
        ),
        (
            "High p99 latency in EU region",
            "p99 latency for our EU users is above 12 seconds. The US region looks normal. Can you check performance routing?",
        ),
        (
            "Embedding endpoint is slow",
            "Embedding requests for batches of 100 texts take 20+ seconds now, they used to finish in 3 seconds. Throughput is much lower.",
        ),
        (
            "Slow time to first token with streaming",
            "Streaming starts only after 6-8 seconds which makes our chat UI feel laggy. Is the model overloaded?",
        ),
        (
            "Latency doubled for long prompts",
            "Prompts above 20k tokens take twice as long as last month. Is this slower inference expected?",
        ),
    ],
    "model_quality": [
        (
            "Model hallucinating product features",
            "The assistant invents features that do not exist in our knowledge base even though the retrieved context is correct. Hallucinating like this is a big problem for our customers.",
        ),
        (
            "Output quality regression after update",
            "Since the model update last week answers are shorter and less accurate. Our evaluation score dropped from 92% to 81%, a clear quality regression.",
        ),
        (
            "Inconsistent JSON output",
            "Even at temperature 0 we get different answers, and sometimes the response is invalid JSON although we ask for a strict schema.",
        ),
        (
            "Model refuses harmless requests",
            "The model is refusing to summarize normal customer emails and says it cannot help. This is a false positive refusal.",
        ),
        (
            "Wrong language in responses",
            "We prompt in Spanish but the model answers in English about half the time. The system prompt clearly asks for Spanish.",
        ),
    ],
    "billing_invoices": [
        (
            "Charged twice this month",
            "I see two charges of $499 on my credit card for the same subscription. Please refund the duplicate payment.",
        ),
        (
            "Need invoice with VAT number",
            "Can you re-issue invoice INV-2231 with our company VAT number and billing address? Our finance team needs it.",
        ),
        (
            "Payment failed but card is valid",
            "My payment failed three times although the card works elsewhere. Please help with this billing problem before the account is suspended.",
        ),
        (
            "Annual plan pricing question",
            "What is the price of the annual plan and can we switch mid-cycle without paying the monthly fee again?",
        ),
        (
            "Cancel subscription and refund",
            "Please cancel my subscription effective today. I was charged yesterday by mistake and want a refund.",
        ),
    ],
    "account_access": [
        (
            "Cannot log in, password reset email not arriving",
            "I requested a password reset several times but never get the email. I checked spam. I am locked out of my account.",
        ),
        (
            "SSO login fails with SAML error",
            "After configuring Okta SAML single sign-on our users see invalid assertion when logging in. We followed the setup guide.",
        ),
        (
            "2FA code not working",
            "My authenticator app codes are rejected and I lost my backup codes. How do I regain access to my account?",
        ),
        (
            "Invite to workspace link expired",
            "I invited a teammate to our workspace but the invitation link says expired. How can I add users?",
        ),
        (
            "Account locked after failed login attempts",
            "My account was locked after several failed login attempts. Please unlock it, I need to access the console.",
        ),
    ],
    "api_authentication": [
        (
            "401 Unauthorized with valid API key",
            "Our API key worked until today, now every request returns 401 unauthorized invalid api key. We did not rotate the key.",
        ),
        (
            "How do I rotate API keys safely?",
            "We need to rotate our secret API key without downtime. Can two api keys be active at once?",
        ),
        (
            "403 forbidden for project scoped key",
            "Project scoped keys get 403 permission denied on the fine-tuning endpoints, but the org key works.",
        ),
        (
            "API key shows as revoked",
            "The dashboard says our api key was revoked but nobody on our team did that. Why was the key disabled? Please issue a new one.",
        ),
        (
            "Bearer token header format error",
            "Sending the Authorization header with the Bearer prefix still returns an unauthorized error. Is there a different header for the Azure endpoint?",
        ),
    ],
    "integrations_sdk": [
        (
            "Python SDK throws TypeError on streaming",
            "After upgrading the python sdk to the latest version we get TypeError: NoneType is not iterable when iterating the stream. Traceback attached.",
        ),
        (
            "Webhook signatures failing verification",
            "Our webhook endpoint rejects every event because signature verification fails. We use the documented HMAC method.",
        ),
        (
            "LangChain integration breaks after upgrade",
            "The LangChain integration raises an import error after we upgraded the package with pip. Which versions are compatible?",
        ),
        (
            "Node SDK types missing for new parameter",
            "The node sdk TypeScript types do not include the new response_format parameter, so our build fails.",
        ),
        (
            "Zapier connector stopped triggering",
            "Our Zapier integration stopped triggering zaps two days ago. Reconnecting the account did not help.",
        ),
    ],
    "fine_tuning_training": [
        (
            "Fine-tuning job failed with validation error",
            "Our fine-tuning job failed immediately: invalid training file format at line 214. The JSONL looks fine to us.",
        ),
        (
            "Fine-tune stuck in queue for 2 days",
            "The training job has been pending for two days. Is there a capacity problem with fine-tuning?",
        ),
        (
            "Dataset size limit for fine-tuning",
            "What is the maximum dataset size and number of epochs for a fine-tuning job on the Pro plan?",
        ),
        (
            "Fine-tuned model returns worse results",
            "After fine-tuning on 5,000 examples the custom model performs worse than the base model. What could be wrong with our training data?",
        ),
        (
            "Cannot deploy fine-tuned checkpoint",
            "The training finished but the checkpoint cannot be deployed. The custom model endpoint returns model not found.",
        ),
    ],
    "data_privacy_security": [
        (
            "GDPR data deletion request",
            "Under GDPR we need all data for our workspace deleted, including logs. Please confirm the data retention period and deletion process.",
        ),
        (
            "Do you train on our data?",
            "Our legal team needs written confirmation that customer prompts are not used for training. How do we opt out and where is the DPA?",
        ),
        (
            "SOC 2 report and security questionnaire",
            "Procurement asks for your SOC 2 report and to complete our security questionnaire before we can sign.",
        ),
        (
            "We accidentally leaked an API key",
            "We pushed a secret key to a public GitHub repo by mistake. We revoked it but want to know if there was any unauthorized usage. Possible breach.",
        ),
        (
            "Prompt injection vulnerability report",
            "We found a prompt injection vulnerability that lets users exfiltrate the system prompt. Where can we report it responsibly?",
        ),
    ],
    "outage_incident": [
        (
            "API is down - everything returns 503",
            "Is the API down? All of our requests return 503 service unavailable right now. Production is down.",
        ),
        (
            "Service unavailable across all regions",
            "We cannot reach the service from any region, complete outage on our side. Nothing works.",
        ),
        (
            "Status page says operational but we have an outage",
            "Your status page shows green but the chat endpoint is not responding at all for us and our whole team.",
        ),
        (
            "Total downtime of chat endpoint since 14:05 UTC",
            "The chat endpoint has been unavailable since 14:05 UTC. Is this an outage? Customers are complaining.",
        ),
        (
            "Is there an outage right now?",
            "Everything is down for us and for other companies we know. Service unavailable 503 errors everywhere.",
        ),
        (
            "503 service unavailable on all endpoints",
            "Every endpoint returns 503 service unavailable. Seems to be a major outage, please confirm on the status page.",
        ),
    ],
    "how_to_usage": [
        (
            "How do I get started with the API?",
            "I'm new here. How do I make my first request? Is there a getting started tutorial in the documentation?",
        ),
        (
            "Which model should I use for summarization?",
            "Which model is best for summarizing long documents, balancing cost and quality? Any best practice?",
        ),
        (
            "How to write a good system prompt",
            "Do you have a guide on prompt engineering for classification tasks? I would like examples of good system prompts.",
        ),
        (
            "How do I use function calling?",
            "Can you point me to documentation with an example of tool use and function calling in Python?",
        ),
        (
            "How to set a max token budget per user",
            "How do I limit the maximum tokens each end user can consume? Is there a documented way?",
        ),
    ],
    "feature_requests": [
        (
            "Feature request: team usage dashboard",
            "It would be great to have a per-member usage dashboard. This is a feature request for the roadmap.",
        ),
        (
            "Please add support for batch discounts",
            "Please add support for discounted batch processing for non-urgent workloads. Is it planned?",
        ),
        (
            "Dark mode for the console",
            "Suggestion: add a dark mode to the web console, my eyes would thank you.",
        ),
        (
            "Roadmap: image input support",
            "Is support for image input on the roadmap? We wish to process screenshots.",
        ),
        (
            "Feature request: export logs as CSV",
            "Would be great if request logs could be exported as CSV. Feature request from our data team.",
        ),
    ],
}
OTHER = [
    (
        "Partnership opportunity",
        "Hi, we are an agency interested in becoming a reseller partner. Who should we speak to?",
    ),
    ("Thanks!", "Just wanted to say your team was really helpful last week. Great job."),
    (
        "Job application",
        "I would like to apply for a position on your engineering team, where can I send my CV?",
    ),
]
TIERS = ["free", "pro", "pro", "team", "enterprise", "free"]

rows, n = [], 1000
base = datetime(2026, 3, 2, 9, 0, tzinfo=timezone.utc)
for gi, (cat, items) in enumerate(G.items()):
    for j, (s, b) in enumerate(items):
        n += 1
        if cat == "outage_incident":  # burst within ~20 min -> demonstrates incident detection
            ts = datetime(2026, 3, 9, 14, 10, tzinfo=timezone.utc) + timedelta(minutes=4 * j)
        else:
            ts = base + timedelta(hours=7 * gi + 3 * j)
        rows.append([f"T-{n}", s, b, TIERS[(gi + j) % len(TIERS)], ts.isoformat(), 0, cat])
for j, (s, b) in enumerate(OTHER):
    n += 1
    rows.append([f"T-{n}", s, b, "free", (base + timedelta(days=3, hours=j)).isoformat(), 0, "other"])

out = Path(__file__).resolve().parent.parent / "data" / "sample_tickets.csv"
with out.open("w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["id", "subject", "body", "customer_tier", "created_at", "reopen_count", "expected_category"])
    w.writerows(rows)
print(f"wrote {len(rows)} tickets -> {out}")
