from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "GNSS_DRAO_DOY232_ARTIFACT_SELECTION.json"


def selected() -> dict[str, object]:
    return json.loads(
        RECEIPT.read_text(encoding="ascii"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )


def test_exact_contract_is_bound() -> None:
    value = selected()
    authority = value["contract_authority"]

    assert authority == {
        "git_commit": "f3f1fe724f5025e932c682b92e1fcf0c9939d8a8",
        "manifest_canonical_sha256": (
            "f0a02eb1d49b7ea01db6db263a1fb81af0d317fd959d1c78c3aece822c842df1"
        ),
        "manifest_name": "GNSS_DRAO_DOY232_QUALIFICATION_CONTRACT.json",
        "semantic_manifest_sha256": (
            "667be5b59b9da90c11710c9c6ae4c3d6ff24b06d73ac0337136b4371e8051e72"
        ),
        "state": "DRAO_DOY232_QUALIFICATION_CONTRACT_FROZEN",
    }


def test_only_one_exact_doy232_artifact_is_selected() -> None:
    value = selected()
    artifact = value["artifact"]
    selection = value["selection"]

    assert artifact["station"] == "DRAO00CAN"
    assert artifact["doy"] == 232
    assert artifact["name"] == "DRAO00CAN_R_20262320000_01D_30S_MO.crx.gz"
    assert artifact["url"].endswith("/2026/232/" + artifact["name"])
    assert artifact["role"] == "QUALIFICATION_ONLY_NEVER_SCORED_NEVER_PRIMARY"
    assert selection["selected_from_observation_content"] is False
    assert selection["alternate_locators_tested"] == 0
    assert selection["fallback_enabled"] is False


def test_head_metadata_is_not_promoted_to_content_integrity() -> None:
    value = selected()
    artifact = value["artifact"]
    head = value["http_head_receipt"]
    future = value["future_materialization"]

    assert head["method"] == "HEAD"
    assert head["status"] == 200
    assert head["content_length"] == 2_904_457
    assert head["body_bytes_accessed"] == 0
    assert artifact["complete_sha256"] is None
    assert artifact["complete_sha256_state"] == "PENDING_COMPLETE_MATERIALIZATION"
    assert artifact["published_cryptographic_checksum"]["value"] is None
    assert future["etag_is_cryptographic_hash"] is False
    assert future["accept_ranges_is_integrity_evidence"] is False
    assert future["complete_sha256_before_decompression"] is True


def test_every_physical_clause_remains_not_evaluated() -> None:
    value = selected()

    assert value["physical_claims_authorized"] == []
    assert value["qualification_clauses"]["artifact_identity"].endswith(
        "COMPLETE_HASH_NOT_EVALUATED"
    )
    assert set(value["qualification_clauses"].values()) - {
        "LOCATOR_AND_HTTP_METADATA_SELECTED_COMPLETE_HASH_NOT_EVALUATED",
        "NOT_EVALUATED",
    } == set()


def test_primary_and_observation_content_remain_sealed() -> None:
    value = selected()
    access = value["access"]

    assert access["http_head_requests"] == 1
    assert access["locator_candidates_attempted"] == 1
    assert access["observation_body_bytes"] == 0
    assert access["observation_headers_parsed"] == 0
    assert access["observation_values_accessed"] == 0
    assert access["primary_locators"] == 0
    assert access["primary_headers_parsed"] == 0
    assert access["primary_payload_bytes"] == 0
    assert access["primary_values_accessed"] == 0


def test_retry_is_bounded_to_same_pre_hash_artifact() -> None:
    future = selected()["future_materialization"]

    assert future["state"] == "NOT_AUTHORIZED_BY_THIS_RECEIPT"
    assert future["maximum_transport_attempts"] == 2
    assert future["resume_allowed_before_complete_hash"] is True
    assert future["same_locator_only"] is True
    assert future["failure_selects_alternate_archive_artifact_date_or_station"] is False
