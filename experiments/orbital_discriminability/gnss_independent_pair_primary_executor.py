"""One-shot ALGO/MDO DOY219 primary executor.

This is disposable experiment code for the already frozen plan. Importing the
module performs no discovery, network access, header parsing, or observation
decoding. A later live run requires a separately supplied authority token and
the exact post-commit executor-seal hash.
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

from experiments.orbital_discriminability import gnss_independent_pair_primary_plan as frozen
from experiments.orbital_discriminability import gnss_independent_pair_primary_predictions as prediction
from experiments.orbital_discriminability import gnss_independent_pair_qualification as qualified
from experiments.orbital_discriminability import gnss_observation_header as headers
from experiments.orbital_discriminability import gnss_phase_repeated_pass_executor as parser_kernel
from experiments.orbital_discriminability import gnss_phase_short_window_primary as primary
from experiments.orbital_discriminability import gnss_phase_short_window_qualification as rinex
from experiments.orbital_discriminability import gnss_structural_qualification as structural


EXECUTOR_VERSION: Final = "g22-g30-algo-mdo-doy219-primary-executor-v1"
EXECUTOR_SEAL_NAME: Final = "GNSS_INDEPENDENT_PAIR_PRIMARY_EXECUTOR_SEAL.json"
OUTCOME_NAME: Final = "GNSS_INDEPENDENT_PAIR_PRIMARY_OUTCOME.json"
AUTHORITY_TOKEN: Final = "AUTHORIZE_ALGO_MDO_DOY219_PRIMARY_ONCE"

PLAN_DOCUMENT_NAME: Final = "GNSS_INDEPENDENT_PAIR_PRIMARY_PLAN.md"
PLAN_DOCUMENT_SHA256: Final = (
    "b6646759bfd6b36027557fc8c58398d0a0268cb677472ca7ed152cc543cf7355"
)
PREDICTIONS_SHA256: Final = (
    "f88b7a9185203fea00a4587335b2018172c5a894409bb5cb13d481d3e9996c0c"
)
PREDICTION_SEAL_SHA256: Final = (
    "f8585632bc5f5ea6f3f94441fae35d58b53ab181bcbeeda32c3daf8747e07793"
)
QUALIFICATION_SUMMARY_NAME: Final = (
    "GNSS_INDEPENDENT_PAIR_QUALIFICATION_SUMMARY.json"
)
QUALIFICATION_SUMMARY_SHA256: Final = (
    "68f14d331509f4bed96176314cab4428d80292d28da5a88430f4068948384493"
)
PRIMARY_KERNEL_SHA256: Final = (
    "bbacf8653a74198941a6380640d43b5e7ffc7d46767039e84604db0de61793fc"
)
PARSER_KERNEL_SHA256: Final = (
    "a03e3daf685851afa067dccb6974f72ba64f468b3823f2607c90e81f75a403fb"
)
RINEX_PARSER_SHA256: Final = (
    "f7ccffa52b1a2497ac6f4a073b00d7966f2ee4e4bec38ff2164629b138a727e8"
)
QUALIFICATION_KERNEL_SHA256: Final = (
    "9f2f81daf251caa6dfc9bc07225f8d5a300597969417da2a4566cab53b1aa155"
)

SATELLITES: Final = (frozen.TARGET, frozen.REFERENCE)
CORE_PHASE: Final = ("L1C", "L2W")
SAME_PATH_CODE: Final = ("C1C", "C2W")
HYPOTHESES: Final = prediction.HYPOTHESES
ONE_MODEL_CALIBRATION_ENVELOPE_M: Final = frozen.SCREEN_PAIRWISE_GUARD_M / 2.0
PREFERRED_OUTCOMES: Final = {
    "ORBITAL_G22": "ORBITAL_MODEL_PREDICTIVELY_PREFERRED",
    "PREFIX_AFFINE": "PREFIX_AFFINE_NULL_PREFERRED",
    "WRONG_ORBIT_G01": "WRONG_ORBIT_G01_PREFERRED",
    "WRONG_ORBIT_G14": "WRONG_ORBIT_G14_PREFERRED",
    "WRONG_ORBIT_G17": "WRONG_ORBIT_G17_PREFERRED",
}

PRODUCTS: Final = tuple(
    primary.ProductLocator(item.station, item.name, item.url)
    for item in frozen.PRODUCTS
)


class IndependentPairExecutorError(RuntimeError):
    """The executor, frozen evidence, or seal binding changed."""


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
    epochs = tuple(
        frozen.RAW_START + timedelta(seconds=index * frozen.STEP_S)
        for index in range(frozen.RAW_EPOCHS)
    )
    if structural.format_gps_epoch(epochs[-1]) != "2026-08-07T06:55:00.000000Z":
        raise IndependentPairExecutorError("PRIMARY_GRID_CHANGED")
    return epochs


def validate_kernel_contract() -> None:
    bindings = {
        "PRIMARY_MODEL_BLIND_KERNEL": (primary.__file__, PRIMARY_KERNEL_SHA256),
        "DOY219_RECORD_PARSER_KERNEL": (
            parser_kernel.__file__,
            PARSER_KERNEL_SHA256,
        ),
        "RINEX_STRUCTURAL_PARSER": (rinex.__file__, RINEX_PARSER_SHA256),
        "QUALIFICATION_HEADER_KERNEL": (
            qualified.__file__,
            QUALIFICATION_KERNEL_SHA256,
        ),
    }
    for name, (path, expected) in bindings.items():
        if canonical_sha256(Path(path)) != expected:
            raise IndependentPairExecutorError(f"{name}_CHANGED")
    if parser_kernel.expected_raw_gps_epochs() != expected_raw_gps_epochs():
        raise IndependentPairExecutorError("REUSED_PARSER_GRID_CHANGED")
    if (
        primary.frozen.STEP_S != frozen.STEP_S
        or primary.frozen.RAW_EPOCHS != frozen.RAW_EPOCHS
        or primary.frozen.FEATURE_EPOCHS != frozen.FEATURE_EPOCHS
        or primary.frozen.CALIBRATION_EPOCHS != frozen.CALIBRATION_EPOCHS
        or primary.frozen.CODE_REQUIRED_RAW_INDICES
        != frozen.CODE_REQUIRED_RAW_INDICES
        or primary.frozen.CODE_MINIMUM_COVERAGE_FRACTION
        != frozen.CODE_MINIMUM_COVERAGE_FRACTION
        or primary.frozen.GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M
        != frozen.GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M
    ):
        raise IndependentPairExecutorError("REUSED_KERNEL_SHAPE_CHANGED")
    if primary.frozen.plan()["measurement_coordinate"][
        "ionosphere_free_coefficients"
    ] != frozen.plan()["coordinate"]["ionosphere_free_coefficients"]:
        raise IndependentPairExecutorError("REUSED_COORDINATE_CHANGED")
    if ONE_MODEL_CALIBRATION_ENVELOPE_M != 1_771.1285336133258:
        raise IndependentPairExecutorError("ONE_MODEL_ENVELOPE_CHANGED")


def executor_manifest() -> dict[str, object]:
    validate_kernel_contract()
    result = {
        "schema": "gnss-independent-pair-primary-executor-manifest-v1",
        "executor_version": EXECUTOR_VERSION,
        "physical_question": frozen.plan()["physical_question"],
        "plan_manifest_sha256": frozen.manifest_sha256(),
        "plan_document": {
            "name": PLAN_DOCUMENT_NAME,
            "canonical_sha256": PLAN_DOCUMENT_SHA256,
        },
        "prediction_sha256": PREDICTIONS_SHA256,
        "prediction_seal_sha256": PREDICTION_SEAL_SHA256,
        "qualification_summary_sha256": QUALIFICATION_SUMMARY_SHA256,
        "reused_exact_kernels": {
            "primary_measurement": PRIMARY_KERNEL_SHA256,
            "doy219_record_parser": PARSER_KERNEL_SHA256,
            "rinex_structural_parser": RINEX_PARSER_SHA256,
            "qualification_header": QUALIFICATION_KERNEL_SHA256,
        },
        "products": [
            {
                "station": item.station,
                "name": item.name,
                "url": item.url,
                "complete_file_bytes": None,
                "complete_file_sha256": None,
            }
            for item in PRODUCTS
        ],
        "partition": frozen.plan()["partition"],
        "coordinate": frozen.plan()["coordinate"],
        "hypotheses": HYPOTHESES,
        "scoring": {
            **frozen.plan()["scoring"],
            "orbital_calibration_peak_to_peak_admission_m": (
                ONE_MODEL_CALIBRATION_ENVELOPE_M
            ),
            "one_model_basis": (
                "FROZEN_PAIRWISE_GUARD_DIVIDED_BY_TWO_NO_NEW_PARAMETER"
            ),
        },
        "transport": {
            "attempts_per_locator": 1,
            "complete_file_hash_before_header_or_decode": True,
            "endpoint_substitution": False,
            "date_substitution": False,
            "fallback_or_reserve": False,
        },
        "persistence": {
            "compressed_rinex": 0,
            "decoded_rinex": 0,
            "phase_code_or_snr_values": 0,
            "aggregate_admission_and_score_receipt_only": True,
        },
        "access": {
            "descriptive_head_requests_in_frozen_plan": 2,
            "headers_opened": 0,
            "payload_bytes": 0,
            "values_accessed": 0,
            "live_execution_authorized_by_manifest": False,
        },
        "forbidden": [
            "PRODUCT_DISCOVERY_OR_LOCATOR_CHANGE",
            "THRESHOLD_NULL_WINDOW_OR_FEATURE_CHANGE",
            "FREE_TIME_PHASE_OR_SUFFIX_REFIT",
            "OUTCOME_FILE_OVERWRITE",
            "PRIMARY_ACCESS_DURING_EXECUTOR_FREEZE",
        ],
    }
    strict_json(result)
    return result


def manifest_sha256() -> str:
    return sha256(strict_json(executor_manifest()).encode("ascii")).hexdigest()


def _load_qualified_headers(root: Path) -> dict[str, Mapping[str, object]]:
    path = Path(root) / QUALIFICATION_SUMMARY_NAME
    if canonical_sha256(path) != QUALIFICATION_SUMMARY_SHA256:
        raise IndependentPairExecutorError("QUALIFICATION_SUMMARY_CHANGED")
    document = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    rows = document.get("headers") if isinstance(document, Mapping) else None
    if not isinstance(rows, list):
        raise IndependentPairExecutorError("QUALIFICATION_HEADERS_INVALID")
    result = {
        str(row["station"]): row for row in rows if isinstance(row, Mapping)
    }
    if list(result) != ["ALGO00CAN", "MDO100USA"]:
        raise IndependentPairExecutorError("QUALIFICATION_HEADER_ORDER_CHANGED")
    for station, row in result.items():
        if (
            row.get("scale_factor_records") != []
            or row.get("applied_bias_records") != []
            or row.get("receiver_clock_offset_applied") != 0
            or not row.get("phase_shift_records")
            or not row.get("full_frozen_window_covered")
        ):
            raise IndependentPairExecutorError(
                f"QUALIFICATION_TRANSFORM_CLOSURE_CHANGED:{station}"
            )
    return result


def validate_frozen_inputs(
    root: Path,
) -> tuple[dict[str, np.ndarray], dict[str, Mapping[str, object]]]:
    base = Path(root)
    validate_kernel_contract()
    frozen.verify_sources(base)
    if canonical_sha256(base / PLAN_DOCUMENT_NAME) != PLAN_DOCUMENT_SHA256:
        raise IndependentPairExecutorError("PRIMARY_PLAN_DOCUMENT_CHANGED")
    prediction_path = base / prediction.PREDICTIONS_NAME
    prediction_seal_path = base / prediction.SEAL_NAME
    if canonical_sha256(prediction_path) != PREDICTIONS_SHA256:
        raise IndependentPairExecutorError("PRIMARY_PREDICTIONS_CHANGED")
    if canonical_sha256(prediction_seal_path) != PREDICTION_SEAL_SHA256:
        raise IndependentPairExecutorError("PRIMARY_PREDICTION_SEAL_CHANGED")
    value = json.loads(
        prediction_path.read_text(encoding="utf-8"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    curves = prediction.validate_predictions(value)
    seal = json.loads(
        prediction_seal_path.read_text(encoding="utf-8"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    if seal.get("state") != "PRIMARY_PLAN_AND_PREDICTION_FROZEN":
        raise IndependentPairExecutorError("PRIMARY_PREDICTION_NOT_FROZEN")
    if seal.get("plan_manifest_sha256") != frozen.manifest_sha256():
        raise IndependentPairExecutorError("PRIMARY_PLAN_BINDING_CHANGED")
    access = seal.get("access_at_seal", {})
    if not isinstance(access, Mapping) or any(
        int(access.get(field, -1)) != 0
        for field in (
            "observation_headers_opened",
            "observation_payload_bytes",
            "observation_values",
        )
    ):
        raise IndependentPairExecutorError("PREDICTION_SEAL_USED_OBSERVATIONS")
    return curves, _load_qualified_headers(base)


def _normalize(value: object) -> str:
    return " ".join(str(value).split())


def _validate_header(
    parsed: Mapping[str, object],
    locator: primary.ProductLocator,
    expected: Mapping[str, object],
) -> dict[str, object]:
    station = locator.station
    if not 3.0 <= float(parsed["rinex_version"]) < 5.0:
        raise primary.PrimaryMeasurementInvalid(
            f"RINEX_VERSION_NOT_EXPLICIT:{station}"
        )
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
    receiver = parsed["receiver"]
    antenna = parsed["antenna"]
    expected_receiver = expected["receiver"]
    expected_antenna = expected["antenna"]
    comparisons = {
        "RECEIVER_SERIAL": (receiver["serial"], expected_receiver["serial"]),
        "RECEIVER_TYPE": (receiver["type"], expected_receiver["type"]),
        "RECEIVER_VERSION": (
            receiver["version_or_radome"],
            expected_receiver["version_or_radome"],
        ),
        "ANTENNA_SERIAL": (antenna["serial"], expected_antenna["serial"]),
        "ANTENNA_TYPE": (antenna["type"], expected_antenna["type"]),
    }
    for label, (actual, wanted) in comparisons.items():
        if _normalize(actual) != _normalize(wanted):
            raise primary.PrimaryMeasurementInvalid(f"{label}_CHANGED:{station}")
    gps_types = tuple(parsed["observable_types"].get("G", ()))
    missing = sorted(set(CORE_PHASE + SAME_PATH_CODE) - set(gps_types))
    if missing:
        raise primary.PrimaryMeasurementInvalid(
            f"REQUIRED_SIGNAL_FAMILY_NOT_DECLARED:{station}:{','.join(missing)}"
        )
    transform_checks = {
        "SCALE_FACTOR_RECORDS": "scale_factor_records",
        "PHASE_SHIFT_RECORDS": "phase_shift_records",
        "APPLIED_BIAS_RECORDS": "applied_bias_records",
        "RECEIVER_CLOCK_OFFSET": "receiver_clock_offset_applied",
    }
    for label, key in transform_checks.items():
        if parsed.get(key) != expected.get(key):
            raise primary.PrimaryMeasurementInvalid(f"{label}_CHANGED:{station}")
    return {
        "station": station,
        "rinex_version": float(parsed["rinex_version"]),
        "marker_name": parsed["marker_name"],
        "receiver": receiver,
        "antenna": antenna,
        "interval_s": float(parsed["interval_s"]),
        "time_of_first_observation": first_info,
        "time_of_last_observation": last_info,
        "receiver_clock_offset_applied": parsed["receiver_clock_offset_applied"],
        "gps_observables": list(gps_types),
        "scale_factor_records": list(parsed.get("scale_factor_records", ())),
        "phase_shift_records": list(parsed.get("phase_shift_records", ())),
        "applied_bias_records": list(parsed.get("applied_bias_records", ())),
        "matches_model_blind_qualification_transform": True,
        "full_frozen_window_covered": True,
    }


def scan_decoded(
    decoded: bytearray,
    locator: primary.ProductLocator,
    expected_header: Mapping[str, object],
) -> primary.StationMeasurement:
    reader = rinex._LineReader(decoded)
    try:
        header_lines = rinex._read_header(reader)
        parsed = headers.parse_header_lines(header_lines)
    except (rinex.QualificationFailure, headers.HeaderAdmissionError) as exc:
        raise primary.PrimaryMeasurementInvalid(
            f"HEADER_INVALID:{locator.station}:{exc}"
        ) from exc
    except Exception as exc:
        raise IndependentPairExecutorError(
            f"HEADER_DESCRIPTION_ERROR:{locator.station}:{type(exc).__name__}:{exc}"
        ) from exc
    header = _validate_header(parsed, locator, expected_header)
    system_types = {
        system: tuple(values) for system, values in parsed["observable_types"].items()
    }
    gps_types = system_types["G"]
    indices = {
        observable: gps_types.index(observable)
        for observable in CORE_PHASE + SAME_PATH_CODE
    }
    records, flags = parser_kernel._read_window_records(reader, system_types)
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
                        f"{structural.format_gps_epoch(epoch)}:{satellite}:{observable}"
                    )
                field = record.fields[field_index]
                if not field[:14].strip():
                    counts["BLANK"] += 1
                    raise primary.PrimaryMeasurementInvalid(
                        f"FIELD_BLANK:{locator.station}:"
                        f"{structural.format_gps_epoch(epoch)}:{satellite}:{observable}"
                    )
                lli = rinex._parse_lli(field)
                if lli != "ZERO_OR_BLANK":
                    raise primary.PrimaryMeasurementInvalid(
                        f"NONZERO_OR_INVALID_LLI:{locator.station}:"
                        f"{structural.format_gps_epoch(epoch)}:{satellite}:"
                        f"{observable}:{lli}"
                    )
                try:
                    phase_cycles[row, satellite_index, phase_index] = (
                        rinex._parse_phase(field)
                    )
                except rinex.QualificationFailure as exc:
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
    if tuple(scan.station for scan in scans) != tuple(item.station for item in PRODUCTS):
        raise primary.PrimaryMeasurementInvalid("PRIMARY_STATION_ORDER_CHANGED")
    if not all(np.all(scan.core_valid) for scan in scans):
        raise primary.PrimaryMeasurementInvalid("CORE_PHASE_WINDOW_INCOMPLETE")
    code_links: list[dict[str, object]] = []
    code_passed = True
    required = np.asarray(frozen.CODE_REQUIRED_RAW_INDICES, dtype=np.int64)
    for scan in scans:
        for satellite_index, satellite in enumerate(SATELLITES):
            for code_index, observable in enumerate(SAME_PATH_CODE):
                present = scan.code_present[:, satellite_index, code_index]
                fraction = float(np.count_nonzero(present) / frozen.RAW_EPOCHS)
                boundary = bool(np.all(present[required]))
                accepted = (
                    fraction >= frozen.CODE_MINIMUM_COVERAGE_FRACTION and boundary
                )
                code_passed = code_passed and accepted
                code_links.append(
                    {
                        "station": scan.station,
                        "satellite": satellite,
                        "observable": observable,
                        "coverage_fraction": fraction,
                        "required_indices_present": boundary,
                        "state": "SATISFIED" if accepted else "UNSATISFIED",
                    }
                )
    if not code_passed:
        failed = next(row for row in code_links if row["state"] == "UNSATISFIED")
        raise primary.PrimaryMeasurementInvalid(
            "SAME_PATH_CODE_WITNESS_FAILED:"
            f"{failed['station']}:{failed['satellite']}:{failed['observable']}"
        )
    health = primary._geometry_free_health(scans)
    if health["state"] != "SATISFIED":
        failed = next(row for row in health["links"] if row["violations"] > 0)
        raise primary.PrimaryMeasurementInvalid(
            "GEOMETRY_FREE_PHASE_HEALTH_FAILED:"
            f"{failed['station']}:{failed['satellite']}:"
            f"{failed['maximum_absolute_second_difference_m']}"
        )
    alpha, beta = frozen.plan()["coordinate"]["ionosphere_free_coefficients"]
    station_coordinates: list[np.ndarray] = []
    for scan in scans:
        phase_m = np.empty((frozen.RAW_EPOCHS, 2), dtype=np.float64)
        for satellite_index in range(2):
            phase_m[:, satellite_index] = (
                float(alpha)
                * scan.phase_cycles[:, satellite_index, 0]
                * primary.LAMBDA_L1_M
                + float(beta)
                * scan.phase_cycles[:, satellite_index, 1]
                * primary.LAMBDA_L2_M
            )
        station_coordinates.append(phase_m[:, 0] - phase_m[:, 1])
        phase_m.fill(0.0)
    coordinate = (station_coordinates[0] - station_coordinates[1])[1:-1]
    for values in station_coordinates:
        values.fill(0.0)
    if coordinate.shape != (frozen.FEATURE_EPOCHS,) or not np.all(
        np.isfinite(coordinate)
    ):
        coordinate.fill(0.0)
        raise primary.PrimaryMeasurementInvalid("PRIMARY_COORDINATE_INVALID")
    admission = {
        "headers": [scan.header for scan in scans],
        "structural_counts": {
            scan.station: scan.structural_counts for scan in scans
        },
        "core_phase_and_lli": "SATISFIED",
        "same_path_code_witness": {"state": "SATISFIED", "links": code_links},
        "geometry_free_phase_health": health,
        "raw_epochs": frozen.RAW_EPOCHS,
        "feature_epochs": frozen.FEATURE_EPOCHS,
    }
    strict_json(admission)
    return coordinate, admission


def score_coordinate(
    observed_m: Sequence[float],
    curves: Mapping[str, Sequence[float]],
) -> dict[str, object]:
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
        raise IndependentPairExecutorError("FROZEN_HYPOTHESIS_CURVES_INVALID")
    orbital_projected, orbital_prefix = primary._fit_prefix(
        observed - normalized["ORBITAL_G22"]
    )
    if (
        orbital_prefix["calibration_peak_to_peak_m"]
        > ONE_MODEL_CALIBRATION_ENVELOPE_M
    ):
        orbital_projected.fill(0.0)
        result = {
            "outcome": "NOT_DETECTABLE",
            "calibration_admission": {
                "state": "UNSATISFIED",
                "limit_m": ONE_MODEL_CALIBRATION_ENVELOPE_M,
                **orbital_prefix,
            },
            "heldout_comparison": "NOT_EVALUATED",
        }
        strict_json(result)
        return result
    scores: list[dict[str, object]] = []
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
            str(row["hypothesis"]),
        )
    )
    best, runner_up = scores[:2]
    preference_margin = float(runner_up["heldout_peak_to_peak_m"]) - float(
        best["heldout_peak_to_peak_m"]
    )
    outcome = (
        PREFERRED_OUTCOMES[str(best["hypothesis"])]
        if preference_margin > frozen.SCREEN_PAIRWISE_GUARD_M
        else "AMBIGUOUS"
    )
    result = {
        "outcome": outcome,
        "calibration_admission": {
            "state": "SATISFIED",
            "limit_m": ONE_MODEL_CALIBRATION_ENVELOPE_M,
            **orbital_prefix,
        },
        "heldout_comparison": {
            "state": "EVALUATED",
            "preference_guard_m": frozen.SCREEN_PAIRWISE_GUARD_M,
            "best_hypothesis": best["hypothesis"],
            "runner_up_hypothesis": runner_up["hypothesis"],
            "preference_margin_m": preference_margin,
            "scores": scores,
        },
    }
    strict_json(result)
    return result


def build_executor_seal(root: Path) -> dict[str, object]:
    curves, headers_by_station = validate_frozen_inputs(root)
    try:
        result = {
            "schema": "gnss-independent-pair-primary-executor-seal-v1",
            "state": "PRIMARY_EXECUTOR_FROZEN_OBSERVATION_UNOPENED",
            "source_commit": _git_commit(),
            "source_sha256": source_sha256(),
            "manifest_sha256": manifest_sha256(),
            "dependencies": primary.dependency_versions(),
            "plan_manifest_sha256": frozen.manifest_sha256(),
            "plan_document_sha256": PLAN_DOCUMENT_SHA256,
            "prediction_sha256": PREDICTIONS_SHA256,
            "prediction_seal_sha256": PREDICTION_SEAL_SHA256,
            "qualification_outcome_sha256": frozen.QUALIFICATION_OUTCOME_SHA256,
            "qualification_summary_sha256": QUALIFICATION_SUMMARY_SHA256,
            "qualified_header_transform_sha256": sha256(
                strict_json(headers_by_station).encode("ascii")
            ).hexdigest(),
            "products": executor_manifest()["products"],
            "authority": {
                "expected_executor_seal_sha256_must_be_supplied": True,
                "live_execution_authorized_by_seal": False,
            },
            "access_at_seal": frozen.plan()["access_at_freeze"],
            "stop": "SEPARATE_REVIEW_BEFORE_ANY_PRIMARY_GET_OR_HEADER_ACCESS",
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
) -> tuple[
    Mapping[str, object],
    dict[str, np.ndarray],
    dict[str, Mapping[str, object]],
]:
    if (
        len(expected_seal_sha256) != 64
        or canonical_sha256(seal_path) != expected_seal_sha256
    ):
        raise IndependentPairExecutorError("EXECUTOR_SEAL_SHA256_MISMATCH")
    seal = json.loads(
        Path(seal_path).read_text(encoding="utf-8"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    if seal.get("state") != "PRIMARY_EXECUTOR_FROZEN_OBSERVATION_UNOPENED":
        raise IndependentPairExecutorError("EXECUTOR_SEAL_STATE_CHANGED")
    if seal.get("source_sha256") != source_sha256():
        raise IndependentPairExecutorError("EXECUTOR_SOURCE_CHANGED")
    if seal.get("manifest_sha256") != manifest_sha256():
        raise IndependentPairExecutorError("EXECUTOR_MANIFEST_CHANGED")
    if seal.get("dependencies") != primary.dependency_versions():
        raise IndependentPairExecutorError("EXECUTOR_DEPENDENCIES_CHANGED")
    if seal.get("plan_manifest_sha256") != frozen.manifest_sha256():
        raise IndependentPairExecutorError("EXECUTOR_PLAN_BINDING_CHANGED")
    if seal.get("plan_document_sha256") != PLAN_DOCUMENT_SHA256:
        raise IndependentPairExecutorError("EXECUTOR_PLAN_DOCUMENT_CHANGED")
    if seal.get("prediction_sha256") != PREDICTIONS_SHA256:
        raise IndependentPairExecutorError("EXECUTOR_PREDICTION_CHANGED")
    if seal.get("prediction_seal_sha256") != PREDICTION_SEAL_SHA256:
        raise IndependentPairExecutorError("EXECUTOR_PREDICTION_SEAL_CHANGED")
    if seal.get("qualification_outcome_sha256") != frozen.QUALIFICATION_OUTCOME_SHA256:
        raise IndependentPairExecutorError("QUALIFICATION_OUTCOME_BINDING_CHANGED")
    if seal.get("qualification_summary_sha256") != QUALIFICATION_SUMMARY_SHA256:
        raise IndependentPairExecutorError("QUALIFICATION_SUMMARY_BINDING_CHANGED")
    if seal.get("products") != executor_manifest()["products"]:
        raise IndependentPairExecutorError("EXECUTOR_PRODUCT_LOCATORS_CHANGED")
    access = seal.get("access_at_seal", {})
    if not isinstance(access, Mapping) or any(
        int(access.get(field, -1)) != 0
        for field in (
            "observation_headers_opened",
            "observation_payload_bytes",
            "observation_values",
        )
    ):
        raise IndependentPairExecutorError("EXECUTOR_SEAL_USED_OBSERVATIONS")
    curves, expected_headers = validate_frozen_inputs(root)
    if seal.get("qualified_header_transform_sha256") != sha256(
        strict_json(expected_headers).encode("ascii")
    ).hexdigest():
        for curve in curves.values():
            curve.fill(0.0)
        raise IndependentPairExecutorError("QUALIFIED_HEADER_TRANSFORM_CHANGED")
    return seal, curves, expected_headers


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
        raise PermissionError("ALGO_MDO_DOY219_PRIMARY_AUTHORITY_REQUIRED")
    output_path = Path(output_directory) / OUTCOME_NAME
    if output_path.exists():
        raise PermissionError("PRIMARY_OUTCOME_ALREADY_EXISTS")
    root = Path(__file__).resolve().parent
    seal, curves, expected_headers = validate_executor_seal(
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
            rinex_payload = primary.decode_in_memory(payload, locator.station)
            decoded.append(rinex_payload)
            scans.append(
                scan_decoded(
                    rinex_payload,
                    locator,
                    expected_headers[locator.station],
                )
            )
        coordinate, admission = measurement_coordinate(scans)
        try:
            score = score_coordinate(coordinate, curves)
        finally:
            coordinate.fill(0.0)
        outcome = {
            "schema": "gnss-independent-pair-primary-outcome-v1",
            "executor_version": EXECUTOR_VERSION,
            "outcome": score["outcome"],
            "executor_seal_sha256": expected_seal_sha256,
            "source_commit": seal["source_commit"],
            "source_sha256": seal["source_sha256"],
            "plan_manifest_sha256": frozen.manifest_sha256(),
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
                "fallback_or_reserve": False,
            },
            "claim_scope": (
                "DISTINCT_ROOT_HELDOUT_G22_G30_MODEL_PREFERENCE_FOR_"
                "ALGO_MDO_DOY219"
                if score["outcome"] == "ORBITAL_MODEL_PREDICTIVELY_PREFERRED"
                else "NO_POSITIVE_DISTINCT_ROOT_ORBITAL_CLAIM"
            ),
        }
    except primary.PrimaryMaterializationError as exc:
        outcome = {
            "schema": "gnss-independent-pair-primary-outcome-v1",
            "executor_version": EXECUTOR_VERSION,
            "execution_state": "PRIMARY_ARTIFACT_MATERIALIZATION_FAILED",
            "physical_outcome": None,
            "reason": str(exc),
            "artifacts": artifacts,
            "heldout_comparison": "NOT_EVALUATED",
            "observation_values_persisted": 0,
        }
    except (primary.PrimaryMeasurementInvalid, rinex.QualificationFailure) as exc:
        outcome = {
            "schema": "gnss-independent-pair-primary-outcome-v1",
            "executor_version": EXECUTOR_VERSION,
            "outcome": "MEASUREMENT_INVALID",
            "reason": str(exc),
            "artifacts": artifacts,
            "heldout_comparison": "NOT_EVALUATED",
            "observation_values_persisted": 0,
        }
    except Exception as exc:
        outcome = {
            "schema": "gnss-independent-pair-primary-outcome-v1",
            "executor_version": EXECUTOR_VERSION,
            "execution_state": "PRIMARY_DESCRIPTION_ERROR",
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
