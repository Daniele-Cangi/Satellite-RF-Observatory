from __future__ import annotations

from pathlib import Path
import json

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    gnss_drao_labelled_forward_doy238_executor as executor,
)
from experiments.orbital_discriminability import (
    gnss_drao_labelled_forward_doy238_integrated_plan as plan,
)


ROOT = Path(__file__).resolve().parents[1]


def header_line(data: str, label: str) -> str:
    return f"{data:<60}{label:<20}\n"


def scale_record(factor: int, observables: tuple[str, ...]) -> str:
    raw = [" "] * 60
    raw[0] = "G"
    raw[2:6] = f"{factor:4d}"
    raw[8:10] = f"{len(observables):2d}"
    text = " ".join(observables)
    raw[11 : 11 + len(text)] = text
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


def nominal_curves() -> dict[str, np.ndarray]:
    value = json.loads((ROOT / plan.BUNDLE_NAME).read_text(encoding="ascii"))
    return {
        satellite: np.asarray(value["labelled_model_curves_m"][satellite])
        for satellite in plan.CODEBOOK
    }


def fixture(
    *,
    marker_name: str = "DRAO",
    include_scale: bool = False,
    scale: int = 1,
    include_phase_shift: bool = False,
    phase_shift: float = 0.0,
    include_clock_header: bool = True,
    clock_applied: int = 1,
    receiver_clock_s: float = 0.0,
    missing: tuple[int, str, str] | None = None,
    extra_track: bool = False,
    witness_excursion: bool = False,
) -> bytearray:
    observables = ("C1C", "L1C", "C2W", "L2W")
    antenna_type = f"{'TWIVC6050':<16}SCIS"
    lines = [
        header_line("     3.04           OBSERVATION DATA    G", "RINEX VERSION / TYPE"),
        header_line(marker_name, "MARKER NAME"),
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
            "  2026     8    26     0     0    0.0000000     GPS",
            "TIME OF FIRST OBS",
        ),
        header_line(
            "  2026     8    26    23    59   30.0000000     GPS",
            "TIME OF LAST OBS",
        ),
    ]
    if include_clock_header:
        lines.append(header_line(f"{clock_applied:6d}", "RCV CLOCK OFFS APPL"))
    if include_scale:
        lines.append(header_line(scale_record(scale, observables), "SYS / SCALE FACTOR"))
    if include_phase_shift:
        lines.extend(
            header_line(phase_record(observable, phase_shift), "SYS / PHASE SHIFT")
            for observable in executor.CORE_PHASE
        )
    lines.append(header_line("", "END OF HEADER"))
    curves = nominal_curves()
    satellites = plan.CODEBOOK + (("G31",) if extra_track else ())
    for epoch_index, epoch in enumerate(executor.expected_epochs()):
        raw_epoch = epoch
        stored_dt = 0.0
        if clock_applied == 0 and receiver_clock_s:
            from datetime import timedelta

            raw_epoch = epoch + timedelta(seconds=receiver_clock_s)
            stored_dt = receiver_clock_s
        second = raw_epoch.second + raw_epoch.microsecond / 1_000_000
        clock_token = f" {receiver_clock_s:.9f}" if receiver_clock_s else ""
        lines.append(
            f"> {raw_epoch.year:4d} {raw_epoch.month:02d} {raw_epoch.day:02d} "
            f"{raw_epoch.hour:02d} {raw_epoch.minute:02d} {second:10.7f}  0 "
            f"{len(satellites):2d}{clock_token}\n"
        )
        for sat_index, satellite in enumerate(satellites):
            if satellite in curves:
                physical = 22_000_000.0 + curves[satellite][epoch_index]
            else:
                physical = 44_000_000.0 + epoch_index * 2.0
            code_value = physical
            if witness_excursion and satellite == "G14" and epoch_index >= plan.PREFIX_EPOCHS:
                code_value += (epoch_index - plan.PREFIX_EPOCHS) * 100.0
            values: dict[str, float | None] = {
                "C1C": (code_value + stored_dt * executor.SPEED_OF_LIGHT_M_S) * scale,
                "L1C": (
                    physical / executor.LAMBDA_L1_M + stored_dt * executor.L1_HZ
                )
                * scale,
                "C2W": (code_value + stored_dt * executor.SPEED_OF_LIGHT_M_S) * scale,
                "L2W": (
                    physical / executor.LAMBDA_L2_M + stored_dt * executor.L2_HZ
                )
                * scale,
            }
            if missing is not None and missing[:2] == (epoch_index, satellite):
                values[missing[2]] = None
            lines.append(
                satellite
                + "".join(field(values[observable]) for observable in observables)
                + "\n"
            )
    return bytearray("".join(lines).encode("ascii"))


def scan(payload: bytearray) -> executor.ForwardScan:
    return executor.scan_decoded_fixture(payload, archive_site_id=plan.STATION)


def test_manifest_binds_plan_and_refuses_before_artifact_access() -> None:
    manifest = executor.executor_manifest(ROOT)

    assert manifest["state"] == "DRAO_DOY238_EXECUTOR_FROZEN_ARTIFACT_UNSELECTED"
    assert manifest["frozen_inputs"] == {
        plan.PLAN_NAME: executor.PLAN_RAW_SHA256,
        plan.BUNDLE_NAME: executor.BUNDLE_RAW_SHA256,
    }
    assert not any(manifest["access_at_freeze"].values())
    with pytest.raises(PermissionError, match="DRAO_DOY238_ARTIFACT_UNSELECTED"):
        executor.refuse_unselected_artifact(ROOT)


def test_marker_literal_is_descriptive_and_extra_track_is_not_scored() -> None:
    payload = fixture(marker_name="DRAO 40105M002", extra_track=True)
    measurement = scan(payload)
    try:
        assert measurement.header["marker_name"] == "DRAO 40105M002"
        assert measurement.header["marker_name_role"] == "DESCRIPTIVE_NOT_LITERAL_BINDING"
        assert measurement.header["extra_gps_tracks"] == ["G31"]
        assert measurement.phase_cycles.shape == (139, 6, 2)
    finally:
        measurement.erase()
        payload[:] = b"\x00" * len(payload)


@pytest.mark.parametrize(
    ("include_scale", "scale", "scale_state"),
    [(False, 1, "SPEC_DEFINED_ABSENCE_UNITY"), (True, 10, "EXPLICIT_RECORD")],
)
def test_scale_factor_absence_and_explicit_records_are_equivalent(
    include_scale: bool, scale: int, scale_state: str
) -> None:
    payload = fixture(include_scale=include_scale, scale=scale)
    measurement = scan(payload)
    try:
        physical = 22_000_000.0 + nominal_curves()["G14"][0]
        actual = measurement.phase_cycles[0, 0, 0] * executor.LAMBDA_L1_M
        assert actual == pytest.approx(physical, abs=0.002)
        ledger = measurement.header["transforms"]["scale_factor"]
        assert ledger["state"] == scale_state
        assert ledger["numerical_rule"] == "DIVIDE_STORED_VALUE_BY_FACTOR"
    finally:
        measurement.erase()
        payload[:] = b"\x00" * len(payload)


def test_phase_shift_is_validated_but_never_applied_twice() -> None:
    absent = fixture()
    explicit = fixture(include_phase_shift=True, phase_shift=0.25)
    left = scan(absent)
    right = scan(explicit)
    try:
        assert np.allclose(left.phase_cycles, right.phase_cycles)
        ledger = right.header["transforms"]["phase_shift"]
        assert ledger["state"] == "EXPLICIT_RECORD"
        assert ledger["numerical_rule"] == "DO_NOT_APPLY_TO_STORED_PHASE"
    finally:
        left.erase()
        right.erase()
        absent[:] = b"\x00" * len(absent)
        explicit[:] = b"\x00" * len(explicit)


def test_receiver_clock_default_and_explicit_correction_are_exactly_once() -> None:
    baseline_payload = fixture(include_clock_header=False)
    corrected_payload = fixture(clock_applied=0, receiver_clock_s=0.001)
    baseline = scan(baseline_payload)
    corrected = scan(corrected_payload)
    try:
        assert np.allclose(baseline.phase_cycles, corrected.phase_cycles, atol=0.01)
        assert np.allclose(baseline.code_m, corrected.code_m, atol=0.01)
        assert (
            baseline.header["transforms"]["receiver_clock"]["state"]
            == "SPEC_DEFINED_DEFAULT_ZERO"
        )
        assert corrected.header["event_time"]["receiver_clock_correction_epochs"] == 139
        assert corrected.header["transforms"]["receiver_clock"]["correction_count"] == "EXACTLY_ONCE"
    finally:
        baseline.erase()
        corrected.erase()
        baseline_payload[:] = b"\x00" * len(baseline_payload)
        corrected_payload[:] = b"\x00" * len(corrected_payload)


def test_transform_conflict_and_incomplete_coverage_are_typed() -> None:
    with pytest.raises(executor.ForwardDescriptionError, match="SCALE_FACTOR_CONFLICT"):
        executor._scale_ledger(
            (scale_record(10, ("L1C",)), scale_record(100, ("L1C",))),
            ("L1C",),
        )
    incomplete = list(phase_record("L1C", 0.0))
    incomplete[16:18] = " 6"
    incomplete[19:22] = "G14"
    with pytest.raises(executor.ForwardDescriptionError, match="PHASE_SHIFT_INCOMPLETE"):
        executor._phase_shift_ledger(("".join(incomplete),), plan.CODEBOOK)


def test_missing_required_field_and_witness_failure_stop_before_score() -> None:
    missing_payload = fixture(missing=(25, "G24", "L2W"))
    try:
        with pytest.raises(
            executor.ForwardMeasurementInvalid,
            match="REQUIRED_LABELLED_TOPOLOGY_INCOMPLETE",
        ):
            scan(missing_payload)
    finally:
        missing_payload[:] = b"\x00" * len(missing_payload)

    witness_payload = fixture(witness_excursion=True)
    measurement = scan(witness_payload)
    try:
        with pytest.raises(
            executor.ForwardMeasurementInvalid, match="SAME_PATH_WITNESS_UNSATISFIED"
        ):
            executor.admit_model_blind(measurement)
    finally:
        measurement.erase()
        witness_payload[:] = b"\x00" * len(witness_payload)


def test_nominal_coordinate_prefers_orbit_and_buffers_are_erased() -> None:
    payload = fixture()
    outcome = executor.execute_synthetic_fixture(
        payload, archive_site_id=plan.STATION, root=ROOT
    )

    assert outcome["outcome"] == "ORBITAL_MODEL_PREDICTIVELY_PREFERRED"
    assert outcome["score"]["best_family"] == executor.FAMILY_ORBITAL
    assert outcome["score"]["heldout_refit"] is False
    assert outcome["score"]["free_time_phase"] is False
    assert outcome["observation_values_persisted"] == 0
    assert not any(payload)
    encoded = executor.strict_json(outcome)
    assert "22000000" not in encoded


def test_affine_and_reversed_controls_select_the_frozen_nulls() -> None:
    families = executor._load_model_families(ROOT)
    affine_control = families[executor.FAMILY_ORBITAL].copy()
    affine_control[plan.PREFIX_EPOCHS :] = 0.0
    try:
        affine = executor.score_admitted_coordinate(
            affine_control, ROOT
        )
    finally:
        affine_control.fill(0.0)
        for values in families.values():
            values.fill(0.0)
    assert affine["outcome"] == "PREFIX_AFFINE_NULL_PREFERRED"

    rows = {
        executor.FAMILY_ORBITAL: {
            "controlling_prefix_peak_to_peak_m": 1.0,
            "controlling_heldout_peak_to_peak_m": 20_000.0,
        },
        executor.FAMILY_AFFINE: {
            "controlling_prefix_peak_to_peak_m": 2.0,
            "controlling_heldout_peak_to_peak_m": 10_000.0,
        },
        executor.FAMILY_REVERSED: {
            "controlling_prefix_peak_to_peak_m": 3.0,
            "controlling_heldout_peak_to_peak_m": 0.0,
        },
    }
    outcome, best, margin = executor._classify_family_metrics(rows)
    assert outcome == "TIME_REVERSED_GEOMETRY_NULL_PREFERRED"
    assert best == executor.FAMILY_REVERSED
    assert margin == 10_000.0


def test_prefix_model_mismatch_is_not_detectable() -> None:
    families = executor._load_model_families(ROOT)
    observed = families[executor.FAMILY_ORBITAL].copy()
    curve = np.square(np.arange(plan.RAW_EPOCHS, dtype=np.float64)) * 5.0
    observed[:, 0] += curve
    observed -= np.mean(observed, axis=1, keepdims=True)
    try:
        result = executor.score_admitted_coordinate(observed, ROOT)
    finally:
        observed.fill(0.0)
        curve.fill(0.0)
        for values in families.values():
            values.fill(0.0)
    assert result["outcome"] == "NOT_DETECTABLE"


def test_description_failure_never_becomes_measurement_failure() -> None:
    payload = fixture()
    try:
        with pytest.raises(executor.ForwardDescriptionError, match="ARCHIVE_SITE_ID_MISMATCH"):
            executor.scan_decoded_fixture(payload, archive_site_id="OTHER00XXX")
    finally:
        payload[:] = b"\x00" * len(payload)


def test_strict_json_rejects_nonfinite() -> None:
    with pytest.raises(ValueError):
        executor.strict_json({"bad": float("nan")})
