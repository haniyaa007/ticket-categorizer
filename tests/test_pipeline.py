import csv
from pathlib import Path

import pytest

from ticketsorter.config import Settings
from ticketsorter.io import load_tickets, write_outputs
from ticketsorter.models import Ticket
from ticketsorter.pipeline import TicketPipeline, accuracy

SAMPLE = Path(__file__).parent.parent / "data" / "sample_tickets.csv"


@pytest.fixture(scope="module")
def pipeline():
    return TicketPipeline(Settings(embedding_backend="tfidf"))


@pytest.fixture(scope="module")
def output(pipeline):
    return pipeline.run(load_tickets(SAMPLE))


def test_category_accuracy_on_sample(output):
    truth = {r["id"]: r["expected_category"] for r in csv.DictReader(SAMPLE.open())}
    assert accuracy(output.results, truth) >= 0.85


def test_clusters_found_and_consistent(output):
    assert output.stats["clusters"] >= 4
    by_id = {r.ticket_id: r for r in output.results}
    for c in output.clusters:
        assert c.size == len(c.ticket_ids) >= 3
        assert all(by_id[i].cluster_id == c.cluster_id for i in c.ticket_ids)


def test_outage_burst_flagged_as_incident(output):
    assert output.stats["possible_incidents"] >= 1
    outage = [r for r in output.results if r.category == "outage_incident"]
    assert all(r.tier == "L2" and r.priority == "P1" for r in outage)


def test_realtime_classification(pipeline):
    t = Ticket(id="x", subject="Cannot login", body="I forgot my password and the reset email never arrives")
    r = pipeline.classify([t])[0]
    assert r.category == "account_access" and r.tier == "L1"


def test_enterprise_bumps_priority(pipeline):
    body = "I was charged twice, please refund the duplicate payment on my invoice"
    free = pipeline.classify([Ticket(id="a", subject="Charged twice", body=body)])[0]
    ent = pipeline.classify([Ticket(id="b", subject="Charged twice", body=body, customer_tier="Enterprise")])[
        0
    ]
    assert int(ent.priority[1]) == int(free.priority[1]) - 1


def test_reopened_ticket_escalates_to_l2(pipeline):
    t = Ticket(id="r", subject="Invoice question", body="Where is my invoice for March?", reopen_count=3)
    assert pipeline.classify([t])[0].tier == "L2"


def test_gibberish_goes_to_other(pipeline):
    r = pipeline.classify([Ticket(id="g", subject="zxqv", body="lorem blorp wibble")])[0]
    assert r.category == "other" and r.confidence == "low"


def test_empty_input(pipeline):
    assert pipeline.run([]).results == []


def test_few_tickets_do_not_crash(pipeline):
    out = pipeline.run(
        [Ticket(id=str(i), subject="429 rate limit", body="too many requests") for i in range(2)]
    )
    assert out.stats["clusters"] == 0 and len(out.results) == 2


def test_outputs_written(output, tmp_path):
    files = write_outputs(output, tmp_path)
    assert {f.name for f in files} == {"tickets_categorized.csv", "clusters.json", "report.md"}
    assert all(f.stat().st_size > 0 for f in files)


def test_ticket_validation():
    with pytest.raises(ValueError):
        Ticket(id="1")
