from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import gnss_orbit_pair_screen as pair


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "GNSS_ORBIT_PAIR_SCREEN_RECEIPT.json"


def test_authority_and_manifest_are_frozen_without_observation_surface() -> None:
    assert [authority.doy for authority in pair.AUTHORITIES] == [216, 217, 218, 219, 220]
    assert [authority.bytes for authority in pair.AUTHORITIES] == [
        8_458_713,
        8_362_647,
        8_375_526,
        8_383_950,
        8_285_778,
    ]
    manifest = pair.manifest()
    assert manifest["parameters"] == {
        "grid_step_s": 30.0,
        "minimum_elevation_deg": 15.0,
        "pre_roll_epochs": 60,
        "pre_roll_duration_s": 1800.0,
        "raw_epochs": 386,
        "feature_epochs": 384,
        "calibration_epochs": 77,
        "heldout_epochs": 307,
        "central_derivative_edge_epochs_dropped": 2,
    }
    serialized = pair.strict_json(manifest).lower()
    assert "observation product discovery or selection" in serialized
    assert "observation_path" not in serialized


def test_guarded_block_never_shortens_and_chooses_robust_earliest_tie() -> None:
    too_short = np.full(pair.GUARDED_BLOCK_EPOCHS - 1, 40.0)
    assert pair.select_guarded_block(too_short) is None

    values = np.full(pair.GUARDED_BLOCK_EPOCHS + 3, 20.0)
    values[0] = 15.1
    values[-1] = 15.1
    start, minimum = pair.select_guarded_block(values)

    assert start == 1
    assert minimum == pytest.approx(20.0)


def test_subthreshold_epoch_is_not_bridged() -> None:
    values = np.full(pair.GUARDED_BLOCK_EPOCHS * 2, 30.0)
    values[pair.GUARDED_BLOCK_EPOCHS - 1] = 14.999

    start, minimum = pair.select_guarded_block(values)

    assert start == pair.GUARDED_BLOCK_EPOCHS
    assert minimum == pytest.approx(30.0)


def test_missing_broadcast_epoch_is_a_gap_not_a_whole_day_error() -> None:
    values = np.full(pair.GUARDED_BLOCK_EPOCHS * 2, 30.0)
    values[pair.GUARDED_BLOCK_EPOCHS - 1] = np.nan

    start, minimum = pair.select_guarded_block(values)

    assert start == pair.GUARDED_BLOCK_EPOCHS
    assert minimum == pytest.approx(30.0)


def test_prefix_affine_uses_exact_frozen_partition() -> None:
    elapsed = np.arange(pair.FEATURE_EPOCHS, dtype=np.float64) * 30.0
    curve = 3.0 + 0.01 * elapsed + 3e-7 * elapsed**2

    metrics = pair.prefix_affine(curve)

    assert metrics["heldout_peak_to_peak_hz"] > 0.0
    with pytest.raises(pair.OrbitPairScreenError, match="feature grid changed"):
        pair.prefix_affine(curve[:-1])


def test_manifest_hash_and_json_are_deterministic_and_strict() -> None:
    assert pair.manifest_sha256() == pair.manifest_sha256()
    assert json.loads(pair.strict_json(pair.manifest())) == pair.manifest()
    with pytest.raises(ValueError):
        pair.strict_json({"bad": float("nan")})


def test_frozen_receipt_selects_only_one_geometry_without_observation_access() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))

    assert receipt["outcome"] == pair.OUTCOME_SELECTED
    assert receipt["screen_source_commit"] == (
        "4ea9fbcd78063d6c7a535b5c6e3917ceb5ef586f"
    )
    assert receipt["rankable_candidate_count"] == 20
    assert receipt["selection_limit"] == 1
    assert receipt["selected_geometry"]["target"] == "G14"
    assert receipt["selected_geometry"]["reference"] == "G17"
    assert receipt["selected_geometry"]["doy"] == 220
    assert receipt["selected_geometry"]["wrong_orbit_null"][
        "controlling_alternative"
    ] == "G22"
    assert receipt["observation_access"] == {
        "products_discovered": 0,
        "products_selected": 0,
        "headers_opened": 0,
        "payload_bytes": 0,
        "values_accessed": 0,
    }
    assert receipt["physical_envelope_compiled"] is False
    assert receipt["prospective_plan_frozen"] is False
    assert receipt["measurement_authorized"] is False
