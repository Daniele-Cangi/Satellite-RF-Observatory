from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTCOME = ROOT / "GNSS_DRAO_DOY232_QUALIFICATION_OUTCOME.json"
MARKER = ROOT / "GNSS_DRAO_DOY232_QUALIFICATION_AUTHORITY_CONSUMED.json"
AUDIT = ROOT / "GNSS_DRAO_DOY232_QUALIFICATION_OUTCOME_AUDIT.json"


def load(path: Path) -> dict[str, object]:
    value = json.loads(
        path.read_text(encoding="ascii"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    assert isinstance(value, dict)
    return value


def test_runtime_outcome_and_authority_marker_are_immutable() -> None:
    outcome = load(OUTCOME)
    marker = load(MARKER)

    assert sha256(OUTCOME.read_bytes()).hexdigest() == (
        "b0c4b1d96969f0fb997013de0dc7229f59c38439ba65a10f342784dd851695aa"
    )
    assert sha256(MARKER.read_bytes()).hexdigest() == (
        "631a09b30892ef382b23dc8f5aae51acefb1561ae7b2006ba74edb0f082dd26a"
    )
    assert outcome["outcome"] == "QUALIFICATION_TOPOLOGY_REJECTED"
    assert outcome["reason"] == "MARKER_NAME_MISMATCH"
    assert marker["state"] == "ONE_SHOT_AUTHORITY_CONSUMED_BEFORE_NETWORK"


def test_audit_does_not_turn_an_insufficient_receipt_into_physical_rejection() -> None:
    audit = load(AUDIT)
    interpretation = audit["physical_interpretation"]

    assert audit["audit_outcome"] == (
        "DRAO_DOY232_IDENTITY_CLAUSE_UNRESOLVED_BY_RECEIPT"
    )
    assert interpretation["physical_decision"] == "NOT_EVALUATED"
    assert interpretation[
        "runtime_physical_decision_measurement_path_rejected_is_supported"
    ] is False
    assert audit["clause_attribution"]["artifact_identity"] == (
        "CONTROL_FLOW_PROVEN_SATISFIED_BEFORE_DECODE"
    )
    assert audit["clause_attribution"]["header_identity_and_time"] == (
        "UNRESOLVED_RECEIPT_INSUFFICIENT"
    )
    assert audit["clause_attribution"]["complete_core_phase"] == "NOT_EVALUATED"


def test_doy232_is_closed_and_doy233_remains_unselected() -> None:
    audit = load(AUDIT)
    roles = audit["roles_after_audit"]
    access = audit["access_at_audit"]

    assert roles["doy232"] == "CONSUMED_CLOSED_NO_RETRY"
    assert roles["doy233"] == "UNSELECTED_UNFROZEN_UNAUTHORISED"
    assert roles["fallback_selected"] is False
    assert not any(access.values())


def test_no_orbital_or_measurement_claim_is_authorized() -> None:
    audit = load(AUDIT)
    execution = audit["observed_execution_path"]
    forbidden = set(audit["physical_interpretation"]["not_authorized_assertions"])

    assert execution["observation_fields_parsed"] == 0
    assert execution["orbital_model_used"] is False
    assert execution["orbital_scores_produced"] == 0
    assert "THE_MEASUREMENT_PATH_FAILED" in forbidden
    assert "ANY_ORBITAL_HYPOTHESIS_WAS_TESTED" in forbidden

