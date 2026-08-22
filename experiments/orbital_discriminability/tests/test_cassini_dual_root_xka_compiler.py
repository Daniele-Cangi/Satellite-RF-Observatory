from __future__ import annotations

from datetime import datetime, timedelta, timezone
import inspect
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    cassini_dual_root_xka_compiler as compiler,
)


def _stream(role="DSS25_X"):
    start = datetime(2005, 6, 8, 19, 17, tzinfo=timezone.utc)
    records = tuple(
        compiler.ControlRecord(
            (start + timedelta(seconds=index))
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z"),
            index,
            8_100_000_000.0,
            327_000_000.0,
            (350_000.0 + index, -5.0, 0.001),
        )
        for index in range(5_280)
    )
    return compiler.ControlStream(role, records, "a" * 64, "b" * 64)


def test_piecewise_nco_coordinate_is_evaluated_without_sample_access():
    stream = _stream()
    starts = np.arange(5_280, dtype=np.float64)
    result = compiler.evaluate_tuning_sky_hz(
        stream,
        np.asarray([0.25, 1.75, 5_279.5]),
        starts,
    )
    expected = []
    for index, offset in ((0, 0.25), (1, 0.75), (5_279, 0.5)):
        nco = 350_000.0 + index - 5.0 * offset + 0.001 * offset**2
        expected.append(8_427_000_000.0 - nco)
    np.testing.assert_allclose(result, expected, rtol=0.0, atol=1e-9)


def test_dual_root_composite_cancels_first_order_plasma_at_both_roots():
    time = np.arange(32, dtype=np.float64)
    carriers = {
        "DSS25_X": np.full(32, 8.425e9),
        "DSS25_KA": np.full(32, 32.028e9),
        "DSS55_X": np.full(32, 8.4247e9),
        "DSS55_KA": np.full(32, 32.0277e9),
    }
    common25 = 2e-5 + time * 1e-9
    common55 = -1e-5 + time * 3e-10
    plasma25 = 7e14 * (1.0 + time / 100.0)
    plasma55 = -4e14 * (1.0 - time / 200.0)
    result = compiler.compose_four_stream_fraction(
        common25 + plasma25 / carriers["DSS25_X"] ** 2,
        common25 + plasma25 / carriers["DSS25_KA"] ** 2,
        common55 + plasma55 / carriers["DSS55_X"] ** 2,
        common55 + plasma55 / carriers["DSS55_KA"] ** 2,
        carriers,
    )
    np.testing.assert_allclose(result, common25 - common55, atol=1e-20)


def test_weights_preserve_common_mode_and_are_not_probability_amplitudes():
    wx, wk = compiler.composition_weights(8.425e9, 32.028e9)
    assert float(wx + wk) == pytest.approx(1.0, abs=1e-15)
    assert float(wx / 8.425e9**2 + wk / 32.028e9**2) == pytest.approx(
        0.0, abs=1e-34
    )
    assert float(wx) < 0.0
    assert float(wk) > 1.0


def test_only_one_prefix_affine_is_fit_and_suffix_curvature_survives():
    elapsed = np.arange(100, dtype=np.float64)
    curve = 9.0 + 0.2 * elapsed + 0.001 * elapsed**2
    residual, metrics = compiler.prefix_affine_projection(curve, 20)
    assert metrics["heldout_peak_to_peak_hz"] > 1.0
    altered_suffix = curve.copy()
    altered_suffix[20:] += 4.0
    _, altered = compiler.prefix_affine_projection(altered_suffix, 20)
    assert altered["constant_hz"] == pytest.approx(metrics["constant_hz"])
    assert altered["slope_hz_s"] == pytest.approx(metrics["slope_hz_s"])
    assert residual.shape == curve.shape


def test_manifest_freezes_causal_state_envelope_and_forbids_posthoc_freedom():
    manifest = compiler.compiler_manifest()
    assert manifest["event_axis"] == "COMMON_CASSINI_TRANSMIT_ET_TDB"
    assert manifest["seven_open_terms"] == list(compiler.OPEN_TERM_NAMES)
    assert manifest["causal_state_policy"]["probabilities"] == "NOT_USED"
    forbidden = set(manifest["forbidden"])
    assert "free time phase" in forbidden
    assert "unresolved term set to zero" in forbidden
    assert "root-sum-square without documented independence" in forbidden
    assert "NCO treated as measured RF" in forbidden


def test_all_seven_terms_remain_unbounded_without_invented_numbers():
    diagnostics = {
        "proper_time_gravity": {"heldout_peak_to_peak_hz": 0.1},
        "relativistic_path": None,
        "troposphere_partial": None,
        "ionosphere_first_order": None,
    }
    ledger = compiler.physical_term_ledger(diagnostics)
    assert [term["name"] for term in ledger] == list(compiler.OPEN_TERM_NAMES)
    assert all(term["bound_state"] == "UNAVAILABLE" for term in ledger)
    assert all(
        term["admitted_heldout_peak_to_peak_bound_hz"] is None
        for term in ledger
    )
    assert ledger[0]["central_model_reduces_envelope"] is False


def test_compiler_input_surface_has_no_iq_or_model_ridge():
    signature = inspect.signature(compiler.compile_exact_metadata)
    assert set(signature.parameters) == {
        "spice", "kernel_paths", "streams", "source_commit"
    }
    source = Path(compiler.__file__).read_text(encoding="utf-8").lower()
    assert "decode_iq" not in source
    assert "signal_strength" not in source
    assert "amplitude_value" not in source


def test_parent_receipts_and_strict_json_are_stable():
    parents = compiler.validate_parent_receipts()
    assert set(parents) == set(compiler.PARENT_RECEIPT_SHA256)
    with pytest.raises(ValueError):
        compiler.strict_json({"bad": float("nan")})
    assert len(compiler.compiler_manifest_sha256()) == 64
    assert len(compiler.canonical_source_sha256()) == 64
