from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    gnss_observer_transfer_spike as spike,
)


ROOT = Path(__file__).resolve().parents[1]
PRIMARY = ROOT / spike.PRIMARY_OUTCOME_NAME
REPEATED = ROOT / spike.REPEATED_OUTCOME_NAME
RECEIPT = ROOT / spike.RECEIPT_NAME
RECEIPT_SHA256 = "e60e130e051626ebbae02aa655ade26071fd1dddd7f79a4f7ff131d476d3f4c5"


@pytest.fixture(scope="module")
def compiled() -> dict[str, object]:
    return spike.compile_mechanism(PRIMARY, REPEATED)


def test_prior_evidence_is_aggregate_exact_hash_and_closed() -> None:
    evidence = spike.validate_prior_evidence(PRIMARY, REPEATED)

    assert evidence[spike.PRIMARY_OUTCOME_NAME]["canonical_sha256"] == (
        spike.PRIMARY_OUTCOME_SHA256
    )
    assert evidence[spike.REPEATED_OUTCOME_NAME]["canonical_sha256"] == (
        spike.REPEATED_OUTCOME_SHA256
    )
    assert all("NO_VALUES_REOPENED" in row["role"] for row in evidence.values())


def test_anchor_removes_only_constant_not_rate() -> None:
    elapsed = np.arange(20, dtype=np.float64) * 30.0
    baseline = 10.0 + 0.4 * elapsed + 0.001 * elapsed**2

    assert np.allclose(
        spike.anchored_coordinate(baseline + 12345.0),
        spike.anchored_coordinate(baseline),
    )
    changed_rate = spike.anchored_coordinate(baseline + 0.1 * elapsed)
    assert not np.allclose(changed_rate, spike.anchored_coordinate(baseline))
    with pytest.raises(spike.ObserverTransferError, match="ANCHOR_MUST_BE_FROZEN"):
        spike.anchored_coordinate(baseline, anchor_index=1)


def test_common_receiver_clock_cancels_but_signal_specific_term_does_not() -> None:
    elapsed = np.arange(30, dtype=np.float64)
    target = 20_000_000.0 + 3.0 * elapsed
    reference = 21_000_000.0 - 2.0 * elapsed
    common_clock = 100.0 + 5.0 * elapsed + np.sin(elapsed)

    expected = spike.single_observer_quotient_m(target, reference)
    assert np.allclose(
        spike.single_observer_quotient_m(
            target + common_clock,
            reference + common_clock,
        ),
        expected,
    )
    signal_specific = spike.single_observer_quotient_m(
        target + 0.2 * elapsed,
        reference,
    )
    assert np.max(np.abs(signal_specific - expected)) == pytest.approx(5.8)


def test_affine_null_is_frozen_from_prediction_and_has_no_observation_fit() -> None:
    elapsed = np.arange(100, dtype=np.float64) * 30.0
    target = 4.0 + 0.2 * elapsed + 0.0004 * elapsed**2
    affine, rate = spike.frozen_adversarial_affine_null(target, elapsed)
    score = spike.score_without_nuisance_fit(
        target,
        {"TARGET": target, "AFFINE": affine},
    )

    assert rate != 0.0
    assert affine[0] == 0.0
    assert score["best_model"] == "TARGET"
    assert score["nuisance_parameters_fit_from_observation"] == 0


def test_two_link_interval_and_pairwise_envelope_are_conservative() -> None:
    term = spike.per_link_interval_term(
        {
            "term": "TEST",
            "per_link_path_bound_m": 2.0,
            "state": "MODELED_INTERVAL",
        }
    )
    assert term["two_link_coordinate_amplitude_bound_m"] == pytest.approx(4.0)
    assert term["heldout_peak_to_peak_bound_m"] == pytest.approx(8.0)

    positive = spike.combine_envelope(20.1, [term])
    blocked = spike.combine_envelope(16.0, [term])
    assert positive["outcome"] == spike.OUTCOME_DISCRIMINATIVE
    assert blocked["outcome"] == spike.OUTCOME_ENVELOPE_INSUFFICIENT


def test_non_finite_or_negative_intervals_are_refused() -> None:
    for value in (float("nan"), float("inf"), -0.1):
        with pytest.raises(spike.ObserverTransferError):
            spike.per_link_interval_term(
                {"term": "BAD", "per_link_path_bound_m": value}
            )


def test_compiled_spike_has_positive_margin_without_free_rate(compiled) -> None:
    assert compiled["outcome"] == spike.OUTCOME_DISCRIMINATIVE
    assert compiled["coordinate"]["free_rate"] is False
    assert compiled["coordinate"]["suffix_fit"] is False
    assert compiled["remaining_physical_margin_m"] > 0.0
    assert compiled["null_scores"]["controlling_null"] == "FROZEN_AFFINE_NULL"
    assert compiled["synthetic_geometry"]["minimum_all_model_elevation_deg"] > 60.0


def test_wrong_orbit_truth_prevents_automatic_target_preference(compiled) -> None:
    mismatch = compiled["synthetic_model_mismatch"]

    assert mismatch["generated_from_nominal_target"] is False
    assert mismatch["best_model"] == "WRONG_ORBIT_1"
    assert mismatch["target_not_automatically_preferred"] is True
    assert mismatch["target_residual"]["heldout_peak_to_peak_m"] > 0.0
    assert mismatch["truth_residual"]["heldout_peak_to_peak_m"] == pytest.approx(0.0)


def test_c_prefix_can_only_admit_witnesses_not_fit_the_orbit(compiled) -> None:
    partition = compiled["partition"]
    hardware = next(
        term
        for term in compiled["physical_terms"]
        if term["term"] == "MULTIPATH_AND_SIGNAL_SPECIFIC_HARDWARE"
    )

    assert partition["witness_prefix_may_fit_or_select_orbit"] is False
    assert partition["witness_prefix_may_apply_predeclared_admission_rules"] is True
    assert hardware["state"] == "REQUIRES_PREDECLARED_C_PREFIX_ADMISSION"
    assert "NOT_TRANSFERRED_FROM_AB" in hardware["provenance"]


def test_receipt_contains_no_real_capability_or_observation_surface(compiled) -> None:
    assert set(compiled["observation_access"].values()) == {0}
    assert compiled["fixture_role"] == (
        "SYNTHETIC_MECHANISM_ONLY_NEVER_CAPABILITY_NEVER_PRIMARY"
    )
    assert compiled["future_capability_selected"] is False
    assert compiled["prospective_plan_frozen"] is False
    assert compiled["measurement_authorized"] is False
    assert compiled["new_gate_created"] is False
    assert json.loads(spike.strict_json(compiled)) == compiled
    with pytest.raises(ValueError):
        spike.strict_json({"bad": float("nan")})


def test_frozen_receipt_binds_source_manifest_and_result() -> None:
    payload = RECEIPT.read_bytes()
    frozen = json.loads(payload)

    assert len(payload) == 12010
    assert sha256(payload).hexdigest() == RECEIPT_SHA256
    assert frozen["source_commit"] == (
        "2c1464f586d0db1e12e39c0be72e4b75505d6d2e"
    )
    assert frozen["source_sha256"] == spike.source_sha256()
    assert frozen["manifest_sha256"] == spike.manifest_sha256()
    assert frozen["outcome"] == spike.OUTCOME_DISCRIMINATIVE
    assert frozen["null_scores"]["controlling_null"] == "FROZEN_AFFINE_NULL"
    assert frozen["null_scores"]["controlling_heldout_separation_m"] == pytest.approx(
        1703.2250464932295
    )
    assert frozen["pairwise_comparison_envelope_m"] == pytest.approx(
        286.8833795985163
    )
    assert frozen["remaining_physical_margin_m"] == pytest.approx(
        1416.3416668947132
    )
    assert set(frozen["observation_access"].values()) == {0}
