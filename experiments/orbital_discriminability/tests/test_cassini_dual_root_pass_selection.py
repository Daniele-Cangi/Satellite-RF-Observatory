from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    cassini_dual_root_pass_selection as selection,
)


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "CASSINI_DUAL_ROOT_PASS_SELECTION_RECEIPT.json"


def test_frozen_candidate_topology_and_media_admission() -> None:
    selection.validate_frozen_selection()

    assert len(selection.CANDIDATES) == 5
    assert [
        candidate.candidate_id
        for candidate in selection.CANDIDATES
        if candidate.geometry_start_utc is not None
    ] == ["SROC_2005_159_DSS25_DSS55"]
    for candidate in selection.CANDIDATES:
        assert len(candidate.product_names) == 4
        assert len(set(candidate.complexes)) == 2
        for station in candidate.stations:
            suffix = station[-2:]
            products = [
                name
                for name in candidate.product_names
                if name[-4:-2] == suffix
            ]
            assert {name[-5] for name in products} == {"x", "k"}


def test_predict_solutions_are_prepass_and_cover_each_session() -> None:
    for candidate in selection.CANDIDATES:
        creation = selection._utc(candidate.predict.product_creation_utc)
        start = selection._utc(candidate.overlap_start_utc)
        stop = selection._utc(candidate.predict.coverage_stop_utc)
        coverage_start = selection._utc(
            candidate.predict.coverage_start_utc
        )
        assert candidate.predict.product_version_type == "PREDICT"
        assert creation < start
        assert coverage_start <= start <= stop


def test_affine_projection_is_prefix_only_and_detects_curvature() -> None:
    elapsed = np.arange(40, dtype=np.float64) * selection.GRID_STEP_S
    affine = 11.0 - 0.03 * elapsed
    curved = affine + 0.0002 * elapsed**2

    affine_metrics = selection._prefix_affine_metrics(affine, 8)
    curved_metrics = selection._prefix_affine_metrics(curved, 8)

    assert affine_metrics["peak_to_peak_hz"] < 1e-12
    assert curved_metrics["peak_to_peak_hz"] > 1.0
    assert curved_metrics["rms_hz"] > 0.0


def test_unresolved_conditions_have_no_numeric_substitution() -> None:
    ledger = {
        row["condition"]: row
        for row in selection.physical_condition_ledger()
    }
    required = {
        "HIGHER_ORDER_PLASMA",
        "EARTH_TROPOSPHERE_DIFFERENTIAL",
        "RECEIVER_PROPER_TIME_GRAVITY_DIFFERENTIAL",
        "USO_RETARDED_TIME_COUPLING",
        "STATION_PHASE_CENTER_CABLE_DELAY",
        "FREQUENCY_REFERENCE_STABILITY",
        "FINITE_INTEGRATION_SPECTRAL_SMEARING",
        "PREDICT_SPK_ORBIT_ERROR",
        "OPEN_TERM_CORRELATION",
    }
    assert required <= set(ledger)
    assert all(row["numeric_substitution"] is None for row in ledger.values())


def test_approximation_policy_does_not_invent_probabilities() -> None:
    policy = selection.approximation_policy()

    assert policy["representation"] == (
        "NON_PROBABILISTIC_CAUSAL_STATE_ENVELOPE"
    )
    assert "UNRESOLVED_AS_ZERO" in policy["prohibited"]
    assert "ROOT_SUM_SQUARE_WITHOUT_INDEPENDENCE" in policy["prohibited"]
    assert "UNJUSTIFIED_PROBABILITY_AMPLITUDES" in policy["prohibited"]


def test_strict_json_rejects_nonfinite_values() -> None:
    with pytest.raises(ValueError):
        selection.strict_json({"value": float("nan")})
    with pytest.raises(ValueError):
        selection.strict_json({"value": float("inf")})


def test_authoritative_receipt_records_positive_geometry_only() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    screen = receipt["geometry_screen"]

    assert receipt["selection_manifest_sha256"] == (
        selection.selection_manifest_sha256()
    )
    assert receipt["outcome"] == selection.OUTCOME_POSITIVE
    assert screen["visibility"]["joint_visible"] is True
    assert screen["controlling_heldout_peak_to_peak_hz"] == pytest.approx(
        0.2991723488431748, abs=1e-12
    )
    assert screen["timing_envelope"]["two_stream_two_sided_hz"] == (
        pytest.approx(1.8707257964933888e-05, abs=1e-15)
    )
    assert receipt["access"] == {
        "amplitude_values": 0,
        "rsr_header_bytes": 0,
        "rsr_iq_bytes": 0,
    }
    assert receipt["experiment_frozen"] is False
    assert "orbital model preference" in receipt["claim"]["not_authorized"]


def test_nonadmitted_candidates_remain_not_evaluated() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    candidates = receipt["candidates"]

    assert candidates[0]["geometry_screen_state"] == "EVALUATED"
    assert all(
        candidate["geometry_screen_state"] == "NOT_EVALUATED"
        for candidate in candidates[1:]
    )
    assert candidates[1]["media_scope"] == "MEDIA_SCOPE_UNKNOWN"
    assert candidates[3]["media_scope"] == "FULL_OVERLAP_OCCULTATION_MEDIA"


def test_manifest_hash_is_stable_regression() -> None:
    assert selection.selection_manifest_sha256() == (
        "9f0f409e2067820578ad8c586213ee8fee1288465c99065f2453c1742053ce69"
    )


def test_all_frozen_utc_values_are_timezone_aware() -> None:
    for candidate in selection.CANDIDATES:
        for text in (
            candidate.overlap_start_utc,
            candidate.overlap_stop_utc,
            candidate.predict.product_creation_utc,
            candidate.predict.coverage_start_utc,
            candidate.predict.coverage_stop_utc,
        ):
            assert datetime.fromisoformat(
                text.replace("Z", "+00:00")
            ).tzinfo is not None
