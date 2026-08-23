from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from math import isclose
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import gnss_double_difference_envelope as envelope
from experiments.orbital_discriminability import gnss_native_doppler_design as design


ROOT = Path(__file__).parents[1]
RECEIPT = ROOT / "GNSS_NATIVE_DOPPLER_FORWARD_DESIGN_RECEIPT.json"
EXPANSION_RECEIPT = (
    ROOT / "GNSS_NATIVE_DOPPLER_EXPANDED_NAVIGATION_RECEIPT.json"
)
ORBITALITY_RECEIPT = ROOT / "GNSS_NATIVE_DOPPLER_ORBITALITY_RECEIPT.json"


def load_receipt() -> dict[str, object]:
    return json.loads(
        RECEIPT.read_text(encoding="ascii"),
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
    )


def test_roles_and_navigation_days_are_bounded() -> None:
    assert design.DEVELOPMENT_DOY == 214
    assert design.CLOSED_PRIMARY_DOY == 215
    assert design.CANDIDATE_DOYS == (216, 217, 218)
    assert [design.expected_navigation_name(day) for day in design.CANDIDATE_DOYS] == [
        "BRDM00DLR_S_20262160000_01D_MN.rnx",
        "BRDM00DLR_S_20262170000_01D_MN.rnx",
        "BRDM00DLR_S_20262180000_01D_MN.rnx",
    ]
    with pytest.raises(design.DopplerDesignError, match="DAY_OUTSIDE"):
        design.expected_navigation_name(215)


def test_expansion_is_a_distinct_predeclared_two_week_navigation_set() -> None:
    assert design.EXPANSION_CANDIDATE_DOYS == tuple(range(219, 233))
    assert design.expected_navigation_name(
        219, design.EXPANSION_CANDIDATE_DOYS
    ) == "BRDM00DLR_S_20262190000_01D_MN.rnx"
    with pytest.raises(design.DopplerDesignError, match="DAY_OUTSIDE"):
        design.expected_navigation_name(218, design.EXPANSION_CANDIDATE_DOYS)
    manifest = design.expansion_manifest()
    assert manifest["frozen_from"]["initial_design_receipt_sha256"] == (
        design.INITIAL_DESIGN_RECEIPT_SHA256
    )
    assert manifest["parameters"]["window_records"] == 380
    assert manifest["observation_access_forbidden"] is True


def test_doy_calendar_mapping_is_explicit() -> None:
    assert design.calendar_date_for_doy(219).isoformat() == "2026-08-07"
    assert design.calendar_date_for_doy(232).isoformat() == "2026-08-20"
    with pytest.raises(design.DopplerDesignError):
        design.calendar_date_for_doy(366)


def test_stale_navigation_epoch_becomes_a_visibility_gap(monkeypatch) -> None:
    epochs = (
        datetime(2026, 8, 7, tzinfo=timezone.utc),
        datetime(2026, 8, 7, tzinfo=timezone.utc) + timedelta(hours=8),
    )

    def select(_records, epoch):
        if epoch == epochs[1]:
            raise design.screen.GnssDoubleDifferenceError("stale")
        return object()

    monkeypatch.setattr(design.screen, "select_ephemeris", select)
    monkeypatch.setattr(
        design.screen,
        "broadcast_ecef",
        lambda _record, _epoch: np.asarray([1.0, 2.0, 3.0]),
    )

    positions = design.broadcast_positions_with_gaps((object(),), epochs)

    assert np.all(np.isfinite(positions[0]))
    assert np.all(np.isnan(positions[1]))


def test_native_dual_frequency_combination_recovers_geometry_and_cancels_iono() -> None:
    fractional = np.asarray([-2.5e-6, 0.0, 1.75e-6])
    ionosphere = np.asarray([1.2e9, -7.5e8, 3.25e8])
    d1 = envelope.GPS_L1_HZ * fractional + ionosphere / envelope.GPS_L1_HZ
    d2 = envelope.GPS_L2_HZ * fractional + ionosphere / envelope.GPS_L2_HZ
    combined = design.ionosphere_free_doppler_l1_equivalent(d1, d2)
    assert np.allclose(combined, envelope.GPS_L1_HZ * fractional, atol=1e-10)


def test_prefix_affine_projection_removes_only_frozen_prefix_fit() -> None:
    elapsed = np.arange(design.WINDOW_RECORDS) * design.STEP_S
    affine = 12.0 - 0.003 * elapsed
    residual, coefficients = design.prefix_affine_projection(affine)
    assert np.max(np.abs(residual)) < 1e-10
    assert isclose(coefficients[0], 12.0, rel_tol=0.0, abs_tol=1e-12)
    assert isclose(coefficients[1], -0.003, rel_tol=0.0, abs_tol=1e-15)


def test_heldout_curvature_survives_prefix_affine_null() -> None:
    elapsed = np.arange(design.WINDOW_RECORDS, dtype=np.float64) * design.STEP_S
    curved = 4.0 + 0.02 * elapsed + 2e-6 * elapsed**2
    separation = design.heldout_non_affine_peak_to_peak(
        curved, np.zeros(design.WINDOW_RECORDS)
    )
    assert separation > 100.0


def test_window_search_never_returns_a_short_window_and_includes_tail() -> None:
    assert design.window_starts(10, 10 + design.WINDOW_RECORDS - 1) == ()
    starts = design.window_starts(10, 10 + design.WINDOW_RECORDS + 41)
    assert starts[0] == 10
    assert starts[-1] == 51
    assert all(start + design.WINDOW_RECORDS <= 431 for start in starts)


def test_manifest_is_strict_and_grants_no_observation_authority() -> None:
    manifest = design.design_manifest()
    assert manifest["scope"].endswith("OBSERVATION_VALUES_UNOPENED")
    assert manifest["roles"]["closed_invalid_primary_doy"] == 215
    assert design.strict_json(manifest)
    with pytest.raises(ValueError):
        design.strict_json({"bad": float("nan")})


def test_native_doppler_rejects_nonfinite_or_mismatched_arrays() -> None:
    with pytest.raises(design.DopplerDesignError):
        design.ionosphere_free_doppler_l1_equivalent([1.0], [1.0, 2.0])
    with pytest.raises(design.DopplerDesignError):
        design.ionosphere_free_doppler_l1_equivalent([np.inf], [1.0])


def test_real_navigation_refusal_is_strict_and_numerically_regressed() -> None:
    receipt = load_receipt()
    assert receipt["design_manifest_sha256"] == design.design_manifest_sha256()
    assert receipt["outcome"] == (
        "NO_NATIVE_DOPPLER_GEOMETRY_WITH_FROZEN_NULL_SUPPORT"
    )
    assert receipt["shortlist"] == []
    assert receipt["instrumental_assessment_reached"] is False
    assert design.strict_json(receipt)
    for day in receipt["day_admission_diagnostics"]:
        assert day["maximum_two_satellite_continuity_records"] == 467
        assert day["two_satellite_sets_meeting_window"] == 14
        assert day["maximum_three_satellite_continuity_records"] == 379
        assert day["three_satellite_sets_meeting_window"] == 0
        assert day["controlling_three_satellite_set"] == ["G14", "G20", "G22"]


def test_navigation_refusal_grants_no_measurement_authority() -> None:
    receipt = load_receipt()
    assert set(receipt["measurement_access"].values()) == {0}
    assert set(receipt["authority"].values()) == {False}
    assert receipt["next_exact_blocker"] == (
        "PREDECLARED_NAVIGATION_SET_HAS_NO_380_EPOCH_THREE_SATELLITE_ROBUST_WINDOW"
    )


def test_expanded_navigation_result_is_strict_and_bound_to_initial_refusal() -> None:
    receipt = json.loads(EXPANSION_RECEIPT.read_text(encoding="ascii"))
    assert receipt["expansion_manifest_sha256"] == (
        design.expansion_manifest_sha256()
    )
    assert design.file_sha256(RECEIPT) == design.INITIAL_DESIGN_RECEIPT_SHA256
    assert receipt["outcome"] == (
        "NO_NATIVE_DOPPLER_GEOMETRY_SHORTLIST_IN_EXPANDED_SET"
    )
    assert receipt["candidate_doys"] == list(range(219, 233))
    assert receipt["shortlist"] == []
    assert design.strict_json(receipt)


def test_expanded_navigation_continuity_regression() -> None:
    receipt = json.loads(EXPANSION_RECEIPT.read_text(encoding="ascii"))
    diagnostics = receipt["day_admission_diagnostics"]
    assert [row["maximum_two_satellite_continuity_records"] for row in diagnostics] == [
        468, 468, 468, 469, 469, 469, 470, 470, 469, 470, 470, 470, 471, 471
    ]
    assert [row["maximum_three_satellite_continuity_records"] for row in diagnostics] == [
        379, 379, 378, 378, 378, 378, 378, 378, 378, 377, 377, 377, 377, 376
    ]
    assert {row["three_satellite_sets_meeting_window"] for row in diagnostics} == {0}
    assert {tuple(row["controlling_three_satellite_set"]) for row in diagnostics} == {
        ("G14", "G20", "G22")
    }


def test_expanded_refusal_does_not_authorize_numeric_development() -> None:
    receipt = json.loads(EXPANSION_RECEIPT.read_text(encoding="ascii"))
    assert set(receipt["measurement_access"].values()) == {0}
    assert set(receipt["authority"].values()) == {False}
    assert receipt["instrumental_assessment_reached"] is False


def test_orbitality_manifest_narrows_claim_instead_of_weakening_window() -> None:
    manifest = design.orbitality_manifest()
    assert manifest["claim_ceiling"] == "ORBITAL_MODEL_PREDICTIVELY_PREFERRED"
    assert manifest["specific_orbit_claim_authorized"] is False
    assert manifest["wrong_orbit_null_present"] is False
    assert manifest["measurement_coordinate"]["nulls"] == ["PREFIX_AFFINE"]
    assert manifest["parameters"]["window_records"] == 380
    assert manifest["frozen_from"]["expansion_receipt_sha256"] == (
        design.file_sha256(EXPANSION_RECEIPT)
    )


def test_affine_candidate_audit_subtracts_direct_clock_envelope(monkeypatch) -> None:
    epochs = design.gps_epoch_grid(design.calendar_date_for_doy(219))
    model = design.DayModel(
        doy=219,
        navigation_source={},
        gps_epochs=epochs,
        utc_epochs=tuple(
            epoch - timedelta(seconds=design.GPS_MINUS_UTC_S) for epoch in epochs
        ),
        satellites=("G01", "G02"),
        fractional={},
        elevation={},
    )
    candidate = design.AffineCandidate(
        doy=219,
        target="G01",
        reference="G02",
        start=10,
        stop=10 + design.WINDOW_RECORDS,
        separation_from_affine_hz=12.5,
        minimum_direct_shift_elevation_deg=16.0,
    )
    monkeypatch.setattr(
        design,
        "direct_clock_envelope_hz",
        lambda *_args: (2.25, (-15.0, 15.0)),
    )

    audited = design.audit_affine_candidate(model, candidate)

    assert audited["remaining_after_direct_clock_envelope_hz"] == 10.25
    assert audited["direct_clock_envelope"]["controlling_station_offsets_s"] == [
        -15.0,
        15.0,
    ]
    assert audited["instrumental_envelope_assessed"] is False


def test_real_orbitality_shortlist_is_strict_and_claim_limited() -> None:
    receipt = json.loads(ORBITALITY_RECEIPT.read_text(encoding="ascii"))
    assert receipt["orbitality_manifest_sha256"] == (
        design.orbitality_manifest_sha256()
    )
    assert design.file_sha256(EXPANSION_RECEIPT) == (
        design.EXPANSION_RECEIPT_SHA256
    )
    assert receipt["outcome"] == (
        "NATIVE_DOPPLER_ORBITALITY_GEOMETRY_SHORTLIST_READY"
    )
    assert receipt["claim_ceiling"] == "ORBITAL_MODEL_PREDICTIVELY_PREFERRED"
    assert receipt["specific_orbit_claim_authorized"] is False
    assert receipt["wrong_orbit_null_present"] is False
    assert receipt["observable"]["nulls"] == ["PREFIX_AFFINE"]
    assert design.strict_json(receipt)


def test_real_orbitality_geometry_is_numerically_regressed() -> None:
    receipt = json.loads(ORBITALITY_RECEIPT.read_text(encoding="ascii"))
    shortlist = receipt["shortlist"]
    assert [(row["doy"], row["target"], row["reference"]) for row in shortlist] == [
        (219, "G15", "G22"),
        (220, "G15", "G22"),
        (221, "G15", "G22"),
    ]
    assert isclose(
        shortlist[0]["prefix_affine_null"]["heldout_non_affine_peak_to_peak_hz"],
        6752.925149916402,
        rel_tol=0.0,
        abs_tol=1e-9,
    )
    assert isclose(
        shortlist[0]["direct_clock_envelope"]["heldout_peak_to_peak_hz"],
        9.388575556670272,
        rel_tol=0.0,
        abs_tol=1e-9,
    )
    assert isclose(
        shortlist[0]["remaining_after_direct_clock_envelope_hz"],
        6743.536574359732,
        rel_tol=0.0,
        abs_tol=1e-9,
    )
    assert shortlist[0]["start_observation_epoch_gps"] == (
        "2026-08-07T16:20:00 GPS"
    )


def test_orbitality_shortlist_grants_no_measurement_authority() -> None:
    receipt = json.loads(ORBITALITY_RECEIPT.read_text(encoding="ascii"))
    assert set(receipt["measurement_access"].values()) == {0}
    assert set(receipt["authority"].values()) == {False}
    assert receipt["instrumental_assessment_reached"] is False
    assert receipt["next_exact_blocker"] == (
        "SEPARATE_AUTHORITY_FOR_DOY214_NATIVE_DOPPLER_NUMERIC_DEVELOPMENT"
    )
    assert all(row["negative_result_interpretable"] is False for row in receipt["shortlist"])
