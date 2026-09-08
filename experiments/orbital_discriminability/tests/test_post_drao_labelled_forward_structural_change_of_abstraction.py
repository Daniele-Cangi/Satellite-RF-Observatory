from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "POST_DRAO_LABELLED_FORWARD_STRUCTURAL_CHANGE_OF_ABSTRACTION.json"


def read(path: Path) -> dict[str, object]:
    value = json.loads(
        path.read_text(encoding="ascii"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    assert isinstance(value, dict)
    return value


def test_audit_is_strictly_offline_and_preserves_the_runtime() -> None:
    audit = read(AUDIT)

    assert audit["outcome"] == (
        "DRAO_CORE_STRUCTURE_PROVEN_TRANSFORM_RECEIPT_UNRESOLVED"
    )
    assert audit["new_gate"] is False
    assert set(audit["access"].values()) == {0}
    assert audit["frozen_runtime_preserved"] == {
        "outcome": "DRAO_STRUCTURE_TOPOLOGY_REJECTED",
        "raw_sha256": (
            "cb97fc2810a1c92a2ae2c17a2201b19eb2fda1d18407eaf8ac93ad367b2272a5"
        ),
        "rewritten": False,
    }


def test_every_bound_source_hash_matches_the_repository() -> None:
    audit = read(AUDIT)
    bindings = audit["source_bindings"]
    expected = {
        "artifact_selection_raw_sha256": (
            "GNSS_DRAO_LABELLED_FORWARD_ARTIFACT_SELECTION.json"
        ),
        "structural_contract_raw_sha256": (
            "GNSS_DRAO_LABELLED_FORWARD_STRUCTURAL_CONTRACT.json"
        ),
        "structural_outcome_raw_sha256": (
            "GNSS_DRAO_LABELLED_FORWARD_STRUCTURAL_OUTCOME.json"
        ),
        "structural_outcome_audit_raw_sha256": (
            "GNSS_DRAO_LABELLED_FORWARD_STRUCTURAL_OUTCOME_AUDIT.json"
        ),
        "independent_station_metadata_raw_sha256": (
            "GNSS_PHASE_INDEPENDENT_PAIR_SCREEN_RECEIPT.json"
        ),
    }
    for key, name in expected.items():
        assert sha256((ROOT / name).read_bytes()).hexdigest() == bindings[key]

    pre_access = audit["pre_access_authority"]
    assert sha256((ROOT / pre_access["document"]).read_bytes()).hexdigest() == (
        pre_access["raw_sha256"]
    )
    assert pre_access["existence_before_doy237_access"] is True


def test_marker_literal_is_removed_without_inventing_its_value() -> None:
    audit = read(AUDIT)
    identity = audit["identity_root"]

    assert identity["state"] == "SATISFIED_BY_COMPOSITE_ROOTS"
    assert {root["state"] for root in identity["controlling_roots"]} == {
        "SATISFIED"
    }
    assert identity["marker_name_literal"]["state"] == (
        "UNRESOLVED_DESCRIPTIVE_NOT_FATAL"
    )
    assert "OBSERVED_MARKER_NAME_EQUALS_DRAO" in identity["claims_not_authorized"]
    assert "OBSERVED_MARKER_NAME_CONTRADICTS_DRAO" in (
        identity["claims_not_authorized"]
    )


def test_structure_is_proven_but_transforms_remain_hard_preconditions() -> None:
    audit = read(AUDIT)
    relocation = audit["clause_relocation"]

    assert relocation["structural_topology"]["state"] == "SATISFIED"
    ledger = relocation["transform_ledger"]
    assert ledger["state"] == "UNRESOLVED_BY_RECEIPT"
    assert ledger["not_a_structural_presence_or_continuity_predicate"] is True
    assert ledger["hard_precondition_for_measurement"] is True
    assert ledger["hard_precondition_for_orbital_score"] is True
    assert set(relocation["measurement_and_orbit"].values()) == {"NOT_EVALUATED"}

    terms = {term["term"]: term for term in audit["transform_terms"]}
    assert terms["SYS_SCALE_FACTOR"]["may_be_assumed"] is False
    assert terms["SYS_PHASE_SHIFT"]["may_be_assumed"] is False
    assert terms["RCV_CLOCK_OFFS_APPL"]["artifact_specific_state"] == (
        "SATISFIED_BY_FROZEN_RUNTIME_RECEIPT"
    )


def test_consumed_artifact_is_not_promoted_or_retried() -> None:
    audit = read(AUDIT)
    disposition = audit["artifact_disposition"]

    assert disposition["role"] == "CONSUMED_STRUCTURAL_EVIDENCE_ONLY"
    assert disposition["core_structure"] == "PROVEN"
    assert disposition["integrated_proof_ready"] is False
    assert disposition["primary_admitted"] is False
    assert disposition["same_artifact_reopen"] is False
    assert disposition["same_artifact_retry"] == 0
    assert disposition["fallback_artifact"] is False
    assert audit["next_physical_vertical_constraints"]["new_artifact_selected"] is False
    assert audit["next_physical_vertical_constraints"]["new_access_authorized"] is False
    assert audit["next_physical_vertical_constraints"]["separate_structural_gate"] is False
    assert "ORBITAL_MODEL_PREDICTIVELY_PREFERRED" in audit["forbidden_claims"]
