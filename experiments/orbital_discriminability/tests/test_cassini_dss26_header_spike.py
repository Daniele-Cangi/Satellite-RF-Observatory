"""Offline tests for the product-bound Cassini DSS-26 header spike."""

from dataclasses import replace
from hashlib import md5, sha256
from pathlib import Path

import numpy as np
import pytest

import experiments.orbital_discriminability.cassini_dss26_header_spike as spike
from experiments.orbital_discriminability.cassini_dss26_header_spike import (
    CassiniHeaderSpikeError,
    _calibrated_curve,
    spike_manifest,
)


def test_manifest_freezes_product_nulls_and_forbidden_access() -> None:
    manifest = spike_manifest()
    assert manifest["development_lidvid"].endswith("s11sags2005_157_1750nnnx26rd::1.0")
    assert manifest["calibration_fraction"] == 0.2
    assert manifest["representative_sample_offset_s"] == 0.5005
    assert manifest["geometry_destroying_target"] == "SATURN BARYCENTER"
    forbidden = " ".join(manifest["forbidden"]).lower()
    assert "iq decoding" in forbidden
    assert "dss-14" in forbidden
    assert "free time phase" in forbidden


def test_artifact_identity_is_required_before_traversal(tmp_path: Path, monkeypatch) -> None:
    body = b"metadata-only-synthetic-record"
    path = tmp_path / spike.DEVELOPMENT_PRODUCT_NAME
    path.write_bytes(body)
    monkeypatch.setattr(spike, "EXPECTED_BYTES", len(body))
    monkeypatch.setattr(spike, "PUBLISHED_MD5", md5(body, usedforsecurity=False).hexdigest())
    monkeypatch.setattr(spike, "DEVELOPMENT_SHA256", sha256(body).hexdigest())
    identity = spike.verify_development_artifact(path)
    assert identity.bytes == len(body)
    path.write_bytes(body + b"changed")
    with pytest.raises(CassiniHeaderSpikeError, match="byte count"):
        spike.verify_development_artifact(path)


def test_two_parameter_calibration_uses_prefix_and_no_time_phase() -> None:
    factor = np.asarray([0.99, 0.991, 0.992, 0.994, 0.997], dtype=np.float64)
    transmit = np.arange(5, dtype=np.float64)
    lo = np.full(5, 1000.0)
    nco = np.asarray([10.0, 11.0, 12.0, 13.5, 16.0])
    curve, fit = _calibrated_curve(factor, transmit, lo, nco, split=3)
    assert np.all(np.isfinite(curve))
    assert np.isfinite(fit.constant_offset_hz)
    assert np.isfinite(fit.affine_aging_hz_s)
    changed_suffix = nco.copy()
    changed_suffix[3:] += 1000.0
    _, second_fit = _calibrated_curve(factor, transmit, lo, changed_suffix, split=3)
    assert second_fit == fit


def test_open_term_refusal_is_a_frozen_typed_outcome() -> None:
    assert spike.TYPED_REFUSAL_OPEN_TERM == (
        "CASSINI_OPEN_TERM_CAN_ABSORB_HELDOUT_SEPARATION"
    )
