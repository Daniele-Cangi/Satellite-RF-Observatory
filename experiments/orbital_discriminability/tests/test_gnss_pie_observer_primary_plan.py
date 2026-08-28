from __future__ import annotations

from pathlib import Path

import pytest

from experiments.orbital_discriminability import (
    gnss_pie_observer_primary_plan as plan,
)


ROOT = Path(plan.__file__).resolve().parent


def compiled() -> dict[str, object]:
    return plan.plan(ROOT)


def test_exact_closed_parents_and_primary_boundary_are_bound() -> None:
    parents = plan.validate_parents(ROOT)
    value = compiled()

    assert set(parents) == {
        plan.GEOMETRY_NAME,
        plan.METADATA_NAME,
        plan.QUALIFICATION_NAME,
        plan.QUALIFICATION_SUMMARY_NAME,
        plan.QUALIFICATION_COVERAGE_NAME,
        plan.PLAN_NAME,
    }
    assert value["outcome"] == "PIE_OBSERVER_PRIMARY_PLAN_FROZEN"
    assert value["access_boundary"] == {
        "this_plan_network_requests": 0,
        "primary_headers_opened": 0,
        "primary_payload_bytes": 0,
        "primary_observation_values": 0,
        "orbital_scores": 0,
        "executor_present": False,
        "execution_authority": False,
    }


def test_primary_role_window_and_partition_are_exact() -> None:
    value = compiled()

    assert value["observer"]["station"] == "PIE100USA"
    assert value["primary_artifact"]["logical_product"] == (
        "PIE100USA_R_20262230000_01D_30S_MO.crx.gz"
    )
    assert "/2026/223/" in value["primary_artifact"]["authority_url"]
    assert value["partition"] == {
        "time_system": "GPS",
        "raw_start": "2026-08-11T05:42:00 GPS",
        "raw_stop": "2026-08-11T06:51:00 GPS",
        "raw_epochs": 139,
        "cadence_s": 30.0,
        "anchor_index": 0,
        "witness_prefix_raw_indices_inclusive": [0, 78],
        "witness_prefix_epochs": 79,
        "heldout_raw_indices_inclusive": [79, 138],
        "heldout_start": "2026-08-11T06:21:30 GPS",
        "heldout_epochs": 60,
        "window_shortening_interpolation_gap_bridging": "FORBIDDEN",
    }


def test_coordinate_has_one_fixed_anchor_and_zero_fitted_nuisance() -> None:
    value = compiled()
    coordinate = value["coordinate"]
    scoring = value["scoring"]

    assert coordinate["station_satellite_order"] == "PIE_G22_MINUS_PIE_G30"
    assert coordinate["anchor"] == "SUBTRACT_RAW_INDEX_ZERO_ONLY"
    assert coordinate["free_constant"] is False
    assert coordinate["free_rate"] is False
    assert coordinate["free_time_phase"] is False
    assert coordinate["suffix_fit"] is False
    assert scoring["nuisance_fit_parameters"] == 0
    assert scoring["prefix_may_fit_or_select_model"] is False


def test_code_phase_limit_is_outcome_independent_and_conservative() -> None:
    value = compiled()
    witness = value["admission"]["same_path_code_phase_witness"]
    alpha, beta = value["coordinate"]["ionosphere_free_weights"].values()
    weighted_chip = plan.CODE_CHIP_RANGE_M * (abs(alpha) + abs(beta))

    assert plan.CODE_CHIP_RANGE_M == pytest.approx(293.0522561094819)
    assert weighted_chip < plan.CODE_PHASE_PER_SATELLITE_PTP_LIMIT_M
    assert witness["peak_to_peak_limit_m"] == 1_250.0
    assert witness["required_coverage_fraction"] == 1.0
    assert witness["evaluated_on_prefix_and_heldout_without_threshold_change"]
    assert witness["may_fit_or_select_orbit"] is False


def test_unwitnessed_four_meter_hardware_term_is_replaced_once() -> None:
    value = compiled()
    hardware = [
        term
        for term in value["physical_envelope"]["terms"]
        if term["term"] == "MULTIPATH_AND_SIGNAL_SPECIFIC_HARDWARE"
    ]

    assert len(hardware) == 1
    assert hardware[0]["state"] == "OBSERVABLE_WITH_FIXED_FULL_WINDOW_LIMIT"
    assert hardware[0]["heldout_peak_to_peak_bound_m"] == 2_500.0
    assert hardware[0]["pairwise_contribution_m"] == 5_000.0
    assert hardware[0]["threshold_learned_from_primary"] is False
    assert value["physical_envelope"]["old_unwitnessed_hardware_term_reused"] is False


def test_revised_margin_regression_remains_strictly_positive() -> None:
    envelope = compiled()["physical_envelope"]

    assert envelope["controlling_affine_separation_m"] == pytest.approx(
        190_232.34133512143
    )
    assert envelope["one_model_envelope_m"] == pytest.approx(3_949.910439198746)
    assert envelope["pairwise_decision_guard_m"] == pytest.approx(7_899.820878397492)
    assert envelope["remaining_margin_m"] == pytest.approx(182_332.52045672393)
    assert envelope["negative_result_interpretable_after_all_admission_clauses"]


def test_nulls_are_fixed_and_receive_the_same_transform() -> None:
    hypotheses = compiled()["hypotheses"]

    assert hypotheses["orbital"] == "BROADCAST_G22_RELATIVE_TO_G30"
    assert hypotheses["frozen_affine"] == {
        "zero_intercept_at_anchor": True,
        "rate_m_s": -343.3209190383492,
        "rate_source": "TARGET_PREDICTION_ONLY_BEFORE_OBSERVATION",
    }
    assert hypotheses["wrong_orbits_replacing_target_only"] == [
        "G01",
        "G14",
        "G17",
    ]
    assert hypotheses["reference_remains"] == "G30"
    assert hypotheses["same_grid_anchor_transform_and_envelope"] is True


def test_outcomes_separate_invalid_not_detectable_and_physical_scores() -> None:
    outcomes = compiled()["future_outcomes"]

    assert "MEASUREMENT_INVALID" in outcomes
    assert "NOT_DETECTABLE" in outcomes
    assert "PIE_HELD_OUT_ORBITAL_MODEL_PREFERRED" in outcomes
    assert "FROZEN_AFFINE_NULL_PREFERRED" in outcomes
    assert "AMBIGUOUS" in outcomes
    assert compiled()["claim_scope"]["not_identity_evidence"] is True


def test_compiler_has_no_network_decoder_or_primary_value_surface() -> None:
    source = Path(plan.__file__).read_text(encoding="utf-8")

    for forbidden in (
        "import requests",
        "import urllib",
        "import socket",
        "import hatanaka",
        "observation_values_m",
    ):
        assert forbidden not in source
    assert compiled()["stop"] == "DO_NOT_OPEN_PRIMARY_OR_BUILD_EXECUTOR"


def test_receipt_is_strict_and_retains_zero_access(monkeypatch) -> None:
    monkeypatch.setattr(plan, "_git_commit", lambda: "a" * 40)
    value = plan.receipt(ROOT)
    encoded = plan.strict_json(value)

    assert value["source_commit"] == "a" * 40
    assert value["primary_access"] == {
        "headers": 0,
        "payload_bytes": 0,
        "observation_values": 0,
    }
    assert value["orbital_scores_produced"] == 0
    assert "NaN" not in encoded and "Infinity" not in encoded


def test_parent_tampering_is_refused_before_plan_compilation(monkeypatch) -> None:
    original = plan.canonical_sha256

    def tampered(path: Path) -> str:
        if Path(path).name == plan.QUALIFICATION_NAME:
            return "0" * 64
        return original(path)

    monkeypatch.setattr(plan, "canonical_sha256", tampered)

    with pytest.raises(plan.PiePlanError, match="FROZEN_PARENT_CHANGED"):
        plan.plan(ROOT)
