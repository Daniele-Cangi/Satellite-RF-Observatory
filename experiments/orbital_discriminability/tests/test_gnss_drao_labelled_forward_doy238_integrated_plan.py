from __future__ import annotations

from hashlib import sha256
import json
from math import isfinite
from pathlib import Path

import pytest

from experiments.orbital_discriminability import (
    gnss_drao_labelled_forward_doy238_integrated_plan as plan,
)


ROOT = Path(__file__).resolve().parents[1]
FROZEN_PLAN = ROOT / plan.PLAN_NAME
FROZEN_BUNDLE = ROOT / plan.BUNDLE_NAME


def synthetic_bundle() -> dict[str, object]:
    return {
        "coordinate": "RETARDED_EARTH_ROTATION_CORRECTED_GEOMETRIC_RANGE_M",
        "grid": {
            "start_gps": "2026-08-26T04:50:00 GPS",
            "stop_gps": "2026-08-26T05:59:00 GPS",
            "heldout_start_gps": "2026-08-26T05:29:30 GPS",
            "step_s": 30,
            "raw_epochs": 139,
            "prefix_epochs": 79,
            "heldout_epochs": 60,
        },
        "labelled_model_curves_m": {
            satellite: [float(index) for index in range(139)]
            for satellite in plan.CODEBOOK
        },
    }


def test_plan_reaches_a_physical_heldout_question_without_selecting_artifact() -> None:
    value = plan.build_plan(synthetic_bundle(), ROOT)

    assert value["state"] == "DRAO_DOY238_INTEGRATED_PLAN_FROZEN_ARTIFACT_UNSELECTED"
    assert value["new_gate"] is False
    assert value["generic_framework"] is False
    assert value["candidate"]["artifact_selected"] is False
    assert value["candidate"]["observation_access_authorized"] is False
    assert set(value["access_at_freeze"].values()) == {0}
    assert value["new_physical_information"].startswith("ONE_REAL_MODEL_CONDITIONED")


def test_transform_ledger_is_hard_and_preserves_typed_absence() -> None:
    value = plan.build_plan(synthetic_bundle(), ROOT)
    ledger = value["pre_score_clauses"]["transform_ledger"]

    assert ledger["absence_malformed_conflict_and_incomplete_coverage_are_DISTINCT"] is True
    assert "SPEC_DEFINED_UNITY_ABSENCE" in ledger["SYS_SCALE_FACTOR"]
    assert "NEVER_APPLY_TWICE" in ledger["SYS_PHASE_SHIFT"]
    assert ledger["unresolved"] == "PRIMARY_NOT_EVALUATED"
    order = value["execution_order"]
    assert order.index("TYPED_TRANSFORM_LEDGER") < order.index("NUMERIC_CONVERSION_IN_RAM")
    assert order.index("MODEL_BLIND_PHYSICAL_WITNESSES") < order.index(
        "PREDICTION_BUNDLE_RELEASE_TO_SCORER"
    )


def test_labelled_topology_ignores_extra_tracks_but_never_substitutes_required() -> None:
    value = plan.build_plan(synthetic_bundle(), ROOT)
    topology = value["pre_score_clauses"]["record_topology"]

    assert topology["required_prns"] == list(plan.CODEBOOK)
    assert topology["required_pairs"] == 834
    assert topology["extra_tracks"] == "DESCRIPTIVE_NOT_FATAL_NOT_SCORED"
    assert topology["interpolation"] is False
    assert topology["gap_bridging"] is False


def test_nulls_have_identical_frozen_nuisance_and_no_heldout_adaptation() -> None:
    value = plan.build_plan(synthetic_bundle(), ROOT)

    assert value["hypotheses"]["same_nuisance_data_and_holdout"] is True
    assert value["decision"]["heldout_refit"] is False
    assert value["decision"]["free_time_phase"] is False
    assert value["decision"]["threshold_changes"] is False
    assert value["retry"]["after_complete_hash"] == 0
    assert value["retry"]["alternate_station_date_window_prn_feature_or_threshold"] is False


def test_maximum_claim_remains_model_conditioned_not_an_anomaly() -> None:
    value = plan.build_plan(synthetic_bundle(), ROOT)
    scope = value["claim_scope"]

    assert scope["maximum_positive"] == "ORBITAL_MODEL_PREDICTIVELY_PREFERRED"
    assert scope["specific_identity"] == "MODEL_CONDITIONED_NOT_INDEPENDENTLY_ESTABLISHED"
    assert scope["distributed_multi_root"] is False
    assert scope["anomaly_or_orbit_determination"] is False


def test_changed_envelope_is_refused_before_prediction_compilation(tmp_path: Path) -> None:
    for name in (plan.ENVELOPE_NAME, plan.REVIEW_NAME):
        (tmp_path / name).write_bytes((ROOT / name).read_bytes())
    (tmp_path / plan.ENVELOPE_NAME).write_text("{}", encoding="ascii")

    with pytest.raises(plan.IntegratedPlanError, match="FROZEN_INPUT_CHANGED"):
        plan.validate_authority(tmp_path)


def test_real_frozen_plan_binds_compiler_and_prediction_before_observation() -> None:
    frozen = json.loads(
        FROZEN_PLAN.read_text(encoding="ascii"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    bundle = json.loads(
        FROZEN_BUNDLE.read_text(encoding="ascii"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )

    assert sha256(FROZEN_PLAN.read_bytes()).hexdigest() == (
        "81e894a403066bc35187cfe9dd463ac5602eae5b80c7d278b270065449802d26"
    )
    assert frozen["source_commit"] == "af0349e4132c1872cfdbf21a57467b31ea110592"
    assert frozen["source_sha256"] == plan.source_sha256()
    assert frozen["prediction"]["bundle_sha256"] == plan.object_sha256(bundle)
    assert frozen["candidate"]["artifact_selected"] is False
    assert set(frozen["access_at_freeze"].values()) == {0}


def test_real_prediction_bundle_has_six_complete_finite_model_only_curves() -> None:
    bundle = json.loads(
        FROZEN_BUNDLE.read_text(encoding="ascii"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    curves = bundle["labelled_model_curves_m"]

    assert set(curves) == set(plan.CODEBOOK)
    assert all(len(values) == 139 for values in curves.values())
    assert all(isfinite(float(value)) for values in curves.values() for value in values)
    assert bundle["role"] == "FROZEN_MODEL_ONLY_NOT_AVAILABLE_TO_MEASUREMENT_ADMISSION"
    assert bundle["observation_values"] == 0
    assert bundle["identity_scope"]["specific_satellite_identity_independently_established"] is False
