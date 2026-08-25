from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.orbital_discriminability import gnss_orbit_pair_envelope as envelope


ROOT = Path(__file__).resolve().parents[1]
SCREEN_RECEIPT = ROOT / envelope.SCREEN_RECEIPT_NAME
ENVELOPE_RECEIPT = ROOT / "GNSS_ORBIT_PAIR_PHYSICAL_ENVELOPE_RECEIPT.json"


def test_manifest_freezes_one_geometry_and_has_no_observation_surface() -> None:
    manifest = envelope.manifest()

    assert manifest["geometry"] == {
        "doy": 220,
        "target": "G14",
        "reference": "G17",
        "wrong_target": "G22",
        "pre_roll_start_gps": "2026-08-08T04:37:00 GPS",
        "raw_start_gps": "2026-08-08T05:07:00 GPS",
        "raw_stop_gps": "2026-08-08T08:19:30 GPS",
        "controlling_heldout_separation_hz": 403.37545402996614,
    }
    assert manifest["partition"] == {
        "raw_epochs": 386,
        "feature_epochs": 384,
        "calibration_epochs": 77,
        "heldout_epochs": 307,
    }
    assert "observation product" in envelope.strict_json(manifest).lower()


def test_exact_screen_receipt_remains_unopened_and_selects_g22_null() -> None:
    receipt = envelope.validate_screen_receipt(SCREEN_RECEIPT)

    assert receipt["selected_geometry"]["wrong_orbit_null"][
        "controlling_alternative"
    ] == "G22"
    assert all(value == 0 for value in receipt["observation_access"].values())


def test_linear_pairwise_combination_blocks_when_envelope_dominates() -> None:
    result = envelope.combine_terms(
        10.0,
        [
            {"heldout_peak_to_peak_bound_hz": 3.0},
            {"heldout_peak_to_peak_bound_hz": 2.1},
        ],
    )

    assert result == {
        "one_model_physical_envelope_hz": pytest.approx(5.1),
        "pairwise_comparison_envelope_hz": pytest.approx(10.2),
        "remaining_physical_margin_hz": pytest.approx(-0.2),
        "negative_result_interpretable_if_measurement_admitted": False,
        "outcome": envelope.OUTCOME_BLOCKED,
    }


def test_linear_pairwise_combination_admits_only_strict_positive_margin() -> None:
    result = envelope.combine_terms(
        10.0, [{"heldout_peak_to_peak_bound_hz": 4.999}]
    )

    assert result["outcome"] == envelope.OUTCOME_ADMITTED
    assert result["remaining_physical_margin_hz"] == pytest.approx(0.002)
    assert result["negative_result_interpretable_if_measurement_admitted"] is True


def test_nonfinite_or_negative_contribution_is_refused() -> None:
    for value in (float("nan"), float("inf"), -0.1):
        with pytest.raises(envelope.OrbitPairEnvelopeError):
            envelope.combine_terms(10.0, [{"heldout_peak_to_peak_bound_hz": value}])


def test_strict_json_refuses_nonfinite_value() -> None:
    assert json.loads(envelope.strict_json(envelope.manifest())) == envelope.manifest()
    with pytest.raises(ValueError):
        envelope.strict_json({"bad": float("nan")})


def test_frozen_envelope_receipt_closes_before_observation_access() -> None:
    receipt = json.loads(ENVELOPE_RECEIPT.read_text(encoding="utf-8"))

    assert receipt["compiler_source_commit"] == (
        "bb92583cf04e94c8ebda0558a1d5845ab20fbb04"
    )
    assert receipt["outcome"] == envelope.OUTCOME_BLOCKED
    assert receipt["null_scores"]["controlling_null"] == "WRONG_ORBIT_G22"
    assert receipt["null_scores"]["controlling_heldout_separation_hz"] == (
        pytest.approx(403.37545402996614)
    )
    assert receipt["one_model_physical_envelope_hz"] == pytest.approx(
        366.877020793687
    )
    assert receipt["pairwise_comparison_envelope_hz"] == pytest.approx(
        733.754041587374
    )
    assert receipt["remaining_physical_margin_hz"] == pytest.approx(
        -330.37858755740785
    )
    assert receipt["negative_result_interpretable_if_measurement_admitted"] is False
    assert all(value == 0 for value in receipt["observation_access"].values())
    assert receipt["prospective_plan_frozen"] is False
    assert receipt["measurement_authorized"] is False
