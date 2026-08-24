from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import gnss_double_difference_envelope as old
from experiments.orbital_discriminability import gnss_double_difference_screen as base
from experiments.orbital_discriminability import gnss_phase_quotient_spike as spike


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "GNSS_PHASE_QUOTIENT_SPIKE_RECEIPT.json"


def test_phase_range_derivative_matches_existing_doppler_coordinate() -> None:
    elapsed = np.arange(40, dtype=np.float64) * base.GRID_STEP_S
    ranges = (
        20_000_000.0 + 3.0 * elapsed + 0.002 * elapsed**2,
        21_000_000.0 - 2.0 * elapsed + 0.001 * elapsed**2,
        22_000_000.0 + 1.0 * elapsed - 0.001 * elapsed**2,
        23_000_000.0 - 4.0 * elapsed + 0.0005 * elapsed**2,
    )
    phase_range = spike.double_difference_range_m(*ranges)
    fractional = [
        -np.gradient(value, base.GRID_STEP_S, edge_order=2)
        / base.SPEED_OF_LIGHT_M_S
        for value in ranges
    ]
    old_frequency = base.double_difference_hz(*fractional)
    phase_derived_frequency = (
        -old.GPS_L1_HZ
        / base.SPEED_OF_LIGHT_M_S
        * np.gradient(phase_range, base.GRID_STEP_S, edge_order=2)
    )

    assert np.allclose(phase_derived_frequency, old_frequency, atol=1e-9)


def test_prefix_fit_cannot_see_or_refit_heldout() -> None:
    elapsed = np.arange(100, dtype=np.float64) * 30.0
    baseline = 10.0 + 0.25 * elapsed
    changed_suffix = baseline.copy()
    changed_suffix[20:] += np.linspace(0.0, 50_000.0, 80)

    baseline_score = spike.phase_prefix_metrics(baseline, split=20)
    changed_score = spike.phase_prefix_metrics(changed_suffix, split=20)

    assert changed_score["constant_m"] == pytest.approx(
        baseline_score["constant_m"]
    )
    assert changed_score["rate_m_s"] == pytest.approx(
        baseline_score["rate_m_s"]
    )
    assert baseline_score["heldout_peak_to_peak_m"] == pytest.approx(0.0)
    assert changed_score["heldout_peak_to_peak_m"] > 49_000.0


def test_ionosphere_free_weights_preserve_geometry_and_cancel_first_order() -> None:
    coordinate = spike.manifest()["coordinate"]
    weights = coordinate["weights"]

    assert weights["L1C"] + weights["L2W"] == pytest.approx(1.0)
    assert coordinate["weight_invariants"]["first_order_dispersive_sum"] == (
        pytest.approx(0.0, abs=1e-30)
    )
    assert coordinate["time_derivative"] == "NONE"
    assert coordinate["suffix_refit"] is False


def test_four_link_interval_is_propagated_before_affine_projection() -> None:
    gain = old.affine_projection_peak_to_peak_gain(384, 77, 30.0)
    term = spike.per_link_interval_term(
        {
            "term": "TEST_PATH",
            "per_link_path_bound_m": 2.0,
            "state": "MODELED_INTERVAL",
        },
        gain,
    )

    assert term["four_link_coordinate_amplitude_bound_m"] == pytest.approx(8.0)
    assert term["heldout_peak_to_peak_bound_m"] == pytest.approx(8.0 * gain)


def test_witnesses_refuse_health_without_correcting_suffix_score() -> None:
    topology = spike.witness_topology()

    assert topology["cycle_slip_and_continuity"][
        "LLI_ON_L1C_AND_L2W"
    ] == "REQUIRED_BREAKS_SEGMENT"
    assert topology["cycle_slip_and_continuity"][
        "GEOMETRY_FREE_PHASE_CONTINUITY"
    ] == "REQUIRED_BREAKS_SEGMENT"
    assert topology["same_path_code"]["fatal_every_epoch"] is False
    assert topology["same_path_code"][
        "role"
    ] == "PREDECLARED_ADMISSION_OR_REFUSAL_WITNESS_NOT_PHASE_CORRECTION"
    assert topology["optional_diagnostic"][
        "fatal_without_quantitative_rule_and_coherent_units"
    ] is False
    assert "NOT_TUNE_THE_ORBITAL_SCORE" in topology["suffix_rule"]


def test_synthetic_physical_mismatch_survives_prefix_affine_null() -> None:
    stress = spike.synthetic_mismatch_stress()

    assert stress["generated_from_nominal_orbit"] is False
    assert stress["family"] == "CONSTANT_UNMODELED_LINE_OF_SIGHT_ACCELERATION"
    assert stress["survives_affine_null"] is True
    assert stress["heldout_peak_to_peak_m"] == pytest.approx(2643.84)


def test_pairwise_envelope_requires_strict_positive_margin() -> None:
    positive = spike.combine_terms(
        10.0, [{"heldout_peak_to_peak_bound_m": 4.9}]
    )
    blocked = spike.combine_terms(
        10.0, [{"heldout_peak_to_peak_bound_m": 5.0}]
    )

    assert positive["outcome"] == spike.OUTCOME_DISCRIMINATIVE
    assert positive["remaining_physical_margin_m"] == pytest.approx(0.2)
    assert blocked["outcome"] == spike.OUTCOME_ENVELOPE_DOMINATES
    assert blocked["remaining_physical_margin_m"] == pytest.approx(0.0)


def test_invalid_numeric_envelope_is_refused() -> None:
    for value in (float("nan"), float("inf"), -0.1):
        with pytest.raises(spike.PhaseQuotientError):
            spike.combine_terms(10.0, [{"heldout_peak_to_peak_bound_m": value}])


def test_manifest_has_no_measurement_or_candidate_selection_surface() -> None:
    manifest = spike.manifest()
    encoded = spike.strict_json(manifest)

    assert manifest["phase"] == "SPIKE"
    assert manifest["fixture"]["role"] == "HISTORICAL_DEVELOPMENT_ONLY_NEVER_PRIMARY"
    assert "observation product" in encoded.lower()
    assert "new satellite station date signal or window selection" in manifest[
        "forbidden"
    ]
    assert json.loads(encoded) == manifest
    with pytest.raises(ValueError):
        spike.strict_json({"bad": float("nan")})


def test_frozen_historical_spike_is_positive_without_observation_authority() -> None:
    canonical = RECEIPT.read_bytes().replace(b"\r\n", b"\n")
    receipt = json.loads(canonical)

    assert sha256(canonical).hexdigest() == (
        "12a93c7f52799042d062747e322568d78d2197721ce05cb84c6214ed36a431e1"
    )
    assert receipt["manifest_sha256"] == (
        "c7a2ce41b2c40e31d3ac41a15ae314baef7c7f7aeb50174b2f6956b89bfc53f0"
    )
    assert receipt["outcome"] == spike.OUTCOME_DISCRIMINATIVE
    assert receipt["null_scores"]["controlling_null"] == "FROZEN_WRONG_ORBIT_G22"
    assert receipt["null_scores"]["controlling_heldout_separation_m"] == (
        pytest.approx(742_458.2974898004)
    )
    assert receipt["pairwise_comparison_envelope_m"] == pytest.approx(
        23_037.025031400655
    )
    assert receipt["remaining_physical_margin_m"] == pytest.approx(
        719_421.2724583998
    )
    assert receipt["physical_terms"][0]["term"] == "STATION_EVENT_TIME"
    assert receipt["legacy_frequency_regression"]["absolute_error_hz"] < 1e-12
    assert receipt["legacy_frequency_regression"][
        "controlling_heldout_separation_hz"
    ] == pytest.approx(403.37545402996614)
    assert set(receipt["observation_access"].values()) == {0}
    assert receipt["new_candidate_selected"] is False
    assert receipt["prospective_plan_frozen"] is False
    assert receipt["measurement_authorized"] is False
