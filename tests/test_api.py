import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from ticketsorter.api import create_app  # noqa: E402
from ticketsorter.config import Settings  # noqa: E402

TICKET = {"id": "1", "subject": "429 too many requests", "body": "rate limit exceeded on prod"}


def client(**kw):
    return TestClient(create_app(Settings(embedding_backend="tfidf", **kw)))


def test_health_and_classify():
    with client() as c:
        assert c.get("/healthz").json()["ready"] is True
        r = c.post("/v1/classify", json=TICKET)
        assert r.status_code == 200 and r.json()["category"] == "rate_limits_quota"


def test_auth_required_when_key_set():
    with client(api_key="secret") as c:
        assert c.post("/v1/classify", json=TICKET).status_code == 401
        assert c.post("/v1/classify", json=TICKET, headers={"X-API-Key": "nope"}).status_code == 401
        assert c.post("/v1/classify", json=TICKET, headers={"X-API-Key": "secret"}).status_code == 200


def test_batch_limit_and_validation():
    with client(max_batch_size=2) as c:
        many = {"tickets": [{**TICKET, "id": str(i)} for i in range(3)]}
        assert c.post("/v1/classify/batch", json=many).status_code == 413
        assert c.post("/v1/classify", json={"id": "1"}).status_code == 422
