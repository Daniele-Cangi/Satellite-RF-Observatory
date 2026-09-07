from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "POST_DRAO_DOY232_QUALIFICATION_CHANGE_OF_ABSTRACTION.json"
HISTORICAL_OUTCOME = ROOT / "GNSS_DRAO_DOY232_QUALIFICATION_OUTCOME.json"
HISTORICAL_AUDIT = ROOT / "GNSS_DRAO_DOY232_QUALIFICATION_OUTCOME_AUDIT.json"


def load(path: Path) -> dict[str, object]:
    value = json.loads(
        path.read_text(encoding="ascii"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    assert isinstance(value, dict)
    return value


def test_historical_outcome_and_audit_remain_immutable() -> None:
    assert sha256(HISTORICAL_OUTCOME.read_bytes()).hexdigest() == (
        "b0c4b1d96969f0fb997013de0dc7229f59c38439ba65a10f342784dd851695aa"
    )
    assert sha256(HISTORICAL_AUDIT.read_bytes()).hexdigest() == (
        "e557e03ec0736e2aca5dcd7fe97596d6317d4fc11a4c4d3d3cd6029c5af473f0"
    )


def test_review_selects_primary_local_admission_not_a_qualification_retry() -> None:
    review = load(REVIEW)
    abstraction = review["current_abstraction"]
    boundary = review["integrated_primary_boundary"]

    assert review["outcome"] == "DRAO_SINGLE_PRIMARY_ADMISSION_PATH_SELECTED"
    assert abstraction["separate_prior_day_qualification_is_causally_required"] is False
    assert abstraction["primary_local_admission_is_causally_required"] is True
    assert boundary["scoring_permitted_only_after_every_admission_clause_passes"] is True
    assert boundary["admission_failure_or_description_error"] == (
        "ORBITAL_COMPARISON_NOT_EVALUATED"
    )


def test_doy233_remains_unselected_and_unopened() -> None:
    review = load(REVIEW)
    path = review["best_physical_path"]

    assert path["artifact_locator_selected"] is False
    assert path["observation_access_authorized"] is False
    assert path["primary_frozen"] is False
    assert review["stop"] == (
        "STOP_BEFORE_DOY233_LOCATOR_HEADER_PAYLOAD_OR_OBSERVATION_ACCESS"
    )


def test_future_identity_receipt_is_attributable() -> None:
    review = load(REVIEW)
    identity = review["identity_semantics_for_future_plan"]
    retained = set(identity["receipt_must_retain_before_decision"])

    assert "MARKER_NUMBER_DOMES_40105M002" in identity["binding_keys"]
    assert identity["marker_name_role"] == (
        "DESCRIPTIVE_CONSISTENCY_FIELD_NOT_A_STANDALONE_IDENTITY_KEY"
    )
    assert {"OBSERVED_MARKER_NAME", "OBSERVED_MARKER_NUMBER"} <= retained
    assert identity["identity_conflict_semantics"].startswith("TYPED_NOT_EVALUATED")


def test_every_potential_assignment_track_requires_complete_witness() -> None:
    review = load(REVIEW)
    admission = review["measurement_admission_for_future_plan"]

    assert admission["opaque_complete_tracks_required"] == 7
    assert admission["symmetric_clutter_exclusions"] == 1
    assert admission["complete_same_path_coverage_required_for_every_admitted_track"] is True
    assert admission["nonzero_lli_breaks_admission"] is True
    assert admission["gap_bridging"] is False
    assert admission["observation_values_persisted"] == 0
