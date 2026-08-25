"""Offline-only DOY 219 prediction compiler and prospective seal.

No observation locator, transport or decoder exists in this module.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timedelta
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
from typing import Final, Mapping

import numpy as np

from experiments.orbital_discriminability import gnss_double_difference_screen as base
from experiments.orbital_discriminability import gnss_orbit_pair_screen as pair
from experiments.orbital_discriminability import gnss_phase_quotient_spike as phase
from experiments.orbital_discriminability import gnss_phase_repeated_pass_plan as frozen
from experiments.orbital_discriminability import (
    gnss_structural_qualification as structural,
)


REPLICATION_VERSION: Final = "g22-g30-doy219-repeated-pass-v1"
PREDICTIONS_NAME: Final = "GNSS_PHASE_REPEATED_PASS_PREDICTIONS.json"
SEAL_NAME: Final = "GNSS_PHASE_REPEATED_PASS_SEAL.json"
MODEL_SATELLITES: Final = ("G22", "G30", "G01", "G14", "G17")
HYPOTHESES: Final = {
    "ORBITAL_G22": "G22",
    "PREFIX_AFFINE": None,
    "WRONG_ORBIT_G01": "G01",
    "WRONG_ORBIT_G14": "G14",
    "WRONG_ORBIT_G17": "G17",
}
PREFIX_AFFINE_REGRESSION_M: Final = 11569.974689858733
NUMERICAL_TOLERANCE_M: Final = 1.0e-6


class RepeatedPassDescriptionError(ValueError):
    """An offline source, prediction or seal violated the frozen plan."""


def strict_json(value: object, *, pretty: bool = False) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
        sort_keys=True,
    )


def canonical_sha256(path: Path) -> str:
    return sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def source_sha256() -> str:
    return canonical_sha256(Path(__file__))


def _git_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
    ).strip()


def dependency_versions() -> dict[str, str]:
    return {
        "python": platform.python_version(),
        "numpy": importlib.metadata.version("numpy"),
    }


def navigation_authority() -> pair.NavigationAuthority:
    authority = next(item for item in pair.AUTHORITIES if item.doy == 219)
    if authority.name != "BRDM00DLR_S_20262190000_01D_MN.rnx":
        raise RepeatedPassDescriptionError("REPLICATION_NAVIGATION_AUTHORITY_CHANGED")
    return authority


def expected_raw_gps_epochs() -> tuple[datetime, ...]:
    result = tuple(
        frozen.REPLICATION_RAW_START + timedelta(seconds=index * frozen.STEP_S)
        for index in range(frozen.RAW_EPOCHS)
    )
    if structural.format_gps_epoch(result[-1]) != "2026-08-07T06:55:00.000000Z":
        raise RepeatedPassDescriptionError("REPLICATION_GRID_CHANGED")
    return result


def validate_navigation(path: Path) -> pair.NavigationAuthority:
    authority = navigation_authority()
    candidate = Path(path)
    if candidate.name != authority.name:
        raise RepeatedPassDescriptionError("REPLICATION_NAVIGATION_NAME_CHANGED")
    if not candidate.is_file() or candidate.stat().st_size != authority.bytes:
        raise RepeatedPassDescriptionError("REPLICATION_NAVIGATION_SIZE_CHANGED")
    if base.file_sha256(candidate) != authority.sha256:
        raise RepeatedPassDescriptionError("REPLICATION_NAVIGATION_SHA256_CHANGED")
    return authority


def _range_curve(
    positions: Mapping[str, np.ndarray],
    station_ecef: Mapping[str, np.ndarray],
    target: str,
) -> np.ndarray:
    left, right = (station.station_id for station in base.STATIONS)
    return phase.double_difference_range_m(
        phase.range_to_station_m(positions[target], station_ecef[left]),
        phase.range_to_station_m(positions["G30"], station_ecef[left]),
        phase.range_to_station_m(positions[target], station_ecef[right]),
        phase.range_to_station_m(positions["G30"], station_ecef[right]),
    )


def compiler_manifest() -> dict[str, object]:
    result = {
        "schema": "gnss-phase-repeated-pass-compiler-manifest-v1",
        "replication_version": REPLICATION_VERSION,
        "plan_manifest_sha256": frozen.manifest_sha256(),
        "navigation": asdict(navigation_authority()),
        "grid": {
            "raw_start_gps": structural.format_gps_epoch(expected_raw_gps_epochs()[0]),
            "raw_stop_gps": structural.format_gps_epoch(expected_raw_gps_epochs()[-1]),
            "step_s": frozen.STEP_S,
            "raw_epochs": frozen.RAW_EPOCHS,
            "feature_raw_indices_inclusive": [1, 137],
            "calibration_feature_indices_inclusive": [0, 76],
            "heldout_feature_indices_inclusive": [77, 136],
        },
        "coordinate": frozen.plan()["coordinate"],
        "hypotheses": HYPOTHESES,
        "scoring": frozen.plan()["scoring"],
        "observation_boundary": {
            "product_locators_resolved": 0,
            "headers_opened": 0,
            "payload_bytes": 0,
            "values_accessed": 0,
            "network_capability": False,
            "decoder_present": False,
        },
        "forbidden": [
            "DOY220_REOPEN_OR_RESCORE",
            "DOY219_OR_DOY218_PRODUCT_DISCOVERY",
            "WINDOW_NULL_THRESHOLD_OR_NUISANCE_CHANGE",
            "FREE_TIME_PHASE_OR_SUFFIX_REFIT",
        ],
    }
    strict_json(result)
    return result


def compiler_manifest_sha256() -> str:
    return sha256(strict_json(compiler_manifest()).encode("ascii")).hexdigest()


def build_predictions(navigation_path: Path) -> dict[str, object]:
    """Compile model coordinates without accepting observation input."""
    authority = validate_navigation(navigation_path)
    records = base.parse_gps_navigation(Path(navigation_path))
    gps_epochs = expected_raw_gps_epochs()
    utc_epochs = tuple(
        epoch - timedelta(seconds=base.GPS_UTC_OFFSET_S) for epoch in gps_epochs
    )
    positions: dict[str, np.ndarray] = {}
    for satellite in MODEL_SATELLITES:
        if satellite not in records:
            raise RepeatedPassDescriptionError(f"MODEL_SATELLITE_MISSING:{satellite}")
        positions[satellite] = np.asarray(
            [
                base.broadcast_ecef(
                    base.select_ephemeris(records[satellite], epoch), epoch
                )
                for epoch in utc_epochs
            ],
            dtype=np.float64,
        )
    station_ecef = {
        station.station_id: base.station_to_ecef(station) for station in base.STATIONS
    }
    elevation_minima: dict[str, float] = {}
    for satellite in MODEL_SATELLITES:
        elevation_minima[satellite] = min(
            float(
                np.min(
                    base.elevation_deg(
                        positions[satellite],
                        station,
                        station_ecef[station.station_id],
                    )
                )
            )
            for station in base.STATIONS
        )
    curves: dict[str, list[float]] = {}
    for hypothesis, satellite in HYPOTHESES.items():
        curve = (
            np.zeros(frozen.FEATURE_EPOCHS, dtype=np.float64)
            if satellite is None
            else _range_curve(positions, station_ecef, satellite)[1:-1]
        )
        if curve.shape != (frozen.FEATURE_EPOCHS,) or not np.all(np.isfinite(curve)):
            raise RepeatedPassDescriptionError(f"MODEL_CURVE_INVALID:{hypothesis}")
        curves[hypothesis] = [float(item) for item in curve]
    orbital = np.asarray(curves["ORBITAL_G22"], dtype=np.float64)
    regression: dict[str, object] = {
        "prefix_affine_heldout_peak_to_peak_m": phase.phase_prefix_metrics(
            orbital,
            split=frozen.CALIBRATION_EPOCHS,
            step_s=frozen.STEP_S,
        )["heldout_peak_to_peak_m"],
        "wrong_orbit_heldout_peak_to_peak_m": {},
    }
    wrong = regression["wrong_orbit_heldout_peak_to_peak_m"]
    assert isinstance(wrong, dict)
    for satellite, expected in frozen.ALTERNATIVE_ORBITS.items():
        metrics = phase.phase_prefix_metrics(
            orbital - np.asarray(curves[f"WRONG_ORBIT_{satellite}"], dtype=np.float64),
            split=frozen.CALIBRATION_EPOCHS,
            step_s=frozen.STEP_S,
        )
        wrong[satellite] = metrics["heldout_peak_to_peak_m"]
        if abs(float(wrong[satellite]) - expected) > NUMERICAL_TOLERANCE_M:
            raise RepeatedPassDescriptionError(
                f"WRONG_ORBIT_REGRESSION_CHANGED:{satellite}"
            )
    if (
        abs(
            float(regression["prefix_affine_heldout_peak_to_peak_m"])
            - PREFIX_AFFINE_REGRESSION_M
        )
        > NUMERICAL_TOLERANCE_M
    ):
        raise RepeatedPassDescriptionError("PREFIX_AFFINE_REGRESSION_CHANGED")
    result = {
        "schema": "gnss-phase-repeated-pass-predictions-v1",
        "replication_version": REPLICATION_VERSION,
        "compiler_source_commit": _git_commit(),
        "compiler_source_sha256": source_sha256(),
        "compiler_manifest_sha256": compiler_manifest_sha256(),
        "compiler_dependencies": dependency_versions(),
        "plan_manifest_sha256": frozen.manifest_sha256(),
        "navigation": asdict(authority),
        "coordinate": "FOUR_LINK_IONOSPHERE_FREE_PHASE_RANGE_MODEL_M",
        "feature_epochs_gps": [
            structural.format_gps_epoch(epoch) for epoch in gps_epochs[1:-1]
        ],
        "curves_m": curves,
        "curve_set_sha256": sha256(strict_json(curves).encode("ascii")).hexdigest(),
        "minimum_elevation_deg_by_model_satellite": elevation_minima,
        "numerical_regression": regression,
        "observation_access": {
            "products_discovered": 0,
            "headers": 0,
            "payload_bytes": 0,
            "values": 0,
        },
    }
    strict_json(result)
    return result


def validate_predictions(value: Mapping[str, object]) -> dict[str, np.ndarray]:
    if value.get("schema") != "gnss-phase-repeated-pass-predictions-v1":
        raise RepeatedPassDescriptionError("PREDICTION_SCHEMA_CHANGED")
    if value.get("plan_manifest_sha256") != frozen.manifest_sha256():
        raise RepeatedPassDescriptionError("PREDICTION_PLAN_BINDING_CHANGED")
    if value.get("navigation") != asdict(navigation_authority()):
        raise RepeatedPassDescriptionError("PREDICTION_NAVIGATION_CHANGED")
    if any(value.get("observation_access", {}).values()):
        raise RepeatedPassDescriptionError("PREDICTIONS_USED_OBSERVATIONS")
    curves_value = value.get("curves_m")
    if not isinstance(curves_value, Mapping) or set(curves_value) != set(HYPOTHESES):
        raise RepeatedPassDescriptionError("PREDICTION_HYPOTHESES_CHANGED")
    if (
        value.get("curve_set_sha256")
        != sha256(strict_json(curves_value).encode("ascii")).hexdigest()
    ):
        raise RepeatedPassDescriptionError("PREDICTION_CURVE_HASH_CHANGED")
    curves = {
        str(name): np.asarray(rows, dtype=np.float64)
        for name, rows in curves_value.items()
    }
    if any(
        curve.shape != (frozen.FEATURE_EPOCHS,) or not np.all(np.isfinite(curve))
        for curve in curves.values()
    ):
        raise RepeatedPassDescriptionError("PREDICTION_CURVE_INVALID")
    return curves


def build_seal(predictions_path: Path) -> dict[str, object]:
    path = Path(predictions_path)
    value = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)),
    )
    validate_predictions(value)
    if value.get("compiler_source_sha256") != source_sha256():
        raise RepeatedPassDescriptionError("PREDICTION_COMPILER_SOURCE_CHANGED")
    if value.get("compiler_manifest_sha256") != compiler_manifest_sha256():
        raise RepeatedPassDescriptionError("PREDICTION_COMPILER_MANIFEST_CHANGED")
    if value.get("compiler_dependencies") != dependency_versions():
        raise RepeatedPassDescriptionError("PREDICTION_DEPENDENCIES_CHANGED")
    result = {
        "schema": "gnss-phase-repeated-pass-seal-v1",
        "state": "REPLICATION_PLAN_AND_PREDICTION_FROZEN",
        "source_commit": value["compiler_source_commit"],
        "source_sha256": source_sha256(),
        "compiler_manifest_sha256": compiler_manifest_sha256(),
        "dependencies": dependency_versions(),
        "plan_manifest_sha256": frozen.manifest_sha256(),
        "primary_outcome_canonical_sha256": frozen.PRIMARY_OUTCOME_SHA256,
        "predictions": {
            "name": path.name,
            "canonical_sha256": canonical_sha256(path),
            "curve_set_sha256": value["curve_set_sha256"],
        },
        "replication": frozen.plan()["roles"]["replication"],
        "sealed_reserve": frozen.plan()["roles"]["reserve"],
        "authority": {
            "replication_access_authorized_by_seal": False,
            "separate_review_required": True,
        },
        "access_at_seal": {
            "products_discovered": 0,
            "headers": 0,
            "payload_bytes": 0,
            "values": 0,
        },
    }
    strict_json(result)
    return result


def write_artifacts(navigation_path: Path, output_dir: Path) -> tuple[Path, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    predictions_path = output / PREDICTIONS_NAME
    predictions_path.write_text(
        strict_json(build_predictions(navigation_path), pretty=True) + "\n",
        encoding="utf-8",
    )
    seal_path = output / SEAL_NAME
    seal_path.write_text(
        strict_json(build_seal(predictions_path), pretty=True) + "\n",
        encoding="utf-8",
    )
    return predictions_path, seal_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--navigation", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    frozen.verify_sources(Path(__file__).resolve().parent)
    predictions_path, seal_path = write_artifacts(args.navigation, args.output_dir)
    print(
        strict_json(
            {
                "outcome": "REPLICATION_PLAN_AND_PREDICTION_FROZEN",
                "plan_manifest_sha256": frozen.manifest_sha256(),
                "predictions_sha256": canonical_sha256(predictions_path),
                "seal_sha256": canonical_sha256(seal_path),
                "observation_access": 0,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
