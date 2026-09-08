from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTCOME = ROOT / "GNSS_DRAO_LABELLED_FORWARD_STRUCTURAL_OUTCOME.json"
AUDIT = ROOT / "GNSS_DRAO_LABELLED_FORWARD_STRUCTURAL_OUTCOME_AUDIT.json"


def read(path: Path) -> dict[str, object]:
    value = json.loads(
        path.read_text(encoding="ascii"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    assert isinstance(value, dict)
    return value


def test_runtime_record_is_immutable_but_not_the_epistemic_terminal() -> None:
    runtime = read(OUTCOME)
    audit = read(AUDIT)

    assert sha256(OUTCOME.read_bytes()).hexdigest() == (
        "cb97fc2810a1c92a2ae2c17a2201b19eb2fda1d18407eaf8ac93ad367b2272a5"
    )
    assert runtime["outcome"] == "DRAO_STRUCTURE_TOPOLOGY_REJECTED"
    assert audit["parent_runtime_record"]["preserved_byte_for_byte"] is True
    assert audit["audit_outcome"] == "DRAO_STRUCTURE_DESCRIPTION_ERROR"


def test_complete_record_topology_is_preserved_as_positive_information() -> None:
    audit = read(AUDIT)
    facts = audit["structural_facts"]

    assert audit["epistemic_classification"]["core_record_topology"] == "SATISFIED"
    assert facts["normal_epochs"] == 139
    assert facts["epoch_grid_deviation_s"] == 0.0
    assert facts["required_satellite_epoch_pairs"] == 834
    assert set(facts["all_required_fields_present"].values()) == {834}
    assert set(facts["phase_lli_zero_or_blank"].values()) == {834}
    assert set(facts["complete_segments"].values()) == {139}


def test_description_failures_cannot_become_physical_rejections() -> None:
    audit = read(AUDIT)
    classification = audit["epistemic_classification"]

    assert classification["identity_compatibility"] == "UNRESOLVED_BY_RECEIPT"
    assert classification["transform_semantics"] == "UNRESOLVED_BY_RECEIPT"
    assert classification["measurement_validity"] == "NOT_EVALUATED"
    assert classification["orbital_model_preference"] == "NOT_EVALUATED"
    assert "DRAO_MEASUREMENT_PATH_REJECTED" in audit["forbidden_claims"]
    assert audit["no_causal_inference_from_missing_receipt_evidence"] is True


def test_execution_persisted_no_measurement_values_or_scores() -> None:
    audit = read(AUDIT)
    access = audit["observation_access"]

    assert set(access.values()) == {0}
    assert audit["terminal_policy"]["same_artifact_structural_retry"] == 0
    assert audit["terminal_policy"]["artifact_reopen_authorized"] is False
    assert audit["terminal_policy"]["fallback_artifact_date_endpoint_or_prn"] is False
