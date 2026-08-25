from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.orbital_discriminability import gnss_phase_short_window_plan as frozen


ROOT = Path(__file__).resolve().parents[1]
DURATION_RECEIPT = ROOT / frozen.DURATION_RECEIPT_NAME


def test_roles_are_distinct_and_frozen_before_product_discovery() -> None:
    plan = frozen.plan()
    qualification = plan["roles"]["qualification"]
    primary = plan["roles"]["primary"]

    assert qualification["doy"] == 217
    assert qualification["raw_start_gps"] == "2026-08-05T05:54:00 GPS"
    assert qualification["raw_stop_gps"] == "2026-08-05T07:03:00 GPS"
    assert primary["doy"] == 220
    assert primary["raw_start_gps"] == "2026-08-08T05:42:00 GPS"
    assert primary["raw_stop_gps"] == "2026-08-08T06:51:00 GPS"
    assert qualification["doy"] != primary["doy"]
    assert plan["role_selection"]["reserve"] is None
    assert plan["role_selection"]["infrastructure_availability_used"] is False
    assert plan["role_selection"]["observation_values_used"] is False
    assert primary["access"] == "SEALED_UNDISCOVERED_UNAUTHORIZED"


def test_shorter_partition_and_witness_boundaries_are_exact() -> None:
    plan = frozen.plan()

    assert plan["partition"] == {
        "step_s": 30,
        "raw_epochs": 139,
        "raw_elapsed_s": 4140,
        "feature_epochs": 137,
        "feature_raw_indices_inclusive": [1, 137],
        "calibration_epochs": 77,
        "calibration_raw_indices_inclusive": [1, 77],
        "heldout_epochs": 60,
        "heldout_raw_indices_inclusive": [78, 137],
        "holdout_may_refit_nuisance": False,
    }
    witness = plan["qualification"]["same_path_code_witness"]
    assert witness["minimum_presence_fraction_per_link"] == 0.95
    assert witness["required_raw_indices"] == [1, 77, 78, 137]
    assert witness["may_adjust_phase_score"] is False
    assert plan["measurement_coordinate"]["derivative"] == "NONE"


def test_primary_nulls_and_physical_guard_are_not_weakened() -> None:
    plan = frozen.plan()

    assert plan["primary_hypotheses"]["wrong_orbits"] == ["G01", "G14", "G17"]
    assert plan["primary_hypotheses"][
        "wrong_orbit_predicted_separations_m"
    ] == frozen.ALTERNATIVE_ORBITS
    assert plan["scoring"]["orbital_calibration_peak_to_peak_admission_m"] == (
        pytest.approx(1192.1168692918313)
    )
    assert plan["scoring"]["heldout_preference_margin_required_m"] == (
        pytest.approx(2384.2337385836627)
    )
    assert plan["scoring"]["frozen_remaining_physical_margin_m"] == (
        pytest.approx(6473.198142081582)
    )
    assert plan["scoring"]["suffix_refit"] == "FORBIDDEN"
    assert plan["scoring"]["free_time_phase"] == "FORBIDDEN"


def test_exact_duration_receipt_authorizes_role_freeze_only() -> None:
    receipt = frozen.verify_duration_receipt(DURATION_RECEIPT)

    assert receipt["source_commit"] == frozen.DURATION_SOURCE_COMMIT
    assert receipt["outcome"] == "PHASE_SHORTER_WINDOW_PHYSICALLY_AVAILABLE"
    assert all(value == 0 for value in receipt["observation_access"].values())
    assert all(value is None for value in receipt["candidate_roles"].values())


def test_changed_duration_receipt_is_refused(tmp_path: Path) -> None:
    changed = json.loads(DURATION_RECEIPT.read_text(encoding="utf-8"))
    changed["shortest_available_heldout_epochs"] = 120
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(changed), encoding="utf-8")

    with pytest.raises(frozen.ShortWindowPlanError, match="DURATION_RECEIPT_CHANGED"):
        frozen.verify_duration_receipt(path)


def test_access_boundary_has_no_observation_surface() -> None:
    plan = frozen.plan()
    access = plan["access_boundary"]

    assert access["observation_products_discovered"] == 0
    assert access["observation_headers_opened"] == 0
    assert access["observation_payload_bytes"] == 0
    assert access["observation_values_accessed"] == 0
    assert access["primary_access"] == "FORBIDDEN"
    assert plan["new_gate_created"] is False
    assert plan["generic_framework_created"] is False


def test_manifest_is_strict_and_finite() -> None:
    encoded = frozen.strict_json(frozen.plan())

    assert json.loads(encoded) == frozen.plan()
    assert "NaN" not in encoded and "Infinity" not in encoded
    assert len(frozen.manifest_sha256()) == 64
