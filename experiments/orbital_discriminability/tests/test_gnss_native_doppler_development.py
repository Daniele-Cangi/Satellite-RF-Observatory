from __future__ import annotations

from datetime import datetime, timedelta, timezone
import inspect

import numpy as np
import pytest

from experiments.orbital_discriminability import gnss_native_doppler_development as development


def header_line(data: str, label: str) -> str:
    return f"{data:<60}{label:<20}\n"


def field(value: float | None) -> str:
    return " " * 16 if value is None else f"{value:14.3f}  "


def epochs(count: int = 5) -> tuple[datetime, ...]:
    start = datetime(2026, 8, 2, 15, 41, tzinfo=timezone.utc)
    return tuple(start + timedelta(seconds=30 * index) for index in range(count))


def fixture(grid: tuple[datetime, ...], *, missing_doppler: bool = False) -> bytearray:
    time_system = " " * 48 + "GPS"
    lines = [
        header_line("     3.04           OBSERVATION DATA    M", "RINEX VERSION / TYPE"),
        header_line("KIRU00SWE", "MARKER NAME"),
        header_line(f"{development.STEP_S:10.3f}", "INTERVAL"),
        header_line(time_system, "TIME OF FIRST OBS"),
        header_line(
            f"G  {len(development.OBSERVABLES):3d} "
            + "".join(f"{item:>3} " for item in development.OBSERVABLES),
            "SYS / # / OBS TYPES",
        ),
        header_line("", "END OF HEADER"),
    ]
    for index, epoch in enumerate(grid):
        lines.append(
            f"> {epoch.year:4d} {epoch.month:02d} {epoch.day:02d} "
            f"{epoch.hour:02d} {epoch.minute:02d} {epoch.second:10.7f}  0  2\n"
        )
        for satellite_index, satellite in enumerate(development.SATELLITES):
            values = (
                22_000_000.0 + index,
                None if missing_doppler and index == 2 and satellite_index == 0 else 1000.0 + 2 * index + satellite_index,
                45.0,
                22_000_010.0 + index,
                800.0 + index + satellite_index,
                43.0,
            )
            lines.append(satellite + "".join(field(value) for value in values) + "\n")
    return bytearray("".join(lines).encode("ascii"))


def test_development_grid_and_window_family_are_exact() -> None:
    grid = development.development_epoch_grid()
    assert len(grid) == 493
    assert grid[0] == development.START_GPS
    assert grid[-1] == development.STOP_GPS
    assert development.WINDOW_COUNT == 114
    assert development.CALIBRATION_RECORDS + development.HELDOUT_RECORDS == development.WINDOW_RECORDS


def test_model_blind_parser_decodes_only_frozen_fields() -> None:
    grid = epochs()
    parsed = development.parse_plain_rinex_development(fixture(grid), "KIRU00SWE", grid)
    try:
        assert parsed.values.shape == (5, 2, 6)
        assert parsed.values[2, 0, development.OBSERVABLES.index("D1C")] == 1004.0
        assert "navigation" not in inspect.signature(development.parse_plain_rinex_development).parameters
    finally:
        parsed.erase()
    assert np.all(parsed.values == 0.0)


def test_missing_doppler_is_measurement_invalid() -> None:
    with pytest.raises(development.DevelopmentMeasurementInvalid, match="MISSING_OR_NONFINITE"):
        development.parse_plain_rinex_development(fixture(epochs(), missing_doppler=True), "KIRU00SWE", epochs())


def test_native_coordinate_has_frozen_station_satellite_order() -> None:
    grid = epochs()
    shape = (len(grid), 2, len(development.OBSERVABLES))
    left_values = np.ones(shape, dtype=np.float64)
    right_values = np.ones(shape, dtype=np.float64)
    for values in (left_values, right_values):
        values[:, :, development.OBSERVABLES.index("C1C")] = 20_000_000.0
        values[:, :, development.OBSERVABLES.index("C2W")] = 20_000_001.0
        values[:, :, development.OBSERVABLES.index("S1C")] = 45.0
        values[:, :, development.OBSERVABLES.index("S2W")] = 43.0
    left_values[:, 0, development.OBSERVABLES.index("D1C")] = 10.0
    left_values[:, 1, development.OBSERVABLES.index("D1C")] = 3.0
    right_values[:, 0, development.OBSERVABLES.index("D1C")] = 4.0
    right_values[:, 1, development.OBSERVABLES.index("D1C")] = 2.0
    left_values[:, :, development.OBSERVABLES.index("D2W")] = 0.0
    right_values[:, :, development.OBSERVABLES.index("D2W")] = 0.0
    left = development.StationDopplerRun("KIRU00SWE", grid, left_values)
    right = development.StationDopplerRun("MAT100ITA", grid, right_values)
    coordinate = development.observed_coordinate(left, right)
    alpha, _ = development.envelope.ionosphere_free_coefficients()
    assert np.allclose(coordinate, alpha * 5.0)


def test_all_windows_contribute_to_conservative_envelope() -> None:
    model = np.linspace(-20.0, 30.0, development.RUN_RECORDS)
    elapsed = np.arange(development.RUN_RECORDS) * development.STEP_S
    observed = model + 3.0 - 0.002 * elapsed
    observed[-1] += 7.5
    result = development.characterize(observed, model)
    assert result["windows_evaluated"] == 114
    assert result["controlling_window"]["stop_gps"] == development.format_gps(development.STOP_GPS)
    assert result["development_residual_peak_to_peak_hz"] == pytest.approx(7.5)
    assert result["provisional_pairwise_guard_hz"] > 15.0


def test_quantization_bound_is_analytic_and_positive() -> None:
    result = development.doppler_quantization_bound_hz()
    assert result["per_link_absolute_bound_hz"] > 0.0005
    assert result["heldout_peak_to_peak_bound_hz"] > result["raw_network_absolute_bound_hz"]


def test_manifest_binds_scope_and_seals_future_observations() -> None:
    manifest = development.runtime_manifest()
    assert manifest["plan"]["sha256"] == development.PLAN_SHA256
    assert manifest["model_blind_extractor"] is True
    assert "DOY219-221 artifact or header access" in manifest["forbidden"]
    assert manifest["parameters"]["window_count"] == 114
    assert development.strict_json(manifest)


def test_strict_json_refuses_nonfinite_and_numpy_scalars() -> None:
    with pytest.raises(ValueError):
        development.strict_json({"bad": float("nan")})
    with pytest.raises(TypeError):
        development.strict_json({"bad": np.float64(1.0)})
