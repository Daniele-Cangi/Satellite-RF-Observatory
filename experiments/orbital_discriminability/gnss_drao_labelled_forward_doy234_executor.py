"""Source-specific offline executor for the frozen DRAO DOY234 proof.

This final-shortlist executor incorporates the RINEX 3.04 reference-signal
blank phase-shift state before any DOY234 observation selection.  It reuses
only already tested numerical primitives from the concluded DOY238 executor;
it has no locator, transport, fallback or generic experiment abstraction.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from typing import Final, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import (
    gnss_drao_labelled_forward_doy234_plan as frozen,
)
from experiments.orbital_discriminability import (
    gnss_drao_labelled_forward_doy238_executor as prior,
)
from experiments.orbital_discriminability import gnss_observation_header as headers
from experiments.orbital_discriminability import (
    gnss_phase_short_window_qualification as rinex,
)
from experiments.orbital_discriminability import gnss_structural_qualification as structural


VERSION: Final = "drao-labelled-forward-doy234-executor-v1"
PLAN_SHA256: Final = "5dca953372dbd2fed07f6750bd3ef029989a5b33b9734ec40c4c7e274482c06c"
BUNDLE_SHA256: Final = "fbbffed1dbae0baa251813893d6dc4e50a4140f74c59829efb4dbd46d8122c50"
ENVELOPE_SHA256: Final = "c608c753cbdbf757f8eaeda31d4e647eeef688a147700820af2c0be1e2cdc47d"
SELECTION_NAME: Final = "GNSS_DRAO_LABELLED_FORWARD_DOY234_ARTIFACT_SELECTION.json"
ONE_MODEL_BOUND_M: Final = 3_964.157666752234

REFERENCE_BLANK: Final = "REFERENCE_SIGNAL_BLANK_CORRECTION"
EXPLICIT: Final = "EXPLICIT_NUMERIC_CORRECTION"
UNKNOWN: Final = "SYSTEM_ALIGNMENT_UNKNOWN_BLANK_RECORD"


class Doy234DescriptionError(RuntimeError):
    """A prospective input, identity or transform description is invalid."""


class Doy234MeasurementInvalid(ValueError):
    """The observation cannot enter the frozen physical comparison."""


ForwardScan = prior.ForwardScan


def strict_json(value: object, *, pretty: bool = False) -> str:
    return prior.strict_json(value, pretty=pretty)


def file_sha256(path: Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def source_sha256() -> str:
    return sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(
        Path(path).read_text(encoding="ascii"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    if not isinstance(value, dict):
        raise Doy234DescriptionError(f"NOT_A_JSON_OBJECT:{Path(path).name}")
    return value


def verify_frozen_inputs(root: Path) -> dict[str, str]:
    root = Path(root)
    expected = {
        frozen.PLAN_NAME: PLAN_SHA256,
        frozen.BUNDLE_NAME: BUNDLE_SHA256,
        frozen.ENVELOPE_NAME: ENVELOPE_SHA256,
    }
    actual = {name: file_sha256(root / name) for name in expected}
    if actual != expected:
        raise Doy234DescriptionError("DRAO_DOY234_FROZEN_INPUT_CHANGED")
    plan = _read_json(root / frozen.PLAN_NAME)
    candidate = plan.get("candidate", {})
    if (
        plan.get("state")
        != "DRAO_DOY234_INTEGRATED_PLAN_FROZEN_ARTIFACT_UNSELECTED"
        or candidate.get("artifact_selected") is not False
        or candidate.get("artifact_name") is not None
        or candidate.get("locator") is not None
        or candidate.get("artifact_sha256") is not None
        or candidate.get("observation_access_authorized") is not False
    ):
        raise Doy234DescriptionError("DRAO_DOY234_PLAN_SELECTION_STATE_CHANGED")
    return actual


def expected_epochs() -> tuple[datetime, ...]:
    epochs = tuple(
        frozen.GPS_START + timedelta(seconds=index * frozen.STEP_S)
        for index in range(frozen.RAW_EPOCHS)
    )
    if structural.format_gps_epoch(epochs[-1]) != "2026-08-22T06:14:00.000000Z":
        raise Doy234DescriptionError("DRAO_DOY234_GRID_CHANGED")
    return epochs


def executor_manifest(root: Path) -> dict[str, object]:
    value = {
        "schema": "gnss-drao-labelled-forward-doy234-executor-manifest-v1",
        "version": VERSION,
        "state": "DRAO_DOY234_EXECUTOR_FROZEN_ARTIFACT_UNSELECTED",
        "frozen_inputs": verify_frozen_inputs(root),
        "window": {"start_gps": structural.format_gps_epoch(expected_epochs()[0]), "stop_gps": structural.format_gps_epoch(expected_epochs()[-1]), "step_s": frozen.STEP_S, "prefix_indices": [0, 78], "heldout_indices": [79, 138]},
        "identity": {"archive_site_id": frozen.STATION, "domes": frozen.DOMES, "receiver": "SEPT_POLARX5_5.2.0", "antenna_radome": "TWIVC6050_SCIS", "marker_name": "DESCRIPTIVE_NOT_LITERAL_BINDING"},
        "phase_shift_states": {
            REFERENCE_BLANK: "VALID_OBSERVATION_CODE_WITH_BLANK_CORRECTION_IS_REFERENCE_SIGNAL",
            EXPLICIT: "VALIDATED_STORED_PHASE_ALREADY_INCLUDES_CORRECTION",
            UNKNOWN: "PRIMARY_NOT_EVALUATED",
            "MALFORMED_CONFLICT_INCOMPLETE": "PRIMARY_NOT_EVALUATED",
        },
        "required": {"prns": list(frozen.CODEBOOK), "fields": list(prior.REQUIRED_FIELDS), "normal_epochs": frozen.RAW_EPOCHS, "lli": "ZERO_OR_BLANK", "extra_tracks": "DESCRIPTIVE_NOT_FATAL_NOT_SCORED"},
        "witnesses": {"geometry_free_second_difference_limit_m": prior.GEOMETRY_FREE_LIMIT_M, "phase_minus_code_heldout_peak_to_peak_limit_m": prior.SAME_PATH_LIMIT_M, "prediction_available": False},
        "score": {"families": [prior.FAMILY_ORBITAL, prior.FAMILY_AFFINE, prior.FAMILY_REVERSED], "guard_b_m": ONE_MODEL_BOUND_M, "metric": "MAX_TRACK_HELDOUT_PEAK_TO_PEAK_M", "nuisance": "PER_TRACK_PREFIX_ONLY_CONSTANT_RATE", "heldout_refit": False, "free_time_phase": False},
        "selection": {"name": SELECTION_NAME, "present_at_freeze": False},
        "access_at_freeze": {"observation_locators": 0, "headers": 0, "payload_bytes": 0, "values": 0, "scores": 0},
        "persistence": {"observation_values": 0, "derived_series": 0, "observation_artifact": 0},
        "new_gate": False,
        "generic_framework": False,
    }
    strict_json(value)
    return value


def refuse_unselected(root: Path) -> None:
    executor_manifest(root)
    if (Path(root) / SELECTION_NAME).exists():
        raise Doy234DescriptionError("UNREVIEWED_DOY234_SELECTION_PRESENT")
    raise PermissionError("DRAO_DOY234_ARTIFACT_UNSELECTED")


def phase_shift_ledger(
    records: Sequence[str], satellites: Sequence[str]
) -> dict[str, object]:
    required: dict[str, dict[str, object]] = {}
    ignored_system_records = 0
    for raw_value in records:
        raw = raw_value.ljust(60)
        system = raw[0:1].strip()
        observable = raw[2:5].strip()
        if not system:
            raise Doy234DescriptionError("PHASE_SHIFT_MALFORMED_SYSTEM")
        if system != "G":
            ignored_system_records += 1
            continue
        if not observable:
            raise Doy234DescriptionError(UNKNOWN)
        if observable not in prior.CORE_PHASE:
            continue
        if observable in required:
            raise Doy234DescriptionError(f"PHASE_SHIFT_CONFLICT:{observable}")
        correction_token = raw[6:14].strip()
        count_token = raw[16:18].strip()
        covered = raw[19:60].split()
        if not correction_token:
            if count_token or covered or raw[14:60].strip():
                raise Doy234DescriptionError(
                    f"PHASE_SHIFT_MALFORMED_REFERENCE:{observable}"
                )
            required[observable] = {
                "state": REFERENCE_BLANK,
                "declared_correction_cycles": None,
                "affected_satellites": [],
                "stored_phase_numerically_modified_again": False,
            }
            continue
        try:
            correction = float(correction_token.replace("D", "E"))
            count = int(count_token or "0")
        except ValueError as exc:
            raise Doy234DescriptionError(
                f"PHASE_SHIFT_MALFORMED_NUMERIC:{observable}"
            ) from exc
        if not isfinite(correction) or count != len(covered):
            raise Doy234DescriptionError(
                f"PHASE_SHIFT_MALFORMED_OR_INCOMPLETE:{observable}"
            )
        unknown_satellites = sorted(set(covered) - set(satellites))
        if unknown_satellites:
            raise Doy234DescriptionError(
                f"PHASE_SHIFT_UNKNOWN_REQUIRED_SATELLITE:{observable}"
            )
        required[observable] = {
            "state": EXPLICIT,
            "declared_correction_cycles": correction,
            "affected_satellites": list(covered) if count else list(satellites),
            "unlisted_satellites_correction_cycles": 0.0,
            "stored_phase_numerically_modified_again": False,
        }
    missing = sorted(set(prior.CORE_PHASE) - set(required))
    if missing:
        raise Doy234DescriptionError(
            f"PHASE_SHIFT_REQUIRED_RECORD_MISSING:{','.join(missing)}"
        )
    return {
        "state": "TYPED_PHASE_SHIFT_LEDGER_COMPLETE",
        "required_observables": required,
        "other_system_records_ignored": ignored_system_records,
        "numerical_rule": "VALIDATE_ONLY_NEVER_APPLY_DECLARED_CORRECTION_AGAIN",
        "source": "RINEX_3_04_SECTION_5_2_12",
    }


def _normalize(value: object) -> str:
    return " ".join(str(value).replace("_", " ").split())


def _validate_header(parsed: Mapping[str, object], archive_site_id: str) -> dict[str, object]:
    if archive_site_id != frozen.STATION:
        raise Doy234DescriptionError("ARCHIVE_SITE_ID_MISMATCH")
    if not 3.0 <= float(parsed["rinex_version"]) < 4.0:
        raise Doy234DescriptionError("RINEX_VERSION_NOT_3")
    if _normalize(parsed.get("marker_number", "")) != frozen.DOMES:
        raise Doy234DescriptionError("MARKER_DOMES_MISMATCH")
    receiver = parsed["receiver"]
    antenna = parsed["antenna"]
    antenna_type = str(antenna["type"]).ljust(20)
    if _normalize(receiver["type"]) != "SEPT POLARX5" or _normalize(receiver["version_or_radome"]) != "5.2.0":
        raise Doy234DescriptionError("RECEIVER_IDENTITY_MISMATCH")
    if _normalize(antenna_type[:16]) != "TWIVC6050" or _normalize(antenna_type[16:20]) != "SCIS":
        raise Doy234DescriptionError("ANTENNA_IDENTITY_MISMATCH")
    if float(parsed["interval_s"]) != frozen.STEP_S:
        raise Doy234DescriptionError("INTERVAL_CHANGED")
    first_info = parsed["time_of_first_observation"]
    last_info = parsed["time_of_last_observation"]
    if first_info["time_system"] != "GPS" or last_info["time_system"] != "GPS":
        raise Doy234DescriptionError("TIME_SYSTEM_NOT_GPS")
    if headers.parse_utc(first_info["utc_like_epoch"]) > expected_epochs()[0] or headers.parse_utc(last_info["utc_like_epoch"]) < expected_epochs()[-1]:
        raise Doy234DescriptionError("FROZEN_WINDOW_NOT_COVERED")
    clock = int(parsed["receiver_clock_offset_applied"])
    if clock not in {0, 1}:
        raise Doy234DescriptionError("RECEIVER_CLOCK_SEMANTICS_UNKNOWN")
    gps_types = tuple(parsed["observable_types"].get("G", ()))
    missing = sorted(set(prior.REQUIRED_FIELDS) - set(gps_types))
    if missing:
        raise Doy234MeasurementInvalid(f"REQUIRED_SIGNAL_FAMILY_NOT_DECLARED:{','.join(missing)}")
    try:
        factors, scale = prior._scale_ledger(parsed.get("scale_factor_records", ()), gps_types)
    except prior.ForwardDescriptionError as exc:
        raise Doy234DescriptionError(str(exc)) from exc
    phase = phase_shift_ledger(parsed.get("phase_shift_records", ()), frozen.CODEBOOK)
    clock_state = (
        "EXPLICIT_RECORD"
        if parsed.get("receiver_clock_offset_provenance") == "EXPLICIT_HEADER_RECORD"
        else "SPEC_DEFINED_DEFAULT_ZERO"
    )
    return {
        "archive_site_id": archive_site_id,
        "marker_name": parsed.get("marker_name"),
        "marker_name_role": "DESCRIPTIVE_NOT_LITERAL_BINDING",
        "marker_number": parsed["marker_number"],
        "receiver_type": _normalize(receiver["type"]),
        "receiver_version": _normalize(receiver["version_or_radome"]),
        "antenna_type": _normalize(antenna_type[:16]),
        "antenna_radome": _normalize(antenna_type[16:20]),
        "time_of_first_observation": first_info,
        "time_of_last_observation": last_info,
        "gps_observables": list(gps_types),
        "transforms": {"scale_factor": scale, "phase_shift": phase, "receiver_clock": {"state": clock_state, "applied_flag": clock, "correction_count": "EXACTLY_ONCE"}},
        "_scale_factors": factors,
    }


def _grid_index(epoch: datetime) -> tuple[int, float]:
    elapsed = (epoch - expected_epochs()[0]).total_seconds() / frozen.STEP_S
    index = int(round(elapsed))
    if index < 0 or index >= frozen.RAW_EPOCHS:
        raise Doy234MeasurementInvalid("EVENT_TIME_OUTSIDE_FROZEN_BOUND")
    deviation = (epoch - expected_epochs()[index]).total_seconds()
    if abs(deviation) >= 15.0:
        raise Doy234MeasurementInvalid("EVENT_TIME_GRID_ASSIGNMENT_INVALID")
    return index, float(deviation)


def _read_records(reader: rinex._LineReader, system_types: Mapping[str, Sequence[str]], clock_applied: int):
    start = expected_epochs()[0] - timedelta(seconds=15)
    stop = expected_epochs()[-1] + timedelta(seconds=15)
    records = {}
    flags: dict[int, int] = {}
    deviations: dict[int, float] = {}
    clocks: dict[int, float] = {}
    while line := reader.readline():
        if not line.startswith(b">"):
            if line.strip():
                raise Doy234MeasurementInvalid("RECORD_INVALID:NON_EPOCH_LINE")
            continue
        try:
            raw_epoch, flag, count, clock = prior._parse_epoch_clock(line)
        except prior.ForwardMeasurementInvalid as exc:
            raise Doy234MeasurementInvalid(str(exc)) from exc
        correction = float(clock) if clock_applied == 0 and clock is not None else 0.0
        epoch = raw_epoch - timedelta(seconds=correction)
        grid = None
        if start <= epoch <= stop:
            grid, deviation = _grid_index(epoch)
            if grid in flags:
                raise Doy234MeasurementInvalid("RECORD_INVALID:DUPLICATE_GRID_EPOCH")
            flags[grid], deviations[grid], clocks[grid] = flag, deviation, correction
        if flag in {2, 3, 4, 5}:
            for _ in range(count):
                if not reader.readline():
                    raise Doy234MeasurementInvalid("RECORD_INVALID:TRUNCATED_SPECIAL_EVENT")
            continue
        if flag == 6:
            for _ in range(count):
                rinex._read_record(reader, system_types)
            continue
        if flag not in {0, 1}:
            raise Doy234MeasurementInvalid(f"RECORD_INVALID:EPOCH_FLAG_{flag}")
        for _ in range(count):
            try:
                satellite, record = rinex._read_record(reader, system_types)
            except rinex.QualificationFailure as exc:
                raise Doy234MeasurementInvalid(str(exc)) from exc
            if grid is None or not satellite.startswith("G"):
                continue
            key = grid, satellite
            if key in records:
                raise Doy234MeasurementInvalid("RECORD_INVALID:DUPLICATE_SATELLITE_RECORD")
            records[key] = record
    return records, flags, deviations, clocks


def scan_decoded(decoded: bytearray, *, archive_site_id: str) -> ForwardScan:
    reader = rinex._LineReader(decoded)
    try:
        parsed = headers.parse_header_lines(rinex._read_header(reader))
    except (headers.HeaderAdmissionError, rinex.QualificationFailure) as exc:
        raise Doy234DescriptionError(f"HEADER_INVALID:{exc}") from exc
    header = _validate_header(parsed, archive_site_id)
    system_types = {system: tuple(values) for system, values in parsed["observable_types"].items()}
    gps_types = system_types["G"]
    indices = {observable: gps_types.index(observable) for observable in prior.REQUIRED_FIELDS}
    records, flags, deviations, clocks = _read_records(
        reader, system_types, int(parsed["receiver_clock_offset_applied"])
    )
    shape = (frozen.RAW_EPOCHS, len(frozen.CODEBOOK), 2)
    phase = np.full(shape, np.nan)
    code = np.full(shape, np.nan)
    phase_good = np.zeros(shape, dtype=np.bool_)
    code_good = np.zeros(shape, dtype=np.bool_)
    epoch_good = np.zeros(frozen.RAW_EPOCHS, dtype=np.bool_)
    coverage = []
    scales = header.pop("_scale_factors")
    for epoch_index, epoch in enumerate(expected_epochs()):
        flag = flags.get(epoch_index)
        epoch_good[epoch_index] = flag == 0
        for satellite_index, satellite in enumerate(frozen.CODEBOOK):
            record = records.get((epoch_index, satellite))
            for observable in prior.REQUIRED_FIELDS:
                field_index = indices[observable]
                field = record.fields[field_index] if record is not None and field_index < record.field_count else None
                if record is None:
                    state, count, continuation = "FIELD_ABSENT", 0, "NOT_APPLICABLE"
                elif field_index >= record.field_count:
                    state, count, continuation = "TRAILING_FIELD_OMITTED", record.field_count, record.continuation_state
                elif not field[:14].strip():
                    state, count, continuation = "FIELD_BLANK", record.field_count, record.continuation_state
                else:
                    state, count, continuation = "PRESENT", record.field_count, record.continuation_state
                scalar = prior._finite_scalar(field)
                lli = rinex._parse_lli(field) if field is not None and observable in prior.CORE_PHASE else "NOT_APPLICABLE"
                if state == "PRESENT" and scalar is None:
                    state = "RECORD_INVALID"
                axis = (prior.CORE_PHASE if observable.startswith("L") else prior.SAME_PATH_CODE).index(observable)
                if state == "PRESENT" and flag == 0:
                    dt = clocks.get(epoch_index, 0.0)
                    value = scalar / scales[observable]
                    if observable.startswith("L") and lli == "ZERO_OR_BLANK":
                        frequency = prior.L1_HZ if observable == "L1C" else prior.L2_HZ
                        phase[epoch_index, satellite_index, axis] = value - dt * frequency
                        phase_good[epoch_index, satellite_index, axis] = True
                    elif observable.startswith("C"):
                        code[epoch_index, satellite_index, axis] = value - dt * prior.SPEED_OF_LIGHT_M_S
                        code_good[epoch_index, satellite_index, axis] = True
                coverage.append({"gps_epoch": structural.format_gps_epoch(epoch), "satellite": satellite, "observable": observable, "state": state, "header_declared_index": field_index, "reconstructed_field_count": count, "continuation_state": continuation, "lli_state": lli, "epoch_flag": flag})
    if not np.all(epoch_good):
        raise Doy234MeasurementInvalid(f"COMPLETE_NORMAL_EPOCH_COUNT_NOT_139:{int(np.count_nonzero(epoch_good))}")
    if not np.all(phase_good) or not np.all(code_good):
        raise Doy234MeasurementInvalid("REQUIRED_LABELLED_TOPOLOGY_INCOMPLETE")
    header["event_time"] = {"state": "STRUCTURALLY_MAPPED", "mapped_epochs": len(deviations), "maximum_absolute_grid_deviation_s": max(abs(value) for value in deviations.values()), "frozen_error_bound_s": [-15.0, 15.0], "receiver_clock_correction_epochs": sum(value != 0.0 for value in clocks.values())}
    header["extra_gps_tracks"] = sorted({satellite for _, satellite in records if satellite not in frozen.CODEBOOK})
    return ForwardScan(header, coverage, phase, code, phase_good, code_good, epoch_good)


def admit_model_blind(scan: ForwardScan) -> tuple[dict[str, object], np.ndarray]:
    try:
        receipt, coordinate = prior.admit_model_blind(scan)
    except prior.ForwardMeasurementInvalid as exc:
        raise Doy234MeasurementInvalid(str(exc)) from exc
    receipt["schema"] = "gnss-drao-labelled-forward-doy234-admission-v1"
    receipt["state"] = "DRAO_DOY234_MEASUREMENT_ADMITTED_FOR_FROZEN_SCORE"
    return receipt, coordinate


def _load_models(root: Path) -> dict[str, np.ndarray]:
    verify_frozen_inputs(root)
    bundle = _read_json(Path(root) / frozen.BUNDLE_NAME)
    raw = bundle.get("labelled_model_curves_m")
    if not isinstance(raw, Mapping) or set(raw) != set(frozen.CODEBOOK):
        raise Doy234DescriptionError("PREDICTION_CODEBOOK_CHANGED")
    nominal = np.column_stack([np.asarray(raw[satellite], dtype=np.float64) for satellite in frozen.CODEBOOK])
    if nominal.shape != (frozen.RAW_EPOCHS, 6) or not np.all(np.isfinite(nominal)):
        raise Doy234DescriptionError("PREDICTION_ARRAY_INVALID")
    nominal -= np.mean(nominal, axis=1, keepdims=True)
    return {prior.FAMILY_ORBITAL: nominal, prior.FAMILY_AFFINE: np.zeros_like(nominal), prior.FAMILY_REVERSED: nominal[::-1].copy()}


def score(centered_observed: np.ndarray, root: Path) -> dict[str, object]:
    if centered_observed.shape != (frozen.RAW_EPOCHS, 6) or not np.all(np.isfinite(centered_observed)):
        raise Doy234MeasurementInvalid("OBSERVED_COORDINATE_INVALID")
    models = _load_models(root)
    rows = {}
    try:
        for family, model in models.items():
            tracks = []
            for index, satellite in enumerate(frozen.CODEBOOK):
                residual = prior._prefix_affine(centered_observed[:, index] - model[:, index])
                prefix = residual[: frozen.PREFIX_EPOCHS]
                heldout = residual[frozen.PREFIX_EPOCHS :]
                tracks.append({"satellite": satellite, "prefix_peak_to_peak_m": float(np.ptp(prefix)), "heldout_peak_to_peak_m": float(np.ptp(heldout)), "heldout_rms_m": float(np.sqrt(np.mean(heldout * heldout)))})
                residual.fill(0.0)
            rows[family] = {"controlling_prefix_peak_to_peak_m": max(row["prefix_peak_to_peak_m"] for row in tracks), "controlling_heldout_peak_to_peak_m": max(row["heldout_peak_to_peak_m"] for row in tracks), "noncontrolling_heldout_rms_m": max(row["heldout_rms_m"] for row in tracks), "tracks": tracks}
        scores = {family: float(row["controlling_heldout_peak_to_peak_m"]) for family, row in rows.items()}
        ordered = sorted(scores, key=lambda family: (scores[family], family))
        best, second = ordered[:2]
        margin = scores[second] - scores[best]
        orbital_prefix = float(rows[prior.FAMILY_ORBITAL]["controlling_prefix_peak_to_peak_m"])
        orbital_heldout = scores[prior.FAMILY_ORBITAL]
        unique = margin > ONE_MODEL_BOUND_M
        if orbital_prefix > ONE_MODEL_BOUND_M:
            outcome = "NOT_DETECTABLE"
        elif unique and best == prior.FAMILY_ORBITAL and orbital_heldout <= ONE_MODEL_BOUND_M:
            outcome = "ORBITAL_MODEL_PREDICTIVELY_PREFERRED"
        elif unique and best == prior.FAMILY_AFFINE:
            outcome = "PREFIX_AFFINE_NULL_PREFERRED"
        elif unique and best == prior.FAMILY_REVERSED:
            outcome = "TIME_REVERSED_GEOMETRY_NULL_PREFERRED"
        elif orbital_heldout > ONE_MODEL_BOUND_M:
            outcome = "ORBITAL_PREDICTION_REJECTED"
        else:
            outcome = "AMBIGUOUS"
        result = {"schema": "gnss-drao-labelled-forward-doy234-score-v1", "outcome": outcome, "family_metrics": rows, "best_family": best, "preference_margin_m": float(margin), "guard_b_m": ONE_MODEL_BOUND_M, "orbital_positive_absolute_bound_satisfied": orbital_heldout <= ONE_MODEL_BOUND_M, "heldout_refit": False, "free_time_phase": False}
        strict_json(result)
        return result
    finally:
        for values in models.values():
            values.fill(0.0)


def main() -> None:
    refuse_unselected(Path(__file__).resolve().parent)


if __name__ == "__main__":
    main()
