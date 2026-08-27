"""Observation-blind DOY223 ALGO/MDO prediction compiler and seal.

The compiler accepts only the frozen exact-hash NOAA broadcast-navigation
product.  It has no observation transport, RINEX observation decoder, or
observation-value surface.  Its only purpose is to freeze the orbital and null
curves before either prospective ALGO/MDO product is requested.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import timedelta
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
from typing import Final, Mapping

import numpy as np

from experiments.orbital_discriminability import gnss_double_difference_screen as geometry
from experiments.orbital_discriminability import gnss_independent_pair_doy223_primary_plan as plan
from experiments.orbital_discriminability import gnss_independent_pair_next_primary_screen as screen
from experiments.orbital_discriminability import gnss_phase_quotient_spike as phase
from experiments.orbital_discriminability import gnss_structural_qualification as structural


COMPILER_VERSION: Final = "g22-g30-algo-mdo-doy223-predictions-v1"
PREDICTIONS_NAME: Final = "GNSS_INDEPENDENT_PAIR_DOY223_PREDICTIONS.json"
SEAL_NAME: Final = "GNSS_INDEPENDENT_PAIR_DOY223_SEAL.json"
MODEL_SATELLITES: Final = ("G22", "G30", "G01", "G14", "G17")
HYPOTHESES: Final = {
    "ORBITAL_G22": "G22",
    "PREFIX_AFFINE": None,
    "WRONG_ORBIT_G01": "G01",
    "WRONG_ORBIT_G14": "G14",
    "WRONG_ORBIT_G17": "G17",
}
NUMERICAL_TOLERANCE_M: Final = 1.0e-6
ELEVATION_TOLERANCE_DEG: Final = 1.0e-9


class Doy223PredictionError(ValueError):
    """A frozen authority, numerical regression, or seal binding changed."""


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
    payload = Path(path).read_bytes().replace(bytes((13, 10)), bytes((10,)))
    return sha256(payload).hexdigest()


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


def _navigation_candidate() -> screen.NavigationCandidate:
    candidates = tuple(
        candidate
        for candidate in screen.NAVIGATION_CANDIDATES
        if candidate.doy == plan.PRIMARY_DOY
    )
    if len(candidates) != 1:
        raise Doy223PredictionError("FROZEN_NAVIGATION_CANDIDATE_CHANGED")
    candidate = candidates[0]
    if candidate.name != plan.NAVIGATION_NAME:
        raise Doy223PredictionError("FROZEN_NAVIGATION_NAME_CHANGED")
    return candidate


def navigation_authority() -> dict[str, object]:
    candidate = _navigation_candidate()
    return {
        **asdict(candidate),
        "compressed_bytes": plan.NAVIGATION_COMPRESSED_BYTES,
        "compressed_sha256": plan.NAVIGATION_COMPRESSED_SHA256,
        "uncompressed_name": candidate.name.removesuffix(".gz"),
        "uncompressed_bytes": plan.NAVIGATION_UNCOMPRESSED_BYTES,
        "uncompressed_sha256": plan.NAVIGATION_UNCOMPRESSED_SHA256,
        "semantics": "BROADCAST_EPHEMERIS_MODEL_NOT_RECEIVER_OBSERVATION",
    }


def _stations() -> tuple[geometry.Station, geometry.Station]:
    authorities = {
        authority.station_id: authority for authority in screen.STATIONS
    }
    try:
        stations = tuple(
            screen._station(authorities[station_id])
            for station_id in ("ALGO00CAN", "MDO100USA")
        )
    except KeyError as exc:
        raise Doy223PredictionError("FROZEN_STATION_MISSING") from exc
    if [station.measurement_root for station in stations] != [
        "ALGO00CAN_40104M002",
        "MDO100USA_40442M012",
    ]:
        raise Doy223PredictionError("FROZEN_STATION_ROOT_CHANGED")
    return stations  # type: ignore[return-value]


def expected_raw_gps_epochs() -> tuple:
    epochs = tuple(
        plan.RAW_START + timedelta(seconds=index * plan.STEP_S)
        for index in range(plan.RAW_EPOCHS)
    )
    if structural.format_gps_epoch(epochs[-1]) != (
        "2026-08-11T06:33:00.000000Z"
    ):
        raise Doy223PredictionError("PRIMARY_GRID_CHANGED")
    return epochs


def compiler_manifest() -> dict[str, object]:
    result = {
        "schema": "gnss-independent-pair-doy223-compiler-manifest-v1",
        "compiler_version": COMPILER_VERSION,
        "plan_manifest_sha256": plan.manifest_sha256(),
        "navigation": navigation_authority(),
        "station_roots": [
            station.measurement_root for station in _stations()
        ],
        "grid": {
            "raw_start_gps": structural.format_gps_epoch(
                expected_raw_gps_epochs()[0]
            ),
            "raw_stop_gps": structural.format_gps_epoch(
                expected_raw_gps_epochs()[-1]
            ),
            "step_s": plan.STEP_S,
            "raw_epochs": plan.RAW_EPOCHS,
            "feature_raw_indices_inclusive": [1, 137],
            "calibration_feature_indices_inclusive": [0, 76],
            "heldout_feature_indices_inclusive": [77, 136],
        },
        "coordinate": plan.plan()["coordinate"],
        "hypotheses": HYPOTHESES,
        "scoring": plan.plan()["scoring"],
        "navigation_input": {
            "accepted": ["EXACT_HASH_GZIP_PATH", "EXACT_HASH_GZIP_STDIN_IN_RAM"],
            "network_capability": False,
            "gzip_persistence_required": False,
        },
        "observation_boundary": {
            "locator_requests": 0,
            "descriptive_head_requests": 0,
            "headers_opened": 0,
            "payload_bytes": 0,
            "values_accessed": 0,
            "network_capability": False,
            "observation_decoder_present": False,
        },
        "forbidden": [
            "PRIMARY_LOCATOR_HEADER_PAYLOAD_OR_VALUE_ACCESS",
            "NEW_GEOMETRY_STATION_DATE_SIGNAL_OR_WINDOW_SELECTION",
            "NULL_THRESHOLD_OR_NUISANCE_CHANGE",
            "FREE_TIME_PHASE_OR_SUFFIX_REFIT",
            "FALLBACK_OR_RESERVE_SELECTION",
        ],
    }
    strict_json(result)
    return result


def compiler_manifest_sha256() -> str:
    return sha256(strict_json(compiler_manifest()).encode("ascii")).hexdigest()


def _parse_exact_navigation_gzip(
    payload: bytes,
) -> tuple[
    dict[str, tuple[geometry.GpsEphemeris, ...]], dict[str, object]
]:
    if len(payload) != plan.NAVIGATION_COMPRESSED_BYTES:
        raise Doy223PredictionError("NAVIGATION_GZIP_SIZE_CHANGED")
    if sha256(payload).hexdigest() != plan.NAVIGATION_COMPRESSED_SHA256:
        raise Doy223PredictionError("NAVIGATION_GZIP_SHA256_CHANGED")
    records, authority = screen.parse_navigation_gzip(
        _navigation_candidate(), payload
    )
    if authority != navigation_authority():
        raise Doy223PredictionError("NAVIGATION_AUTHORITY_CHANGED")
    return records, authority


def build_predictions_from_gzip(payload: bytes) -> dict[str, object]:
    records, authority = _parse_exact_navigation_gzip(payload)
    return _build_predictions(records, authority)


def build_predictions(navigation_gzip_path: Path) -> dict[str, object]:
    payload = Path(navigation_gzip_path).read_bytes()
    try:
        return build_predictions_from_gzip(payload)
    finally:
        payload = b""


def _build_predictions(
    records: Mapping[str, tuple[geometry.GpsEphemeris, ...]],
    authority: Mapping[str, object],
) -> dict[str, object]:
    missing = set(MODEL_SATELLITES) - set(records)
    if missing:
        raise Doy223PredictionError(
            f"MODEL_SATELLITE_MISSING:{','.join(sorted(missing))}"
        )
    gps_epochs = expected_raw_gps_epochs()
    utc_epochs = tuple(
        epoch - timedelta(seconds=geometry.GPS_UTC_OFFSET_S)
        for epoch in gps_epochs
    )
    positions: dict[str, np.ndarray] = {
        satellite: np.asarray(
            [
                geometry.broadcast_ecef(
                    geometry.select_ephemeris(records[satellite], epoch), epoch
                )
                for epoch in utc_epochs
            ],
            dtype=np.float64,
        )
        for satellite in MODEL_SATELLITES
    }
    stations = _stations()
    station_ecef = {
        station.station_id: geometry.station_to_ecef(station)
        for station in stations
    }

    def range_curve(target: str) -> np.ndarray:
        left, right = (station.station_id for station in stations)
        return phase.double_difference_range_m(
            phase.range_to_station_m(positions[target], station_ecef[left]),
            phase.range_to_station_m(positions["G30"], station_ecef[left]),
            phase.range_to_station_m(positions[target], station_ecef[right]),
            phase.range_to_station_m(positions["G30"], station_ecef[right]),
        )

    curves: dict[str, list[float]] = {}
    for hypothesis, satellite in HYPOTHESES.items():
        curve = (
            np.zeros(plan.FEATURE_EPOCHS, dtype=np.float64)
            if satellite is None
            else range_curve(satellite)[1:-1]
        )
        if curve.shape != (plan.FEATURE_EPOCHS,) or not np.all(
            np.isfinite(curve)
        ):
            raise Doy223PredictionError(f"MODEL_CURVE_INVALID:{hypothesis}")
        curves[hypothesis] = [float(value) for value in curve]

    orbital = np.asarray(curves["ORBITAL_G22"], dtype=np.float64)
    prefix = phase.phase_prefix_metrics(
        orbital,
        split=plan.CALIBRATION_EPOCHS,
        step_s=plan.STEP_S,
    )
    if abs(
        float(prefix["heldout_peak_to_peak_m"])
        - plan.SCREEN_PREFIX_AFFINE_SEPARATION_M
    ) > NUMERICAL_TOLERANCE_M:
        raise Doy223PredictionError("PREFIX_AFFINE_REGRESSION_CHANGED")
    wrong_metrics: dict[str, dict[str, float]] = {}
    for satellite, expected in plan.SCREEN_WRONG_ORBIT_SEPARATIONS_M.items():
        metrics = phase.phase_prefix_metrics(
            orbital
            - np.asarray(
                curves[f"WRONG_ORBIT_{satellite}"], dtype=np.float64
            ),
            split=plan.CALIBRATION_EPOCHS,
            step_s=plan.STEP_S,
        )
        if abs(
            float(metrics["heldout_peak_to_peak_m"]) - expected
        ) > NUMERICAL_TOLERANCE_M:
            raise Doy223PredictionError(
                f"WRONG_ORBIT_REGRESSION_CHANGED:{satellite}"
            )
        wrong_metrics[satellite] = {
            key: float(value) for key, value in metrics.items()
        }

    elevations = {
        satellite: {
            station.station_id: float(
                np.min(
                    geometry.elevation_deg(
                        positions[satellite],
                        station,
                        station_ecef[station.station_id],
                    )
                )
            )
            for station in stations
        }
        for satellite in MODEL_SATELLITES
    }
    minimum_elevation = min(
        value for by_station in elevations.values() for value in by_station.values()
    )
    if abs(
        minimum_elevation - plan.SCREEN_MINIMUM_MODEL_ELEVATION_DEG
    ) > ELEVATION_TOLERANCE_DEG:
        raise Doy223PredictionError("MINIMUM_ELEVATION_REGRESSION_CHANGED")

    result = {
        "schema": "gnss-independent-pair-doy223-predictions-v1",
        "compiler_version": COMPILER_VERSION,
        "compiler_source_commit": _git_commit(),
        "compiler_source_sha256": source_sha256(),
        "compiler_manifest_sha256": compiler_manifest_sha256(),
        "compiler_dependencies": dependency_versions(),
        "plan_manifest_sha256": plan.manifest_sha256(),
        "navigation": dict(authority),
        "station_roots": [
            station.measurement_root for station in stations
        ],
        "coordinate": (
            "ALGO_MINUS_MDO_FOUR_LINK_IONOSPHERE_FREE_PHASE_RANGE_MODEL_M"
        ),
        "feature_epochs_gps": [
            structural.format_gps_epoch(epoch) for epoch in gps_epochs[1:-1]
        ],
        "curves_m": curves,
        "curve_set_sha256": sha256(
            strict_json(curves).encode("ascii")
        ).hexdigest(),
        "minimum_elevation_deg_by_model_satellite_and_station": elevations,
        "minimum_model_elevation_deg": minimum_elevation,
        "numerical_regression": {
            "prefix_affine": {
                key: float(value) for key, value in prefix.items()
            },
            "wrong_orbits": wrong_metrics,
            "controlling_null": "WRONG_ORBIT_G14",
            "controlling_heldout_separation_m": (
                plan.SCREEN_CONTROLLING_SEPARATION_M
            ),
            "pairwise_decision_guard_m": plan.SCREEN_PAIRWISE_GUARD_M,
            "remaining_physical_margin_m": plan.SCREEN_REMAINING_MARGIN_M,
        },
        "observation_access": {
            "locator_requests": 0,
            "descriptive_head_requests": 0,
            "headers": 0,
            "payload_bytes": 0,
            "values": 0,
        },
    }
    strict_json(result)
    for values in positions.values():
        values.fill(0.0)
    return result


def validate_predictions(value: Mapping[str, object]) -> dict[str, np.ndarray]:
    if value.get("schema") != "gnss-independent-pair-doy223-predictions-v1":
        raise Doy223PredictionError("PREDICTION_SCHEMA_CHANGED")
    if value.get("plan_manifest_sha256") != plan.manifest_sha256():
        raise Doy223PredictionError("PREDICTION_PLAN_BINDING_CHANGED")
    if value.get("navigation") != navigation_authority():
        raise Doy223PredictionError("PREDICTION_NAVIGATION_CHANGED")
    access = value.get("observation_access", {})
    if not isinstance(access, Mapping) or any(
        int(access.get(field, -1)) != 0
        for field in (
            "locator_requests",
            "descriptive_head_requests",
            "headers",
            "payload_bytes",
            "values",
        )
    ):
        raise Doy223PredictionError("PREDICTIONS_USED_OBSERVATIONS")
    curves_value = value.get("curves_m")
    if not isinstance(curves_value, Mapping) or set(curves_value) != set(
        HYPOTHESES
    ):
        raise Doy223PredictionError("PREDICTION_HYPOTHESES_CHANGED")
    if value.get("curve_set_sha256") != sha256(
        strict_json(curves_value).encode("ascii")
    ).hexdigest():
        raise Doy223PredictionError("PREDICTION_CURVE_HASH_CHANGED")
    curves = {
        str(name): np.asarray(rows, dtype=np.float64)
        for name, rows in curves_value.items()
    }
    if any(
        curve.shape != (plan.FEATURE_EPOCHS,)
        or not np.all(np.isfinite(curve))
        for curve in curves.values()
    ):
        raise Doy223PredictionError("PREDICTION_CURVE_INVALID")
    return curves


def build_seal(predictions_path: Path) -> dict[str, object]:
    path = Path(predictions_path)
    value = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    validate_predictions(value)
    if value.get("compiler_source_sha256") != source_sha256():
        raise Doy223PredictionError("PREDICTION_COMPILER_SOURCE_CHANGED")
    if value.get("compiler_manifest_sha256") != compiler_manifest_sha256():
        raise Doy223PredictionError("PREDICTION_COMPILER_MANIFEST_CHANGED")
    if value.get("compiler_dependencies") != dependency_versions():
        raise Doy223PredictionError("PREDICTION_DEPENDENCIES_CHANGED")
    result = {
        "schema": "gnss-independent-pair-doy223-seal-v1",
        "state": "PRIMARY_PLAN_AND_PREDICTION_FROZEN",
        "source_commit": value["compiler_source_commit"],
        "source_sha256": source_sha256(),
        "compiler_manifest_sha256": compiler_manifest_sha256(),
        "dependencies": dependency_versions(),
        "plan_manifest_sha256": plan.manifest_sha256(),
        "source_authorities": {
            **plan.plan()["source_authorities"],
            "broadcast_navigation": navigation_authority(),
        },
        "predictions": {
            "name": path.name,
            "canonical_sha256": canonical_sha256(path),
            "curve_set_sha256": value["curve_set_sha256"],
        },
        "primary": plan.plan()["roles"]["primary"],
        "authority": {
            "primary_access_authorized_by_seal": False,
            "separate_review_required": True,
        },
        "access_at_seal": plan.plan()["access_at_freeze"],
        "stop": "STOP_BEFORE_ANY_PRIMARY_OBSERVATION_REQUEST_FOR_REVIEW",
    }
    strict_json(result)
    return result


def write_artifacts(
    output_dir: Path,
    *,
    navigation_gzip_path: Path | None = None,
    navigation_gzip: bytes | None = None,
) -> tuple[Path, Path]:
    if (navigation_gzip_path is None) == (navigation_gzip is None):
        raise Doy223PredictionError("EXACTLY_ONE_NAVIGATION_INPUT_REQUIRED")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    predictions = (
        build_predictions(navigation_gzip_path)
        if navigation_gzip_path is not None
        else build_predictions_from_gzip(navigation_gzip or b"")
    )
    predictions_path = output / PREDICTIONS_NAME
    predictions_path.write_text(
        strict_json(predictions, pretty=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    seal_path = output / SEAL_NAME
    seal_path.write_text(
        strict_json(build_seal(predictions_path), pretty=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return predictions_path, seal_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--navigation-gzip", type=Path)
    source.add_argument("--navigation-gzip-stdin", action="store_true")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    plan.verify_sources(root)
    payload = sys.stdin.buffer.read() if args.navigation_gzip_stdin else None
    try:
        predictions_path, seal_path = write_artifacts(
            args.output_dir,
            navigation_gzip_path=args.navigation_gzip,
            navigation_gzip=payload,
        )
    finally:
        payload = None
    print(
        strict_json(
            {
                "outcome": "PRIMARY_PLAN_AND_PREDICTION_FROZEN",
                "plan_manifest_sha256": plan.manifest_sha256(),
                "predictions_sha256": canonical_sha256(predictions_path),
                "seal_sha256": canonical_sha256(seal_path),
                "primary_observation_access": 0,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
