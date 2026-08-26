from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    gnss_independent_pair_primary_executor as executor,
)
from experiments.orbital_discriminability import (
    gnss_independent_pair_primary_plan as frozen,
)
from experiments.orbital_discriminability import gnss_phase_short_window_primary as primary


ROOT = Path(__file__).resolve().parents[1]


def header_line(data: str, label: str) -> str:
    return f"{data:<60}{label:<20}\n"


def field(value: float | None, lli: int = 0) -> str:
    if value is None:
        return " " * 16
    return f"{value:14.3f}{' ' if lli == 0 else lli} "


def synthetic_expected(locator: primary.ProductLocator) -> dict[str, object]:
    config = executor.qualified.EXPECTED_CONFIGURATION[locator.station]
    return {
        "receiver": {
            "serial": config["receiver_serial"],
            "type": config["receiver_type"],
            "version_or_radome": config["receiver_version"],
        },
        "antenna": {
            "serial": config["antenna_serial"],
            "type": config["antenna_type"],
            "version_or_radome": "",
        },
        "scale_factor_records": [],
        "phase_shift_records": [],
        "applied_bias_records": [],
        "receiver_clock_offset_applied": 0,
    }


def fixture(
    locator: primary.ProductLocator,
    *,
    nonzero_lli: tuple[int, str, str] | None = None,
) -> bytearray:
    observables = ("C1C", "L1C", "S1C", "C2W", "L2W", "S2W")
    expected = synthetic_expected(locator)
    receiver = expected["receiver"]
    antenna = expected["antenna"]
    lines = [
        header_line(
            "     3.04           OBSERVATION DATA    G",
            "RINEX VERSION / TYPE",
        ),
        header_line(locator.station[:4], "MARKER NAME"),
        header_line(
            f"{receiver['serial']:<20}{receiver['type']:<20}"
            f"{receiver['version_or_radome']:<20}",
            "REC # / TYPE / VERS",
        ),
        header_line(
            f"{antenna['serial']:<20}{antenna['type']:<20}",
            "ANT # / TYPE",
        ),
        header_line(" -2350000.0 -4650000.0 3670000.0", "APPROX POSITION XYZ"),
        header_line(
            f"G  {len(observables):3d} "
            + "".join(f"{item:>3} " for item in observables),
            "SYS / # / OBS TYPES",
        ),
        header_line("      30.000", "INTERVAL"),
        header_line(
            "  2026     8     7     0     0    0.0000000     GPS",
            "TIME OF FIRST OBS",
        ),
        header_line(
            "  2026     8     7    23    59   30.0000000     GPS",
            "TIME OF LAST OBS",
        ),
        header_line("", "END OF HEADER"),
    ]
    station_bias = 200.0 if locator.station == "MDO100USA" else 0.0
    for epoch_index, epoch in enumerate(executor.expected_raw_gps_epochs()):
        lines.append(
            f"> {epoch.year:4d} {epoch.month:02d} {epoch.day:02d} "
            f"{epoch.hour:02d} {epoch.minute:02d} {epoch.second:10.7f}  0  2\n"
        )
        for satellite_index, satellite in enumerate(executor.SATELLITES):
            values: dict[str, tuple[float | None, int]] = {
                "C1C": (22_000_000.0 + epoch_index + satellite_index, 0),
                "L1C": (
                    115_000_000.0
                    + station_bias
                    + epoch_index * 0.020
                    + satellite_index,
                    0,
                ),
                "S1C": (45.0, 0),
                "C2W": (22_000_010.0 + epoch_index + satellite_index, 0),
                "L2W": (
                    89_000_000.0
                    + station_bias
                    + epoch_index * 0.015
                    + satellite_index,
                    0,
                ),
                "S2W": (43.0, 0),
            }
            if nonzero_lli and nonzero_lli[:2] == (epoch_index, satellite):
                value, _ = values[nonzero_lli[2]]
                values[nonzero_lli[2]] = (value, 1)
            lines.append(
                satellite
                + "".join(field(*values[item]) for item in observables)
                + "\n"
            )
    return bytearray("".join(lines).encode("ascii"))


def synthetic_curves(second_best_margin_m: float) -> dict[str, np.ndarray]:
    prefix = np.zeros(frozen.CALIBRATION_EPOCHS, dtype=np.float64)

    def tail(scale: float) -> np.ndarray:
        return np.concatenate(
            (
                prefix,
                np.linspace(0.0, scale, frozen.HELDOUT_EPOCHS, dtype=np.float64),
            )
        )

    return {
        "ORBITAL_G22": tail(0.0),
        "PREFIX_AFFINE": tail(second_best_margin_m),
        "WRONG_ORBIT_G01": tail(10_000.0),
        "WRONG_ORBIT_G14": tail(20_000.0),
        "WRONG_ORBIT_G17": tail(30_000.0),
    }


def test_manifest_is_exact_and_grants_no_live_authority() -> None:
    manifest = executor.executor_manifest()
    encoded = executor.strict_json(manifest)

    assert [row["station"] for row in manifest["products"]] == [
        "ALGO00CAN",
        "MDO100USA",
    ]
    assert all("2026219" in row["name"] for row in manifest["products"])
    assert executor.AUTHORITY_TOKEN not in encoded
    assert manifest["access"]["headers_opened"] == 0
    assert manifest["access"]["payload_bytes"] == 0
    assert manifest["access"]["values_accessed"] == 0
    assert manifest["transport"]["attempts_per_locator"] == 1
    assert manifest["transport"]["fallback_or_reserve"] is False


def test_frozen_inputs_include_exact_curves_and_qualified_header_transforms() -> None:
    curves, qualified_headers = executor.validate_frozen_inputs(ROOT)
    try:
        assert set(curves) == set(executor.HYPOTHESES)
        assert all(curve.shape == (137,) for curve in curves.values())
        assert list(qualified_headers) == ["ALGO00CAN", "MDO100USA"]
        assert all(
            row["receiver_clock_offset_applied"] == 0
            and row["scale_factor_records"] == []
            and row["applied_bias_records"] == []
            and row["phase_shift_records"]
            for row in qualified_headers.values()
        )
    finally:
        for curve in curves.values():
            curve.fill(0.0)


def test_parser_and_coordinate_use_algo_mdo_doy219_only() -> None:
    scans = [
        executor.scan_decoded(fixture(locator), locator, synthetic_expected(locator))
        for locator in executor.PRODUCTS
    ]
    try:
        coordinate, admission = executor.measurement_coordinate(scans)
        coordinate.fill(0.0)
    finally:
        for scan in scans:
            scan.erase()

    assert executor.expected_raw_gps_epochs()[0] == frozen.RAW_START
    assert admission["core_phase_and_lli"] == "SATISFIED"
    assert admission["same_path_code_witness"]["state"] == "SATISFIED"
    assert admission["geometry_free_phase_health"]["state"] == "SATISFIED"
    assert admission["feature_epochs"] == 137
    assert all(np.count_nonzero(scan.phase_cycles) == 0 for scan in scans)


def test_nonzero_lli_is_measurement_invalid() -> None:
    locator = executor.PRODUCTS[0]
    payload = fixture(locator, nonzero_lli=(77, "G22", "L1C"))

    with pytest.raises(primary.PrimaryMeasurementInvalid, match="NONZERO_OR_INVALID_LLI"):
        executor.scan_decoded(payload, locator, synthetic_expected(locator))


def test_header_transform_change_is_measurement_invalid() -> None:
    locator = executor.PRODUCTS[0]
    expected = synthetic_expected(locator)
    expected["phase_shift_records"] = ["G L1C  0.25000"]

    with pytest.raises(primary.PrimaryMeasurementInvalid, match="PHASE_SHIFT_RECORDS_CHANGED"):
        executor.scan_decoded(fixture(locator), locator, expected)


def test_scoring_uses_frozen_algo_mdo_pairwise_guard() -> None:
    observed = np.zeros(frozen.FEATURE_EPOCHS, dtype=np.float64)
    below = executor.score_coordinate(
        observed,
        synthetic_curves(frozen.SCREEN_PAIRWISE_GUARD_M),
    )
    above = executor.score_coordinate(
        observed,
        synthetic_curves(frozen.SCREEN_PAIRWISE_GUARD_M + 1.0),
    )

    assert below["outcome"] == "AMBIGUOUS"
    assert above["outcome"] == "ORBITAL_MODEL_PREDICTIVELY_PREFERRED"
    assert above["heldout_comparison"]["preference_guard_m"] == pytest.approx(
        3_542.2570672266515
    )
    assert above["calibration_admission"]["limit_m"] == pytest.approx(
        1_771.1285336133258
    )


def test_authority_refuses_before_seal_or_network(monkeypatch, tmp_path: Path) -> None:
    called = False

    def forbidden(_locator: primary.ProductLocator):
        nonlocal called
        called = True
        raise AssertionError("network reached")

    monkeypatch.setattr(primary, "materialize", forbidden)
    with pytest.raises(
        PermissionError,
        match="ALGO_MDO_DOY219_PRIMARY_AUTHORITY_REQUIRED",
    ):
        executor.run_once(tmp_path, "", "0" * 64, tmp_path / "missing.json")
    assert called is False


def test_existing_outcome_refuses_before_seal_or_network(
    monkeypatch, tmp_path: Path
) -> None:
    (tmp_path / executor.OUTCOME_NAME).write_text("occupied", encoding="ascii")
    called = False

    def forbidden(_locator: primary.ProductLocator):
        nonlocal called
        called = True
        raise AssertionError("network reached")

    monkeypatch.setattr(primary, "materialize", forbidden)
    with pytest.raises(PermissionError, match="PRIMARY_OUTCOME_ALREADY_EXISTS"):
        executor.run_once(
            tmp_path,
            executor.AUTHORITY_TOKEN,
            "0" * 64,
            tmp_path / "missing.json",
        )
    assert called is False


def test_strict_json_rejects_nonfinite_values() -> None:
    with pytest.raises(ValueError):
        executor.strict_json({"bad": float("nan")})
    assert json.loads(executor.strict_json(executor.executor_manifest())) == (
        executor.executor_manifest()
    )
