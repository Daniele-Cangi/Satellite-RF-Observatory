from dataclasses import replace
from hashlib import sha256
import json

import pytest

from experiments.orbital_discriminability import g1_3_2_documents as docs


URL = "https://operator.invalid/inventory-doc"


def _plan() -> docs.G132DocumentPlan:
    return docs.G132DocumentPlan.for_selected_urls((URL,))


def test_bounded_body_is_hashed_before_descriptor_and_not_persisted() -> None:
    body = b"""<html><head><title> Receiver   API </title></head>
    <body>machine-readable JSON receiver directory
    <a href='/public/list.json#fragment'>inventory</a></body></html>"""

    receipt = docs.describe_document_bytes(
        _plan(),
        requested_url=URL,
        final_url=URL,
        status=200,
        headers={"Content-Type": "text/html; charset=utf-8"},
        body=body,
    )

    assert receipt.artifact_sha256 == sha256(body).hexdigest()
    assert receipt.hashed_before_parsing
    assert receipt.title == "Receiver API"
    assert receipt.candidate_links == ("https://operator.invalid/public/list.json",)
    assert receipt.raw_document_persisted is False
    encoded = receipt.strict_json()
    assert body.decode() not in encoded
    json.loads(encoded, parse_constant=lambda value: pytest.fail(value))


def test_document_over_limit_is_refused_before_description() -> None:
    plan = replace(_plan(), maximum_document_bytes=1_048_576)
    with pytest.raises(ValueError, match="exceeds"):
        docs.describe_document_bytes(
            plan,
            requested_url=URL,
            final_url=URL,
            status=200,
            headers={},
            body=b"x" * (1_048_576 + 1),
        )


def test_non_selected_document_cannot_enter_transport() -> None:
    with pytest.raises(ValueError, match="not in the frozen"):
        docs.describe_document_bytes(
            _plan(),
            requested_url="https://substitute.invalid/",
            final_url="https://substitute.invalid/",
            status=200,
            headers={},
            body=b"substitute",
        )


def test_plan_keeps_parent_document_limits_and_zero_rf() -> None:
    plan = _plan()
    plan.validate()
    assert plan.maximum_document_bytes == 1_048_576
    assert plan.request_timeout_s == 15.0
    assert plan.retry_count == 0
    assert plan.status_requests_allowed is False
    assert plan.rf_requests_allowed is False


@pytest.mark.parametrize(
    "change",
    (
        {"maximum_document_bytes": 1_048_577},
        {"request_timeout_s": 15.1},
        {"retry_count": 1},
        {"maximum_documents_per_candidate": 3},
        {"maximum_descriptor_links": 21},
        {"status_requests_allowed": True},
        {"rf_requests_allowed": True},
    ),
)
def test_transport_limits_are_immutable(change: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        replace(_plan(), **change).validate()


def test_descriptor_links_are_deterministic_bounded_and_public() -> None:
    links = "".join(
        f"<a href='/receiver/list/{index}'>x</a>" for index in range(25)
    )
    body = f"<html><body>{links}<a href='mailto:x@y'>mail</a></body></html>".encode()
    receipt = docs.describe_document_bytes(
        _plan(),
        requested_url=URL,
        final_url=URL,
        status=200,
        headers={},
        body=body,
    )
    assert len(receipt.candidate_links) == 20
    assert receipt.candidate_links[0].endswith("/receiver/list/0")
    assert receipt.candidate_links[-1].endswith("/receiver/list/19")
