"""Text cleaning and PII/secret redaction.

Two views of a ticket:
* ``clean_for_embedding`` - removes noise (quotes, signatures, ids, urls) so similar problems
  look similar regardless of customer-specific values.
* ``redact_for_llm`` - keeps readable placeholders and masks secrets/PII. ALWAYS use this before
  sending any ticket text to a third-party API.
"""

from __future__ import annotations

import re

_QUOTED_LINE = re.compile(r"(?m)^\s*>.*$")
_REPLY_HEADER = re.compile(r"(?is)\n\s*on .{5,120} wrote:.*$")
_SIGNATURE = re.compile(r"(?is)\n--\s*\n.*$|\n\s*sent from my (?:iphone|ipad|android).*$")
_SECRET = re.compile(
    r"\b(?:sk|pk|rk)[-_](?:live|test|proj|ant)?[-_]?[A-Za-z0-9_\-]{16,}\b|"
    r"\bBearer\s+[A-Za-z0-9._\-]{16,}|"
    r"\bAKIA[0-9A-Z]{16}\b|"
    r"\bghp_[A-Za-z0-9]{20,}\b",
    re.I,
)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_URL = re.compile(r"https?://\S+")
_UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
_CARD_OR_PHONE = re.compile(r"\b(?:\d[ -]?){9,18}\d\b")
_IP = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
_WS = re.compile(r"[ \t]+")
_NL = re.compile(r"\n{3,}")

MAX_CHARS = 2000


def _strip_noise(text: str) -> str:
    text = _REPLY_HEADER.sub("", text)
    text = _QUOTED_LINE.sub("", text)
    text = _SIGNATURE.sub("", text)
    return text


def _scrub(text: str, repl: dict[str, str]) -> str:
    text = _SECRET.sub(repl["secret"], text)
    text = _EMAIL.sub(repl["email"], text)
    text = _URL.sub(repl["url"], text)
    text = _UUID.sub(repl["id"], text)
    text = _IP.sub(repl["ip"], text)
    text = _CARD_OR_PHONE.sub(repl["number"], text)
    text = _WS.sub(" ", text)
    text = _NL.sub("\n\n", text)
    return text.strip()[:MAX_CHARS]


def clean_for_embedding(text: str) -> str:
    blank = dict.fromkeys(["secret", "email", "url", "id", "ip", "number"], " ")
    return _scrub(_strip_noise(text), blank)


def redact_for_llm(text: str) -> str:
    repl = {
        "secret": "[SECRET]",
        "email": "[EMAIL]",
        "url": "[URL]",
        "id": "[ID]",
        "ip": "[IP]",
        "number": "[NUMBER]",
    }
    return _scrub(_strip_noise(text), repl)
