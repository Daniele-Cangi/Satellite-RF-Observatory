"""Offline tests for the LuGRE constellation-snapshot geometry screen."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    lugre_snapshot_discriminability as screen,
)


def test_manifest_freezes_physical_question_and_zero_lugre_access() -> None:
    value = screen.manifest()

    assert value["physical_question"] == (
        "CAN_ONE_SIMULTANEOUS_ANONYMOUS_GPS_DOPPLER_SET_RETAIN_"
        "ORBITAL_IDENTITY_AFTER_COMMON_CLOCK_AND_SCALE_PROJECTION"
    )
    assert value["coordinate"]["signals_per_snapshot"] == 4
    assert value["coordinate"]["common_offset"] == "PROJECTED"
    assert value["coordinate"]["common_positive_scale"].startswith("PROJECTED")
    assert len(value["snapshots"]) == 7
    assert [row["operation"] for row in value["snapshots"]] == [
        "OP32",
        "OP37",
        "OP38",
        "OP40",
        "OP73",
        "OP74",
        "OP76",
    ]
    assert not any(value["observation_boundary"].values())
    assert value["prospective_plan_frozen"] is False
    assert value["primary_selected"] is False
    assert value["new_gate"] is False


def test_authorities_are_bounded_to_six_navigation_days_and_clps() -> None:
    assert [int(row.name[4:7]) for row in screen.NAVIGATION] == [
        55,
        58,
        62,
        63,
        73,
        74,
    ]
    assert all(len(row.sha256) == 64 and row.bytes > 0 for row in screen.NAVIGATION)
    assert all(len(row.sha256) == 64 and row.bytes > 0 for row in screen.SPICE)
    assert {row.observer_source for row in screen.SNAPSHOTS} == {
        "RECONSTRUCTED_CRUISE_SPK",
        "ACTUAL_LANDING_SITE_SPK",
    }


def test_affine_projection_removes_only_common_offset_and_positive_scale() -> None:
    model = np.asarray([-9.0, -2.0, 4.0, 13.0])
    target = 117.0 + 1.0025 * model
    assert screen.affine_residual_rmse_hz(target, model) == pytest.approx(
        0.0, abs=1.0e-12
    )

    reversed_target = 117.0 - model
    assert screen.affine_residual_rmse_hz(reversed_target, model) > 7.0


def test_four_signal_codebook_has_explicit_wrong_subset_margin() -> None:
    values = {
        "G01": -17.0,
        "G02": -6.5,
        "G03": 2.0,
        "G04": 15.0,
        "G05": 31.0,
    }
    result = screen.codebook_separation(values)

    assert result["candidate_count"] == 5
    assert result["hypothesis_count"] == 5
    assert result["signals_per_hypothesis"] == 4
    controlling = result["controlling_assignment"]
    assert len(controlling["true_subset"]) == 4
    assert len(controlling["nearest_wrong_subset"]) == 4
    assert controlling["true_subset"] != controlling["nearest_wrong_subset"]
    assert controlling["affine_projected_rmse_hz"] > 0.0
    assert controlling["maximum_total_per_track_rms_envelope_hz"] == pytest.approx(
        controlling["affine_projected_rmse_hz"] / 2.0
    )


def test_rank_affine_null_is_not_silently_removed_when_it_matches() -> None:
    result = screen.rank_affine_null(
        {"G01": 0.0, "G02": 1.0, "G03": 2.0, "G04": 3.0, "G05": 9.0}
    )

    assert result["controlling_true_subset"] == ["G01", "G02", "G03", "G04"]
    assert result["affine_projected_rmse_hz"] == pytest.approx(0.0, abs=1.0e-12)


def test_geometry_null_receives_same_affine_projection() -> None:
    true = {"G01": -12.0, "G02": -3.0, "G03": 5.0, "G04": 17.0, "G05": 35.0}
    null = {key: 800.0 + 0.5 * value for key, value in true.items()}
    result = screen.null_separation(true, null)

    assert result["affine_projected_rmse_hz"] == pytest.approx(0.0, abs=1.0e-12)
    assert result["maximum_total_per_track_rms_envelope_hz"] == pytest.approx(
        0.0, abs=1.0e-12
    )


def test_occultation_and_boresight_geometry_are_explicit() -> None:
    satellite = np.asarray([26_560_000.0, 0.0, 0.0])
    same_side_observer = np.asarray([384_400_000.0, 0.0, 0.0])
    opposite_observer = np.asarray([-384_400_000.0, 0.0, 0.0])

    assert screen._earth_occulted(satellite, same_side_observer) is False
    assert screen._earth_occulted(satellite, opposite_observer) is True
    assert screen._off_boresight_deg(satellite, opposite_observer) == pytest.approx(0.0)
    assert screen._off_boresight_deg(satellite, same_side_observer) == pytest.approx(
        180.0
    )


def test_strict_json_refuses_nonfinite_values() -> None:
    assert json.loads(screen.strict_json({"finite": np.float64(1.25)})) == {
        "finite": 1.25
    }
    with pytest.raises(ValueError):
        screen.strict_json({"bad": float("nan")})
    with pytest.raises(ValueError):
        screen.strict_json({"bad": float("inf")})


def test_source_has_no_lugre_network_or_sample_surface() -> None:
    source = Path(screen.__file__).read_text(encoding="utf-8").lower()

    for forbidden in (
        "import requests",
        "import urllib",
        "import socket",
        "zenodo.org/api",
        "lugre.zip",
        "def decode_iq",
        "def parse_iqs",
        "tlm_nav",
    ):
        assert forbidden not in source
