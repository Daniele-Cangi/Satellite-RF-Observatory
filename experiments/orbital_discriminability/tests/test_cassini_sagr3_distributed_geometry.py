from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import cassini_dss26_one_way as one_way
from experiments.orbital_discriminability import (
    cassini_sagr3_distributed_geometry as screen,
)


def _fixed_state(position, velocity=(0.0, 0.0, 0.0)):
    state = one_way.StateVector(tuple(position), tuple(velocity))
    return lambda _epoch: state


def test_forward_light_time_uses_relative_scalar():
    c = one_way.SPEED_OF_LIGHT_M_S
    event = screen.solve_forward_event(
        100_000_000.0,
        _fixed_state((c, 0.0, 0.0)),
        _fixed_state((0.0, 0.0, 0.0)),
        _fixed_state((2.0 * c, 0.0, 0.0)),
        tolerance_s=1e-12,
    )

    assert event.geometric_light_time_s == pytest.approx(1.0, abs=1e-15)
    assert event.receive_et_tdb_s == pytest.approx(100_000_001.0, abs=0.0)
    assert event.kinematic_frequency_factor == pytest.approx(1.0, abs=0.0)
    assert np.degrees(event.elevation_rad) == pytest.approx(90.0, abs=1e-12)


def test_bounded_product_topology_is_not_three_independent_roots():
    roles = {product.role: product for product in screen.PRODUCTS}

    assert set(roles) == {
        "MEASUREMENT_X_DSS25",
        "WITNESS_KA_DSS25",
        "MEASUREMENT_X_DSS65",
    }
    assert roles["MEASUREMENT_X_DSS25"].start_utc == roles["WITNESS_KA_DSS25"].start_utc
    assert roles["MEASUREMENT_X_DSS25"].records == roles["WITNESS_KA_DSS25"].records
    assert roles["MEASUREMENT_X_DSS25"].receive_station == roles["WITNESS_KA_DSS25"].receive_station
    assert roles["MEASUREMENT_X_DSS65"].receive_station != roles["MEASUREMENT_X_DSS25"].receive_station
    assert all(product.uplink_station == "DSS-14" for product in roles.values())


def test_cross_band_decomposition_recovers_common_and_dispersive_terms():
    common = np.asarray([1e-8, -2e-8, 4e-8])
    dispersive = np.asarray([1e9, -4e9, 3e9])
    observed_x = common + dispersive / screen.X_BAND_HZ**2
    observed_ka = common + dispersive / screen.KA_BAND_HZ**2

    recovered_common, recovered_dispersive = screen.decompose_common_and_dispersive(
        observed_x, observed_ka
    )

    assert recovered_common == pytest.approx(common, rel=0.0, abs=1e-23)
    assert recovered_dispersive == pytest.approx(dispersive, rel=1e-9, abs=1e-6)


def test_prefix_affine_null_cannot_refit_the_holdout():
    elapsed = np.arange(100, dtype=np.float64)
    curve = 4.0 - 0.25 * elapsed
    curve[20:] += np.linspace(0.0, 3.0, 80) ** 2

    metrics = screen._prefix_affine_metrics(curve, 20)

    assert metrics["prefix_rmse_hz"] < 1e-12
    assert metrics["peak_to_peak_hz"] == pytest.approx(9.0, abs=1e-10)


def test_manifest_is_deterministic_and_forbids_measurement_access():
    first = screen.screen_manifest_sha256()
    second = screen.screen_manifest_sha256()

    assert first == second
    assert len(first) == 64
    assert "header" not in screen.screen_distributed_geometry.__annotations__
    with pytest.raises(ValueError):
        screen.strict_json({"not_finite": float("inf")})


def test_frozen_receipt_is_a_screen_not_physical_admission():
    path = Path(screen.__file__).with_name(
        "CASSINI_SAGR3_DISTRIBUTED_GEOMETRY_RECEIPT.json"
    )
    receipt = json.loads(path.read_text(encoding="utf-8"))

    assert receipt["screen_outcome"] == screen.OUTCOME_POSITIVE
    assert receipt["coordinate"]["records"] == 16_800
    assert receipt["visibility"]["joint_visible_on_complete_grid"] is True
    assert receipt["physical_admission"] is False
    assert receipt["rsr_header_access_authorized"] is False
    assert receipt["iq_access_authorized"] is False
    assert receipt["detector_authorized"] is False
    assert receipt["same_path_witness"]["raw_cross_band_difference_is_orbital_measurement"] is False
