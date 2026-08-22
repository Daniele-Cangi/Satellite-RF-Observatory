from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import gnss_double_difference_screen as screen


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "GNSS_DOUBLE_DIFFERENCE_GEOMETRY_SCREEN_RECEIPT.json"


def real_g11_ephemeris_fixture() -> screen.GpsEphemeris:
    return screen.GpsEphemeris(
        satellite="G11",
        toc_gps=datetime(2026, 8, 3, tzinfo=timezone.utc),
        af0_s=-0.0002546012401581,
        af1_s_s=1.216449163621e-11,
        af2_s_s2=0.0,
        iode=231.0,
        crs_m=-27.28125,
        delta_n_rad_s=4.094813422558e-09,
        m0_rad=-2.364654371357,
        cuc_rad=-1.298263669014e-06,
        eccentricity=0.00254776480142,
        cus_rad=1.09001994133e-05,
        sqrt_a_m_sqrt=5153.658655167,
        toe_sow=86400.0,
        cic_rad=-9.313225746155e-09,
        omega0_rad=0.3497928194178,
        cis_rad=-2.98023223877e-08,
        i0_rad=0.9627769322323,
        crc_m=170.3125,
        argument_perigee_rad=-2.34655599591,
        omega_dot_rad_s=-7.823540167565e-09,
        idot_rad_s=-2.582250418238e-10,
        gps_week=2430,
        sv_accuracy_m=2.0,
        sv_health=0,
        tgd_s=-8.847564458847e-09,
        transmission_sow=79218.0,
        fit_interval_h=4.0,
    )


def test_real_broadcast_position_regression() -> None:
    position = screen.broadcast_ecef(
        real_g11_ephemeris_fixture(),
        datetime(2026, 8, 3, tzinfo=timezone.utc),
    )

    assert position == pytest.approx(
        [-4949575.310954183, 14371315.457214491, 21839538.10848933],
        abs=1e-6,
    )


def test_double_difference_removes_common_receiver_and_satellite_terms() -> None:
    geometry = {
        "left_target": np.asarray([1.0, 1.2, 1.4]),
        "left_reference": np.asarray([0.2, 0.1, 0.0]),
        "right_target": np.asarray([0.8, 0.7, 0.6]),
        "right_reference": np.asarray([-0.1, -0.2, -0.3]),
    }
    receiver_left = np.asarray([10.0, 11.0, 12.0])
    receiver_right = np.asarray([-4.0, -3.0, -2.0])
    satellite_target = np.asarray([8.0, 7.0, 6.0])
    satellite_reference = np.asarray([2.0, 3.0, 4.0])

    observed = screen.double_difference_hz(
        geometry["left_target"] + receiver_left + satellite_target,
        geometry["left_reference"] + receiver_left + satellite_reference,
        geometry["right_target"] + receiver_right + satellite_target,
        geometry["right_reference"] + receiver_right + satellite_reference,
    )
    expected = screen.double_difference_hz(*geometry.values())

    assert observed == pytest.approx(expected)


def test_identical_station_geometry_has_zero_double_difference() -> None:
    target = np.asarray([0.1, 0.2, 0.3])
    reference = np.asarray([-0.4, -0.2, 0.0])

    assert screen.double_difference_hz(target, reference, target, reference) == (
        pytest.approx(np.zeros(3))
    )


def test_prefix_affine_null_is_calibration_only_and_detects_curvature() -> None:
    elapsed = np.arange(100, dtype=np.float64) * screen.GRID_STEP_S
    affine = 4.0 - 0.02 * elapsed
    curved = affine + 2e-6 * elapsed**2

    null = screen.prefix_affine_metrics(affine, 20, screen.GRID_STEP_S)
    mismatch = screen.prefix_affine_metrics(curved, 20, screen.GRID_STEP_S)

    assert null["heldout_peak_to_peak_hz"] < 1e-10
    assert mismatch["heldout_peak_to_peak_hz"] > 10.0


def test_visibility_segments_never_bridge_a_false_epoch() -> None:
    assert screen.contiguous_true_segments(
        [False, True, True, False, True, False]
    ) == ((1, 3), (4, 5))


def test_manifest_is_stable_and_has_no_observation_input() -> None:
    manifest = screen.screen_manifest()

    assert screen.screen_manifest_sha256() == (
        "8a97c9fa6330ddc3fd54538bd22682edcc02697cb76ba7edb1a9c1def7963764"
    )
    assert "RINEX observation access" in manifest["forbidden"]
    assert "observation" not in manifest["parameters"]


def test_historical_receipt_remains_geometry_only_and_unopened() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))

    assert receipt["outcome"] == screen.OUTCOME_SHORTLIST
    assert receipt["screen_manifest_sha256"] == (
        "68d5f24eca97ab35e0ba5fd4fc82b4ab753150c880f8a1014ef8a5b388761a12"
    )
    assert receipt["geometry_screen"]["candidate_windows"] == 176
    assert [row["target"] for row in receipt["geometry_screen"]["shortlist"]] == [
        "G11",
        "G19",
        "G18",
    ]
    assert receipt["observation_access"] == {
        "carrier_phase_values": 0,
        "doppler_values": 0,
        "observation_payload_bytes": 0,
        "rinex_observation_files": 0,
        "snr_values": 0,
    }
    for product in receipt["observation_product_metadata"]:
        assert product["availability"] == "AVAILABLE_NOT_OPENED"
        assert product["sha256"] is None
    assert receipt["experiment_frozen"] is False
    assert receipt["measurement_authorized"] is False


def test_strict_json_refuses_nonfinite_values() -> None:
    with pytest.raises(ValueError):
        screen.strict_json({"value": float("nan")})
    with pytest.raises(ValueError):
        screen.strict_json({"value": float("inf")})
