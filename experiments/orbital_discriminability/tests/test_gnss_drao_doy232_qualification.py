from __future__ import annotations

from datetime import timedelta
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    gnss_drao_doy232_qualification as qualification,
)


ROOT = Path(__file__).resolve().parents[1]
SEAL = ROOT / qualification.SEAL_NAME
SEAL_SHA256 = "9f021dcf9da8961eef114b423950d064035eb8df69ec346225dcf9fa82bb6a5e"


def header_line(data: str, label: str) -> str:
    return f"{data:<60}{label:<20}\n"


def scale_record(factor: int, observables: tuple[str, ...]) -> str:
    raw = [" "] * 60
    raw[0] = "G"
    raw[2:6] = f"{factor:4d}"
    raw[8:10] = f"{len(observables):2d}"
    raw[11 : 11 + len(" ".join(observables))] = " ".join(observables)
    return "".join(raw)


def phase_record(observable: str, correction: float = 0.0) -> str:
    raw = [" "] * 60
    raw[0] = "G"
    raw[2:5] = observable
    raw[6:14] = f"{correction:8.5f}"
    raw[16:18] = " 0"
    return "".join(raw)


def field(value: float | None, lli: int = 0) -> str:
    if value is None:
        return " " * 16
    return f"{value:14.3f}{' ' if lli == 0 else lli} "


def fixture(
    *,
    scale_factor: int = 1,
    receiver_clock_applied: int = 1,
    receiver_clock_s: float = 0.0,
    blank: tuple[int, str, str] | None = None,
    nonzero_lli: tuple[int, str, str] | None = None,
    phase_jump: tuple[int, str] | None = None,
    witness_excursion: bool = False,
    phase_shift_records: tuple[str, ...] | None = None,
) -> bytearray:
    observables = ("C1C", "L1C", "C2W", "L2W", "S1C", "S2W")
    antenna_type = f"{'TWIVC6050':<16}SCIS"
    lines = [
        header_line("     3.04           OBSERVATION DATA    G", "RINEX VERSION / TYPE"),
        header_line("DRAO", "MARKER NAME"),
        header_line("40105M002", "MARKER NUMBER"),
        header_line(
            f"{'RX':<20}{'SEPT POLARX5':<20}{'5.2.0':<20}",
            "REC # / TYPE / VERS",
        ),
        header_line(f"{'ANT':<20}{antenna_type:<20}", "ANT # / TYPE"),
        header_line(" -2059164.0 -3621108.0 4814432.0", "APPROX POSITION XYZ"),
        header_line(
            f"G  {len(observables):3d} "
            + "".join(f"{observable:>3} " for observable in observables),
            "SYS / # / OBS TYPES",
        ),
        header_line("      30.000", "INTERVAL"),
        header_line(
            "  2026     8    20     0     0    0.0000000     GPS",
            "TIME OF FIRST OBS",
        ),
        header_line(
            "  2026     8    20    23    59   30.0000000     GPS",
            "TIME OF LAST OBS",
        ),
        header_line(f"{receiver_clock_applied:6d}", "RCV CLOCK OFFS APPL"),
    ]
    if scale_factor != 1:
        lines.append(
            header_line(
                scale_record(scale_factor, ("C1C", "L1C", "C2W", "L2W")),
                "SYS / SCALE FACTOR",
            )
        )
    shifts = phase_shift_records or (phase_record("L1C"), phase_record("L2W"))
    lines.extend(header_line(record, "SYS / PHASE SHIFT") for record in shifts)
    lines.append(header_line("", "END OF HEADER"))

    for epoch_index, expected_epoch in enumerate(qualification.expected_epochs()):
        raw_epoch = expected_epoch + timedelta(
            seconds=(receiver_clock_s if receiver_clock_applied == 0 else 0.0)
        )
        second = raw_epoch.second + raw_epoch.microsecond / 1_000_000
        clock_suffix = (
            f" {receiver_clock_s:.12f}" if receiver_clock_applied == 0 else ""
        )
        lines.append(
            f"> {raw_epoch.year:4d} {raw_epoch.month:02d} {raw_epoch.day:02d} "
            f"{raw_epoch.hour:02d} {raw_epoch.minute:02d} {second:10.7f}  0  6"
            f"{clock_suffix}\n"
        )
        for sat_index, satellite in enumerate(qualification.SATELLITES):
            physical = 22_000_000.0 + sat_index * 100.0 + epoch_index
            values = {
                "C1C": physical,
                "L1C": physical / qualification.LAMBDA_L1_M,
                "C2W": physical,
                "L2W": physical / qualification.LAMBDA_L2_M,
                "S1C": 45.0,
                "S2W": 44.0,
            }
            if witness_excursion and satellite == "G07" and epoch_index >= 79:
                values["C1C"] += (epoch_index - 79) * 100.0
            if phase_jump == (epoch_index, satellite):
                values["L1C"] += 1.0
            if receiver_clock_applied == 0:
                values["C1C"] += receiver_clock_s * qualification.frozen.SPEED_OF_LIGHT_M_S
                values["C2W"] += receiver_clock_s * qualification.frozen.SPEED_OF_LIGHT_M_S
                values["L1C"] += receiver_clock_s * qualification.frozen.L1_HZ
                values["L2W"] += receiver_clock_s * qualification.frozen.L2_HZ
            stored = {
                observable: (
                    value * scale_factor
                    if observable in {"C1C", "L1C", "C2W", "L2W"}
                    else value
                )
                for observable, value in values.items()
            }
            lli = {observable: 0 for observable in observables}
            if nonzero_lli and nonzero_lli[:2] == (epoch_index, satellite):
                lli[nonzero_lli[2]] = 1
            if blank and blank[:2] == (epoch_index, satellite):
                stored[blank[2]] = None
            lines.append(
                satellite
                + "".join(field(stored[observable], lli[observable]) for observable in observables)
                + "\n"
            )
    return bytearray("".join(lines).encode("ascii"))


def scan(**kwargs) -> qualification.QualificationScan:
    payload = fixture(**kwargs)
    try:
        return qualification.scan_decoded(payload)
    finally:
        payload[:] = b"\x00" * len(payload)


def test_manifest_is_model_blind_and_primary_remains_unselected() -> None:
    manifest = qualification.executor_manifest(ROOT)
    encoded = qualification.strict_json(manifest)

    assert manifest["product"]["sha256"] == qualification.ARTIFACT_SHA256
    assert manifest["health"]["orbital_model_available"] is False
    assert manifest["health"]["orbital_scores_produced"] == 0
    assert manifest["persistence"]["observation_values"] == 0
    assert manifest["access_at_freeze"]["primary_locators"] == 0
    assert "2026233" not in encoded
    assert "orbit_prediction" not in encoded.lower()
    assert not any(manifest["access_at_freeze"].values())


def test_scale_factor_is_divided_before_physical_health() -> None:
    baseline = scan()
    scaled = scan(scale_factor=10)
    try:
        assert np.allclose(baseline.phase_cycles, scaled.phase_cycles, atol=1.0e-3)
        assert np.allclose(baseline.code_m, scaled.code_m, atol=1.0e-3)
        assert qualification.evaluate(scaled)["outcome"] == (
            "DRAO_QUALIFICATION_PASSED_PRIMARY_STILL_SEALED"
        )
    finally:
        baseline.erase()
        scaled.erase()


def test_phase_shift_is_validated_but_never_double_applied() -> None:
    shifted = scan(
        phase_shift_records=(phase_record("L1C", 0.25), phase_record("L2W", -0.25))
    )
    try:
        assert shifted.header["phase_shift_numerically_applied_again"] is False
        assert shifted.header["phase_shift_records"]["L1C"][0]["cycles"] == 0.25
        assert qualification.evaluate(shifted)["outcome"] == (
            "DRAO_QUALIFICATION_PASSED_PRIMARY_STILL_SEALED"
        )
    finally:
        shifted.erase()

    with pytest.raises(
        qualification.DraoQualificationError,
        match="PHASE_SHIFT_COVERAGE_INCOMPLETE:L2W",
    ):
        scan(phase_shift_records=(phase_record("L1C"),))


def test_receiver_clock_transform_recovers_epoch_phase_and_code() -> None:
    baseline = scan()
    corrected = scan(receiver_clock_applied=0, receiver_clock_s=0.001)
    try:
        assert np.allclose(baseline.phase_cycles, corrected.phase_cycles, atol=2.0e-3)
        assert np.allclose(baseline.code_m, corrected.code_m, atol=2.0e-3)
        event_time = corrected.header["event_time"]
        assert event_time["maximum_absolute_grid_deviation_s"] == pytest.approx(0.0)
        assert event_time["receiver_clock_correction_epochs"] == 139
        assert event_time["qualification_reduces_bound"] is False
    finally:
        baseline.erase()
        corrected.erase()


def test_complete_six_track_fixture_passes_without_orbital_score() -> None:
    measurement = scan()
    try:
        summary = qualification.evaluate(measurement)
        assert summary["outcome"] == "DRAO_QUALIFICATION_PASSED_PRIMARY_STILL_SEALED"
        assert all(state == "SATISFIED" for state in summary["clauses"].values())
        assert summary["coverage_rows"] == 139 * 6 * 6
        assert summary["orbital_model_used"] is False
        assert summary["orbital_scores_produced"] == 0
        assert summary["possible_primary_doy233"] == "UNSELECTED_UNFROZEN_UNAUTHORISED"
    finally:
        measurement.erase()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"blank": (50, "G08", "L2W")},
        {"blank": (50, "G08", "C2W")},
        {"nonzero_lli": (50, "G08", "L1C")},
        {"phase_jump": (50, "G08")},
    ],
)
def test_topology_failures_do_not_become_orbital_results(kwargs) -> None:
    measurement = scan(**kwargs)
    try:
        summary = qualification.evaluate(measurement)
        assert summary["outcome"] == "QUALIFICATION_TOPOLOGY_REJECTED"
        assert summary["orbital_scores_produced"] == 0
    finally:
        measurement.erase()


def test_same_path_limit_has_its_own_typed_refusal() -> None:
    measurement = scan(witness_excursion=True)
    try:
        summary = qualification.evaluate(measurement)
        assert summary["clauses"]["complete_core_phase"] == "SATISFIED"
        assert summary["clauses"]["complete_same_path_code"] == "SATISFIED"
        assert summary["clauses"]["physical_same_path_witness"] == "UNSATISFIED"
        assert summary["outcome"] == "QUALIFICATION_PHYSICAL_WITNESS_REJECTED"
    finally:
        measurement.erase()


def test_structural_rows_contain_no_observation_values_and_arrays_erase() -> None:
    measurement = scan()
    encoded = qualification.strict_json(measurement.coverage)
    assert '"value"' not in encoded
    assert "22000000" not in encoded
    assert len(measurement.coverage) == 5004
    measurement.erase()
    assert np.count_nonzero(measurement.phase_cycles) == 0
    assert np.count_nonzero(measurement.code_m) == 0


def test_strict_json_and_unopened_seal_are_finite() -> None:
    seal = qualification.build_executor_seal(ROOT)

    assert seal["state"] == "DRAO_DOY232_QUALIFICATION_EXECUTOR_FROZEN_UNOPENED"
    assert not any(seal["access_at_seal"].values())
    assert seal["authority"]["live_execution_authorized_by_seal"] is False
    assert json.loads(qualification.strict_json(seal)) == seal
    with pytest.raises(ValueError):
        qualification.strict_json({"bad": float("nan")})


def test_frozen_executor_seal_binds_source_without_granting_authority() -> None:
    seal = qualification.validate_executor_seal(ROOT, SEAL, SEAL_SHA256)

    assert qualification.file_sha256(SEAL) == SEAL_SHA256
    assert seal["source_commit"] == "d227f19335a7237f6f2e7176c9a5a34f8ddaeea1"
    assert seal["source_sha256"] == qualification.source_sha256()
    assert seal["manifest_sha256"] == qualification.manifest_sha256(ROOT)
    assert seal["product"]["sha256"] == qualification.ARTIFACT_SHA256
    assert seal["authority"]["live_execution_authorized_by_seal"] is False
    assert not any(seal["access_at_seal"].values())


def test_live_executor_requires_separate_authority_before_any_network(tmp_path) -> None:
    with pytest.raises(PermissionError, match="AUTHORITY_REQUIRED"):
        qualification.run_once(tmp_path, "", "0" * 64, tmp_path / "seal.json")
    assert list(tmp_path.iterdir()) == []
