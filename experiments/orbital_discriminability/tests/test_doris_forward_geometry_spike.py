"""Offline tests for the bounded DORIS orbit-only geometry spike."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import inspect
import json
from pathlib import Path

import ncompress
import numpy as np
import pytest

from experiments.orbital_discriminability import doris_forward_geometry_spike as spike


def _sp3_fixture(path: Path, satellite_id: str = "L74") -> str:
    lines = [
        "#cV2026  9  1  0  0  0.00000000       3 ORBIT ITRF  EXT CNES",
        "## 2435      0.00000000    60.00000000 61284 0.0000000000000",
        "%c L  cc TAI ccc cccc cccc cccc cccc ccccc ccccc ccccc ccccc",
    ]
    for minute, x_m, velocity_mps in (
        (0, 7_000_000.0, 0.0),
        (1, 7_000_060.0, 2.0),
        (2, 7_000_240.0, 4.0),
    ):
        lines.append(f"*  2026  9  1  0 {minute:2d}  0.00000000")
        lines.append(
            f"P{satellite_id}{x_m / 1000.0:14.7f}{0.0:14.7f}{0.0:14.7f}{999999.999999:14.6f}"
        )
        lines.append(
            f"V{satellite_id}{velocity_mps / 0.1:14.7f}{0.0:14.7f}{0.0:14.7f}{999999.999999:14.6f}"
        )
    lines.append("EOF")
    compressed = ncompress.compress(("\n".join(lines) + "\n").encode("ascii"))
    path.write_bytes(compressed)
    return sha256(compressed).hexdigest()


def test_parser_requires_hash_identity_and_cnes_ext_tai(tmp_path: Path) -> None:
    path = tmp_path / "fixture.Z"
    digest = _sp3_fixture(path)

    trajectory = spike.parse_frozen_sp3_z(
        path,
        expected_name="fixture.Z",
        expected_sha256=digest,
        expected_satellite_id="L74",
    )

    assert trajectory.satellite_id == "L74"
    assert trajectory.start_tai == datetime(2026, 9, 1, tzinfo=timezone.utc)
    assert trajectory.positions_m.shape == (3, 3)
    assert trajectory.velocities_mps[:, 0].tolist() == [0.0, 2.0, 4.0]
    with pytest.raises(spike.DorisGeometryError, match="SHA-256"):
        spike.parse_frozen_sp3_z(
            path,
            expected_name="fixture.Z",
            expected_sha256="0" * 64,
            expected_satellite_id="L74",
        )


def test_hermite_interpolation_preserves_endpoints_and_quadratic() -> None:
    times = np.array([0.0, 60.0, 120.0])
    positions = np.column_stack((7_000_000.0 + times**2 / 60.0, times * 0.0, times * 0.0))
    velocities = np.column_stack((times / 30.0, times * 0.0, times * 0.0))
    trajectory = spike.Sp3Trajectory(
        satellite_id="L74",
        start_tai=datetime(2026, 9, 1, tzinfo=timezone.utc),
        times_tai_s=times,
        positions_m=positions,
        velocities_mps=velocities,
        header="fixture",
    )
    requested = np.array([0.0, 30.0, 60.0, 90.0, 120.0])

    interpolated_position, interpolated_velocity = spike.interpolate_hermite(
        trajectory, requested
    )

    assert interpolated_position[:, 0] == pytest.approx(
        7_000_000.0 + requested**2 / 60.0
    )
    assert interpolated_velocity[:, 0] == pytest.approx(requested / 30.0)


def test_prefix_affine_projection_cannot_absorb_heldout_curvature() -> None:
    time = np.arange(100, dtype=float) * spike.INTERPOLATION_STEP_S
    curved = 3.0 + 0.01 * time + 2.0e-5 * time**2

    residual = spike.prefix_affine_residual(curved, 25)

    assert np.ptp(residual) > 1.0
    assert residual.size == 75


def test_station_scope_is_small_and_predeclared() -> None:
    assert len(spike.STATIONS) == 8
    assert spike.PAIRS == (
        ("TLSB", "GR4B"),
        ("TLSB", "WEUC"),
        ("PAUB", "RIMC"),
        ("KRWB", "LAPB"),
    )
    assert spike.FROZEN_ALONG_TRACK_SHIFTS_S == (-60.0, 60.0)
    assert all(station.source_resolution_arcmin == 1.0 for station in spike.STATIONS.values())


def test_spike_has_no_rinex_or_network_access() -> None:
    source = inspect.getsource(spike)

    for forbidden in (
        "requests",
        "urllib",
        "ftplib",
        "s3arx26242",
        "s3arx26245",
        "open_rinex",
    ):
        assert forbidden not in source
    assert "observation_rinex_access" in source
    assert "CNES_EXTRAPOLATED_PRE_OBSERVATION" in source


def test_frozen_receipt_preserves_scope_and_input_identity() -> None:
    receipt_path = (
        Path(__file__).parents[1] / "DORIS_FORWARD_GEOMETRY_RECEIPT.json"
    )
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert receipt["outcome"] == (
        "DORIS_FORWARD_GEOMETRY_SHORTLISTED_MEASUREMENT_UNADMITTED"
    )
    assert receipt["observation_rinex_access"] == "ZERO"
    assert receipt["observation_values_access"] == "ZERO"
    assert receipt["ephemeral_orbit_artifact_retention"] == (
        "ZERO_AFTER_HASHED_ANALYSIS"
    )
    assert receipt["measurement_admission"] == "NOT_EVALUATED"
    assert [artifact["sha256"] for artifact in receipt["input_artifacts"]] == [
        spike.CURRENT_S3A_SHA256,
        spike.PRIOR_S3A_SHA256,
        spike.ALTERNATIVE_S3B_SHA256,
    ]
    assert receipt["shortlist"][0]["pair"] == ["KRWB", "LAPB"]
    assert receipt["root_topology"]["independent_receive_hardware_roots"] is False
