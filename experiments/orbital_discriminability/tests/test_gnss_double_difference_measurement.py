from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    gnss_double_difference_measurement as measurement,
)


def header_line(data: str, label: str) -> str:
    return f"{data:<60}{label:<20}\n"


def field(value: float | None, lli: int = 0) -> str:
    if value is None:
        return " " * 16
    return f"{value:14.3f}{' ' if lli == 0 else lli} "


def fixture(
    epochs: tuple[datetime, ...],
    *,
    missing_snr: bool = False,
    lli_epoch: int | None = None,
    phase_jump_epoch: int | None = None,
) -> bytearray:
    types = measurement.OBSERVABLES
    lines = [
        header_line(
            "     3.04           OBSERVATION DATA    M", "RINEX VERSION / TYPE"
        ),
        header_line(
            f"G  {len(types):3d} " + "".join(f"{item:>3} " for item in types),
            "SYS / # / OBS TYPES",
        ),
        header_line("", "END OF HEADER"),
    ]
    for epoch_index, epoch in enumerate(epochs):
        lines.append(
            f"> {epoch.year:4d} {epoch.month:02d} {epoch.day:02d} {epoch.hour:02d} "
            f"{epoch.minute:02d} {epoch.second:10.7f}  0  2\n"
        )
        for sat_index, satellite in enumerate(measurement.SATELLITES):
            phase_jump = (
                1.0 if phase_jump_epoch == epoch_index and sat_index == 0 else 0.0
            )
            values = (
                22_000_000.0 + epoch_index,
                115_000_000.0 + epoch_index * 0.02 + phase_jump,
                None if missing_snr and epoch_index == 2 and sat_index == 0 else 45.0,
                22_000_010.0 + epoch_index,
                89_000_000.0 + epoch_index * 0.015,
                43.0,
            )
            lines.append(
                satellite
                + "".join(
                    field(
                        value,
                        1 if lli_epoch == epoch_index and obs_index in (1, 4) else 0,
                    )
                    for obs_index, value in enumerate(values)
                )
                + "\n"
            )
    return bytearray("".join(lines).encode("ascii"))


def short_epochs(count: int = 5) -> tuple[datetime, ...]:
    start = datetime(2026, 8, 3, 10, 1, 30, tzinfo=timezone.utc)
    return tuple(start + timedelta(seconds=30 * index) for index in range(count))


def test_plain_parser_extracts_only_frozen_fields() -> None:
    epochs = short_epochs()
    parsed = measurement.parse_plain_rinex_window(fixture(epochs), "SYNTH", epochs)
    try:
        assert parsed.values.shape == (5, 2, 6)
        assert parsed.lli.shape == (5, 2, 2)
        assert parsed.values[2, 0, 0] == 22_000_002.0
        assert np.all(parsed.lli == 0)
    finally:
        parsed.erase()
    assert np.all(parsed.values == 0.0)


def test_missing_same_path_witness_is_measurement_invalid() -> None:
    epochs = short_epochs()
    with pytest.raises(measurement.MeasurementInvalid, match="MISSING_OR_NONFINITE"):
        measurement.parse_plain_rinex_window(
            fixture(epochs, missing_snr=True), "SYNTH", epochs
        )


def test_nonzero_lli_is_refused() -> None:
    epochs = measurement.frozen_epoch_grid()
    parsed = measurement.parse_plain_rinex_window(
        fixture(epochs, lli_epoch=100), "SYNTH", epochs
    )
    try:
        with pytest.raises(measurement.MeasurementInvalid, match="NONZERO_LLI"):
            measurement.validate_station(parsed)
    finally:
        parsed.erase()


def test_structural_half_cycle_geometry_free_rule_refuses_jump() -> None:
    epochs = measurement.frozen_epoch_grid()
    parsed = measurement.parse_plain_rinex_window(
        fixture(epochs, phase_jump_epoch=100), "SYNTH", epochs
    )
    try:
        with pytest.raises(measurement.MeasurementInvalid, match="GEOMETRY_FREE"):
            measurement.validate_station(parsed)
    finally:
        parsed.erase()


def test_prefix_only_scoring_prefers_nominal_when_guard_is_cleared() -> None:
    elapsed = (
        np.arange(measurement.FEATURE_RECORDS, dtype=np.float64) * measurement.STEP_S
    )
    nominal = 0.0002 * elapsed * elapsed
    wrong = -0.0002 * elapsed * elapsed
    observed = nominal + 12.0 - 0.01 * elapsed
    hypotheses = {
        "H_G11": nominal.copy(),
        "H_AFFINE": np.zeros_like(nominal),
        "H_G12": wrong,
    }
    outcome, scores, margins = measurement.evaluate_observed(observed, hypotheses)
    assert outcome == "ORBITAL_MODEL_PREDICTIVELY_PREFERRED"
    assert scores["H_G11"]["heldout_peak_to_peak_hz"] < 1e-8
    assert margins["H_G11"] > measurement.PAIRWISE_DECISION_GUARD_HZ


def test_large_calibration_residual_is_not_detectable() -> None:
    observed = np.zeros(measurement.FEATURE_RECORDS, dtype=np.float64)
    observed[: measurement.CALIBRATION_RECORDS] = (
        np.arange(measurement.CALIBRATION_RECORDS) % 2
    ) * 1_000.0
    hypotheses = {
        name: np.zeros_like(observed) for name in ("H_G11", "H_AFFINE", "H_G12")
    }
    outcome, _, margins = measurement.evaluate_observed(observed, hypotheses)
    assert outcome == "NOT_DETECTABLE"
    assert margins == {}


def test_manifest_freezes_dependency_and_no_persistence_policy() -> None:
    manifest = measurement.decoder_manifest()
    assert manifest["dependencies"]["python_package_hatanaka"] == "2.8.1"
    assert manifest["parameters"]["geometry_free_limit_basis"] == (
        "HALF_OF_SHORTEST_USED_CARRIER_WAVELENGTH"
    )
    assert manifest["zero_persistence"]["decompressed_rinex"] == (
        "RAM_BYTEARRAY_OVERWRITTEN_IN_FINALLY"
    )
    measurement.strict_json(manifest)
