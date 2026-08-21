from __future__ import annotations

from hashlib import sha256
import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    cassini_sagr3_composite_xka as composite,
)
from experiments.orbital_discriminability import (
    cassini_sagr3_distributed_geometry as geometry,
)


def test_time_varying_weights_preserve_common_and_cancel_first_order_plasma():
    samples = 401
    phase = np.linspace(-1.0, 1.0, samples)
    fx = geometry.X_BAND_HZ + 125_000.0 * phase
    fka = geometry.KA_BAND_HZ + 475_000.0 * phase
    common = 2.0e-5 + 3.0e-8 * phase + 7.0e-9 * phase**2
    plasma = 8.0e14 * (1.0 + 0.2 * phase)
    zx = common + plasma / fx**2
    zka = common + plasma / fka**2

    weight_x, weight_ka = composite.composition_weights(fx, fka)
    recovered = composite.compose_dss25_common_fraction(zx, zka, fx, fka)

    assert np.allclose(weight_x + weight_ka, 1.0, rtol=0.0, atol=3e-16)
    assert np.allclose(
        weight_x / fx**2 + weight_ka / fka**2,
        0.0,
        rtol=0.0,
        atol=1e-35,
    )
    assert np.allclose(recovered, common, rtol=0.0, atol=8e-21)


def test_composite_preserves_geometry_but_dss65_plasma_survives():
    samples = 301
    phase = np.linspace(0.0, 1.0, samples)
    fx = geometry.X_BAND_HZ + 80_000.0 * phase
    fka = geometry.KA_BAND_HZ + 300_000.0 * phase
    g25 = 1.1e-5 + 5.0e-9 * np.sin(phase * np.pi)
    g65 = 0.9e-5 + 2.0e-9 * phase**2
    p25 = 7.0e14 * (1.0 + phase)
    p65 = 2.0e14 * (1.0 - 0.25 * phase)

    observed = composite.compose_distributed_x_hz(
        g25 + p25 / fx**2,
        g25 + p25 / fka**2,
        g65 + p65 / fx**2,
        fx,
        fka,
    )
    expected = fx * (g25 - g65 - p65 / fx**2)

    assert np.allclose(observed, expected, rtol=0.0, atol=4e-11)
    assert not np.allclose(observed, fx * (g25 - g65), rtol=0.0, atol=1e-7)


def test_cross_band_hardware_enters_with_explicit_weights():
    fx = geometry.X_BAND_HZ
    fka = geometry.KA_BAND_HZ
    weight_x, weight_ka = composite.composition_weights(fx, fka)
    g25 = np.asarray([1.0e-5, 1.2e-5])
    g65 = np.asarray([0.7e-5, 0.8e-5])
    h25x = np.asarray([1.0e-9, 2.0e-9])
    h25ka = np.asarray([-3.0e-9, 4.0e-9])
    h65x = np.asarray([5.0e-10, -7.0e-10])

    observed = composite.compose_distributed_x_hz(
        g25 + h25x,
        g25 + h25ka,
        g65 + h65x,
        fx,
        fka,
    )
    expected = fx * (
        g25 - g65 + weight_x * h25x + weight_ka * h25ka - h65x
    )

    assert observed == pytest.approx(expected, abs=2e-11)


def test_only_one_prefix_affine_is_fit_after_composition():
    samples = 90
    split = 30
    elapsed = np.arange(samples, dtype=np.float64)
    curve = 4.0 + 0.125 * elapsed
    curve[split:] += np.linspace(0.0, 1.0, samples - split) ** 2

    residual, metrics = composite.project_composite_prefix_affine(
        curve, calibration_records=split
    )

    assert np.max(np.abs(residual[:split])) < 1e-12
    assert metrics["peak_to_peak_hz"] == pytest.approx(1.0, abs=1e-11)
    assert "dss25_x_fraction" not in inspect.signature(
        composite.project_composite_prefix_affine
    ).parameters


def test_receipt_binds_frozen_parents_and_keeps_physical_claim_blocked():
    receipt = composite.build_audit_receipt()

    assert receipt["outcome"] == composite.OUTCOME_NOT_ADMITTED
    assert receipt["sub_outcomes"][0] == composite.COMPOSITION_ADMITTED
    assert composite.PLASMA_NOT_EVALUATED in receipt["sub_outcomes"]
    assert receipt["instantaneous_carrier_coordinate"]["state"] == (
        "NOT_MATERIALIZED_FROM_PARENT_AGGREGATE_RECEIPTS"
    )
    assert receipt["projection"]["per_band_affine"] == "PROHIBITED"
    assert receipt["projection"]["suffix_refit"] == "PROHIBITED"
    assert receipt["controlling_geometry"]["heldout_peak_to_peak_hz"] == (
        0.07231370056321107
    )
    assert receipt["access"]["iq_bytes_accessed"] == 0
    assert receipt["access"]["header_reaccess"] is False
    assert receipt["access"]["network"] is False


def test_unresolved_terms_are_not_silently_zeroed():
    receipt = composite.build_audit_receipt()
    ledger = {entry["term"]: entry for entry in receipt["physical_ledger"]}

    assert ledger["DSS25_FIRST_ORDER_COLD_PLASMA"]["measurement_state"] == (
        "NOT_EVALUATED_WITHOUT_IQ"
    )
    assert ledger["DSS65_FIRST_ORDER_COLD_PLASMA"]["state"] == "UNRESOLVED"
    assert ledger["DIFFERENTIAL_TROPOSPHERE"]["state"] == "UNRESOLVED"
    assert ledger["RECEIVER_PROPER_TIME_GRAVITY_DIFFERENTIAL"]["state"] == (
        "UNRESOLVED"
    )
    assert ledger["CROSS_BAND_AND_CROSS_STATION_RECEIVER_HARDWARE"][
        "state"
    ] == "UNRESOLVED"


def test_frozen_receipt_is_strict_and_matches_module_manifest():
    path = Path(composite.__file__).with_name(
        "CASSINI_SAGR3_COMPOSITE_XKA_RECEIPT.json"
    )
    raw = path.read_bytes()
    receipt = json.loads(
        raw,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
    )

    assert receipt == composite.build_audit_receipt()
    assert receipt["audit_manifest_sha256"] == composite.audit_manifest_sha256()
    assert len(sha256(raw).hexdigest()) == 64
    with pytest.raises(ValueError):
        composite.strict_json({"value": float("nan")})


@pytest.mark.parametrize(
    "fx,fka",
    [
        (0.0, geometry.KA_BAND_HZ),
        (geometry.X_BAND_HZ, geometry.X_BAND_HZ),
        (float("nan"), geometry.KA_BAND_HZ),
        (geometry.X_BAND_HZ, float("inf")),
    ],
)
def test_invalid_carrier_coordinates_are_refused(fx: float, fka: float):
    with pytest.raises(composite.CassiniCompositeXKaError):
        composite.composition_weights(fx, fka)
