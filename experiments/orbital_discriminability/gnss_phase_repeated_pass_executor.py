"""One-shot DOY 219 GNSS repeated-pass executor.

This module is experiment-specific. Importing it performs no discovery,
network access or observation decoding. Live access requires a separately
supplied authority token and the exact executor-seal hash.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import gc
from hashlib import sha256
import json
from math import sqrt
from pathlib import Path
import subprocess
from typing import Final, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import gnss_observation_header as headers
from experiments.orbital_discriminability import gnss_phase_repeated_pass as prediction
from experiments.orbital_discriminability import (
    gnss_phase_repeated_pass_plan as frozen,
)
from experiments.orbital_discriminability import (
    gnss_phase_short_window_primary as primary,
)
from experiments.orbital_discriminability import (
    gnss_phase_short_window_qualification as qualification,
)
from experiments.orbital_discriminability import (
    gnss_structural_qualification as structural,
)


EXECUTOR_VERSION: Final = "g22-g30-doy219-repeated-pass-executor-v1"
EXECUTOR_SEAL_NAME: Final = "GNSS_PHASE_REPEATED_PASS_EXECUTOR_SEAL.json"
OUTCOME_NAME: Final = "GNSS_PHASE_REPEATED_PASS_OUTCOME.json"
AUTHORITY_TOKEN: Final = "AUTHORIZE_DOY219_REPEATED_PASS_ONCE"
PREDICTIONS_SHA256: Final = (
    "d408696d5c9d6e446216fdd7bad240a300e4d0d6d27af470756ff7d1413896b0"
)
PREDICTION_SEAL_SHA256: Final = (
    "8d4466be2037420fb251f7ed70de8d463d9489264948245606a1a65b5d79987d"
)
PRIMARY_KERNEL_SHA256: Final = (
    "bbacf8653a74198941a6380640d43b5e7ffc7d46767039e84604db0de61793fc"
)

SATELLITES: Final = ("G22", "G30")
CORE_PHASE: Final = ("L1C", "L2W")
SAME_PATH_CODE: Final = ("C1C", "C2W")
HYPOTHESES: Final = prediction.HYPOTHESES
PREFERRED_OUTCOMES: Final = {
    "ORBITAL_G22": "ORBITAL_MODEL_REPEATED_PASS_PREFERRED",
    "PREFIX_AFFINE": "PREFIX_AFFINE_NULL_PREFERRED",
    "WRONG_ORBIT_G01": "WRONG_ORBIT_G01_PREFERRED",
    "WRONG_ORBIT_G14": "WRONG_ORBIT_G14_PREFERRED",
    "WRONG_ORBIT_G17": "WRONG_ORBIT_G17_PREFERRED",
}

PRODUCTS: Final = (
    primary.ProductLocator(
        "GOLD00USA",
        "GOLD00USA_R_20262190000_01D_30S_MO.crx.gz",
        "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/219/"
        "GOLD00USA_R_20262190000_01D_30S_MO.crx.gz",
    ),
    primary.ProductLocator(
        "NLIB00USA",
        "NLIB00USA_R_20262190000_01D_30S_MO.crx.gz",
        "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/219/"
        "NLIB00USA_R_20262190000_01D_30S_MO.crx.gz",
    ),
)


class RepeatedPassDescriptionError(ValueError):
    """The executor, seal or reused model-blind kernel changed."""


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


def expected_raw_gps_epochs() -> tuple[datetime, ...]:
    result = tuple(
        frozen.REPLICATION_RAW_START + timedelta(seconds=index * frozen.STEP_S)
        for index in range(frozen.RAW_EPOCHS)
    )
    if structural.format_gps_epoch(result[-1]) != "2026-08-07T06:55:00.000000Z":
        raise RepeatedPassDescriptionError("REPLICATION_GRID_CHANGED")
    return result


def validate_reused_kernel_contract() -> None:
    if primary.source_sha256() != PRIMARY_KERNEL_SHA256:
        raise RepeatedPassDescriptionError("PRIMARY_MODEL_BLIND_KERNEL_CHANGED")
    prior = primary.frozen
    if (
        prior.STEP_S != frozen.STEP_S
        or prior.RAW_EPOCHS != frozen.RAW_EPOCHS
        or prior.FEATURE_EPOCHS != frozen.FEATURE_EPOCHS
        or prior.CALIBRATION_EPOCHS != frozen.CALIBRATION_EPOCHS
        or prior.CODE_REQUIRED_RAW_INDICES != frozen.CODE_REQUIRED_RAW_INDICES
        or prior.CODE_MINIMUM_COVERAGE_FRACTION != frozen.CODE_MINIMUM_COVERAGE_FRACTION
        or prior.GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M
        != frozen.GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M
    ):
        raise RepeatedPassDescriptionError("REUSED_KERNEL_SHAPE_CONTRACT_CHANGED")
    old_coefficients = prior.plan()["measurement_coordinate"][
        "ionosphere_free_coefficients"
    ]
    if old_coefficients != frozen.plan()["coordinate"]["ionosphere_free_coefficients"]:
        raise RepeatedPassDescriptionError("REUSED_KERNEL_COORDINATE_CHANGED")
    if tuple(item.station for item in primary.PRODUCTS) != tuple(
        item.station for item in PRODUCTS
    ):
        raise RepeatedPassDescriptionError("REUSED_KERNEL_STATION_ORDER_CHANGED")


def executor_manifest() -> dict[str, object]:
    validate_reused_kernel_contract()
    result = {
        "schema": "gnss-phase-repeated-pass-executor-manifest-v1",
        "executor_version": EXECUTOR_VERSION,
        "physical_question": frozen.plan()["physical_question"],
        "plan_manifest_sha256": frozen.manifest_sha256(),
        "prediction_sha256": PREDICTIONS_SHA256,
        "prediction_seal_sha256": PREDICTION_SEAL_SHA256,
        "model_blind_kernel": {
            "module": "gnss_phase_short_window_primary.py",
            "canonical_sha256": PRIMARY_KERNEL_SHA256,
            "reused": [
                "HATANAKA_DECODE_IN_RAM",
                "ARTIFACT_MATERIALIZATION_HASH_BEFORE_DECODE",
                "COORDINATE_COMPOSITION_AND_ERASE",
                "PREFIX_CONSTANT_RATE_FIT",
            ],
            "not_reused": [
                "DOY220_GRID",
                "DOY220_LOCATORS",
                "DOY220_THRESHOLDS",
                "DOY220_SEAL",
                "DOY220_OUTCOME",
            ],
        },
        "products": [
            {
                "station": item.station,
                "name": item.name,
                "url": item.url,
                "bytes": None,
                "sha256": None,
            }
            for item in PRODUCTS
        ],
        "scoring": frozen.plan()["scoring"],
        "transport": {
            "attempts_per_locator": 1,
            "complete_file_hash_before_decode": True,
            "endpoint_substitution": False,
            "date_substitution": False,
            "reserve_fallback": False,
        },
        "persistence": {
            "compressed_rinex": 0,
            "decoded_rinex": 0,
            "phase_code_or_snr_values": 0,
            "aggregate_outcome_only": True,
        },
        "access": {
            "products_discovered": 0,
            "headers_opened": 0,
            "payload_bytes": 0,
            "values_accessed": 0,
            "live_execution_authorized_by_manifest": False,
        },
        "forbidden": [
            "DOY220_REOPEN_OR_RESCORE",
            "DOY218_DISCOVERY_OR_FALLBACK",
            "THRESHOLD_NULL_WINDOW_OR_FEATURE_CHANGE",
            "FREE_TIME_PHASE_OR_SUFFIX_REFIT",
            "OUTCOME_FILE_OVERWRITE",
        ],
    }
    strict_json(result)
    return result


def manifest_sha256() -> str:
    return sha256(strict_json(executor_manifest()).encode("ascii")).hexdigest()


def validate_frozen_inputs(root: Path) -> dict[str, np.ndarray]:
    root = Path(root)
    frozen.verify_sources(root)
    prediction_path = root / prediction.PREDICTIONS_NAME
    prediction_seal_path = root / prediction.SEAL_NAME
    if canonical_sha256(prediction_path) != PREDICTIONS_SHA256:
        raise RepeatedPassDescriptionError("REPLICATION_PREDICTIONS_CHANGED")
    if canonical_sha256(prediction_seal_path) != PREDICTION_SEAL_SHA256:
        raise RepeatedPassDescriptionError("REPLICATION_PREDICTION_SEAL_CHANGED")
    value = json.loads(
        prediction_path.read_text(encoding="utf-8"),
        parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)),
    )
    curves = prediction.validate_predictions(value)
    seal = json.loads(
        prediction_seal_path.read_text(encoding="utf-8"),
        parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)),
    )
    if seal.get("state") != "REPLICATION_PLAN_AND_PREDICTION_FROZEN":
        raise RepeatedPassDescriptionError("REPLICATION_PREDICTION_NOT_FROZEN")
    if seal.get("plan_manifest_sha256") != frozen.manifest_sha256():
        raise RepeatedPassDescriptionError("REPLICATION_PLAN_BINDING_CHANGED")
    if any(seal.get("access_at_seal", {}).values()):
        raise RepeatedPassDescriptionError("PREDICTION_SEAL_USED_OBSERVATIONS")
    return curves


def _normalize(value: object) -> str:
    return " ".join(str(value).split())


def _validate_header(
    parsed: Mapping[str, object], locator: primary.ProductLocator
) -> dict[str, object]:
    station = locator.station
    if str(parsed["marker_name"]) != station[:4]:
        raise primary.PrimaryMeasurementInvalid(f"MARKER_IDENTITY_MISMATCH:{station}")
    if float(parsed["interval_s"]) != float(frozen.STEP_S):
        raise primary.PrimaryMeasurementInvalid(f"INTERVAL_CHANGED:{station}")
    first_info = parsed["time_of_first_observation"]
    last_info = parsed["time_of_last_observation"]
    if first_info["time_system"] != "GPS" or last_info["time_system"] != "GPS":
        raise primary.PrimaryMeasurementInvalid(
            f"OBSERVATION_TIME_SYSTEM_NOT_GPS:{station}"
        )
    first = headers.parse_utc(first_info["utc_like_epoch"])
    last = headers.parse_utc(last_info["utc_like_epoch"])
    epochs = expected_raw_gps_epochs()
    if first > epochs[0] or last < epochs[-1]:
        raise primary.PrimaryMeasurementInvalid(f"FROZEN_WINDOW_NOT_COVERED:{station}")
    expected = primary.EXPECTED_CONFIGURATION[station]
    receiver = parsed["receiver"]
    antenna = parsed["antenna"]
    if _normalize(receiver["type"]) != expected["receiver_type"]:
        raise primary.PrimaryMeasurementInvalid(f"RECEIVER_TYPE_CHANGED:{station}")
    if _normalize(receiver["version_or_radome"]) != expected["receiver_version"]:
        raise primary.PrimaryMeasurementInvalid(f"RECEIVER_VERSION_CHANGED:{station}")
    if _normalize(antenna["type"]) != expected["antenna_type"]:
        raise primary.PrimaryMeasurementInvalid(f"ANTENNA_TYPE_CHANGED:{station}")
    gps_types = tuple(parsed["observable_types"].get("G", ()))
    missing = sorted(set(CORE_PHASE + SAME_PATH_CODE) - set(gps_types))
    if missing:
        raise primary.PrimaryMeasurementInvalid(
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
                raise primary.PrimaryMeasurementInvalid("RECORD_INVALID:NON_EPOCH_LINE")
            continue
        try:
            epoch, flag, satellite_count = qualification._parse_epoch(line)
        except qualification.QualificationFailure as exc:
            raise primary.PrimaryMeasurementInvalid(str(exc)) from exc
        if epoch > stop:
            break
        in_window = start <= epoch <= stop
        if in_window:
            if epoch not in epoch_set:
                raise primary.PrimaryMeasurementInvalid("RECORD_INVALID:OFF_GRID_EPOCH")
            if epoch in flags:
                raise primary.PrimaryMeasurementInvalid(
                    "RECORD_INVALID:DUPLICATE_EPOCH"
                )
            flags[epoch] = flag
        if flag in {2, 3, 4, 5}:
            for _ in range(satellite_count):
                if not reader.readline():
                    raise primary.PrimaryMeasurementInvalid(
                        "RECORD_INVALID:TRUNCATED_SPECIAL_EVENT"
                    )
            continue
        if flag == 6:
            for _ in range(satellite_count):
                try:
                    qualification._read_record(reader, system_types)
                except qualification.QualificationFailure as exc:
                    raise primary.PrimaryMeasurementInvalid(str(exc)) from exc
            continue
        if flag not in {0, 1}:
            raise primary.PrimaryMeasurementInvalid(f"RECORD_INVALID:EPOCH_FLAG_{flag}")
        for _ in range(satellite_count):
            try:
                satellite, record = qualification._read_record(reader, system_types)
            except qualification.QualificationFailure as exc:
                raise primary.PrimaryMeasurementInvalid(str(exc)) from exc
            if not in_window or satellite not in SATELLITES:
                continue
            key = epoch, satellite
            if key in records:
                raise primary.PrimaryMeasurementInvalid(
                    "RECORD_INVALID:DUPLICATE_SATELLITE_RECORD"
                )
            records[key] = record
    return records, flags


def scan_decoded(
    decoded: bytearray, locator: primary.ProductLocator
) -> primary.StationMeasurement:
    reader = qualification._LineReader(decoded)
    try:
        header_lines = qualification._read_header(reader)
        parsed = headers.parse_header_lines(header_lines)
    except (
        qualification.QualificationFailure,
        headers.HeaderAdmissionError,
    ) as exc:
        raise primary.PrimaryMeasurementInvalid(
            f"HEADER_INVALID:{locator.station}:{exc}"
        ) from exc
    except Exception as exc:
        raise RepeatedPassDescriptionError(
            f"HEADER_DESCRIPTION_ERROR:{locator.station}:" f"{type(exc).__name__}:{exc}"
        ) from exc
    header = _validate_header(parsed, locator)
    system_types = {
        system: tuple(values) for system, values in parsed["observable_types"].items()
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
            raise primary.PrimaryMeasurementInvalid(
                f"EPOCH_ABSENT_OR_FLAGGED:{locator.station}:"
                f"{structural.format_gps_epoch(epoch)}:{flags.get(epoch)}"
            )
        for satellite_index, satellite in enumerate(SATELLITES):
            record = records.get((epoch, satellite))
            if record is None:
                raise primary.PrimaryMeasurementInvalid(
                    f"SATELLITE_RECORD_ABSENT:{locator.station}:"
                    f"{structural.format_gps_epoch(epoch)}:{satellite}"
                )
            for phase_index, observable in enumerate(CORE_PHASE):
                field_index = indices[observable]
                if field_index >= record.field_count:
                    counts["TRAILING_FIELD_OMITTED"] += 1
                    raise primary.PrimaryMeasurementInvalid(
                        f"TRAILING_FIELD_OMITTED:{locator.station}:"
                        f"{structural.format_gps_epoch(epoch)}:{satellite}:"
                        f"{observable}"
                    )
                field = record.fields[field_index]
                if not field[:14].strip():
                    counts["BLANK"] += 1
                    raise primary.PrimaryMeasurementInvalid(
                        f"FIELD_BLANK:{locator.station}:"
                        f"{structural.format_gps_epoch(epoch)}:{satellite}:"
                        f"{observable}"
                    )
                lli = qualification._parse_lli(field)
                if lli != "ZERO_OR_BLANK":
                    raise primary.PrimaryMeasurementInvalid(
                        f"NONZERO_OR_INVALID_LLI:{locator.station}:"
                        f"{structural.format_gps_epoch(epoch)}:{satellite}:"
                        f"{observable}:{lli}"
                    )
                try:
                    phase_cycles[row, satellite_index, phase_index] = (
                        qualification._parse_phase(field)
                    )
                except qualification.QualificationFailure as exc:
                    raise primary.PrimaryMeasurementInvalid(str(exc)) from exc
                counts["PRESENT"] += 1
            core_valid[row, satellite_index] = True
            for code_index, observable in enumerate(SAME_PATH_CODE):
                field_index = indices[observable]
                present = field_index < record.field_count and bool(
                    record.fields[field_index][:14].strip()
                )
                code_present[row, satellite_index, code_index] = present
                counts["PRESENT" if present else "BLANK"] += 1
    return primary.StationMeasurement(
        station=locator.station,
        header=header,
        phase_cycles=phase_cycles,
        core_valid=core_valid,
        code_present=code_present,
        structural_counts=counts,
    )


def measurement_coordinate(
    scans: Sequence[primary.StationMeasurement],
) -> tuple[np.ndarray, dict[str, object]]:
    validate_reused_kernel_contract()
    return primary.measurement_coordinate(scans)


def score_coordinate(
    observed_m: Sequence[float],
    curves: Mapping[str, Sequence[float]],
) -> dict[str, object]:
    validate_reused_kernel_contract()
    observed = np.asarray(observed_m, dtype=np.float64)
    if observed.shape != (frozen.FEATURE_EPOCHS,) or not np.all(np.isfinite(observed)):
        raise primary.PrimaryMeasurementInvalid("OBSERVED_COORDINATE_INVALID")
    normalized = {
        name: np.asarray(value, dtype=np.float64) for name, value in curves.items()
    }
    if set(normalized) != set(HYPOTHESES) or any(
        value.shape != observed.shape or not np.all(np.isfinite(value))
        for value in normalized.values()
    ):
        raise RepeatedPassDescriptionError("FROZEN_HYPOTHESIS_CURVES_INVALID")
    orbital_projected, orbital_prefix = primary._fit_prefix(
        observed - normalized["ORBITAL_G22"]
    )
    if orbital_prefix["calibration_peak_to_peak_m"] > frozen.ONE_MODEL_ENVELOPE_M:
        orbital_projected.fill(0.0)
        result = {
            "outcome": "NOT_DETECTABLE",
            "calibration_admission": {
                "state": "UNSATISFIED",
                "limit_m": frozen.ONE_MODEL_ENVELOPE_M,
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
            else primary._fit_prefix(observed - normalized[name])
        )
        heldout = projected[split:]
        scores.append(
            {
                "hypothesis": name,
                **prefix,
                "heldout_peak_to_peak_m": float(np.ptp(heldout)),
                "heldout_rms_m": float(sqrt(float(np.mean(heldout**2)))),
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
    preference_margin = float(runner_up["heldout_peak_to_peak_m"]) - float(
        best["heldout_peak_to_peak_m"]
    )
    outcome = (
        PREFERRED_OUTCOMES[str(best["hypothesis"])]
        if preference_margin > frozen.PAIRWISE_DECISION_GUARD_M
        else "AMBIGUOUS"
    )
    result = {
        "outcome": outcome,
        "calibration_admission": {
            "state": "SATISFIED",
            "limit_m": frozen.ONE_MODEL_ENVELOPE_M,
            **orbital_prefix,
        },
        "heldout_comparison": {
            "state": "EVALUATED",
            "preference_guard_m": frozen.PAIRWISE_DECISION_GUARD_M,
            "best_hypothesis": best["hypothesis"],
            "runner_up_hypothesis": runner_up["hypothesis"],
            "preference_margin_m": preference_margin,
            "scores": scores,
        },
    }
    strict_json(result)
    return result


def build_executor_seal(root: Path) -> dict[str, object]:
    curves = validate_frozen_inputs(root)
    try:
        result = {
            "schema": "gnss-phase-repeated-pass-executor-seal-v1",
            "state": "REPLICATION_EXECUTOR_FROZEN_OBSERVATION_UNOPENED",
            "source_commit": _git_commit(),
            "source_sha256": source_sha256(),
            "manifest_sha256": manifest_sha256(),
            "dependencies": primary.dependency_versions(),
            "plan_manifest_sha256": frozen.manifest_sha256(),
            "primary_outcome_canonical_sha256": frozen.PRIMARY_OUTCOME_SHA256,
            "prediction_sha256": PREDICTIONS_SHA256,
            "prediction_seal_sha256": PREDICTION_SEAL_SHA256,
            "model_blind_kernel_sha256": PRIMARY_KERNEL_SHA256,
            "products": executor_manifest()["products"],
            "authority": {
                "expected_executor_seal_sha256_must_be_supplied": True,
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
    finally:
        for curve in curves.values():
            curve.fill(0.0)


def validate_executor_seal(
    root: Path,
    seal_path: Path,
    expected_seal_sha256: str,
) -> tuple[Mapping[str, object], dict[str, np.ndarray]]:
    if (
        len(expected_seal_sha256) != 64
        or canonical_sha256(seal_path) != expected_seal_sha256
    ):
        raise RepeatedPassDescriptionError("EXECUTOR_SEAL_SHA256_MISMATCH")
    seal = json.loads(
        Path(seal_path).read_text(encoding="utf-8"),
        parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)),
    )
    if seal.get("state") != "REPLICATION_EXECUTOR_FROZEN_OBSERVATION_UNOPENED":
        raise RepeatedPassDescriptionError("EXECUTOR_SEAL_STATE_CHANGED")
    if seal.get("source_sha256") != source_sha256():
        raise RepeatedPassDescriptionError("EXECUTOR_SOURCE_CHANGED")
    if seal.get("manifest_sha256") != manifest_sha256():
        raise RepeatedPassDescriptionError("EXECUTOR_MANIFEST_CHANGED")
    if seal.get("dependencies") != primary.dependency_versions():
        raise RepeatedPassDescriptionError("EXECUTOR_DEPENDENCIES_CHANGED")
    if seal.get("plan_manifest_sha256") != frozen.manifest_sha256():
        raise RepeatedPassDescriptionError("EXECUTOR_PLAN_BINDING_CHANGED")
    if seal.get("prediction_sha256") != PREDICTIONS_SHA256:
        raise RepeatedPassDescriptionError("EXECUTOR_PREDICTION_BINDING_CHANGED")
    if seal.get("prediction_seal_sha256") != PREDICTION_SEAL_SHA256:
        raise RepeatedPassDescriptionError("EXECUTOR_PREDICTION_SEAL_BINDING_CHANGED")
    if seal.get("model_blind_kernel_sha256") != PRIMARY_KERNEL_SHA256:
        raise RepeatedPassDescriptionError("EXECUTOR_KERNEL_BINDING_CHANGED")
    if seal.get("products") != executor_manifest()["products"]:
        raise RepeatedPassDescriptionError("EXECUTOR_PRODUCT_LOCATORS_CHANGED")
    if any(seal.get("access_at_seal", {}).values()):
        raise RepeatedPassDescriptionError("EXECUTOR_SEAL_USED_OBSERVATIONS")
    return seal, validate_frozen_inputs(root)


def _write_json(path: Path, value: object) -> None:
    Path(path).write_text(
        strict_json(value, pretty=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def run_once(
    output_directory: Path,
    authority_token: str,
    expected_seal_sha256: str,
    executor_seal_path: Path,
) -> dict[str, object]:
    if authority_token != AUTHORITY_TOKEN:
        raise PermissionError("DOY219_REPLICATION_AUTHORITY_REQUIRED")
    output_path = Path(output_directory) / OUTCOME_NAME
    if output_path.exists():
        raise PermissionError("REPLICATION_OUTCOME_ALREADY_EXISTS")
    root = Path(__file__).resolve().parent
    seal, curves = validate_executor_seal(
        root, executor_seal_path, expected_seal_sha256
    )
    compressed: list[bytearray] = []
    decoded: list[bytearray] = []
    scans: list[primary.StationMeasurement] = []
    artifacts: list[dict[str, object]] = []
    try:
        for locator in PRODUCTS:
            payload, artifact = primary.materialize(locator)
            compressed.append(payload)
            artifacts.append(artifact)
        for locator, payload in zip(PRODUCTS, compressed, strict=True):
            rinex = primary.decode_in_memory(payload, locator.station)
            decoded.append(rinex)
            scans.append(scan_decoded(rinex, locator))
        coordinate, admission = measurement_coordinate(scans)
        try:
            score = score_coordinate(coordinate, curves)
        finally:
            coordinate.fill(0.0)
        outcome = {
            "schema": "gnss-phase-repeated-pass-outcome-v1",
            "executor_version": EXECUTOR_VERSION,
            "outcome": score["outcome"],
            "executor_seal_sha256": expected_seal_sha256,
            "source_commit": seal["source_commit"],
            "source_sha256": seal["source_sha256"],
            "plan_manifest_sha256": frozen.manifest_sha256(),
            "primary_outcome_canonical_sha256": frozen.PRIMARY_OUTCOME_SHA256,
            "prediction_sha256": PREDICTIONS_SHA256,
            "artifacts": artifacts,
            "measurement_admission": admission,
            "score": score,
            "observation_access": {
                "products": len(PRODUCTS),
                "headers": len(scans),
                "compressed_bytes_in_ram": sum(len(item) for item in compressed),
                "decoded_bytes_in_ram": sum(len(item) for item in decoded),
                "phase_scalars_parsed_in_ram": frozen.RAW_EPOCHS * 2 * 2 * 2,
                "phase_code_or_snr_values_persisted": 0,
            },
            "persistence": {
                "compressed_rinex": 0,
                "decoded_rinex": 0,
                "observation_values": 0,
                "aggregate_admission_and_score_receipt_only": True,
            },
            "retry": {
                "attempts_per_locator": 1,
                "endpoint_substitution": False,
                "date_substitution": False,
                "reserve_fallback": False,
            },
            "claim_scope": (
                "REPEATED_PASS_CONSISTENCY_FOR_TWO_GOLD_NLIB_G22_G30_PASSES"
                if score["outcome"] == "ORBITAL_MODEL_REPEATED_PASS_PREFERRED"
                else "NO_POSITIVE_REPEATED_PASS_CLAIM"
            ),
        }
    except primary.PrimaryMaterializationError as exc:
        outcome = {
            "schema": "gnss-phase-repeated-pass-outcome-v1",
            "executor_version": EXECUTOR_VERSION,
            "execution_state": "REPLICATION_ARTIFACT_MATERIALIZATION_FAILED",
            "physical_outcome": None,
            "reason": str(exc),
            "artifacts": artifacts,
            "heldout_comparison": "NOT_EVALUATED",
            "observation_values_persisted": 0,
        }
    except (
        primary.PrimaryMeasurementInvalid,
        qualification.QualificationFailure,
    ) as exc:
        outcome = {
            "schema": "gnss-phase-repeated-pass-outcome-v1",
            "executor_version": EXECUTOR_VERSION,
            "outcome": "MEASUREMENT_INVALID",
            "reason": str(exc),
            "artifacts": artifacts,
            "heldout_comparison": "NOT_EVALUATED",
            "observation_values_persisted": 0,
        }
    except Exception as exc:
        outcome = {
            "schema": "gnss-phase-repeated-pass-outcome-v1",
            "executor_version": EXECUTOR_VERSION,
            "execution_state": "REPLICATION_DESCRIPTION_ERROR",
            "physical_outcome": None,
            "reason": f"{type(exc).__name__}:{exc}",
            "artifacts": artifacts,
            "heldout_comparison": "NOT_EVALUATED",
            "observation_values_persisted": 0,
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
    _write_json(output_path, outcome)
    return outcome


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-executor-seal", action="store_true")
    parser.add_argument("--execute-live", action="store_true")
    parser.add_argument("--authority", default="")
    parser.add_argument("--executor-seal-sha256", default="")
    parser.add_argument("--executor-seal", type=Path)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path(__file__).resolve().parent,
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    if args.write_executor_seal:
        _write_json(
            args.output_directory / EXECUTOR_SEAL_NAME,
            build_executor_seal(root),
        )
        return
    if not args.execute_live or args.executor_seal is None:
        raise SystemExit("OFFLINE_EXECUTOR_FREEZE_OR_SEPARATE_LIVE_AUTHORITY_REQUIRED")
    print(
        strict_json(
            run_once(
                args.output_directory,
                args.authority,
                args.executor_seal_sha256,
                args.executor_seal,
            )
        )
    )


if __name__ == "__main__":
    main()
