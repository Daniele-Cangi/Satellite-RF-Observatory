from __future__ import annotations

import json
from pathlib import Path

from experiments.orbital_discriminability import (
    gnss_drao_labelled_forward_structural_contract as contract,
)


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "GNSS_DRAO_LABELLED_FORWARD_ARTIFACT_SELECTION.json"


def selected() -> dict[str, object]:
    value = json.loads(
        RECEIPT.read_text(encoding="ascii"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    assert isinstance(value, dict)
    return value


def test_selection_binds_merged_structural_contract() -> None:
    value = selected()
    authority = value["contract_authority"]

    assert authority["main_merge_commit"] == "d62afa86b38d98259897db5ce096ee7ee3abf528"
    assert authority["contract_state"] == contract.CONTRACT_STATE
    assert authority["contract_markdown_canonical_sha256"] == contract.MARKDOWN_SHA256
    assert authority["physical_envelope_canonical_sha256"] == contract.ENVELOPE_SHA256


def test_only_exact_deterministic_doy237_product_is_selected() -> None:
    value = selected()
    artifact = value["artifact"]
    selection = value["selection"]

    assert value["state"] == "DRAO_LABELLED_FORWARD_ARTIFACT_SELECTED_UNOPENED"
    assert artifact["station"] == "DRAO00CAN"
    assert artifact["doy"] == 237
    assert artifact["name"] == "DRAO00CAN_R_20262370000_01D_30S_MO.crx.gz"
    assert artifact["url"].endswith("/2026/237/" + artifact["name"])
    assert selection["fallback_enabled"] is False
    assert selection["selected_from_observation_content"] is False
    assert value["access"]["alternate_locators_attempted"] == 0


def test_head_metadata_does_not_masquerade_as_content_hash() -> None:
    value = selected()
    artifact = value["artifact"]
    head = value["http_head_receipt"]
    future = value["future_structural_execution"]

    assert head["method"] == "HEAD"
    assert head["status"] == 200
    assert head["content_length"] == 2_849_014
    assert head["body_bytes_accessed"] == 0
    assert artifact["complete_sha256"] is None
    assert artifact["complete_sha256_state"] == "PENDING_COMPLETE_MATERIALIZATION"
    assert future["etag_is_cryptographic_hash"] is False
    assert future["complete_transport_sha256_before_decompression"] is True


def test_receipt_grants_no_body_measurement_or_scientific_authority() -> None:
    value = selected()

    assert value["physical_claims_authorized"] == []
    assert value["artifact"]["body_access_authorized"] is False
    assert value["future_structural_execution"]["state"] == "NOT_AUTHORIZED_BY_THIS_RECEIPT"
    assert value["access"] == {
        "alternate_locators_attempted": 0,
        "http_head_requests": 1,
        "observation_body_bytes": 0,
        "observation_headers_parsed": 0,
        "observation_values_accessed": 0,
        "orbital_scores": 0,
    }


def test_future_execution_has_only_pre_hash_transport_retry() -> None:
    future = selected()["future_structural_execution"]

    assert future["maximum_transport_attempts_before_complete_hash"] == 2
    assert future["resume_allowed_before_complete_hash"] is True
    assert future["same_locator_only"] is True
    assert future["post_complete_hash_retry"] == 0
    assert future["fallback_date_endpoint_artifact_or_prn"] is False
    assert future["observation_values_may_be_persisted"] is False
