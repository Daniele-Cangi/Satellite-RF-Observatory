"""Observation-blind prediction seal for the prospective AMC DOY221 test.

Only the exact-hash NOAA broadcast-navigation product enters this compiler.
There is no observation transport, observation decoder, carrier-phase input,
or scoring surface.  The output freezes the orbital and null coordinates that
a later, separately authorized AMC observation may test.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
from typing import Final, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import (
    gnss_double_difference_screen as geometry,
)
from experiments.orbital_discriminability import (
    gnss_independent_pair_next_primary_screen as navigation,
)
from experiments.orbital_discriminability import (
    gnss_observer_transfer_geometry as geometry_receipt,
)
from experiments.orbital_discriminability import (
    gnss_observer_transfer_spike as transfer,
)
from experiments.orbital_discriminability import (
    gnss_phase_independent_pair_screen as station_scope,
)
from experiments.orbital_discriminability import (
    gnss_amc_observer_primary_plan as plan,
)

COMPILER_VERSION: Final = "amc-g22-g30-doy221-prediction-seal-v1"
PREDICTIONS_NAME: Final = "AMC_OBSERVER_PRIMARY_PREDICTIONS.json"
SEAL_NAME: Final = "AMC_OBSERVER_PRIMARY_PREDICTION_SEAL.json"
PLAN_RECEIPT_NAME: Final = plan.RECEIPT_NAME
PLAN_RECEIPT_SHA256: Final = (
    "615cce5046e218f583483175c8774357680d80450d5b97928685f728fb2fb89b"
)
FROZEN_PLAN_MANIFEST_SHA256: Final = (
    "0a3c1e3768566da6242d6aaffd6c751a23d6bf167c7f54d0498fe75f365609b0"
)

MODEL_SATELLITES: Final = (plan.TARGET, plan.REFERENCE, *plan.WRONG_ORBITS)
HYPOTHESES: Final = {
    "ORBITAL_G22": "G22",
    "FROZEN_AFFINE_NULL": None,
    "WRONG_ORBIT_G01": "G01",
    "WRONG_ORBIT_G14": "G14",
    "WRONG_ORBIT_G17": "G17",
}
RAW_START_GPS: Final = datetime(2026, 8, 9, 5, 41, 30, tzinfo=timezone.utc)
RAW_STOP_GPS: Final = datetime(2026, 8, 9, 6, 50, 30, tzinfo=timezone.utc)
TIMING_OFFSETS_S: Final = (
    -plan.MAXIMUM_EVENT_TIME_ERROR_S,
    plan.MAXIMUM_EVENT_TIME_ERROR_S,
)
EXPECTED_NULL_SEPARATIONS_M: Final = {
    "FROZEN_AFFINE_NULL": 162_247.192926376,
    "WRONG_ORBIT_G01": 498_274.704483632,
    "WRONG_ORBIT_G14": 220_149.1083578728,
    "WRONG_ORBIT_G17": 162_722.8794388622,
}
EXPECTED_TIMING_BOUND_M: Final = 1_138.6249408759177
EXPECTED_MINIMUM_SHIFTED_ELEVATION_DEG: Final = 25.72562823684935
NUMERICAL_TOLERANCE_M: Final = 1.0e-6
ELEVATION_TOLERANCE_DEG: Final = 1.0e-9


class AmcPredictionError(ValueError):
    """A frozen authority, prediction invariant, or access boundary changed."""


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
        "numpy": importlib.metadata.version("numpy"),
        "python": platform.python_version(),
    }


def _navigation_candidate() -> navigation.NavigationCandidate:
    candidates = tuple(
        candidate
        for candidate in geometry_receipt.NAVIGATION_CANDIDATES
        if candidate.doy == 221
    )
    if len(candidates) != 1:
        raise AmcPredictionError("FROZEN_NAVIGATION_CANDIDATE_CHANGED")
    candidate = candidates[0]
    if candidate.name != "brdc2210.26n.gz":
        raise AmcPredictionError("FROZEN_NAVIGATION_NAME_CHANGED")
    return candidate


def navigation_authority() -> dict[str, object]:
    candidate = _navigation_candidate()
    frozen = geometry_receipt.EXPECTED_NAVIGATION[221]
    return {
        **asdict(candidate),
        **frozen,
        "uncompressed_name": candidate.name.removesuffix(".gz"),
        "semantics": "BROADCAST_EPHEMERIS_MODEL_NOT_RECEIVER_OBSERVATION",
    }


def _observer_authority() -> station_scope.CandidateStation:
    candidates = tuple(
        candidate
        for candidate in station_scope.CANDIDATES
        if candidate.station_id == plan.STATION
    )
    if len(candidates) != 1:
        raise AmcPredictionError("FROZEN_AMC_AUTHORITY_CHANGED")
    candidate = candidates[0]
    exact = (
        candidate.latitude_deg,
        candidate.longitude_deg,
        candidate.height_m,
        candidate.domes,
    )
    expected = (
        plan.STATION_LATITUDE_DEG,
        plan.STATION_LONGITUDE_DEG,
        1911.3941,
        "40472S005",
    )
    if exact != expected:
        raise AmcPredictionError("FROZEN_AMC_COORDINATES_CHANGED")
    return candidate


def _station() -> geometry.Station:
    candidate = _observer_authority()
    return geometry.Station(
        candidate.station_id,
        candidate.latitude_deg,
        candidate.longitude_deg,
        candidate.height_m,
        "UNKNOWN_NOT_REQUIRED_FOR_ORBIT_ONLY_PREDICTION",
        candidate.receiver,
        candidate.antenna,
        "ROBOT",
        f"{candidate.station_id}_{candidate.domes}",
        candidate.station_page_url,
    )


def expected_raw_gps_epochs() -> tuple[datetime, ...]:
    epochs = tuple(
        RAW_START_GPS + timedelta(seconds=index * plan.STEP_S)
        for index in range(plan.RAW_EPOCHS)
    )
    if epochs[-1] != RAW_STOP_GPS:
        raise AmcPredictionError("PRIMARY_GRID_CHANGED")
    return epochs


def _format_gps(epoch: datetime) -> str:
    return epoch.isoformat(timespec="seconds").replace("+00:00", " GPS")


def _read_plan_receipt(root: Path) -> dict[str, object]:
    receipt_path = Path(root) / PLAN_RECEIPT_NAME
    if (
        not receipt_path.is_file()
        or canonical_sha256(receipt_path) != PLAN_RECEIPT_SHA256
    ):
        raise AmcPredictionError("FROZEN_PLAN_RECEIPT_CHANGED")
    value = json.loads(
        receipt_path.read_text(encoding="utf-8"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    if not isinstance(value, dict):
        raise AmcPredictionError("FROZEN_PLAN_RECEIPT_NOT_OBJECT")
    if value.get("outcome") != plan.OUTCOME:
        raise AmcPredictionError("FROZEN_PLAN_OUTCOME_CHANGED")
    if value.get("manifest_sha256") != FROZEN_PLAN_MANIFEST_SHA256:
        raise AmcPredictionError("FROZEN_PLAN_MANIFEST_CHANGED")
    if value.get("next_authority") != "OFFLINE_PREDICTION_SEAL_REVIEW_ONLY":
        raise AmcPredictionError("PREDICTION_SEAL_NOT_AUTHORIZED")
    if any(value.get("primary_access", {}).values()):
        raise AmcPredictionError("PRIMARY_ALREADY_OPENED")
    if value.get("orbital_scores_produced") != 0:
        raise AmcPredictionError("PLAN_ALREADY_SCORED_OBSERVATION")
    return value


def verify_plan(root: Path) -> dict[str, object]:
    plan.validate_parents(root)
    value = _read_plan_receipt(root)
    if plan.manifest_sha256(root) != FROZEN_PLAN_MANIFEST_SHA256:
        raise AmcPredictionError("LIVE_PLAN_MANIFEST_CHANGED")
    return {
        "name": PLAN_RECEIPT_NAME,
        "canonical_sha256": PLAN_RECEIPT_SHA256,
        "outcome": value["outcome"],
        "manifest_sha256": value["manifest_sha256"],
        "role": "FROZEN_PROSPECTIVE_PLAN_NO_OBSERVATION_REOPENED",
    }


def compiler_manifest(root: Path) -> dict[str, object]:
    verify_plan(root)
    result = {
        "schema": "amc-observer-prediction-compiler-manifest-v1",
        "compiler_version": COMPILER_VERSION,
        "plan_manifest_sha256": FROZEN_PLAN_MANIFEST_SHA256,
        "navigation": navigation_authority(),
        "observer_root": _station().measurement_root,
        "grid": {
            "time_system": "GPS",
            "raw_start_gps": _format_gps(expected_raw_gps_epochs()[0]),
            "raw_stop_gps": _format_gps(expected_raw_gps_epochs()[-1]),
            "step_s": plan.STEP_S,
            "raw_epochs": plan.RAW_EPOCHS,
            "anchor_index": plan.ANCHOR_INDEX,
            "witness_prefix_raw_indices_inclusive": [0, 78],
            "heldout_raw_indices_inclusive": [79, 138],
        },
        "coordinate": plan.plan(root)["coordinate"],
        "hypotheses": HYPOTHESES,
        "timing_envelope": {
            "offsets_s": list(TIMING_OFFSETS_S),
            "direct_trajectory_not_local_slope": True,
            "applied_to_target_and_reference_together": True,
        },
        "scoring": plan.plan(root)["scoring"],
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
            "AMC_DOY221_LOCATOR_HEADER_PAYLOAD_OR_VALUE_ACCESS",
            "STATION_DATE_SIGNAL_WINDOW_OR_PARTITION_CHANGE",
            "NULL_THRESHOLD_NUISANCE_OR_ANCHOR_CHANGE",
            "FREE_CONSTANT_RATE_TIME_PHASE_OR_SUFFIX_REFIT",
            "OBSERVATION_SCORING",
        ],
    }
    strict_json(result)
    return result


def compiler_manifest_sha256(root: Path) -> str:
    return sha256(strict_json(compiler_manifest(root)).encode("ascii")).hexdigest()


def _parse_exact_navigation_gzip(
    payload: bytes,
) -> tuple[dict[str, tuple[geometry.GpsEphemeris, ...]], dict[str, object]]:
    expected = navigation_authority()
    if len(payload) != expected["compressed_bytes"]:
        raise AmcPredictionError("NAVIGATION_GZIP_SIZE_CHANGED")
    if sha256(payload).hexdigest() != expected["compressed_sha256"]:
        raise AmcPredictionError("NAVIGATION_GZIP_SHA256_CHANGED")
    records, authority = navigation.parse_navigation_gzip(
        _navigation_candidate(), payload
    )
    if authority != expected:
        raise AmcPredictionError("NAVIGATION_AUTHORITY_CHANGED")
    return records, authority


def _positions(
    records: Mapping[str, tuple[geometry.GpsEphemeris, ...]],
    satellite: str,
    gps_epochs: Sequence[datetime],
    offset_s: float = 0.0,
) -> np.ndarray:
    utc_epochs = tuple(
        epoch
        - timedelta(seconds=geometry.GPS_UTC_OFFSET_S)
        + timedelta(seconds=offset_s)
        for epoch in gps_epochs
    )
    return np.asarray(
        [
            geometry.broadcast_ecef(
                geometry.select_ephemeris(records[satellite], epoch), epoch
            )
            for epoch in utc_epochs
        ],
        dtype=np.float64,
    )


def _metrics(left: Sequence[float], right: Sequence[float]) -> dict[str, float]:
    return transfer.separation_metrics(
        left,
        right,
        confirmation_start=plan.HELDOUT_START_INDEX,
    )


def _build_predictions(
    records: Mapping[str, tuple[geometry.GpsEphemeris, ...]],
    authority: Mapping[str, object],
    root: Path,
) -> dict[str, object]:
    missing = set(MODEL_SATELLITES) - set(records)
    if missing:
        raise AmcPredictionError(f"MODEL_SATELLITE_MISSING:{','.join(sorted(missing))}")
    gps_epochs = expected_raw_gps_epochs()
    observer = _station()
    station_ecef = geometry.station_to_ecef(observer)
    positions = {
        (satellite, offset): _positions(records, satellite, gps_epochs, offset)
        for satellite in MODEL_SATELLITES
        for offset in (0.0, *TIMING_OFFSETS_S)
    }

    def coordinate(target: str, offset_s: float = 0.0) -> np.ndarray:
        target_range = np.linalg.norm(
            positions[(target, offset_s)] - station_ecef, axis=1
        )
        reference_range = np.linalg.norm(
            positions[(plan.REFERENCE, offset_s)] - station_ecef, axis=1
        )
        return transfer.anchored_coordinate(target_range - reference_range)

    orbital_coordinates = {
        satellite: coordinate(satellite)
        for satellite in (plan.TARGET, *plan.WRONG_ORBITS)
    }
    elapsed_s = np.arange(plan.RAW_EPOCHS, dtype=np.float64) * plan.STEP_S
    curves = {
        "ORBITAL_G22": orbital_coordinates[plan.TARGET],
        "FROZEN_AFFINE_NULL": plan.FROZEN_AFFINE_RATE_M_S * elapsed_s,
        **{
            f"WRONG_ORBIT_{satellite}": orbital_coordinates[satellite]
            for satellite in plan.WRONG_ORBITS
        },
    }
    if set(curves) != set(HYPOTHESES):
        raise AmcPredictionError("HYPOTHESIS_SET_CHANGED")
    if any(
        curve.shape != (plan.RAW_EPOCHS,) or not np.all(np.isfinite(curve))
        for curve in curves.values()
    ):
        raise AmcPredictionError("MODEL_CURVE_INVALID")

    null_regressions = {
        name: _metrics(curves["ORBITAL_G22"], curve)
        for name, curve in curves.items()
        if name != "ORBITAL_G22"
    }
    for name, expected in EXPECTED_NULL_SEPARATIONS_M.items():
        actual = float(null_regressions[name]["heldout_peak_to_peak_m"])
        if abs(actual - expected) > NUMERICAL_TOLERANCE_M:
            raise AmcPredictionError(f"NULL_REGRESSION_CHANGED:{name}")

    timing_curves: dict[str, list[float]] = {}
    timing_metrics: dict[str, dict[str, float | str]] = {}
    for satellite in (plan.TARGET, *plan.WRONG_ORBITS):
        nominal = orbital_coordinates[satellite]
        for offset in TIMING_OFFSETS_S:
            name = f"{satellite}_{offset:+.1f}s"
            shifted = coordinate(satellite, offset)
            metrics = _metrics(nominal, shifted)
            timing_curves[name] = [float(value) for value in shifted]
            timing_metrics[name] = {
                **metrics,
                "model_satellite": satellite,
                "offset_s": float(offset),
            }
    controlling_timing_name, controlling_timing = max(
        timing_metrics.items(),
        key=lambda item: (float(item[1]["heldout_peak_to_peak_m"]), item[0]),
    )
    if (
        abs(
            float(controlling_timing["heldout_peak_to_peak_m"])
            - EXPECTED_TIMING_BOUND_M
        )
        > NUMERICAL_TOLERANCE_M
    ):
        raise AmcPredictionError("TIMING_ENVELOPE_REGRESSION_CHANGED")

    elevations = {
        f"{satellite}_{offset:+.1f}s": [
            float(value)
            for value in geometry.elevation_deg(
                positions[(satellite, offset)], observer, station_ecef
            )
        ]
        for satellite in MODEL_SATELLITES
        for offset in (0.0, *TIMING_OFFSETS_S)
    }
    minimum_shifted_elevation = min(min(values) for values in elevations.values())
    if (
        abs(minimum_shifted_elevation - EXPECTED_MINIMUM_SHIFTED_ELEVATION_DEG)
        > ELEVATION_TOLERANCE_DEG
    ):
        raise AmcPredictionError("VISIBILITY_REGRESSION_CHANGED")
    if minimum_shifted_elevation < geometry.MINIMUM_ELEVATION_DEG:
        raise AmcPredictionError("JOINT_VISIBILITY_NOT_COMPLETE")

    serial_curves = {
        name: [float(value) for value in curve] for name, curve in curves.items()
    }
    plan_value = plan.plan(root)
    result = {
        "schema": "amc-observer-primary-predictions-v1",
        "compiler_version": COMPILER_VERSION,
        "compiler_source_commit": _git_commit(),
        "compiler_source_sha256": source_sha256(),
        "compiler_manifest_sha256": compiler_manifest_sha256(root),
        "compiler_dependencies": dependency_versions(),
        "plan_manifest_sha256": FROZEN_PLAN_MANIFEST_SHA256,
        "navigation": dict(authority),
        "observer_root": observer.measurement_root,
        "coordinate": "ANCHORED_AMC_G22_MINUS_AMC_G30_PHASE_RANGE_MODEL_M",
        "raw_epochs_gps": [_format_gps(epoch) for epoch in gps_epochs],
        "curves_m": serial_curves,
        "curve_set_sha256": sha256(
            strict_json(serial_curves).encode("ascii")
        ).hexdigest(),
        "direct_timing_envelope_curves_m": timing_curves,
        "timing_curve_set_sha256": sha256(
            strict_json(timing_curves).encode("ascii")
        ).hexdigest(),
        "minimum_elevation_deg_by_model_and_offset": {
            name: min(values) for name, values in elevations.items()
        },
        "minimum_time_shifted_model_elevation_deg": minimum_shifted_elevation,
        "numerical_regression": {
            "nulls": null_regressions,
            "controlling_null": "FROZEN_AFFINE_NULL",
            "controlling_heldout_separation_m": (plan.FROZEN_CONTROLLING_SEPARATION_M),
            "timing": timing_metrics,
            "controlling_timing_curve": controlling_timing_name,
            "direct_timing_envelope_m": EXPECTED_TIMING_BOUND_M,
            "one_model_physical_envelope_m": plan.REVISED_ONE_MODEL_ENVELOPE_M,
            "pairwise_decision_guard_m": plan.REVISED_PAIRWISE_GUARD_M,
            "remaining_physical_margin_m": plan.REVISED_REMAINING_MARGIN_M,
        },
        "physical_envelope": plan_value["physical_envelope"],
        "observation_access": {
            "locator_requests": 0,
            "descriptive_head_requests": 0,
            "headers": 0,
            "payload_bytes": 0,
            "values": 0,
        },
        "orbital_scores_produced": 0,
    }
    strict_json(result)
    for values in positions.values():
        values.fill(0.0)
    return result


def build_predictions_from_gzip(payload: bytes, root: Path) -> dict[str, object]:
    records, authority = _parse_exact_navigation_gzip(payload)
    return _build_predictions(records, authority, Path(root))


def build_predictions(navigation_gzip_path: Path, root: Path) -> dict[str, object]:
    payload = Path(navigation_gzip_path).read_bytes()
    try:
        return build_predictions_from_gzip(payload, root)
    finally:
        payload = b""


def validate_predictions(
    value: Mapping[str, object], root: Path
) -> dict[str, np.ndarray]:
    if value.get("schema") != "amc-observer-primary-predictions-v1":
        raise AmcPredictionError("PREDICTION_SCHEMA_CHANGED")
    if value.get("plan_manifest_sha256") != FROZEN_PLAN_MANIFEST_SHA256:
        raise AmcPredictionError("PREDICTION_PLAN_BINDING_CHANGED")
    if value.get("navigation") != navigation_authority():
        raise AmcPredictionError("PREDICTION_NAVIGATION_CHANGED")
    if value.get("compiler_manifest_sha256") != compiler_manifest_sha256(root):
        raise AmcPredictionError("PREDICTION_COMPILER_MANIFEST_CHANGED")
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
        raise AmcPredictionError("PREDICTIONS_USED_OBSERVATIONS")
    if value.get("orbital_scores_produced") != 0:
        raise AmcPredictionError("PREDICTIONS_SCORED_OBSERVATION")
    curves_value = value.get("curves_m")
    if not isinstance(curves_value, Mapping) or set(curves_value) != set(HYPOTHESES):
        raise AmcPredictionError("PREDICTION_HYPOTHESES_CHANGED")
    if (
        value.get("curve_set_sha256")
        != sha256(strict_json(curves_value).encode("ascii")).hexdigest()
    ):
        raise AmcPredictionError("PREDICTION_CURVE_HASH_CHANGED")
    curves = {
        str(name): np.asarray(rows, dtype=np.float64)
        for name, rows in curves_value.items()
    }
    if any(
        curve.shape != (plan.RAW_EPOCHS,) or not np.all(np.isfinite(curve))
        for curve in curves.values()
    ):
        raise AmcPredictionError("PREDICTION_CURVE_INVALID")
    timing = value.get("direct_timing_envelope_curves_m")
    if not isinstance(timing, Mapping) or len(timing) != 8:
        raise AmcPredictionError("PREDICTION_TIMING_CURVES_CHANGED")
    if (
        value.get("timing_curve_set_sha256")
        != sha256(strict_json(timing).encode("ascii")).hexdigest()
    ):
        raise AmcPredictionError("PREDICTION_TIMING_HASH_CHANGED")
    return curves


def build_seal(predictions_path: Path, root: Path) -> dict[str, object]:
    path = Path(predictions_path)
    value = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    validate_predictions(value, root)
    if value.get("compiler_source_sha256") != source_sha256():
        raise AmcPredictionError("PREDICTION_COMPILER_SOURCE_CHANGED")
    if value.get("compiler_dependencies") != dependency_versions():
        raise AmcPredictionError("PREDICTION_DEPENDENCIES_CHANGED")
    result = {
        "schema": "amc-observer-primary-prediction-seal-v1",
        "state": "AMC_OBSERVER_PRIMARY_PREDICTION_FROZEN",
        "source_commit": value["compiler_source_commit"],
        "source_sha256": source_sha256(),
        "compiler_manifest_sha256": compiler_manifest_sha256(root),
        "dependencies": dependency_versions(),
        "plan": verify_plan(root),
        "navigation": navigation_authority(),
        "predictions": {
            "name": path.name,
            "canonical_sha256": canonical_sha256(path),
            "curve_set_sha256": value["curve_set_sha256"],
            "timing_curve_set_sha256": value["timing_curve_set_sha256"],
        },
        "primary": {
            "station": plan.STATION,
            "logical_product": plan.PRIMARY_PRODUCT,
            "access": "SEALED_UNAUTHORIZED",
            "headers_opened": 0,
            "payload_bytes": 0,
            "observation_values": 0,
        },
        "authority": {
            "primary_access_authorized_by_seal": False,
            "executor_authorized_by_seal": False,
            "separate_review_required": True,
        },
        "orbital_scores_produced": 0,
        "stop": "STOP_BEFORE_EXECUTOR_OR_PRIMARY_OBSERVATION_ACCESS_FOR_REVIEW",
    }
    strict_json(result)
    return result


def write_artifacts(
    output_dir: Path,
    root: Path,
    *,
    navigation_gzip_path: Path | None = None,
    navigation_gzip: bytes | None = None,
) -> tuple[Path, Path]:
    if (navigation_gzip_path is None) == (navigation_gzip is None):
        raise AmcPredictionError("EXACTLY_ONE_NAVIGATION_INPUT_REQUIRED")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    predictions = (
        build_predictions(navigation_gzip_path, root)
        if navigation_gzip_path is not None
        else build_predictions_from_gzip(navigation_gzip or b"", root)
    )
    predictions_path = output / PREDICTIONS_NAME
    predictions_path.write_text(
        strict_json(predictions, pretty=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    seal_path = output / SEAL_NAME
    seal_path.write_text(
        strict_json(build_seal(predictions_path, root), pretty=True) + "\n",
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
    payload = sys.stdin.buffer.read() if args.navigation_gzip_stdin else None
    try:
        predictions_path, seal_path = write_artifacts(
            args.output_dir,
            root,
            navigation_gzip_path=args.navigation_gzip,
            navigation_gzip=payload,
        )
    finally:
        payload = None
    print(
        strict_json(
            {
                "outcome": "AMC_OBSERVER_PRIMARY_PREDICTION_FROZEN",
                "predictions_sha256": canonical_sha256(predictions_path),
                "seal_sha256": canonical_sha256(seal_path),
                "primary_observation_access": 0,
                "orbital_scores_produced": 0,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
