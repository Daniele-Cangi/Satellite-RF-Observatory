from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "GNSS_DRAO_DOY232_MATERIALIZATION_DESCRIPTION_ERROR.json"


def failure() -> dict[str, object]:
    return json.loads(
        RECEIPT.read_text(encoding="ascii"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )


def test_failure_is_descriptive_not_physical() -> None:
    value = failure()

    assert value["outcome"] == "QUALIFICATION_DESCRIPTION_ERROR"
    assert value["physical_decision"] == "NOT_EVALUATED"
    assert value["failure"]["physical_rejection"] is False
    assert value["failure"]["artifact_materialization_failed"] is False
    assert set(value["qualification_clauses"].values()) == {"NOT_EVALUATED"}


def test_unreceipted_numbers_are_not_fabricated() -> None:
    artifact = failure()["artifact"]

    assert artifact["actual_complete_bytes"] == {
        "state": "UNAVAILABLE_AFTER_RECEIPT_CONSTRUCTION_ERROR",
        "value": None,
    }
    assert artifact["complete_sha256"] == {
        "state": "COMPUTED_IN_FAILED_PROCESS_BUT_NOT_RETAINED",
        "value": None,
    }
    assert artifact["expected_bytes"] == 2_904_457


def test_cleanup_decode_and_primary_boundaries_are_preserved() -> None:
    value = failure()
    access = value["access"]

    assert value["artifact"]["payload_retained_after_attempt"] == 0
    assert access["decompression_attempted"] is False
    assert access["observation_headers_parsed"] == 0
    assert access["observation_values_accessed"] == 0
    assert access["primary_locators"] == 0
    assert access["primary_headers_parsed"] == 0
    assert access["primary_payload_bytes"] == 0
    assert access["primary_values_accessed"] == 0


def test_no_post_hash_retry_was_taken() -> None:
    retry = failure()["retry"]

    assert retry["contract_retry_after_complete_hash_or_decode"] == 0
    assert retry["performed_after_failure"] == 0
    assert retry["state"] == "PROHIBITED_AFTER_HASH_BY_FROZEN_CONTRACT"
