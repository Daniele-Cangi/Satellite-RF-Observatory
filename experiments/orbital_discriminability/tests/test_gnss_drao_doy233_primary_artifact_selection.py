from __future__ import annotations

import json
from pathlib import Path

from experiments.orbital_discriminability import (
    gnss_drao_doy233_integrated_primary_plan as plan,
)


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "GNSS_DRAO_DOY233_PRIMARY_ARTIFACT_SELECTION.json"


def selected() -> dict[str, object]:
    value = json.loads(
        RECEIPT.read_text(encoding="ascii"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    assert isinstance(value, dict)
    return value


def test_selection_binds_merged_plan_and_executor() -> None:
    authority = selected()["proof_authority"]

    assert authority["main_merge_commit"] == "dfea90243c0ecd00389d6192bbc320c606c25412"
    assert authority["plan_canonical_sha256"] == plan.canonical_sha256(
        ROOT / plan.PLAN_NAME
    )
    assert authority["executor_manifest_canonical_sha256"] == plan.canonical_sha256(
        ROOT / "GNSS_DRAO_DOY233_INTEGRATED_PRIMARY_EXECUTOR_MANIFEST.json"
    )


def test_only_exact_deterministic_doy233_product_is_selected() -> None:
    value = selected()
    artifact = value["artifact"]
    selection = value["selection"]

    assert value["state"] == "DRAO_DOY233_PRIMARY_ARTIFACT_SELECTED_UNOPENED"
    assert artifact["station"] == "DRAO00CAN"
    assert artifact["doy"] == 233
    assert artifact["name"] == "DRAO00CAN_R_20262330000_01D_30S_MO.crx.gz"
    assert artifact["url"].endswith("/2026/233/" + artifact["name"])
    assert artifact["role"] == "HELDOUT_PRIMARY_ONE_SHOT"
    assert selection["alternate_locators_tested"] == 0
    assert selection["fallback_enabled"] is False
    assert selection["selected_from_observation_content"] is False


def test_head_metadata_does_not_masquerade_as_content_hash() -> None:
    value = selected()
    artifact = value["artifact"]
    head = value["http_head_receipt"]
    future = value["future_one_shot_execution"]

    assert head["method"] == "HEAD"
    assert head["status"] == 200
    assert head["content_length"] == 2_886_587
    assert head["body_bytes_accessed"] == 0
    assert artifact["complete_sha256"] is None
    assert artifact["complete_sha256_state"] == "PENDING_COMPLETE_MATERIALIZATION"
    assert future["etag_is_cryptographic_hash"] is False
    assert future["complete_sha256_before_decompression"] is True


def test_receipt_grants_no_body_or_scientific_authority() -> None:
    value = selected()

    assert value["physical_claims_authorized"] == []
    assert value["artifact"]["body_access_authorized"] is False
    assert value["future_one_shot_execution"]["state"] == "NOT_AUTHORIZED_BY_THIS_RECEIPT"
    assert value["access"] == {
        "http_head_requests": 1,
        "locator_candidates_attempted": 1,
        "observation_body_bytes": 0,
        "observation_headers_parsed": 0,
        "observation_values_accessed": 0,
        "orbital_scores": 0,
    }


def test_future_execution_has_only_pre_hash_transport_retry() -> None:
    future = selected()["future_one_shot_execution"]

    assert future["maximum_transport_attempts_before_complete_hash"] == 2
    assert future["resume_allowed_before_complete_hash"] is True
    assert future["same_locator_only"] is True
    assert future["post_complete_hash_retry"] == 0
    assert future["failure_selects_alternate_archive_artifact_date_or_station"] is False
