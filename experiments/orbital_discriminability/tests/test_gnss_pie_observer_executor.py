from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Mapping

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    gnss_pie_observer_executor as executor,
)
from experiments.orbital_discriminability import (
    gnss_pie_observer_primary_plan as plan,
)


ROOT = Path(__file__).resolve().parents[1]
EXECUTOR_SEAL = ROOT / executor.EXECUTOR_SEAL_NAME
EXECUTOR_SOURCE_COMMIT = "c9334e45025e837a11cc62eec084b1e0495a58e2"
EXECUTOR_SOURCE_SHA256 = (
    "aaa59603eec7dc3139bb4f935faa899e9a8158708c877d8356c459500cf9727a"
)
EXECUTOR_MANIFEST_SHA256 = (
    "68d0b9ccadfc6f97cbf522784c4c6957352d231739c27f69ef6c0ba1353fb4e3"
)
EXECUTOR_SEAL_SHA256 = (
    "3b15c0c899756c48c80a6339cb6c6e20a0f493f379f8b439c445caf1bf033e2b"
)


def header_line(data: str, label: str) -> str:
    return f"{data:<60}{label:<20}\n"


def field(value: float, lli: int = 0) -> str:
    return f"{value:14.3f}{' ' if lli == 0 else lli} "


def synthetic_transform() -> dict[str, object]:
    return {
        "marker_name": "PIE1",
        "receiver": {
            "serial": "4100427",
            "type": "SEPT POLARX5TR",
            "version_or_radome": "5.7.0",
        },
        "antenna": {
            "serial": "CR520022114",
            "type": "ASH701945E_M NONE",
            "version_or_radome": "",
        },
        "receiver_clock_offset_applied": 0,
        "required_phase_shift_records": [],
        "applied_bias_records": [],
        "scale_factor_records": [],
    }


def fixture(
    *,
    nonzero_lli: tuple[int, str, str] | None = None,
    code_slew_m: float = 0.0,
) -> bytearray:
    observables = ("C1C", "L1C", "S1C", "C2W", "L2W", "S2W")
    lines = [
        header_line(
            "     3.04           OBSERVATION DATA    G", "RINEX VERSION / TYPE"
        ),
        header_line("PIE1", "MARKER NAME"),
        header_line(
            f"{'4100427':<20}{'SEPT POLARX5TR':<20}{'5.7.0':<20}",
            "REC # / TYPE / VERS",
        ),
        header_line(f"{'CR520022114':<20}{'ASH701945E_M NONE':<20}", "ANT # / TYPE"),
        header_line(" -1640916.0 -5014782.0 3575448.0", "APPROX POSITION XYZ"),
        header_line(
            f"G  {len(observables):3d} "
            + "".join(f"{item:>3} " for item in observables),
            "SYS / # / OBS TYPES",
        ),
        header_line("      30.000", "INTERVAL"),
        header_line(
            "  2026     8    11     0     0    0.0000000     GPS",
            "TIME OF FIRST OBS",
        ),
        header_line(
            "  2026     8    11    23    59   30.0000000     GPS",
            "TIME OF LAST OBS",
        ),
        header_line("", "END OF HEADER"),
    ]
    for epoch_index, epoch in enumerate(executor.expected_raw_gps_epochs()):
        lines.append(
            f"> {epoch.year:4d} {epoch.month:02d} {epoch.day:02d} "
            f"{epoch.hour:02d} {epoch.minute:02d} {epoch.second:10.7f}  0  2\n"
        )
        for satellite_index, satellite in enumerate(executor.SATELLITES):
            phase_base = 115_000_000.0 + satellite_index * 2_000.0
            code_base = 22_000_000.0 + satellite_index * 100.0
            values: dict[str, tuple[float, int]] = {
                "C1C": (code_base + epoch_index * code_slew_m, 0),
                "L1C": (phase_base + epoch_index * 0.020, 0),
                "S1C": (45.0, 0),
                "C2W": (code_base + 10.0 + epoch_index * code_slew_m, 0),
                "L2W": (
                    89_000_000.0 + satellite_index * 1_500.0 + epoch_index * 0.015,
                    0,
                ),
                "S2W": (43.0, 0),
            }
            if nonzero_lli and nonzero_lli[:2] == (epoch_index, satellite):
                value, _ = values[nonzero_lli[2]]
                values[nonzero_lli[2]] = (value, 1)
            lines.append(
                satellite + "".join(field(*values[item]) for item in observables) + "\n"
            )
    return bytearray("".join(lines).encode("ascii"))


def synthetic_curves(second_best_margin_m: float) -> dict[str, np.ndarray]:
    curves = {
        name: np.zeros(plan.RAW_EPOCHS, dtype=np.float64)
        for name in executor.HYPOTHESES
    }
    curves["FROZEN_AFFINE_NULL"][plan.HELDOUT_START_INDEX :] = np.linspace(
        0.0, second_best_margin_m, plan.HELDOUT_EPOCHS
    )
    for index, name in enumerate(
        ("WRONG_ORBIT_G01", "WRONG_ORBIT_G14", "WRONG_ORBIT_G17"), start=2
    ):
        curves[name][plan.HELDOUT_START_INDEX :] = np.linspace(
            0.0, index * 100_000.0, plan.HELDOUT_EPOCHS
        )
    return curves


def test_manifest_is_one_product_observation_blind_and_no_fit() -> None:
    manifest = executor.executor_manifest(ROOT)
    encoded = executor.strict_json(manifest)

    assert manifest["product"]["station"] == "PIE100USA"
    assert manifest["product"]["fallback"] is False
    assert manifest["transport"]["maximum_attempts_before_complete_hash"] == 2
    assert manifest["scoring"]["fit_or_projection"] == "NONE"
    assert manifest["scoring"]["nuisance_fit_parameters"] == 0
    assert manifest["live_execution_authorized"] is False
    assert not any(manifest["access_at_freeze"].values())
    assert executor.AUTHORITY_TOKEN not in encoded


def test_frozen_executor_seal_binds_source_manifest_and_zero_access() -> None:
    assert executor.canonical_sha256(EXECUTOR_SEAL) == EXECUTOR_SEAL_SHA256
    assert executor.source_sha256() == EXECUTOR_SOURCE_SHA256
    assert executor.manifest_sha256(ROOT) == EXECUTOR_MANIFEST_SHA256

    seal, curves, transform = executor.validate_executor_seal(
        ROOT, EXECUTOR_SEAL, EXECUTOR_SEAL_SHA256
    )
    try:
        assert seal["state"] == "PIE_OBSERVER_PRIMARY_EXECUTOR_FROZEN_UNOPENED"
        assert seal["source_commit"] == EXECUTOR_SOURCE_COMMIT
        assert seal["source_sha256"] == EXECUTOR_SOURCE_SHA256
        assert seal["manifest_sha256"] == EXECUTOR_MANIFEST_SHA256
        assert not any(seal["access_at_seal"].values())
        assert seal["authority"]["live_execution_authorized_by_seal"] is False
        assert transform["receiver"]["serial"] == "4100427"
    finally:
        for curve in curves.values():
            curve.fill(0.0)


def test_frozen_inputs_bind_exact_prediction_and_qualified_transform() -> None:
    curves, transform = executor.validate_frozen_inputs(ROOT)
    try:
        assert set(curves) == set(executor.HYPOTHESES)
        assert all(curve.shape == (139,) for curve in curves.values())
        assert transform["receiver"]["serial"] == "4100427"
        assert transform["required_phase_shift_records"] == ["G L1C", "G L2W"]
    finally:
        for curve in curves.values():
            curve.fill(0.0)


def test_parser_coordinate_and_witness_use_exact_139_epoch_grid() -> None:
    scan = executor.scan_decoded(fixture(), synthetic_transform())
    try:
        coordinate, admission = executor.measurement_coordinate(scan)
        coordinate.fill(0.0)
    finally:
        scan.erase()

    assert admission["core_phase_and_lli"] == "SATISFIED"
    assert admission["geometry_free_phase_health"]["state"] == "SATISFIED"
    assert admission["same_path_code_phase_witness"]["state"] == "SATISFIED"
    assert admission["event_time"]["maximum_absolute_deviation_s"] == 0.0
    assert admission["raw_epochs"] == 139


def test_nonzero_lli_is_measurement_invalid() -> None:
    with pytest.raises(executor.PrimaryMeasurementInvalid, match="NONZERO"):
        executor.scan_decoded(
            fixture(nonzero_lli=(79, "G22", "L1C")), synthetic_transform()
        )


def test_code_phase_witness_over_limit_is_not_detectable() -> None:
    scan = executor.scan_decoded(fixture(code_slew_m=20.0), synthetic_transform())
    try:
        with pytest.raises(executor.PrimaryNotDetectable, match="WITNESS_OVER_LIMIT"):
            executor.measurement_coordinate(scan)
    finally:
        scan.erase()


def test_scoring_has_no_prefix_fit_and_uses_strict_guard() -> None:
    observed = np.zeros(plan.RAW_EPOCHS, dtype=np.float64)
    below = executor.score_coordinate(
        observed, synthetic_curves(plan.REVISED_PAIRWISE_GUARD_M)
    )
    above = executor.score_coordinate(
        observed, synthetic_curves(plan.REVISED_PAIRWISE_GUARD_M + 1.0)
    )

    assert below["outcome"] == "AMBIGUOUS"
    assert above["outcome"] == "PIE_HELD_OUT_ORBITAL_MODEL_PREFERRED"
    assert above["heldout_comparison"]["nuisance_parameters_fit"] == 0
    assert above["heldout_comparison"]["raw_indices_inclusive"] == [79, 138]


def test_authority_refuses_before_seal_marker_or_materializer() -> None:
    called = False

    def forbidden():
        nonlocal called
        called = True
        raise AssertionError("network reached")

    with TemporaryDirectory(dir=ROOT) as directory:
        output = Path(directory)
        with pytest.raises(PermissionError, match="AUTHORITY_REQUIRED"):
            executor.run_once(
                output,
                "",
                "0" * 64,
                output / "missing.json",
                materializer=forbidden,
            )
        assert not (output / executor.AUTHORITY_MARKER_NAME).exists()
    assert called is False


def test_one_shot_marker_precedes_materialization_and_buffers_are_erased(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    curves = synthetic_curves(plan.REVISED_PAIRWISE_GUARD_M + 1.0)
    seal = {"source_commit": "frozen", "source_sha256": "a" * 64}
    compressed = bytearray(b"compressed")
    decoded = fixture()
    scans: list[executor.StationMeasurement] = []
    coordinates: list[np.ndarray] = []

    def validate(*_args):
        return seal, curves, synthetic_transform()

    def materialize():
        assert marker_path.exists()
        return compressed, {
            "station": "PIE100USA",
            "product": plan.PRIMARY_PRODUCT,
            "attempts": 1,
            "complete_file_bytes": len(compressed),
            "complete_file_sha256": sha256(compressed).hexdigest(),
        }

    def decompress(_payload: bytearray):
        return decoded

    original_scan = executor.scan_decoded
    original_coordinate = executor.measurement_coordinate

    def scan(payload: bytearray, transform: Mapping[str, object]):
        value = original_scan(payload, transform)
        scans.append(value)
        return value

    def coordinate(scan_value: executor.StationMeasurement):
        value, admission = original_coordinate(scan_value)
        coordinates.append(value)
        return value, admission

    monkeypatch.setattr(executor, "validate_executor_seal", validate)
    monkeypatch.setattr(executor, "decompress_in_memory", decompress)
    monkeypatch.setattr(executor, "scan_decoded", scan)
    monkeypatch.setattr(executor, "measurement_coordinate", coordinate)

    with TemporaryDirectory(dir=ROOT) as directory:
        output = Path(directory)
        marker_path = output / executor.AUTHORITY_MARKER_NAME
        outcome = executor.run_once(
            output,
            executor.AUTHORITY_TOKEN,
            "f" * 64,
            output / "seal.json",
            materializer=materialize,
        )
        persisted = (output / executor.OUTCOME_NAME).read_text(encoding="utf-8")
        with pytest.raises(PermissionError, match="ALREADY_CONSUMED"):
            executor.run_once(
                output,
                executor.AUTHORITY_TOKEN,
                "f" * 64,
                output / "seal.json",
                materializer=materialize,
            )

    assert outcome["outcome"] == "PIE_HELD_OUT_ORBITAL_MODEL_PREFERRED"
    assert "phase_cycles" not in persisted and "code_m" not in persisted
    assert outcome["persistence"]["observation_values"] == 0
    assert not any(compressed) and not any(decoded)
    assert all(not np.any(scan.phase_cycles) for scan in scans)
    assert all(not np.any(value) for value in coordinates)


def test_description_failure_cannot_become_measurement_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    curves = synthetic_curves(plan.REVISED_PAIRWISE_GUARD_M + 1.0)

    def validate(*_args):
        return (
            {"source_commit": "frozen", "source_sha256": "a" * 64},
            curves,
            synthetic_transform(),
        )

    def describe_failure():
        raise executor.PrimaryDescriptionError("DIRECTORY_DESCRIPTION_FAILED")

    monkeypatch.setattr(executor, "validate_executor_seal", validate)
    with TemporaryDirectory(dir=ROOT) as directory:
        outcome = executor.run_once(
            Path(directory),
            executor.AUTHORITY_TOKEN,
            "f" * 64,
            Path(directory) / "seal.json",
            materializer=describe_failure,
        )

    assert outcome["execution_state"] == "PRIMARY_DESCRIPTION_ERROR"
    assert outcome["physical_outcome"] is None
    assert outcome["heldout_comparison"] == "NOT_EVALUATED"


def test_transport_budget_is_exactly_two_pre_hash_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0

    def interrupted():
        nonlocal attempts
        attempts += 1
        raise executor.TransportInterruption("TIMEOUT")

    monkeypatch.setattr(executor, "_new_gssc_session", interrupted)

    with pytest.raises(executor.PrimaryMaterializationError) as caught:
        executor.materialize_gssc()

    assert attempts == 2
    assert caught.value.receipt["attempts"] == 2
    assert caught.value.receipt["complete_file_sha256"] is None
    assert caught.value.receipt["retry_after_hash_or_decode"] is False


def test_description_error_has_zero_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0

    def description_error():
        nonlocal attempts
        attempts += 1
        raise executor.PrimaryDescriptionError("DIRECTORY_SCHEMA_CHANGED")

    monkeypatch.setattr(executor, "_new_gssc_session", description_error)

    with pytest.raises(executor.PrimaryDescriptionError):
        executor.materialize_gssc()

    assert attempts == 1


def test_strict_json_rejects_nonfinite_values() -> None:
    with pytest.raises(ValueError):
        executor.strict_json({"bad": float("nan")})
    with pytest.raises(ValueError):
        executor.strict_json({"bad": float("inf")})
    assert datetime.fromisoformat("2026-08-11T05:42:00+00:00").tzinfo is not None
