"""Sealed DOY 220 G22/G30 phase decoder and held-out scorer.

This is experiment-specific code. Model curves are compiled from the frozen
broadcast-navigation authority before primary access. Observation scalars can
enter only through the two predeclared locators during a separately authorised
one-shot execution, remain in RAM, and are erased after aggregate receipts.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import gc
from hashlib import sha256
import importlib.metadata
import json
from math import sqrt
from pathlib import Path
import platform
import subprocess
from typing import Final, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import hatanaka
import numpy as np

from experiments.orbital_discriminability import gnss_double_difference_screen as base
from experiments.orbital_discriminability import gnss_observation_header as headers
from experiments.orbital_discriminability import gnss_orbit_pair_screen as pair
from experiments.orbital_discriminability import gnss_phase_quotient_spike as phase
from experiments.orbital_discriminability import gnss_phase_short_window_plan as frozen
from experiments.orbital_discriminability import (
    gnss_phase_short_window_qualification as qualification,
)
from experiments.orbital_discriminability import gnss_structural_qualification as structural


PRIMARY_VERSION: Final = "g22-g30-phase-short-window-doy220-primary-v1"
PREDICTIONS_NAME: Final = "GNSS_PHASE_SHORT_WINDOW_PRIMARY_PREDICTIONS.json"
SEAL_NAME: Final = "GNSS_PHASE_SHORT_WINDOW_PRIMARY_SEAL.json"
OUTCOME_NAME: Final = "GNSS_PHASE_SHORT_WINDOW_PRIMARY_OUTCOME.json"
AUTHORITY_TOKEN: Final = "AUTHORIZE_DOY220_SHORT_WINDOW_PRIMARY_ONCE"
MAX_TRANSPORT_ATTEMPTS: Final = 1
HTTP_TIMEOUT_S: Final = 120.0
MAX_COMPRESSED_BYTES: Final = 20_000_000

QUALIFICATION_OUTCOME_NAME: Final = qualification.OUTCOME_NAME
QUALIFICATION_OUTCOME_SHA256: Final = (
    "c592ae34c665322d1bc209d6d868d1ab5aedae10934d3a79a524231dab765322"
)
QUALIFICATION_SUMMARY_SHA256: Final = (
    "64a453b2117ad4a156024f9297d5e6457da530d5b2fe6001d232988776bf748b"
)
QUALIFICATION_COVERAGE_SHA256: Final = (
    "a1bcf2b0117caaa08694631bcacc6f3a4ea044f7319f7e1b90b79784ce8e3a5e"
)

SATELLITES: Final = ("G22", "G30")
CORE_PHASE: Final = ("L1C", "L2W")
SAME_PATH_CODE: Final = ("C1C", "C2W")
MODEL_SATELLITES: Final = ("G22", "G30", "G01", "G14", "G17")
HYPOTHESES: Final = {
    "ORBITAL_G22": "G22",
    "PREFIX_AFFINE": None,
    "WRONG_ORBIT_G01": "G01",
    "WRONG_ORBIT_G14": "G14",
    "WRONG_ORBIT_G17": "G17",
}
PREFERRED_OUTCOMES: Final = {
    "ORBITAL_G22": "ORBITAL_MODEL_PREDICTIVELY_PREFERRED",
    "PREFIX_AFFINE": "PREFIX_AFFINE_NULL_PREFERRED",
    "WRONG_ORBIT_G01": "WRONG_ORBIT_G01_PREFERRED",
    "WRONG_ORBIT_G14": "WRONG_ORBIT_G14_PREFERRED",
    "WRONG_ORBIT_G17": "WRONG_ORBIT_G17_PREFERRED",
}

SPEED_OF_LIGHT_M_S: Final = 299_792_458.0
GPS_L1_HZ: Final = 1_575_420_000.0
GPS_L2_HZ: Final = 1_227_600_000.0
LAMBDA_L1_M: Final = SPEED_OF_LIGHT_M_S / GPS_L1_HZ
LAMBDA_L2_M: Final = SPEED_OF_LIGHT_M_S / GPS_L2_HZ

EXPECTED_CONFIGURATION: Final = {
    "GOLD00USA": {
        "receiver_type": "JAVAD TRE_G3TH DELTA",
        "receiver_version": "4.2.03",
        "antenna_type": "AOAD/M_T NONE",
    },
    "NLIB00USA": {
        "receiver_type": "SEPT POLARX5TR",
        "receiver_version": "5.7.0",
        "antenna_type": "JAVRINGANT_DM SCIS",
    },
}


@dataclass(frozen=True, slots=True)
class ProductLocator:
    station: str
    name: str
    url: str


PRODUCTS: Final = (
    ProductLocator(
        "GOLD00USA",
        "GOLD00USA_R_20262200000_01D_30S_MO.crx.gz",
        "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/220/"
        "GOLD00USA_R_20262200000_01D_30S_MO.crx.gz",
    ),
    ProductLocator(
        "NLIB00USA",
        "NLIB00USA_R_20262200000_01D_30S_MO.crx.gz",
        "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/220/"
        "NLIB00USA_R_20262200000_01D_30S_MO.crx.gz",
    ),
)


class PrimaryMeasurementInvalid(ValueError):
    """The measurement failed a frozen physical-admission clause."""


class PrimaryMaterializationError(RuntimeError):
    """A complete primary artifact was not materialized in the single attempt."""


class PrimaryDescriptionError(RuntimeError):
    """Software or receipt description failed without a physical decision."""


@dataclass(slots=True)
class StationMeasurement:
    station: str
    header: dict[str, object]
    phase_cycles: np.ndarray
    core_valid: np.ndarray
    code_present: np.ndarray
    structural_counts: dict[str, int]

    def erase(self) -> None:
        self.phase_cycles.fill(0.0)
        self.core_valid.fill(False)
        self.code_present.fill(False)


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
        "hatanaka": importlib.metadata.version("hatanaka"),
        "ncompress": importlib.metadata.version("ncompress"),
    }


def navigation_authority() -> pair.NavigationAuthority:
    authority = next(item for item in pair.AUTHORITIES if item.doy == frozen.PRIMARY_DOY)
    if authority.name != "BRDM00DLR_S_20262200000_01D_MN.rnx":
        raise PrimaryDescriptionError("PRIMARY_NAVIGATION_AUTHORITY_CHANGED")
    return authority


def expected_raw_gps_epochs() -> tuple[datetime, ...]:
    result = tuple(
        frozen.PRIMARY_RAW_START + timedelta(seconds=index * frozen.STEP_S)
        for index in range(frozen.RAW_EPOCHS)
    )
    if structural.format_gps_epoch(result[-1]) != "2026-08-08T06:51:00.000000Z":
        raise PrimaryDescriptionError("PRIMARY_WINDOW_GRID_CHANGED")
    return result


def manifest() -> dict[str, object]:
    authority = navigation_authority()
    result = {
        "primary_version": PRIMARY_VERSION,
        "source_sha256": source_sha256(),
        "dependencies_at_seal_runtime": dependency_versions(),
        "proof_plan_manifest_sha256": frozen.manifest_sha256(),
        "qualification_closure": {
            "outcome_name": QUALIFICATION_OUTCOME_NAME,
            "outcome_sha256": QUALIFICATION_OUTCOME_SHA256,
            "summary_sha256": QUALIFICATION_SUMMARY_SHA256,
            "coverage_sha256": QUALIFICATION_COVERAGE_SHA256,
            "required_outcome": "GNSS_SHORT_WINDOW_QUALIFICATION_PASSED",
        },
        "navigation": asdict(authority),
        "products": [asdict(item) for item in PRODUCTS],
        "window": {
            "raw_start_gps": structural.format_gps_epoch(expected_raw_gps_epochs()[0]),
            "raw_stop_gps": structural.format_gps_epoch(expected_raw_gps_epochs()[-1]),
            "step_s": frozen.STEP_S,
            "raw_epochs": frozen.RAW_EPOCHS,
            "feature_raw_indices_inclusive": [1, 137],
            "calibration_feature_indices_inclusive": [0, 76],
            "heldout_feature_indices_inclusive": [77, 136],
        },
        "measurement_coordinate": frozen.plan()["measurement_coordinate"],
        "hypotheses": HYPOTHESES,
        "scoring": {
            "nuisance": "CONSTANT_PLUS_RATE_ON_77_EPOCH_PREFIX_PER_HYPOTHESIS",
            "orbital_calibration_peak_to_peak_admission_m": (
                frozen.PRIMARY_ONE_MODEL_ENVELOPE_M
            ),
            "heldout_preference_margin_required_m": (
                frozen.PRIMARY_PAIRWISE_DECISION_GUARD_M
            ),
            "suffix_refit": False,
            "free_time_phase": False,
            "outcomes": list(frozen.plan()["future_primary_outcomes"]),
        },
        "transport": {
            "attempts_per_locator": MAX_TRANSPORT_ATTEMPTS,
            "timeout_s": HTTP_TIMEOUT_S,
            "maximum_compressed_bytes": MAX_COMPRESSED_BYTES,
            "complete_file_hash_before_decode": True,
            "retry_after_freeze": False,
        },
        "persistence": {
            "compressed_rinex": 0,
            "decoded_rinex": 0,
            "phase_code_or_snr_values": 0,
            "aggregate_admission_and_score_receipt_only": True,
        },
        "access_boundary": {
            "primary_products_discovered": 0,
            "primary_headers_opened": 0,
            "primary_payload_bytes": 0,
            "primary_values_accessed": 0,
            "live_execution_authorized_by_manifest": False,
        },
        "forbidden": [
            "qualification value reuse",
            "primary access before exact seal review",
            "window feature threshold or null change",
            "free time phase or suffix refit",
            "interpolation or gap bridging",
            "artifact or observation-value persistence",
            "retry endpoint or date substitution",
        ],
    }
    strict_json(result)
    return result


def manifest_sha256() -> str:
    return sha256(strict_json(manifest()).encode("ascii")).hexdigest()


def validate_qualification_closure(root: Path) -> Mapping[str, object]:
    outcome_path = root / QUALIFICATION_OUTCOME_NAME
    if canonical_sha256(outcome_path) != QUALIFICATION_OUTCOME_SHA256:
        raise PrimaryDescriptionError("QUALIFICATION_OUTCOME_CHANGED")
    outcome = json.loads(
        outcome_path.read_text(encoding="utf-8"),
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
    )
    if outcome.get("outcome") != "GNSS_SHORT_WINDOW_QUALIFICATION_PASSED":
        raise PrimaryDescriptionError("QUALIFICATION_NOT_PASSED")
    if outcome.get("proof_plan_manifest_sha256") != frozen.manifest_sha256():
        raise PrimaryDescriptionError("QUALIFICATION_PLAN_BINDING_CHANGED")
    if any(outcome.get("primary_doy220_access", {}).values()):
        raise PrimaryDescriptionError("PRIMARY_ALREADY_ACCESSED_AT_QUALIFICATION")
    if outcome.get("summary", {}).get("sha256") != QUALIFICATION_SUMMARY_SHA256:
        raise PrimaryDescriptionError("QUALIFICATION_SUMMARY_CHANGED")
    if outcome.get("coverage", {}).get("sha256") != QUALIFICATION_COVERAGE_SHA256:
        raise PrimaryDescriptionError("QUALIFICATION_COVERAGE_CHANGED")
    return outcome


def validate_navigation(path: Path) -> pair.NavigationAuthority:
    authority = navigation_authority()
    candidate = Path(path)
    if candidate.name != authority.name:
        raise PrimaryDescriptionError("PRIMARY_NAVIGATION_NAME_CHANGED")
    if not candidate.is_file() or candidate.stat().st_size != authority.bytes:
        raise PrimaryDescriptionError("PRIMARY_NAVIGATION_SIZE_CHANGED")
    if base.file_sha256(candidate) != authority.sha256:
        raise PrimaryDescriptionError("PRIMARY_NAVIGATION_SHA256_CHANGED")
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


def build_predictions(navigation_path: Path) -> dict[str, object]:
    """Compile frozen model coordinates; no observation input is accepted."""
    authority = validate_navigation(navigation_path)
    records = base.parse_gps_navigation(Path(navigation_path))
    gps_epochs = expected_raw_gps_epochs()
    utc_epochs = tuple(
        epoch - timedelta(seconds=base.GPS_UTC_OFFSET_S) for epoch in gps_epochs
    )
    positions: dict[str, np.ndarray] = {}
    for satellite in MODEL_SATELLITES:
        if satellite not in records:
            raise PrimaryDescriptionError(f"MODEL_SATELLITE_MISSING:{satellite}")
        positions[satellite] = np.asarray(
            [
                base.broadcast_ecef(base.select_ephemeris(records[satellite], epoch), epoch)
                for epoch in utc_epochs
            ],
            dtype=np.float64,
        )
    station_ecef = {
        station.station_id: base.station_to_ecef(station) for station in base.STATIONS
    }
    elevation_minima: dict[str, float] = {}
    for satellite in MODEL_SATELLITES:
        minima = []
        for station in base.STATIONS:
            elevations = base.elevation_deg(
                positions[satellite], station, station_ecef[station.station_id]
            )
            minima.append(float(np.min(elevations)))
        elevation_minima[satellite] = min(minima)
    curves: dict[str, list[float]] = {}
    for hypothesis, satellite in HYPOTHESES.items():
        curve = (
            np.zeros(frozen.FEATURE_EPOCHS, dtype=np.float64)
            if satellite is None
            else _range_curve(positions, station_ecef, satellite)[1:-1]
        )
        if curve.shape != (frozen.FEATURE_EPOCHS,) or not np.all(np.isfinite(curve)):
            raise PrimaryDescriptionError(f"MODEL_CURVE_INVALID:{hypothesis}")
        curves[hypothesis] = [float(item) for item in curve]
    orbital = np.asarray(curves["ORBITAL_G22"], dtype=np.float64)
    regression: dict[str, object] = {
        "prefix_affine_heldout_peak_to_peak_m": phase.phase_prefix_metrics(
            orbital, split=frozen.CALIBRATION_EPOCHS, step_s=frozen.STEP_S
        )["heldout_peak_to_peak_m"],
        "wrong_orbit_heldout_peak_to_peak_m": {},
    }
    wrong_regression = regression["wrong_orbit_heldout_peak_to_peak_m"]
    assert isinstance(wrong_regression, dict)
    for satellite in frozen.ALTERNATIVE_ORBITS:
        metrics = phase.phase_prefix_metrics(
            orbital - np.asarray(curves[f"WRONG_ORBIT_{satellite}"], dtype=np.float64),
            split=frozen.CALIBRATION_EPOCHS,
            step_s=frozen.STEP_S,
        )
        wrong_regression[satellite] = metrics["heldout_peak_to_peak_m"]
    tolerance_m = 1.0e-6
    if abs(
        float(regression["prefix_affine_heldout_peak_to_peak_m"])
        - 11401.473007275607
    ) > tolerance_m:
        raise PrimaryDescriptionError("PREFIX_AFFINE_REGRESSION_CHANGED")
    for satellite, expected in frozen.ALTERNATIVE_ORBITS.items():
        actual = float(wrong_regression[satellite])
        if abs(actual - expected) > tolerance_m:
            raise PrimaryDescriptionError(f"WRONG_ORBIT_REGRESSION_CHANGED:{satellite}")
    result = {
        "schema": "gnss-phase-short-window-primary-predictions-v1",
        "primary_version": PRIMARY_VERSION,
        "compiler_source_commit": _git_commit(),
        "compiler_source_sha256": source_sha256(),
        "compiler_manifest_sha256": manifest_sha256(),
        "compiler_dependencies": dependency_versions(),
        "proof_plan_manifest_sha256": frozen.manifest_sha256(),
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
    if value.get("schema") != "gnss-phase-short-window-primary-predictions-v1":
        raise PrimaryDescriptionError("PREDICTION_SCHEMA_CHANGED")
    if value.get("proof_plan_manifest_sha256") != frozen.manifest_sha256():
        raise PrimaryDescriptionError("PREDICTION_PLAN_BINDING_CHANGED")
    if value.get("navigation") != asdict(navigation_authority()):
        raise PrimaryDescriptionError("PREDICTION_NAVIGATION_CHANGED")
    if any(value.get("observation_access", {}).values()):
        raise PrimaryDescriptionError("PREDICTIONS_USED_OBSERVATIONS")
    curves_value = value.get("curves_m")
    if not isinstance(curves_value, Mapping):
        raise PrimaryDescriptionError("PREDICTION_CURVES_MISSING")
    if set(curves_value) != set(HYPOTHESES):
        raise PrimaryDescriptionError("PREDICTION_HYPOTHESES_CHANGED")
    if value.get("curve_set_sha256") != sha256(
        strict_json(curves_value).encode("ascii")
    ).hexdigest():
        raise PrimaryDescriptionError("PREDICTION_CURVE_HASH_CHANGED")
    curves = {
        str(name): np.asarray(rows, dtype=np.float64)
        for name, rows in curves_value.items()
    }
    if any(
        curve.shape != (frozen.FEATURE_EPOCHS,) or not np.all(np.isfinite(curve))
        for curve in curves.values()
    ):
        raise PrimaryDescriptionError("PREDICTION_CURVE_INVALID")
    return curves


def build_seal(predictions_path: Path) -> dict[str, object]:
    path = Path(predictions_path)
    value = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)),
    )
    validate_predictions(value)
    if value.get("compiler_source_sha256") != source_sha256():
        raise PrimaryDescriptionError("PREDICTION_COMPILER_SOURCE_CHANGED")
    if value.get("compiler_manifest_sha256") != manifest_sha256():
        raise PrimaryDescriptionError("PREDICTION_COMPILER_MANIFEST_CHANGED")
    if value.get("compiler_dependencies") != dependency_versions():
        raise PrimaryDescriptionError(
            "PREDICTION_COMPILER_DEPENDENCIES_CHANGED"
        )
    result = {
        "schema": "gnss-phase-short-window-primary-seal-v1",
        "state": "PRIMARY_SCORER_FROZEN_PRIMARY_UNOPENED",
        "source_commit": value["compiler_source_commit"],
        "source_sha256": source_sha256(),
        "manifest_sha256": manifest_sha256(),
        "dependencies": dependency_versions(),
        "proof_plan_manifest_sha256": frozen.manifest_sha256(),
        "qualification_outcome_sha256": QUALIFICATION_OUTCOME_SHA256,
        "qualification_summary_sha256": QUALIFICATION_SUMMARY_SHA256,
        "qualification_coverage_sha256": QUALIFICATION_COVERAGE_SHA256,
        "predictions": {
            "name": path.name,
            "sha256": canonical_sha256(path),
            "curve_set_sha256": value["curve_set_sha256"],
        },
        "primary_products": [
            {**asdict(item), "bytes": None, "sha256": None} for item in PRODUCTS
        ],
        "authority": {
            "token": AUTHORITY_TOKEN,
            "expected_seal_sha256_must_be_supplied_separately": True,
            "live_execution_authorized_by_seal": False,
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


def validate_seal(
    seal_path: Path,
    predictions_path: Path,
    expected_seal_sha256: str,
) -> tuple[Mapping[str, object], dict[str, np.ndarray]]:
    if (
        len(expected_seal_sha256) != 64
        or canonical_sha256(seal_path) != expected_seal_sha256
    ):
        raise PrimaryDescriptionError("PRIMARY_SEAL_SHA256_MISMATCH")
    seal = json.loads(
        Path(seal_path).read_text(encoding="utf-8"),
        parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)),
    )
    if seal.get("state") != "PRIMARY_SCORER_FROZEN_PRIMARY_UNOPENED":
        raise PrimaryDescriptionError("PRIMARY_SEAL_STATE_CHANGED")
    if seal.get("source_sha256") != source_sha256():
        raise PrimaryDescriptionError("PRIMARY_SOURCE_CHANGED_AFTER_SEAL")
    if seal.get("manifest_sha256") != manifest_sha256():
        raise PrimaryDescriptionError("PRIMARY_MANIFEST_CHANGED_AFTER_SEAL")
    if seal.get("dependencies") != dependency_versions():
        raise PrimaryDescriptionError("PRIMARY_DEPENDENCIES_CHANGED_AFTER_SEAL")
    if seal.get("proof_plan_manifest_sha256") != frozen.manifest_sha256():
        raise PrimaryDescriptionError("PRIMARY_PLAN_CHANGED_AFTER_SEAL")
    if seal.get("qualification_outcome_sha256") != QUALIFICATION_OUTCOME_SHA256:
        raise PrimaryDescriptionError("PRIMARY_QUALIFICATION_BINDING_CHANGED")
    expected_prediction = seal.get("predictions", {})
    if expected_prediction.get("name") != Path(predictions_path).name:
        raise PrimaryDescriptionError("PRIMARY_PREDICTION_NAME_CHANGED")
    if canonical_sha256(predictions_path) != expected_prediction.get("sha256"):
        raise PrimaryDescriptionError("PRIMARY_PREDICTION_SHA256_CHANGED")
    prediction = json.loads(
        Path(predictions_path).read_text(encoding="utf-8"),
        parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)),
    )
    return seal, validate_predictions(prediction)


def _normalize(value: object) -> str:
    return " ".join(str(value).split())


def _validate_header(
    parsed: Mapping[str, object], locator: ProductLocator
) -> dict[str, object]:
    station = locator.station
    if str(parsed["marker_name"]) != station[:4]:
        raise PrimaryMeasurementInvalid(f"MARKER_IDENTITY_MISMATCH:{station}")
    if float(parsed["interval_s"]) != float(frozen.STEP_S):
        raise PrimaryMeasurementInvalid(f"INTERVAL_CHANGED:{station}")
    first_info = parsed["time_of_first_observation"]
    last_info = parsed["time_of_last_observation"]
    if first_info["time_system"] != "GPS" or last_info["time_system"] != "GPS":
        raise PrimaryMeasurementInvalid(
            f"OBSERVATION_TIME_SYSTEM_NOT_GPS:{station}"
        )
    first = headers.parse_utc(first_info["utc_like_epoch"])
    last = headers.parse_utc(last_info["utc_like_epoch"])
    epochs = expected_raw_gps_epochs()
    if first > epochs[0] or last < epochs[-1]:
        raise PrimaryMeasurementInvalid(f"FROZEN_WINDOW_NOT_COVERED:{station}")
    expected = EXPECTED_CONFIGURATION[station]
    receiver = parsed["receiver"]
    antenna = parsed["antenna"]
    if _normalize(receiver["type"]) != expected["receiver_type"]:
        raise PrimaryMeasurementInvalid(f"RECEIVER_TYPE_CHANGED:{station}")
    if _normalize(receiver["version_or_radome"]) != expected["receiver_version"]:
        raise PrimaryMeasurementInvalid(f"RECEIVER_VERSION_CHANGED:{station}")
    if _normalize(antenna["type"]) != expected["antenna_type"]:
        raise PrimaryMeasurementInvalid(f"ANTENNA_TYPE_CHANGED:{station}")
    gps_types = tuple(parsed["observable_types"].get("G", ()))
    missing = sorted(set(CORE_PHASE + SAME_PATH_CODE) - set(gps_types))
    if missing:
        raise PrimaryMeasurementInvalid(
            f"REQUIRED_SIGNAL_FAMILY_NOT_DECLARED:{station}:{','.join(missing)}"
        )
    return {
        "station": station,
        "marker_name": parsed["marker_name"],
        "receiver_type": _normalize(receiver["type"]),
        "receiver_version": _normalize(receiver["version_or_radome"]),
        "antenna_type": _normalize(antenna["type"]),
        "interval_s": float(parsed["interval_s"]),
        "time_of_first_observation": first_info,
        "time_of_last_observation": last_info,
        "gps_observables": list(gps_types),
        "full_frozen_window_covered": True,
    }


def _read_window_records(
    reader: qualification._LineReader,
    system_types: Mapping[str, Sequence[str]],
) -> tuple[
    dict[tuple[datetime, str], qualification._Record],
    dict[datetime, int],
]:
    epochs = expected_raw_gps_epochs()
    epoch_set = set(epochs)
    start, stop = epochs[0], epochs[-1]
    records: dict[tuple[datetime, str], qualification._Record] = {}
    flags: dict[datetime, int] = {}
    while True:
        line = reader.readline()
        if not line:
            break
        if not line.startswith(b">"):
            if line.strip():
                raise PrimaryMeasurementInvalid("RECORD_INVALID:NON_EPOCH_LINE")
            continue
        try:
            epoch, flag, satellite_count = qualification._parse_epoch(line)
        except qualification.QualificationFailure as exc:
            raise PrimaryMeasurementInvalid(str(exc)) from exc
        if epoch > stop:
            break
        in_window = start <= epoch <= stop
        if in_window:
            if epoch not in epoch_set:
                raise PrimaryMeasurementInvalid("RECORD_INVALID:OFF_GRID_EPOCH")
            if epoch in flags:
                raise PrimaryMeasurementInvalid("RECORD_INVALID:DUPLICATE_EPOCH")
            flags[epoch] = flag
        if flag in {2, 3, 4, 5}:
            for _ in range(satellite_count):
                if not reader.readline():
                    raise PrimaryMeasurementInvalid(
                        "RECORD_INVALID:TRUNCATED_SPECIAL_EVENT"
                    )
            continue
        if flag == 6:
            for _ in range(satellite_count):
                try:
                    qualification._read_record(reader, system_types)
                except qualification.QualificationFailure as exc:
                    raise PrimaryMeasurementInvalid(str(exc)) from exc
            continue
        if flag not in {0, 1}:
            raise PrimaryMeasurementInvalid(f"RECORD_INVALID:EPOCH_FLAG_{flag}")
        for _ in range(satellite_count):
            try:
                satellite, record = qualification._read_record(reader, system_types)
            except qualification.QualificationFailure as exc:
                raise PrimaryMeasurementInvalid(str(exc)) from exc
            if not in_window or satellite not in SATELLITES:
                continue
            key = epoch, satellite
            if key in records:
                raise PrimaryMeasurementInvalid(
                    "RECORD_INVALID:DUPLICATE_SATELLITE_RECORD"
                )
            records[key] = record
    return records, flags


def scan_decoded(
    decoded: bytearray, locator: ProductLocator
) -> StationMeasurement:
    reader = qualification._LineReader(decoded)
    try:
        header_lines = qualification._read_header(reader)
        parsed = headers.parse_header_lines(header_lines)
    except (
        qualification.QualificationFailure,
        headers.HeaderAdmissionError,
    ) as exc:
        raise PrimaryMeasurementInvalid(
            f"HEADER_INVALID:{locator.station}:{exc}"
        ) from exc
    except Exception as exc:
        raise PrimaryDescriptionError(
            f"HEADER_DESCRIPTION_ERROR:{locator.station}:"
            f"{type(exc).__name__}:{exc}"
        ) from exc
    header = _validate_header(parsed, locator)
    system_types = {
        system: tuple(values)
        for system, values in parsed["observable_types"].items()
    }
    gps_types = system_types["G"]
    indices = {
        observable: gps_types.index(observable)
        for observable in CORE_PHASE + SAME_PATH_CODE
    }
    records, flags = _read_window_records(reader, system_types)
    phase_cycles = np.full((frozen.RAW_EPOCHS, 2, 2), np.nan, dtype=np.float64)
    core_valid = np.zeros((frozen.RAW_EPOCHS, 2), dtype=np.bool_)
    code_present = np.zeros((frozen.RAW_EPOCHS, 2, 2), dtype=np.bool_)
    counts = {"PRESENT": 0, "BLANK": 0, "TRAILING_FIELD_OMITTED": 0}
    for row, epoch in enumerate(expected_raw_gps_epochs()):
        if flags.get(epoch) != 0:
            raise PrimaryMeasurementInvalid(
                f"EPOCH_ABSENT_OR_FLAGGED:{locator.station}:"
                f"{structural.format_gps_epoch(epoch)}:{flags.get(epoch)}"
            )
        for sat_index, satellite in enumerate(SATELLITES):
            record = records.get((epoch, satellite))
            if record is None:
                raise PrimaryMeasurementInvalid(
                    f"SATELLITE_RECORD_ABSENT:{locator.station}:"
                    f"{structural.format_gps_epoch(epoch)}:{satellite}"
                )
            for phase_index, observable in enumerate(CORE_PHASE):
                field_index = indices[observable]
                if field_index >= record.field_count:
                    counts["TRAILING_FIELD_OMITTED"] += 1
                    raise PrimaryMeasurementInvalid(
                        f"TRAILING_FIELD_OMITTED:{locator.station}:"
                        f"{structural.format_gps_epoch(epoch)}:{satellite}:"
                        f"{observable}"
                    )
                field = record.fields[field_index]
                if not field[:14].strip():
                    counts["BLANK"] += 1
                    raise PrimaryMeasurementInvalid(
                        f"FIELD_BLANK:{locator.station}:"
                        f"{structural.format_gps_epoch(epoch)}:{satellite}:"
                        f"{observable}"
                    )
                lli = qualification._parse_lli(field)
                if lli != "ZERO_OR_BLANK":
                    raise PrimaryMeasurementInvalid(
                        f"NONZERO_OR_INVALID_LLI:{locator.station}:"
                        f"{structural.format_gps_epoch(epoch)}:{satellite}:"
                        f"{observable}:{lli}"
                    )
                try:
                    phase_cycles[row, sat_index, phase_index] = (
                        qualification._parse_phase(field)
                    )
                except qualification.QualificationFailure as exc:
                    raise PrimaryMeasurementInvalid(str(exc)) from exc
                counts["PRESENT"] += 1
            core_valid[row, sat_index] = True
            for code_index, observable in enumerate(SAME_PATH_CODE):
                field_index = indices[observable]
                present = (
                    field_index < record.field_count
                    and bool(record.fields[field_index][:14].strip())
                )
                code_present[row, sat_index, code_index] = present
                counts["PRESENT" if present else "BLANK"] += 1
    return StationMeasurement(
        station=locator.station,
        header=header,
        phase_cycles=phase_cycles,
        core_valid=core_valid,
        code_present=code_present,
        structural_counts=counts,
    )


def _geometry_free_health(
    scans: Sequence[StationMeasurement],
) -> dict[str, object]:
    links = []
    passed = True
    for scan in scans:
        for sat_index, satellite in enumerate(SATELLITES):
            geometry_free_m = (
                scan.phase_cycles[:, sat_index, 0] * LAMBDA_L1_M
                - scan.phase_cycles[:, sat_index, 1] * LAMBDA_L2_M
            )
            second = np.diff(geometry_free_m, n=2)
            maximum = float(np.max(np.abs(second)))
            violations = int(
                np.count_nonzero(
                    np.abs(second)
                    > frozen.GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M
                )
            )
            passed = passed and violations == 0
            links.append(
                {
                    "station": scan.station,
                    "satellite": satellite,
                    "evaluated_second_differences": int(second.size),
                    "maximum_absolute_second_difference_m": maximum,
                    "violations": violations,
                }
            )
            geometry_free_m.fill(0.0)
            second.fill(0.0)
    return {
        "state": "SATISFIED" if passed else "UNSATISFIED",
        "limit_m": frozen.GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M,
        "links": links,
    }


def measurement_coordinate(
    scans: Sequence[StationMeasurement],
) -> tuple[np.ndarray, dict[str, object]]:
    if tuple(scan.station for scan in scans) != tuple(
        item.station for item in PRODUCTS
    ):
        raise PrimaryMeasurementInvalid("PRIMARY_STATION_ORDER_CHANGED")
    if not all(np.all(scan.core_valid) for scan in scans):
        raise PrimaryMeasurementInvalid("CORE_PHASE_WINDOW_INCOMPLETE")
    code_links = []
    code_passed = True
    required = np.asarray(frozen.CODE_REQUIRED_RAW_INDICES, dtype=np.int64)
    for scan in scans:
        for sat_index, satellite in enumerate(SATELLITES):
            for code_index, observable in enumerate(SAME_PATH_CODE):
                present = scan.code_present[:, sat_index, code_index]
                fraction = float(
                    np.count_nonzero(present) / frozen.RAW_EPOCHS
                )
                boundary = bool(np.all(present[required]))
                accepted = (
                    fraction >= frozen.CODE_MINIMUM_COVERAGE_FRACTION
                    and boundary
                )
                code_passed = code_passed and accepted
                code_links.append(
                    {
                        "station": scan.station,
                        "satellite": satellite,
                        "observable": observable,
                        "coverage_fraction": fraction,
                        "required_indices_present": boundary,
                        "state": (
                            "SATISFIED" if accepted else "UNSATISFIED"
                        ),
                    }
                )
    if not code_passed:
        failed = next(
            row for row in code_links if row["state"] == "UNSATISFIED"
        )
        raise PrimaryMeasurementInvalid(
            "SAME_PATH_CODE_WITNESS_FAILED:"
            f"{failed['station']}:{failed['satellite']}:"
            f"{failed['observable']}"
        )
    health = _geometry_free_health(scans)
    if health["state"] != "SATISFIED":
        failed = next(
            row for row in health["links"] if row["violations"] > 0
        )
        raise PrimaryMeasurementInvalid(
            "GEOMETRY_FREE_PHASE_HEALTH_FAILED:"
            f"{failed['station']}:{failed['satellite']}:"
            f"{failed['maximum_absolute_second_difference_m']}"
        )
    station_coordinates: list[np.ndarray] = []
    alpha, beta = frozen.plan()["measurement_coordinate"][
        "ionosphere_free_coefficients"
    ]
    for scan in scans:
        phase_m = np.empty((frozen.RAW_EPOCHS, 2), dtype=np.float64)
        for sat_index in range(2):
            phase_m[:, sat_index] = (
                float(alpha)
                * scan.phase_cycles[:, sat_index, 0]
                * LAMBDA_L1_M
                + float(beta)
                * scan.phase_cycles[:, sat_index, 1]
                * LAMBDA_L2_M
            )
        station_coordinates.append(phase_m[:, 0] - phase_m[:, 1])
        phase_m.fill(0.0)
    coordinate = (station_coordinates[0] - station_coordinates[1])[1:-1]
    for values in station_coordinates:
        values.fill(0.0)
    if (
        coordinate.shape != (frozen.FEATURE_EPOCHS,)
        or not np.all(np.isfinite(coordinate))
    ):
        coordinate.fill(0.0)
        raise PrimaryMeasurementInvalid("PRIMARY_COORDINATE_INVALID")
    admission = {
        "headers": [scan.header for scan in scans],
        "structural_counts": {
            scan.station: scan.structural_counts for scan in scans
        },
        "core_phase_and_lli": "SATISFIED",
        "same_path_code_witness": {
            "state": "SATISFIED",
            "links": code_links,
        },
        "geometry_free_phase_health": health,
        "raw_epochs": frozen.RAW_EPOCHS,
        "feature_epochs": frozen.FEATURE_EPOCHS,
    }
    strict_json(admission)
    return coordinate, admission


def _fit_prefix(
    residual: np.ndarray,
) -> tuple[np.ndarray, dict[str, float]]:
    values = np.asarray(residual, dtype=np.float64)
    if (
        values.shape != (frozen.FEATURE_EPOCHS,)
        or not np.all(np.isfinite(values))
    ):
        raise PrimaryDescriptionError("SCORE_RESIDUAL_INVALID")
    elapsed = np.arange(values.size, dtype=np.float64) * frozen.STEP_S
    split = frozen.CALIBRATION_EPOCHS
    design = np.column_stack((np.ones(split), elapsed[:split]))
    coefficients, *_ = np.linalg.lstsq(
        design, values[:split], rcond=None
    )
    projected = values - (
        coefficients[0] + coefficients[1] * elapsed
    )
    calibration = projected[:split]
    summary = {
        "constant_m": float(coefficients[0]),
        "rate_m_s": float(coefficients[1]),
        "calibration_peak_to_peak_m": float(np.ptp(calibration)),
        "calibration_rms_m": float(
            sqrt(float(np.mean(calibration**2)))
        ),
    }
    return projected, summary


def score_coordinate(
    observed_m: Sequence[float],
    curves: Mapping[str, Sequence[float]],
) -> dict[str, object]:
    observed = np.asarray(observed_m, dtype=np.float64)
    if (
        observed.shape != (frozen.FEATURE_EPOCHS,)
        or not np.all(np.isfinite(observed))
    ):
        raise PrimaryMeasurementInvalid("OBSERVED_COORDINATE_INVALID")
    normalized = {
        name: np.asarray(value, dtype=np.float64)
        for name, value in curves.items()
    }
    if set(normalized) != set(HYPOTHESES) or any(
        value.shape != observed.shape or not np.all(np.isfinite(value))
        for value in normalized.values()
    ):
        raise PrimaryDescriptionError("FROZEN_HYPOTHESIS_CURVES_INVALID")
    orbital_projected, orbital_prefix = _fit_prefix(
        observed - normalized["ORBITAL_G22"]
    )
    if (
        orbital_prefix["calibration_peak_to_peak_m"]
        > frozen.PRIMARY_ONE_MODEL_ENVELOPE_M
    ):
        orbital_projected.fill(0.0)
        result = {
            "outcome": "NOT_DETECTABLE",
            "calibration_admission": {
                "state": "UNSATISFIED",
                "limit_m": frozen.PRIMARY_ONE_MODEL_ENVELOPE_M,
                **orbital_prefix,
            },
            "heldout_comparison": "NOT_EVALUATED",
        }
        strict_json(result)
        return result
    scores = []
    split = frozen.CALIBRATION_EPOCHS
    for name in HYPOTHESES:
        projected, prefix = (
            (orbital_projected, orbital_prefix)
            if name == "ORBITAL_G22"
            else _fit_prefix(observed - normalized[name])
        )
        heldout = projected[split:]
        scores.append(
            {
                "hypothesis": name,
                **prefix,
                "heldout_peak_to_peak_m": float(np.ptp(heldout)),
                "heldout_rms_m": float(
                    sqrt(float(np.mean(heldout**2)))
                ),
            }
        )
        if name != "ORBITAL_G22":
            projected.fill(0.0)
    orbital_projected.fill(0.0)
    scores.sort(
        key=lambda row: (
            float(row["heldout_peak_to_peak_m"]),
            row["hypothesis"],
        )
    )
    best, runner_up = scores[:2]
    preference_margin = float(
        runner_up["heldout_peak_to_peak_m"]
    ) - float(best["heldout_peak_to_peak_m"])
    outcome = (
        PREFERRED_OUTCOMES[str(best["hypothesis"])]
        if preference_margin
        > frozen.PRIMARY_PAIRWISE_DECISION_GUARD_M
        else "AMBIGUOUS"
    )
    result = {
        "outcome": outcome,
        "calibration_admission": {
            "state": "SATISFIED",
            "limit_m": frozen.PRIMARY_ONE_MODEL_ENVELOPE_M,
            **orbital_prefix,
        },
        "heldout_comparison": {
            "state": "EVALUATED",
            "preference_guard_m": (
                frozen.PRIMARY_PAIRWISE_DECISION_GUARD_M
            ),
            "best_hypothesis": best["hypothesis"],
            "runner_up_hypothesis": runner_up["hypothesis"],
            "preference_margin_m": preference_margin,
            "scores": scores,
        },
    }
    strict_json(result)
    return result


def materialize(
    locator: ProductLocator,
) -> tuple[bytearray, dict[str, object]]:
    payload = bytearray()
    try:
        request = Request(
            locator.url,
            headers={
                "User-Agent": "Satellite-RF-Observatory/gnss-primary"
            },
        )
        with urlopen(request, timeout=HTTP_TIMEOUT_S) as response:
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                payload.extend(block)
                if len(payload) > MAX_COMPRESSED_BYTES:
                    raise PrimaryMaterializationError(
                        f"COMPRESSED_SIZE_LIMIT:{locator.station}"
                    )
        if not payload:
            raise PrimaryMaterializationError(
                f"EMPTY_ARTIFACT:{locator.station}"
            )
        return payload, {
            "station": locator.station,
            "product": locator.name,
            "url": locator.url,
            "attempts": 1,
            "complete_file_bytes": len(payload),
            "complete_file_sha256": sha256(payload).hexdigest(),
            "hash_before_any_decode": True,
        }
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        payload[:] = b"\x00" * len(payload)
        raise PrimaryMaterializationError(
            f"ARTIFACT_MATERIALIZATION_FAILED:{locator.station}:"
            f"{type(exc).__name__}:{exc}"
        ) from exc


def decode_in_memory(payload: bytearray, station: str) -> bytearray:
    try:
        return bytearray(hatanaka.decompress(bytes(payload), strict=True))
    except Exception as exc:
        raise PrimaryMeasurementInvalid(
            f"HATANAKA_DECODE_FAILED:{station}"
        ) from exc


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        strict_json(value, pretty=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def run_once(
    output_directory: Path,
    authority_token: str,
    expected_seal_sha256: str,
    seal_path: Path,
    predictions_path: Path,
) -> dict[str, object]:
    if authority_token != AUTHORITY_TOKEN:
        raise PermissionError("DOY220_PRIMARY_AUTHORITY_REQUIRED")
    root = Path(__file__).resolve().parent
    validate_qualification_closure(root)
    seal, curves = validate_seal(
        seal_path, predictions_path, expected_seal_sha256
    )
    compressed: list[bytearray] = []
    decoded: list[bytearray] = []
    scans: list[StationMeasurement] = []
    artifacts: list[dict[str, object]] = []
    try:
        for locator in PRODUCTS:
            payload, artifact = materialize(locator)
            compressed.append(payload)
            artifacts.append(artifact)
        for locator, payload in zip(
            PRODUCTS, compressed, strict=True
        ):
            rinex = decode_in_memory(payload, locator.station)
            decoded.append(rinex)
            scans.append(scan_decoded(rinex, locator))
        coordinate, admission = measurement_coordinate(scans)
        try:
            score = score_coordinate(coordinate, curves)
        finally:
            coordinate.fill(0.0)
        outcome = {
            "schema": "gnss-phase-short-window-primary-outcome-v1",
            "primary_version": PRIMARY_VERSION,
            "outcome": score["outcome"],
            "seal_sha256": expected_seal_sha256,
            "source_commit": seal["source_commit"],
            "source_sha256": seal["source_sha256"],
            "proof_plan_manifest_sha256": frozen.manifest_sha256(),
            "artifacts": artifacts,
            "measurement_admission": admission,
            "score": score,
            "observation_access": {
                "products": len(PRODUCTS),
                "headers": len(scans),
                "compressed_bytes_in_ram": sum(
                    len(item) for item in compressed
                ),
                "decoded_bytes_in_ram": sum(
                    len(item) for item in decoded
                ),
                "phase_scalars_parsed_in_ram": (
                    frozen.RAW_EPOCHS * 2 * 2 * 2
                ),
                "phase_code_or_snr_values_persisted": 0,
            },
            "persistence": {
                "compressed_rinex": 0,
                "decoded_rinex": 0,
                "observation_values": 0,
                "aggregate_admission_and_score_receipt_only": True,
            },
            "retry": {
                "post_freeze_attempts_per_locator": 1,
                "substitution": False,
            },
            "claim_scope": (
                "HELDOUT_ORBITAL_MODEL_PREFERENCE_BELOW_SATELLITE_IDENTITY"
                if score["outcome"]
                == "ORBITAL_MODEL_PREDICTIVELY_PREFERRED"
                else "NO_POSITIVE_ORBITAL_CLAIM"
            ),
        }
    except PrimaryMaterializationError as exc:
        outcome = {
            "schema": "gnss-phase-short-window-primary-outcome-v1",
            "primary_version": PRIMARY_VERSION,
            "execution_state": (
                "PRIMARY_ARTIFACT_MATERIALIZATION_FAILED"
            ),
            "physical_outcome": None,
            "reason": str(exc),
            "artifacts": artifacts,
            "heldout_comparison": "NOT_EVALUATED",
        }
    except (
        PrimaryMeasurementInvalid,
        qualification.QualificationFailure,
    ) as exc:
        outcome = {
            "schema": "gnss-phase-short-window-primary-outcome-v1",
            "primary_version": PRIMARY_VERSION,
            "outcome": "MEASUREMENT_INVALID",
            "reason": str(exc),
            "artifacts": artifacts,
            "heldout_comparison": "NOT_EVALUATED",
            "observation_values_persisted": 0,
        }
    except Exception as exc:
        outcome = {
            "schema": "gnss-phase-short-window-primary-outcome-v1",
            "primary_version": PRIMARY_VERSION,
            "execution_state": "PRIMARY_DESCRIPTION_ERROR",
            "physical_outcome": None,
            "reason": f"{type(exc).__name__}:{exc}",
            "artifacts": artifacts,
            "heldout_comparison": "NOT_EVALUATED",
        }
    finally:
        for scan in scans:
            scan.erase()
        for payload in decoded + compressed:
            payload[:] = b"\x00" * len(payload)
        for curve in curves.values():
            curve.fill(0.0)
        gc.collect()
    strict_json(outcome)
    _write_json(Path(output_directory) / OUTCOME_NAME, outcome)
    return outcome


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compile-predictions", type=Path)
    parser.add_argument("--write-seal", type=Path)
    parser.add_argument("--execute-live", action="store_true")
    parser.add_argument("--authority", default="")
    parser.add_argument("--seal-sha256", default="")
    parser.add_argument("--seal", type=Path)
    parser.add_argument("--predictions", type=Path)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path(__file__).resolve().parent,
    )
    args = parser.parse_args()
    if args.compile_predictions is not None:
        _write_json(
            args.output_directory / PREDICTIONS_NAME,
            build_predictions(args.compile_predictions),
        )
        return
    if args.write_seal is not None:
        _write_json(
            args.output_directory / SEAL_NAME,
            build_seal(args.write_seal),
        )
        return
    if (
        not args.execute_live
        or args.seal is None
        or args.predictions is None
    ):
        raise SystemExit(
            "OFFLINE_FREEZE_OR_SEPARATE_PRIMARY_AUTHORITY_REQUIRED"
        )
    print(
        strict_json(
            run_once(
                args.output_directory,
                args.authority,
                args.seal_sha256,
                args.seal,
                args.predictions,
            )
        )
    )


if __name__ == "__main__":
    main()
