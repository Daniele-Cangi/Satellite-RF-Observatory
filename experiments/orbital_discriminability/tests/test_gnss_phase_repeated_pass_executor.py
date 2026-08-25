from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    gnss_phase_repeated_pass_executor as executor,
)
from experiments.orbital_discriminability import (
    gnss_phase_repeated_pass_plan as frozen,
)
from experiments.orbital_discriminability import (
    gnss_phase_short_window_primary as primary,
)


ROOT = Path(__file__).resolve().parents[1]


def header_line(data: str, label: str) -> str:
    return f"{data:<60}{label:<20}\n"


def field(value: float | None, lli: int = 0) -> str:
    if value is None:
        return " " * 16
    return f"{value:14.3f}{' ' if lli == 0 else lli} "


def fixture(
    locator: primary.ProductLocator,
    *,
    nonzero_lli: tuple[int, str, str] | None = None,
) -> bytearray:
    observables = ("C1C", "L1C", "S1C", "C2W", "L2W", "S2W")
    config = primary.EXPECTED_CONFIGURATION[locator.station]
    lines = [
        header_line(
            "     3.04           OBSERVATION DATA    G",
            "RINEX VERSION / TYPE",
        ),
        header_line(locator.station[:4], "MARKER NAME"),
        header_line(
            f"SERIAL              {config['receiver_type']:<20}"
            f"{config['receiver_version']:<20}",
            "REC # / TYPE / VERS",
        ),
        header_line(
            f"ANTENNA             {config['antenna_type']:<20}",
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
    station_bias = 200.0 if locator.station == "NLIB00USA" else 0.0
    for epoch_index, epoch in enumerate(executor.expected_raw_gps_epochs()):
        lines.append(
            f"> {epoch.year:4d} {epoch.month:02d} {epoch.day:02d} "
            f"{epoch.hour:02d} {epoch.minute:02d} "
            f"{epoch.second:10.7f}  0  2\n"
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
                    89_000_000.0 + station_bias + epoch_index * 0.015 + satellite_index,
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
        "WRONG_ORBIT_G01": tail(5_000.0),
        "WRONG_ORBIT_G14": tail(10_000.0),
        "WRONG_ORBIT_G17": tail(20_000.0),
    }


def test_manifest_is_doy219_only_and_grants_no_live_authority() -> None:
    manifest = executor.executor_manifest()
    encoded = executor.strict_json(manifest)

    assert all("2026219" in row["name"] for row in manifest["products"])
    assert "2026218" not in encoded
    assert executor.AUTHORITY_TOKEN not in encoded
    assert not any(manifest["access"].values())
    assert manifest["transport"] == {
        "attempts_per_locator": 1,
        "complete_file_hash_before_decode": True,
        "endpoint_substitution": False,
        "date_substitution": False,
        "reserve_fallback": False,
    }


def test_reused_kernel_contract_is_exact_and_excludes_doy220_state() -> None:
    executor.validate_reused_kernel_contract()
    kernel = executor.executor_manifest()["model_blind_kernel"]

    assert kernel["canonical_sha256"] == executor.PRIMARY_KERNEL_SHA256
    assert "DOY220_GRID" in kernel["not_reused"]
    assert "DOY220_OUTCOME" in kernel["not_reused"]
    assert "PREFIX_CONSTANT_RATE_FIT" in kernel["reused"]


def test_frozen_inputs_are_exact_and_observation_blind() -> None:
    curves = executor.validate_frozen_inputs(ROOT)
    try:
        assert set(curves) == set(executor.HYPOTHESES)
        assert all(curve.shape == (frozen.FEATURE_EPOCHS,) for curve in curves.values())
    finally:
        for curve in curves.values():
            curve.fill(0.0)


def test_parser_and_coordinate_use_the_doy219_grid() -> None:
    scans = [
        executor.scan_decoded(fixture(locator), locator)
        for locator in executor.PRODUCTS
    ]
    try:
        coordinate, admission = executor.measurement_coordinate(scans)
        coordinate.fill(0.0)
    finally:
        for scan in scans:
            scan.erase()

    assert executor.expected_raw_gps_epochs()[0] == frozen.REPLICATION_RAW_START
    assert admission["core_phase_and_lli"] == "SATISFIED"
    assert admission["same_path_code_witness"]["state"] == "SATISFIED"
    assert admission["geometry_free_phase_health"]["state"] == "SATISFIED"
    assert admission["feature_epochs"] == 137
    assert all(np.count_nonzero(scan.phase_cycles) == 0 for scan in scans)


def test_nonzero_lli_is_measurement_invalid() -> None:
    payload = fixture(
        executor.PRODUCTS[0],
        nonzero_lli=(77, "G22", "L1C"),
    )
    with pytest.raises(
        primary.PrimaryMeasurementInvalid,
        match="NONZERO_OR_INVALID_LLI",
    ):
        executor.scan_decoded(payload, executor.PRODUCTS[0])


def test_replication_uses_its_own_frozen_pairwise_guard() -> None:
    curves = synthetic_curves(2_380.0)
    observed = np.zeros(frozen.FEATURE_EPOCHS, dtype=np.float64)

    repeated = executor.score_coordinate(observed, curves)
    consumed_primary = primary.score_coordinate(observed, curves)

    assert repeated["outcome"] == "ORBITAL_MODEL_REPEATED_PASS_PREFERRED"
    assert repeated["heldout_comparison"]["preference_margin_m"] == pytest.approx(
        2_380.0
    )
    assert consumed_primary["outcome"] == "AMBIGUOUS"


def test_authority_refuses_before_seal_or_network(monkeypatch, tmp_path: Path) -> None:
    called = False

    def forbidden(_locator: primary.ProductLocator):
        nonlocal called
        called = True
        raise AssertionError("network reached")

    monkeypatch.setattr(primary, "materialize", forbidden)
    with pytest.raises(PermissionError, match="DOY219_REPLICATION_AUTHORITY_REQUIRED"):
        executor.run_once(
            tmp_path,
            "",
            "0" * 64,
            tmp_path / "missing-seal.json",
        )
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
    with pytest.raises(PermissionError, match="REPLICATION_OUTCOME_ALREADY_EXISTS"):
        executor.run_once(
            tmp_path,
            executor.AUTHORITY_TOKEN,
            "0" * 64,
            tmp_path / "missing-seal.json",
        )
    assert called is False


def test_strict_json_rejects_nonfinite_values() -> None:
    with pytest.raises(ValueError):
        executor.strict_json({"bad": float("nan")})
    assert json.loads(executor.strict_json(executor.executor_manifest())) == (
        executor.executor_manifest()
    )


def test_executor_seal_is_exact_and_observation_blind() -> None:
    seal_path = ROOT / executor.EXECUTOR_SEAL_NAME
    expected = "490f60155dde4972df411d08717462e28b123883e3ef4aea15d708c982208ed6"

    assert executor.canonical_sha256(seal_path) == expected
    seal, curves = executor.validate_executor_seal(ROOT, seal_path, expected)
    try:
        assert seal["source_commit"] == ("d080bbb6b4db5d7328863e02d1df0baff6331658")
        assert seal["source_sha256"] == executor.source_sha256()
        assert seal["manifest_sha256"] == executor.manifest_sha256()
        assert seal["authority"]["live_execution_authorized_by_seal"] is False
        assert not any(seal["access_at_seal"].values())
        assert all(value.shape == (137,) for value in curves.values())
    finally:
        for curve in curves.values():
            curve.fill(0.0)


def test_injected_one_shot_uses_two_hashes_one_outcome_and_no_values(
    monkeypatch, tmp_path: Path
) -> None:
    materialized: list[bytearray] = []
    decoded: list[bytearray] = []

    def fake_materialize(locator: primary.ProductLocator):
        payload = fixture(locator)
        materialized.append(payload)
        return payload, {
            "station": locator.station,
            "product": locator.name,
            "url": locator.url,
            "attempts": 1,
            "complete_file_bytes": len(payload),
            "complete_file_sha256": executor.sha256(payload).hexdigest(),
            "hash_before_any_decode": True,
        }

    def fake_decode(payload: bytearray, _station: str) -> bytearray:
        result = bytearray(payload)
        decoded.append(result)
        return result

    prediction_value = json.loads(
        (ROOT / executor.prediction.PREDICTIONS_NAME).read_text(encoding="utf-8")
    )
    orbital = np.asarray(prediction_value["curves_m"]["ORBITAL_G22"], dtype=np.float64)

    def matching_coordinate(_scans):
        elapsed = np.arange(orbital.size, dtype=np.float64) * frozen.STEP_S
        return orbital + 12.5 + 0.002 * elapsed, {"synthetic": "SATISFIED"}

    monkeypatch.setattr(primary, "materialize", fake_materialize)
    monkeypatch.setattr(primary, "decode_in_memory", fake_decode)
    monkeypatch.setattr(executor, "measurement_coordinate", matching_coordinate)

    seal_sha = "490f60155dde4972df411d08717462e28b123883e3ef4aea15d708c982208ed6"
    outcome = executor.run_once(
        tmp_path,
        executor.AUTHORITY_TOKEN,
        seal_sha,
        ROOT / executor.EXECUTOR_SEAL_NAME,
    )

    assert outcome["outcome"] == "ORBITAL_MODEL_REPEATED_PASS_PREFERRED"
    assert len(outcome["artifacts"]) == 2
    assert all(row["hash_before_any_decode"] for row in outcome["artifacts"])
    assert outcome["persistence"]["observation_values"] == 0
    encoded = (tmp_path / executor.OUTCOME_NAME).read_text(encoding="utf-8")
    assert '"phase_cycles"' not in encoded
    assert '"curves_m"' not in encoded
    assert all(not np.any(payload) for payload in materialized + decoded)

    with pytest.raises(PermissionError, match="REPLICATION_OUTCOME_ALREADY_EXISTS"):
        executor.run_once(
            tmp_path,
            executor.AUTHORITY_TOKEN,
            seal_sha,
            ROOT / executor.EXECUTOR_SEAL_NAME,
        )
