"""Compile the frozen orbit family into one identity-opaque prediction bundle.

This privileged compiler may read the preaccess mapping and the exact-hash
broadcast-navigation product.  Its output contains only opaque identifiers,
same-grid model arrays and the already frozen scoring constants.  It has no
observation transport, observation decoder or scoring surface.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
from typing import Final, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import (
    gnss_blind_orbit_assignment_plan as frozen_plan,
)
from experiments.orbital_discriminability import (
    gnss_blind_orbit_assignment_screen as screen,
)
from experiments.orbital_discriminability import (
    gnss_double_difference_screen as geometry,
)
from experiments.orbital_discriminability import (
    gnss_independent_pair_next_primary_screen as navigation,
)


COMPILER_VERSION: Final = "gnss-blind-orbit-opaque-predictions-v1"
BUNDLE_NAME: Final = "GNSS_BLIND_ORBIT_ASSIGNMENT_OPAQUE_PREDICTIONS.json"
PLAN_RECEIPT_NAME: Final = frozen_plan.RECEIPT_NAME
PLAN_RECEIPT_SHA256: Final = (
    "b35ccbee73762f7d9a8957f4d72c34ae684447a24fab055712708e064fbf3d9f"
)
PLAN_MANIFEST_SHA256: Final = (
    "f557d09596b1a11dad976aee61bc53d7271eeab1555ac45652404aa41e933e3c"
)
SCREEN_RECEIPT_NAME: Final = frozen_plan.SCREEN_NAME
SCREEN_RECEIPT_SHA256: Final = frozen_plan.SCREEN_SHA256
MAPPING_NAME: Final = frozen_plan.MAPPING_NAME
MAPPING_SHA256: Final = frozen_plan.MAPPING_SHA256

NAVIGATION_NAME: Final = "brdc2260.26n.gz"
NAVIGATION_COMPRESSED_BYTES: Final = 71_489
NAVIGATION_COMPRESSED_SHA256: Final = (
    "d2b2006769aac07d40497c547edef37c1cf1a32780981dffab971c610ae5b0b9"
)
NAVIGATION_UNCOMPRESSED_BYTES: Final = 297_923
NAVIGATION_UNCOMPRESSED_SHA256: Final = (
    "4042f7a4138aa16acd8b2700d88ccca799f7b4c6e5ffa9f47b79ae371f05d665"
)

RAW_EPOCHS: Final = frozen_plan.RAW_EPOCHS
PREFIX_EPOCHS: Final = frozen_plan.PREFIX_EPOCHS
HELDOUT_EPOCHS: Final = frozen_plan.HELDOUT_EPOCHS
STEP_S: Final = frozen_plan.STEP_S
START_INDEX: Final = 749
TIMING_OFFSETS_S: Final = (-15.0, 15.0)
NUMERICAL_TOLERANCE_M: Final = 1.0e-6
ELEVATION_TOLERANCE_DEG: Final = 1.0e-9


class BlindOrbitPredictionError(ValueError):
    """A frozen authority, prediction or blindness invariant changed."""


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
    payload = Path(path).read_bytes().replace(b"\r\n", b"\n")
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


def _read_strict_object(path: Path) -> dict[str, object]:
    value = json.loads(
        Path(path).read_text(encoding="utf-8"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    if not isinstance(value, dict):
        raise BlindOrbitPredictionError(f"NOT_JSON_OBJECT:{path.name}")
    return value


def _exact_parent(root: Path, name: str, digest: str) -> Path:
    path = Path(root) / name
    if not path.is_file() or canonical_sha256(path) != digest:
        raise BlindOrbitPredictionError(f"FROZEN_PARENT_CHANGED:{name}")
    return path


def validate_authority(root: Path) -> dict[str, object]:
    root = Path(root)
    plan_path = _exact_parent(root, PLAN_RECEIPT_NAME, PLAN_RECEIPT_SHA256)
    screen_path = _exact_parent(
        root, SCREEN_RECEIPT_NAME, SCREEN_RECEIPT_SHA256
    )
    mapping_path = _exact_parent(root, MAPPING_NAME, MAPPING_SHA256)
    plan_value = _read_strict_object(plan_path)
    screen_value = _read_strict_object(screen_path)
    mapping_value = _read_strict_object(mapping_path)

    if plan_value.get("outcome") != "BLIND_ORBIT_ASSIGNMENT_PLAN_FROZEN":
        raise BlindOrbitPredictionError("PLAN_OUTCOME_CHANGED")
    if plan_value.get("plan_manifest_sha256") != PLAN_MANIFEST_SHA256:
        raise BlindOrbitPredictionError("PLAN_MANIFEST_CHANGED")
    if any(plan_value.get("access_boundary", {}).values()):
        raise BlindOrbitPredictionError("PLAN_ACCESS_BOUNDARY_CHANGED")
    if screen_value.get("outcome") != "BLIND_ASSIGNMENT_GEOMETRY_SHORTLISTED":
        raise BlindOrbitPredictionError("SCREEN_OUTCOME_CHANGED")
    selected = screen_value.get("selected")
    if not isinstance(selected, Mapping) or selected.get("start_index") != START_INDEX:
        raise BlindOrbitPredictionError("SCREEN_WINDOW_CHANGED")
    if selected.get("candidate_family") != list(frozen_plan.CANDIDATE_FAMILY):
        raise BlindOrbitPredictionError("SCREEN_FAMILY_CHANGED")
    if mapping_value.get("created_before_primary_access") is not True:
        raise BlindOrbitPredictionError("MAPPING_NOT_PREACCESS")
    if mapping_value.get("blindness_semantics", {}).get(
        "mapping_may_enter_scorer_process"
    ) is not False:
        raise BlindOrbitPredictionError("MAPPING_SCORER_BOUNDARY_CHANGED")
    return {
        "plan_receipt_sha256": PLAN_RECEIPT_SHA256,
        "plan_manifest_sha256": PLAN_MANIFEST_SHA256,
        "screen_receipt_sha256": SCREEN_RECEIPT_SHA256,
        "mapping_sha256": MAPPING_SHA256,
        "primary_access": dict(plan_value["access_boundary"]),
    }


def _navigation_candidate() -> navigation.NavigationCandidate:
    candidates = tuple(
        candidate
        for candidate in screen.NAVIGATION_CANDIDATES
        if candidate.doy == 226
    )
    if len(candidates) != 1 or candidates[0].name != NAVIGATION_NAME:
        raise BlindOrbitPredictionError("NAVIGATION_CANDIDATE_CHANGED")
    return candidates[0]


def navigation_authority(root: Path) -> dict[str, object]:
    screen_value = _read_strict_object(
        _exact_parent(root, SCREEN_RECEIPT_NAME, SCREEN_RECEIPT_SHA256)
    )
    rows = screen_value.get("navigation")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise BlindOrbitPredictionError("NAVIGATION_AUTHORITY_MISSING")
    matches = [row for row in rows if row.get("doy") == 226]
    if len(matches) != 1:
        raise BlindOrbitPredictionError("NAVIGATION_AUTHORITY_AMBIGUOUS")
    authority = dict(matches[0])
    exact = {
        "name": NAVIGATION_NAME,
        "compressed_bytes": NAVIGATION_COMPRESSED_BYTES,
        "compressed_sha256": NAVIGATION_COMPRESSED_SHA256,
        "uncompressed_bytes": NAVIGATION_UNCOMPRESSED_BYTES,
        "uncompressed_sha256": NAVIGATION_UNCOMPRESSED_SHA256,
        "semantics": "BROADCAST_EPHEMERIS_MODEL_NOT_RECEIVER_OBSERVATION",
    }
    if any(authority.get(key) != value for key, value in exact.items()):
        raise BlindOrbitPredictionError("NAVIGATION_AUTHORITY_CHANGED")
    return authority


def compiler_manifest(root: Path) -> dict[str, object]:
    authority = validate_authority(root)
    result = {
        "schema": "gnss-blind-orbit-prediction-compiler-manifest-v1",
        "compiler_version": COMPILER_VERSION,
        "authority": authority,
        "navigation": navigation_authority(root),
        "grid": {
            "time_system": "GPS",
            "raw_start": frozen_plan.RAW_START_GPS,
            "raw_stop": frozen_plan.RAW_STOP_GPS,
            "raw_epochs": RAW_EPOCHS,
            "step_s": STEP_S,
            "prefix_epochs": PREFIX_EPOCHS,
            "heldout_epochs": HELDOUT_EPOCHS,
            "anchor_index": 0,
        },
        "output": {
            "opaque_hypotheses": 6,
            "named_hypotheses": 0,
            "mapping_rows": 0,
            "observer_or_product_metadata": 0,
        },
        "observation_boundary": {
            "network_capability": False,
            "observation_transport": False,
            "observation_decoder": False,
            "primary_locators_queried": 0,
            "primary_headers_opened": 0,
            "primary_payload_bytes": 0,
            "primary_values": 0,
            "scores": 0,
        },
        "stop": "WRITE_OPAQUE_PREDICTIONS_ONLY_NO_SCORING_OR_PRIMARY_ACCESS",
    }
    strict_json(result)
    return result


def compiler_manifest_sha256(root: Path) -> str:
    payload = strict_json(compiler_manifest(root)).encode("ascii")
    return sha256(payload).hexdigest()


def _parse_navigation(
    payload: bytes, root: Path
) -> tuple[dict[str, tuple[geometry.GpsEphemeris, ...]], dict[str, object]]:
    if len(payload) != NAVIGATION_COMPRESSED_BYTES:
        raise BlindOrbitPredictionError("NAVIGATION_GZIP_SIZE_CHANGED")
    if sha256(payload).hexdigest() != NAVIGATION_COMPRESSED_SHA256:
        raise BlindOrbitPredictionError("NAVIGATION_GZIP_SHA256_CHANGED")
    records, authority = navigation.parse_navigation_gzip(
        _navigation_candidate(), payload
    )
    if authority != navigation_authority(root):
        raise BlindOrbitPredictionError("NAVIGATION_DECODED_AUTHORITY_CHANGED")
    return records, authority


def _window_epochs() -> tuple[datetime, ...]:
    day = screen.gps_day_grid(_navigation_candidate())
    epochs = day[START_INDEX : START_INDEX + RAW_EPOCHS]
    if len(epochs) != RAW_EPOCHS:
        raise BlindOrbitPredictionError("PREDICTION_GRID_LENGTH_CHANGED")
    if geometry.format_gps(epochs[0]) != frozen_plan.RAW_START_GPS:
        raise BlindOrbitPredictionError("PREDICTION_GRID_START_CHANGED")
    if geometry.format_gps(epochs[-1]) != frozen_plan.RAW_STOP_GPS:
        raise BlindOrbitPredictionError("PREDICTION_GRID_STOP_CHANGED")
    return epochs


def _anchored_range_coordinate(
    records: Mapping[str, tuple[geometry.GpsEphemeris, ...]],
    satellite: str,
    epochs: Sequence[datetime],
    station_ecef: np.ndarray,
    offset_s: float = 0.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    target_positions = screen._position_series(
        records, satellite, epochs, offset_s
    )
    reference_positions = screen._position_series(
        records, frozen_plan.REFERENCE, epochs, offset_s
    )
    target_range = np.linalg.norm(target_positions - station_ecef, axis=1)
    reference_range = np.linalg.norm(reference_positions - station_ecef, axis=1)
    coordinate = target_range - reference_range
    coordinate = coordinate - coordinate[0]
    return coordinate, target_positions, reference_positions


def _opaque_mapping(root: Path) -> dict[str, str]:
    value = _read_strict_object(_exact_parent(root, MAPPING_NAME, MAPPING_SHA256))
    rows = value.get("mapping")
    if not isinstance(rows, list) or len(rows) != 6:
        raise BlindOrbitPredictionError("MAPPING_ROWS_CHANGED")
    result = {str(row["model"]): str(row["opaque_id"]) for row in rows}
    if len(result) != 6 or len(set(result.values())) != 6:
        raise BlindOrbitPredictionError("MAPPING_NOT_BIJECTIVE")
    return result


def _model_label(satellite: str) -> str:
    return f"{satellite}_RELATIVE_TO_{frozen_plan.REFERENCE}"


def _validate_regressions(
    named_curves: Mapping[str, np.ndarray], root: Path
) -> dict[str, object]:
    screen_value = _read_strict_object(
        _exact_parent(root, SCREEN_RECEIPT_NAME, SCREEN_RECEIPT_SHA256)
    )
    selected = screen_value["selected"]
    target = named_curves[_model_label(frozen_plan.TARGET)]
    expected = {
        str(row["satellite"]): float(row["heldout_peak_to_peak_m"])
        for row in selected["nearest_four_alternatives"]
    }
    actual: dict[str, float] = {}
    for satellite, expected_separation in expected.items():
        metrics = screen.prefix_affine_separation(
            target - named_curves[_model_label(satellite)]
        )
        separation = float(metrics["heldout_peak_to_peak_m"])
        if abs(separation - expected_separation) > NUMERICAL_TOLERANCE_M:
            raise BlindOrbitPredictionError(
                f"ALTERNATIVE_REGRESSION_CHANGED:{satellite}"
            )
        actual[satellite] = separation
    affine = screen.prefix_affine_separation(target)
    affine_separation = float(affine["heldout_peak_to_peak_m"])
    expected_affine = float(selected["affine_null"]["heldout_peak_to_peak_m"])
    if abs(affine_separation - expected_affine) > NUMERICAL_TOLERANCE_M:
        raise BlindOrbitPredictionError("AFFINE_REGRESSION_CHANGED")
    return {
        "affine_heldout_peak_to_peak_m": affine_separation,
        "alternative_heldout_peak_to_peak_m": actual,
        "pairwise_guard_m": frozen_plan.PAIRWISE_GUARD_M,
        "minimum_combined_remaining_margin_m": (
            frozen_plan.MINIMUM_COMBINED_MARGIN_M
        ),
    }


def build_bundle_from_gzip(payload: bytes, root: Path) -> dict[str, object]:
    root = Path(root)
    validate_authority(root)
    records, _ = _parse_navigation(payload, root)
    mapping = _opaque_mapping(root)
    epochs = _window_epochs()
    station_ecef = geometry.station_to_ecef(screen.STATION)
    named_curves: dict[str, np.ndarray] = {}
    timing_non_affine: dict[str, dict[str, float]] = {}
    minimum_elevation = float("inf")

    for satellite in frozen_plan.CANDIDATE_FAMILY:
        label = _model_label(satellite)
        nominal, target_positions, reference_positions = _anchored_range_coordinate(
            records, satellite, epochs, station_ecef
        )
        if not np.all(np.isfinite(nominal)):
            raise BlindOrbitPredictionError(f"NONFINITE_MODEL:{satellite}")
        named_curves[label] = nominal
        for positions in (target_positions, reference_positions):
            elevation = geometry.elevation_deg(
                positions, screen.STATION, station_ecef
            )
            minimum_elevation = min(minimum_elevation, float(np.min(elevation)))
        for offset in TIMING_OFFSETS_S:
            shifted, shifted_target, shifted_reference = _anchored_range_coordinate(
                records, satellite, epochs, station_ecef, offset
            )
            metrics = screen.prefix_affine_separation(nominal - shifted)
            timing_non_affine.setdefault(mapping[label], {})[
                f"{offset:+.1f}"
            ] = float(metrics["heldout_peak_to_peak_m"])
            for positions in (shifted_target, shifted_reference):
                elevation = geometry.elevation_deg(
                    positions, screen.STATION, station_ecef
                )
                minimum_elevation = min(
                    minimum_elevation, float(np.min(elevation))
                )

    named_curves["PREFIX_AFFINE_ONLY"] = np.zeros(RAW_EPOCHS, dtype=np.float64)
    regressions = _validate_regressions(named_curves, root)
    if (
        abs(minimum_elevation - frozen_plan.MINIMUM_SHIFTED_ELEVATION_DEG)
        > ELEVATION_TOLERANCE_DEG
    ):
        raise BlindOrbitPredictionError("VISIBILITY_REGRESSION_CHANGED")

    opaque_curves = {
        mapping[label]: [float(value) for value in curve]
        for label, curve in named_curves.items()
    }
    if set(opaque_curves) != set(mapping.values()):
        raise BlindOrbitPredictionError("OPAQUE_CURVE_SET_CHANGED")
    result = {
        "schema": "gnss-blind-orbit-opaque-prediction-bundle-v1",
        "grid": {
            "time_system": "GPS",
            "epochs": RAW_EPOCHS,
            "step_s": STEP_S,
            "prefix_indices_inclusive": [0, PREFIX_EPOCHS - 1],
            "heldout_indices_inclusive": [PREFIX_EPOCHS, RAW_EPOCHS - 1],
        },
        "opaque_ids": sorted(opaque_curves),
        "curves_m": opaque_curves,
        "scoring": {
            "per_hypothesis_prefix_fit": ["CONSTANT", "LINEAR_RATE"],
            "per_hypothesis_parameter_count": 2,
            "pairwise_guard_m": frozen_plan.PAIRWISE_GUARD_M,
            "metric_order": ["PEAK_TO_PEAK_M", "RMS_M", "OPAQUE_ID"],
            "heldout_refit": False,
            "free_time_phase": False,
            "time_warp": False,
        },
    }
    rendered = strict_json(result)
    for forbidden in (
        "G22",
        "G30",
        "PREFIX_AFFINE_ONLY",
        "satellite",
        "mapping",
        "observer",
        "product",
    ):
        if forbidden.lower() in rendered.lower():
            raise BlindOrbitPredictionError(f"OPAQUE_BUNDLE_DISCLOSURE:{forbidden}")
    strict_json(regressions)
    strict_json(timing_non_affine)
    for curve in named_curves.values():
        curve.fill(0.0)
    return result


def bundle_curve_set_sha256(bundle: Mapping[str, object]) -> str:
    payload = strict_json(bundle["curves_m"]).encode("ascii")
    return sha256(payload).hexdigest()


def write_bundle(payload: bytes, root: Path, output: Path) -> dict[str, object]:
    output = Path(output)
    if output.exists():
        raise BlindOrbitPredictionError("OPAQUE_BUNDLE_ALREADY_EXISTS")
    value = build_bundle_from_gzip(payload, root)
    output.write_bytes((strict_json(value, pretty=True) + "\n").encode("ascii"))
    return {
        "outcome": "OPAQUE_PREDICTION_BUNDLE_WRITTEN",
        "compiler_source_commit": _git_commit(),
        "compiler_source_sha256": source_sha256(),
        "compiler_manifest_sha256": compiler_manifest_sha256(root),
        "dependencies": dependency_versions(),
        "bundle_canonical_sha256": canonical_sha256(output),
        "curve_set_sha256": bundle_curve_set_sha256(value),
        "bundle_bytes": len(output.read_bytes().replace(b"\r\n", b"\n")),
        "primary_access": {
            "locators_queried": 0,
            "headers_opened": 0,
            "payload_bytes": 0,
            "values": 0,
        },
        "scores": 0,
        "next_maximum": "FREEZE_IDENTITY_BLIND_SCORER_AGAINST_THIS_EXACT_BUNDLE",
    }


def main() -> None:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--navigation-gzip", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=root / BUNDLE_NAME)
    args = parser.parse_args()
    payload = args.navigation_gzip.read_bytes()
    summary = write_bundle(payload, root, args.output)
    payload = b""
    print(strict_json(summary))


if __name__ == "__main__":
    main()
