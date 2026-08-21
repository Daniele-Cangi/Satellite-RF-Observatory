from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import cassini_dss26_one_way as one_way
from experiments.orbital_discriminability import cassini_gwe1_geometry_screen as screen


def test_bounded_topology_is_one_root_with_three_links_and_two_witnesses():
    assert [session.role for session in screen.SESSIONS] == [
        "DEVELOPMENT_CANDIDATE",
        "RESERVE_CANDIDATE",
        "PRIMARY_CANDIDATE",
    ]
    for session in screen.SESSIONS:
        assert {
            (item.uplink_band, item.downlink_band) for item in session.rsr_products
        } == {
            ("X", "X"),
            ("X", "KA"),
            ("KA", "KA"),
        }
        assert {item.instrument for item in session.path_delay_products} == {
            "AWVR1",
            "AWVR2",
        }
        assert session.common_start_utc == max(
            item.start_utc
            for item in (*session.rsr_products, *session.path_delay_products)
        )
        assert session.common_stop_utc == min(
            item.stop_utc
            for item in (*session.rsr_products, *session.path_delay_products)
        )


def test_rectilinear_null_is_frozen_at_prefix_end():
    nominal = lambda _epoch: one_way.StateVector(
        position_m=(10.0, 20.0, 30.0),
        velocity_m_s=(1.0, -2.0, 0.5),
    )
    null = screen._rectilinear_state_provider(nominal, 100.0)

    assert null(90.0).position_m == pytest.approx((0.0, 40.0, 25.0))
    assert null(110.0).position_m == pytest.approx((20.0, 0.0, 35.0))
    assert null(200.0).velocity_m_s == (1.0, -2.0, 0.5)


def test_affine_null_fits_prefix_only_and_cannot_refit_holdout():
    elapsed = np.arange(100, dtype=np.float64)
    curve = 2.0 + 0.1 * elapsed
    curve[20:] += np.linspace(0.0, 4.0, 80) ** 2

    residual, metrics = screen._prefix_affine_residual(curve, 20, 1.0)

    assert np.max(np.abs(residual[:20])) < 1e-12
    assert metrics["heldout_peak_to_peak"] == pytest.approx(16.0, abs=1e-10)


def test_manifest_is_deterministic_and_forbids_measurement_access():
    assert screen.screen_manifest_sha256() == screen.screen_manifest_sha256()
    assert len(screen.screen_manifest_sha256()) == 64
    assert "header" not in screen.screen_gwe1_geometry.__annotations__
    with pytest.raises(ValueError):
        screen.strict_json({"bad": float("nan")})


def test_exact_kernel_manifest_binds_prepass_predict_trajectory():
    trajectory = next(
        item for item in screen.KERNELS if item.role == "CASSINI_TRAJECTORY"
    )

    assert trajectory.name == "010222A_SK_JP054_JP458.bsp"
    assert "PREDICT_CREATED_2001_02_22" in trajectory.independence
    assert "NO_RECONSTRUCTED_ARC" in trajectory.independence


def test_frozen_receipt_keeps_screen_separate_from_admission():
    receipt_path = Path(screen.__file__).with_name(
        "CASSINI_GWE1_GEOMETRY_SCREEN_RECEIPT.json"
    )
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert receipt["screen_manifest_sha256"] == screen.screen_manifest_sha256()
    assert receipt["screen_outcome"] == screen.OUTCOME_POSITIVE
    assert receipt["physical_admission"] is False
    assert receipt["rsr_header_access_authorized"] is False
    assert receipt["path_delay_table_access_authorized"] is False
    assert receipt["iq_access_authorized"] is False
    assert receipt["detector_authorized"] is False
    assert receipt["causal_topology"]["independent_receive_roots"] == ["DSS-25"]
    primary = next(
        item for item in receipt["screens"] if item["role"] == "PRIMARY_CANDIDATE"
    )
    ka = primary["screening_carrier_scalings"]["NOMINAL_KA_32_GHZ"]
    assert ka["orbital_vs_rectilinear_peak_to_peak_hz"] == pytest.approx(
        0.22840931771829498, rel=0.0, abs=1e-12
    )
    assert (
        ka["orbital_vs_rectilinear_peak_to_peak_hz"]
        < ka["orbital_vs_affine_peak_to_peak_hz"]
    )
