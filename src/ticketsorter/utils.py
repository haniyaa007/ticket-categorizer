from __future__ import annotations

import re
from collections.abc import Iterable


def compile_terms(terms: Iterable[str]) -> re.Pattern[str] | None:
    """Compile a list of words/phrases into one whole-word, case-insensitive regex."""
    cleaned = sorted({t.lower().strip() for t in terms if t and t.strip()}, key=len, reverse=True)
    if not cleaned:
        return None
    alt = "|".join(re.escape(t) for t in cleaned)
    return re.compile(rf"(?<!\w)(?:{alt})(?!\w)")


def find_terms(pattern: re.Pattern[str] | None, text: str) -> list[str]:
    return sorted(set(pattern.findall(text))) if pattern else []
