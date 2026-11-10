from ticketsorter.preprocess import clean_for_embedding, redact_for_llm


def test_redacts_secrets_and_pii():
    t = "My key sk-live-ABCDEFGHIJKLMNOPQRSTUV and email bob@acme.com, see https://x.io/a?b=1"
    r = redact_for_llm(t)
    assert "sk-live" not in r and "bob@acme.com" not in r and "https://" not in r
    assert "[SECRET]" in r and "[EMAIL]" in r and "[URL]" in r


def test_strips_quoted_replies_and_signature():
    t = "Still broken\n> old quoted line\n\nOn Mon, Jan 1, 2026 at 9:00 AM Support wrote:\nold stuff"
    assert clean_for_embedding(t) == "Still broken"


def test_keeps_error_codes():
    assert "429" in clean_for_embedding("Getting 429 errors")


def test_truncates():
    assert len(clean_for_embedding("word " * 5000)) <= 2000
