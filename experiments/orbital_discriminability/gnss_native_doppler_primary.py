"""One-shot evaluator for the frozen DOY-219 native-Doppler experiment.

The module has no network surface and grants no access authority.  Observation
identity is checked before decompression; the RINEX extractor receives no
navigation or predicted trajectory.  Only scalar receipts may be persisted.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import gzip
from hashlib import sha256
import importlib.metadata
import json
import math
from pathlib import Path
import re
from typing import Final, Sequence

import hatanaka
import numpy as np

from experiments.orbital_discriminability import gnss_double_difference_envelope as envelope
from experiments.orbital_discriminability import gnss_double_difference_screen as screen
from experiments.orbital_discriminability import gnss_independent_forward_review as review
from experiments.orbital_discriminability import gnss_independent_primary_evaluator as rinex
from experiments.orbital_discriminability import gnss_native_doppler_design as design
from experiments.orbital_discriminability import gnss_native_doppler_model_bound as model_bound
from experiments.orbital_discriminability.gnss_observation_header import ProductAuthority


EVALUATOR_VERSION: Final = "gnss-native-doppler-primary-v1"
PLAN_NAME: Final = "GNSS_NATIVE_DOPPLER_PRIMARY_PLAN.md"
PLAN_SHA256: Final = "d6a1257d1b7870f73ce27014278538222082754f5b17fef55c438cb96c9f03bb"
MODEL_BOUND_RECEIPT_NAME: Final = "GNSS_NATIVE_DOPPLER_MODEL_BOUND_RECEIPT.json"
MODEL_BOUND_RECEIPT_SHA256: Final = "cfc43f90b3c8bfacf4003d47a1c33719f6ac866caf9dfbf18c4d0f27b64023f9"
MODEL_BOUND_MANIFEST_SHA256: Final = "9d90c3a1a071c152cdb16b0514c40567deb3375f2e1d0a7c632e70efa1cbb224"
DEVELOPMENT_RECEIPT_SHA256: Final = "698c1ee3e4eeca460fc0e3b81c5373e49ee7b2d7970e45823f902b2e53d73711"

TARGET: Final = "G15"
REFERENCE: Final = "G22"
SATELLITES: Final = (TARGET, REFERENCE)
STATION_IDS: Final = ("KIRU00SWE", "MAT100ITA")
OBSERVABLES: Final = ("C1C", "D1C", "S1C", "C2W", "D2W", "S2W")
DOPPLER_OBSERVABLES: Final = ("D1C", "D2W")
CODE_OBSERVABLES: Final = ("C1C", "C2W")
SNR_OBSERVABLES: Final = ("S1C", "S2W")
HYPOTHESES: Final = ("H_ORBITAL", "H_AFFINE")
START_GPS: Final = datetime(2026, 8, 7, 16, 20, tzinfo=timezone.utc)
STOP_GPS: Final = datetime(2026, 8, 7, 19, 29, 30, tzinfo=timezone.utc)
STEP_S: Final = 30.0
RECORDS: Final = 380
CALIBRATION_RECORDS: Final = 76
HELDOUT_RECORDS: Final = 304
GPS_MINUS_UTC_S: Final = 18.0
PREFIX_MODEL_RESIDUAL_LIMIT_HZ: Final = 1.7027139799721753
DISPERSIVE_NETWORK_LIMIT_HZ: Final = 0.2717166666666344
PAIRWISE_DECISION_GUARD_HZ: Final = 2326.8486747825173
GEOMETRY_MARGIN_AFTER_CLOCK_HZ: Final = 6743.536574359732
BROADCAST_MODEL_INTERVAL_M_PER_LINK: Final = 10.608

NAVIGATION_PRODUCT: Final = model_bound.NAVIGATION_PRODUCTS[0]
PRIMARY_PRODUCTS: Final = (
    {
        "station_id": "KIRU00SWE",
        "measurement_root": "KIRU00SWE_RECEIVER_ANTENNA_CLOCK",
        "name": "KIRU00SWE_R_20262190000_01D_30S_MO.crx.gz",
    },
    {
        "station_id": "MAT100ITA",
        "measurement_root": "MAT100ITA_RECEIVER_ANTENNA_CLOCK",
        "name": "MAT100ITA_R_20262190000_01D_30S_MO.crx.gz",
    },
)
ALLOWED_PHYSICAL_OUTCOMES: Final = (
    "MEASUREMENT_INVALID",
    "NOT_DETECTABLE",
    "ORBITAL_MODEL_PREDICTIVELY_PREFERRED",
    "PREFIX_AFFINE_NULL_PREFERRED",
    "AMBIGUOUS",
)


class ArtifactMaterializationFailed(ValueError):
    """Complete observation identity was not established before decode."""


class MeasurementInvalid(ValueError):
    """A frozen physical measurement-admission clause failed."""


class PrimaryEvaluationError(RuntimeError):
    """The descriptive/software path failed without a physical decision."""


@dataclass(slots=True)
class StationRun:
    station_id: str
    epochs_gps: tuple[datetime, ...]
    values: np.ndarray

    def erase(self) -> None:
        self.values.fill(0.0)


def frozen_epoch_grid() -> tuple[datetime, ...]:
    epochs = tuple(
        START_GPS + timedelta(seconds=STEP_S * index)
        for index in range(RECORDS)
    )
    if epochs[-1] != STOP_GPS:
        raise RuntimeError("FROZEN_PRIMARY_GRID_CHANGED")
    return epochs


def runtime_manifest() -> dict[str, object]:
    alpha, beta = envelope.ionosphere_free_coefficients()
    return {
        "evaluator_version": EVALUATOR_VERSION,
        "plan": {"name": PLAN_NAME, "sha256": PLAN_SHA256},
        "lineage": {
            "development_receipt_sha256": DEVELOPMENT_RECEIPT_SHA256,
            "model_bound_receipt_sha256": MODEL_BOUND_RECEIPT_SHA256,
            "model_bound_manifest_sha256": MODEL_BOUND_MANIFEST_SHA256,
        },
        "dependencies": {
            "hatanaka": importlib.metadata.version("hatanaka"),
            "ncompress": importlib.metadata.version("ncompress"),
            "numpy": importlib.metadata.version("numpy"),
        },
        "products": {
            "observations": [dict(item) for item in PRIMARY_PRODUCTS],
            "navigation": {
                "name": NAVIGATION_PRODUCT.compressed_name,
                "bytes": NAVIGATION_PRODUCT.compressed_bytes,
                "sha256": NAVIGATION_PRODUCT.compressed_sha256,
                "decoded_name": NAVIGATION_PRODUCT.name,
                "decoded_bytes": NAVIGATION_PRODUCT.bytes,
                "decoded_sha256": NAVIGATION_PRODUCT.sha256,
            },
        },
        "parameters": {
            "stations": list(STATION_IDS),
            "satellites": list(SATELLITES),
            "observables": list(OBSERVABLES),
            "start_gps": format_gps(START_GPS),
            "stop_gps": format_gps(STOP_GPS),
            "step_s": STEP_S,
            "records": RECORDS,
            "calibration_records": CALIBRATION_RECORDS,
            "heldout_records": HELDOUT_RECORDS,
            "ionosphere_free_coefficients": [alpha, beta],
            "l1_equivalent_formula": "alpha*D1C+beta*(GPS_L1_HZ/GPS_L2_HZ)*D2W",
            "network_order": "(KIRU_G15-KIRU_G22)-(MAT1_G15-MAT1_G22)",
            "prefix_model_residual_limit_hz": PREFIX_MODEL_RESIDUAL_LIMIT_HZ,
            "dispersive_network_limit_hz": DISPERSIVE_NETWORK_LIMIT_HZ,
            "pairwise_decision_guard_hz": PAIRWISE_DECISION_GUARD_HZ,
            "broadcast_model_interval_m_per_link": BROADCAST_MODEL_INTERVAL_M_PER_LINK,
        },
        "model_blind_extractor": True,
        "hypotheses": {
            "H_ORBITAL": "EXACT_FROZEN_G15_G22_BROADCAST_CURVE",
            "H_AFFINE": "ZERO_GEOMETRIC_STRUCTURE",
            "shared_nuisance": "INDEPENDENT_CONSTANT_PLUS_SLOPE_ON_PREFIX_ONLY",
        },
        "score": "HELDOUT_RESIDUAL_PEAK_TO_PEAK_HZ",
        "claim_ceiling": "ORBITAL_MODEL_PREDICTIVELY_PREFERRED",
        "post_freeze_retry": 0,
        "network_surface": False,
        "access_authorized": False,
        "zero_persistence": {
            "observations_and_derived_series": True,
            "decompressed_rinex": "RAM_BYTEARRAY_OVERWRITTEN",
            "receipt": "STRICT_SCALARS_ONLY",
        },
    }


def runtime_manifest_sha256() -> str:
    return sha256(strict_json(runtime_manifest()).encode("ascii")).hexdigest()


def parse_plain_rinex_primary(
    decoded: bytearray,
    station_id: str,
    expected_epochs: Sequence[datetime] | None = None,
) -> StationRun:
    """Extract only D/C/S on the frozen grid; no model argument exists."""
    epochs = tuple(expected_epochs or frozen_epoch_grid())
    reader = rinex._LineReader(decoded)
    system_types, header = rinex._read_header(reader)
    _validate_header(header, station_id)
    gps_types = system_types.get("G")
    if gps_types is None or any(item not in gps_types for item in OBSERVABLES):
        raise MeasurementInvalid("FROZEN_GPS_SIGNAL_FAMILY_MISSING")
    selected_index = {name: gps_types.index(name) for name in OBSERVABLES}
    epoch_index = {epoch: index for index, epoch in enumerate(epochs)}
    if len(epoch_index) != len(epochs):
        raise PrimaryEvaluationError("DUPLICATE_EXPECTED_EPOCH")
    values = np.full((len(epochs), 2, len(OBSERVABLES)), np.nan, dtype=np.float64)
    try:
        _fill_run(reader, system_types, selected_index, epochs, epoch_index, values)
    except Exception:
        values.fill(0.0)
        raise
    return StationRun(station_id, epochs, values)


def _validate_header(header: dict[str, object], station_id: str) -> None:
    marker = str(header.get("marker_name", "")).upper()
    if marker not in {station_id.upper(), station_id[:4].upper()}:
        raise MeasurementInvalid("STATION_MARKER_MISMATCH")
    if header.get("interval_s") != STEP_S:
        raise MeasurementInvalid("NON_30S_HEADER_INTERVAL")
    if header.get("time_system") != "GPS":
        raise MeasurementInvalid("NON_GPS_OBSERVATION_TIME_SYSTEM")
    if header.get("rcv_clock_offsets_applied") != 0:
        raise MeasurementInvalid("RECEIVER_CLOCK_OFFSETS_APPLIED")


def _fill_run(
    reader: rinex._LineReader,
    system_types: dict[str, tuple[str, ...]],
    selected_index: dict[str, int],
    expected_epochs: tuple[datetime, ...],
    epoch_index: dict[datetime, int],
    values: np.ndarray,
) -> None:
    seen_epochs: set[datetime] = set()
    seen_links: set[tuple[datetime, str]] = set()
    first_expected, last_expected = expected_epochs[0], expected_epochs[-1]
    while True:
        line = reader.readline()
        if not line:
            break
        if not line.startswith(b">"):
            if line.strip():
                raise PrimaryEvaluationError("AMBIGUOUS_NON_EPOCH_RECORD")
            continue
        try:
            epoch, flag, satellite_count = rinex._parse_epoch(line)
        except rinex.MeasurementInvalid as exc:
            raise MeasurementInvalid(str(exc)) from exc
        except rinex.PrimaryEvaluationError as exc:
            raise PrimaryEvaluationError(str(exc)) from exc
        in_window = first_expected <= epoch <= last_expected
        if in_window:
            if epoch not in epoch_index:
                raise MeasurementInvalid("NON_30S_EPOCH_IN_FROZEN_RUN")
            if epoch in seen_epochs:
                raise MeasurementInvalid("DUPLICATE_EPOCH_IN_FROZEN_RUN")
            if flag != 0:
                raise MeasurementInvalid("NON_OBSERVATION_EPOCH_FLAG")
            seen_epochs.add(epoch)
        elif epoch > last_expected:
            break
        if flag in {2, 3, 4, 5}:
            for _ in range(satellite_count):
                if not reader.readline():
                    raise PrimaryEvaluationError("TRUNCATED_SPECIAL_EVENT_RECORD")
            continue
        if flag not in {0, 1, 6}:
            raise PrimaryEvaluationError(f"UNSUPPORTED_EPOCH_FLAG:{flag}")
        for _ in range(satellite_count):
            try:
                satellite, fields = rinex._read_satellite_record(reader, system_types)
            except rinex.PrimaryEvaluationError as exc:
                raise PrimaryEvaluationError(str(exc)) from exc
            if not in_window or satellite not in SATELLITES:
                continue
            link = (epoch, satellite)
            if link in seen_links:
                raise MeasurementInvalid("DUPLICATE_TARGET_SATELLITE_RECORD")
            seen_links.add(link)
            row = epoch_index[epoch]
            satellite_index = SATELLITES.index(satellite)
            for observation_index, observable in enumerate(OBSERVABLES):
                field_index = selected_index[observable]
                if field_index >= len(fields):
                    raise MeasurementInvalid("MISSING_REQUIRED_OBSERVATION_FIELD")
                value = _parse_scalar(fields[field_index])
                if value is None or not np.isfinite(value):
                    raise MeasurementInvalid("MISSING_OR_NONFINITE_REQUIRED_OBSERVATION")
                values[row, satellite_index, observation_index] = value
    if seen_epochs != set(expected_epochs):
        raise MeasurementInvalid("MISSING_FROZEN_EPOCH")
    required = {(epoch, satellite) for epoch in expected_epochs for satellite in SATELLITES}
    if seen_links != required or not np.all(np.isfinite(values)):
        raise MeasurementInvalid("MISSING_FROZEN_LINK_OR_OBSERVABLE")


def _parse_scalar(field: bytes) -> float | None:
    text = field[:14].strip()
    if not text:
        return None
    try:
        return float(text.replace(b"D", b"E"))
    except ValueError as exc:
        raise MeasurementInvalid("AMBIGUOUS_OBSERVATION_SCALAR") from exc


def validate_station(run: StationRun) -> dict[str, object]:
    expected = (RECORDS, 2, len(OBSERVABLES))
    if run.epochs_gps != frozen_epoch_grid() or run.values.shape != expected:
        raise MeasurementInvalid("FROZEN_ARRAY_OR_GRID_INVALID")
    if not np.all(np.isfinite(run.values)):
        raise MeasurementInvalid("NONFINITE_REQUIRED_OBSERVATION")
    code = run.values[:, :, [OBSERVABLES.index(item) for item in CODE_OBSERVABLES]]
    snr = run.values[:, :, [OBSERVABLES.index(item) for item in SNR_OBSERVABLES]]
    if np.any(code <= 0.0) or np.any(snr <= 0.0):
        raise MeasurementInvalid("SAME_PATH_WITNESS_NONPOSITIVE")
    return {
        "station_id": run.station_id,
        "epoch_records": RECORDS,
        "selected_scalar_count": int(run.values.size),
        "doppler_scalar_count": RECORDS * 2 * len(DOPPLER_OBSERVABLES),
        "same_path_witness_scalar_count": RECORDS * 2 * (len(CODE_OBSERVABLES) + len(SNR_OBSERVABLES)),
        "continuity": "COMPLETE_30S_ALL_FROZEN_LINKS",
        "finite": True,
        "code_and_snr_positive": True,
    }


def _l1_equivalent_links(run: StationRun) -> np.ndarray:
    d1 = run.values[:, :, OBSERVABLES.index("D1C")]
    d2 = run.values[:, :, OBSERVABLES.index("D2W")]
    return design.ionosphere_free_doppler_l1_equivalent(d1, d2)


def observed_coordinate(left: StationRun, right: StationRun) -> np.ndarray:
    if left.epochs_gps != right.epochs_gps:
        raise MeasurementInvalid("STATION_EPOCH_GRIDS_DIFFER")
    left_links = _l1_equivalent_links(left)
    right_links = _l1_equivalent_links(right)
    coordinate = (left_links[:, 0] - left_links[:, 1]) - (right_links[:, 0] - right_links[:, 1])
    left_links.fill(0.0)
    right_links.fill(0.0)
    if coordinate.shape != (RECORDS,) or not np.all(np.isfinite(coordinate)):
        coordinate.fill(0.0)
        raise MeasurementInvalid("OBSERVED_COORDINATE_INVALID")
    return coordinate


def dispersive_network_series(left: StationRun, right: StationRun) -> np.ndarray:
    ratio = envelope.GPS_L1_HZ / envelope.GPS_L2_HZ

    def station(run: StationRun) -> np.ndarray:
        d1 = run.values[:, :, OBSERVABLES.index("D1C")]
        d2 = run.values[:, :, OBSERVABLES.index("D2W")]
        links = d1 - ratio * d2
        value = links[:, 0] - links[:, 1]
        links.fill(0.0)
        return value

    left_value = station(left)
    right_value = station(right)
    result = left_value - right_value
    left_value.fill(0.0)
    right_value.fill(0.0)
    return result


def same_path_health(left: StationRun, right: StationRun) -> dict[str, object]:
    dispersive = dispersive_network_series(left, right)
    try:
        prefix_ptp = float(np.ptp(dispersive[:CALIBRATION_RECORDS]))
        heldout_ptp = float(np.ptp(dispersive[CALIBRATION_RECORDS:]))
        prefix_minima: dict[str, float] = {}
        heldout_minima: dict[str, float] = {}
        snr_ok = True
        for run in (left, right):
            for satellite_index, satellite in enumerate(SATELLITES):
                for observable in SNR_OBSERVABLES:
                    series = run.values[:, satellite_index, OBSERVABLES.index(observable)]
                    key = f"{run.station_id}:{satellite}:{observable}"
                    prefix_minima[key] = float(np.min(series[:CALIBRATION_RECORDS]))
                    heldout_minima[key] = float(np.min(series[CALIBRATION_RECORDS:]))
                    snr_ok = snr_ok and heldout_minima[key] >= prefix_minima[key]
        return {
            "prefix_dispersive_peak_to_peak_hz": prefix_ptp,
            "heldout_dispersive_peak_to_peak_hz": heldout_ptp,
            "dispersive_limit_hz": DISPERSIVE_NETWORK_LIMIT_HZ,
            "prefix_dispersive_clause": "SATISFIED" if prefix_ptp <= DISPERSIVE_NETWORK_LIMIT_HZ else "UNSATISFIED",
            "heldout_dispersive_clause": "SATISFIED" if heldout_ptp <= DISPERSIVE_NETWORK_LIMIT_HZ else "UNSATISFIED",
            "same_link_snr_non_degradation_clause": "SATISFIED" if snr_ok else "UNSATISFIED",
            "prefix_snr_minima_db_hz": prefix_minima,
            "heldout_snr_minima_db_hz": heldout_minima,
        }
    finally:
        dispersive.fill(0.0)


def compile_model(navigation_gzip: Path) -> tuple[np.ndarray, dict[str, object]]:
    path = Path(navigation_gzip)
    if path.name != NAVIGATION_PRODUCT.compressed_name or not path.is_file():
        raise PrimaryEvaluationError("FROZEN_NAVIGATION_PRODUCT_MISSING_OR_WRONG")
    compressed = bytearray(path.read_bytes())
    raw = bytearray()
    positions: dict[str, np.ndarray] = {}
    fractional: dict[tuple[str, str], np.ndarray] = {}
    try:
        if len(compressed) != NAVIGATION_PRODUCT.compressed_bytes or sha256(compressed).hexdigest() != NAVIGATION_PRODUCT.compressed_sha256:
            raise PrimaryEvaluationError("COMPRESSED_NAVIGATION_IDENTITY_MISMATCH")
        try:
            raw.extend(gzip.decompress(bytes(compressed)))
        except (OSError, EOFError) as exc:
            raise PrimaryEvaluationError("NAVIGATION_DECOMPRESSION_FAILED") from exc
        if len(raw) != NAVIGATION_PRODUCT.bytes or sha256(raw).hexdigest() != NAVIGATION_PRODUCT.sha256:
            raise PrimaryEvaluationError("DECOMPRESSED_NAVIGATION_IDENTITY_MISMATCH")
        records = model_bound.parse_all_gps_navigation(bytes(raw))
        epochs_utc = tuple(epoch - timedelta(seconds=GPS_MINUS_UTC_S) for epoch in frozen_epoch_grid())
        stations = tuple(review.STATIONS[item] for item in STATION_IDS)
        station_ecef = {station.station_id: screen.station_to_ecef(station) for station in stations}
        selection_rows: list[dict[str, object]] = []
        for satellite in SATELLITES:
            selected = [model_bound.select_latest_record(records[satellite], epoch) for epoch in epochs_utc]
            positions[satellite] = np.asarray(
                [screen.broadcast_ecef(item[0], epoch) for item, epoch in zip(selected, epochs_utc, strict=True)],
                dtype=np.float64,
            )
            selection_rows.append({
                "satellite": satellite,
                "epochs": RECORDS,
                "maximum_age_s": float(max(item[1] for item in selected)),
                "health_values": sorted({item[0].sv_health for item in selected}),
                "fit_interval_h_values": sorted({float(item[0].fit_interval_h) for item in selected}),
            })
            for station in stations:
                fractional[(station.station_id, satellite)] = screen.fractional_doppler(
                    positions[satellite], station_ecef[station.station_id], STEP_S
                )
        left, right = STATION_IDS
        curve = envelope.GPS_L1_HZ * (
            (fractional[(left, TARGET)] - fractional[(left, REFERENCE)])
            - (fractional[(right, TARGET)] - fractional[(right, REFERENCE)])
        )
        if curve.shape != (RECORDS,) or not np.all(np.isfinite(curve)):
            curve.fill(0.0)
            raise PrimaryEvaluationError("MODEL_CURVE_INVALID")
        return curve, {
            "name": NAVIGATION_PRODUCT.compressed_name,
            "bytes": len(compressed),
            "sha256": NAVIGATION_PRODUCT.compressed_sha256,
            "decoded_bytes": len(raw),
            "decoded_sha256": NAVIGATION_PRODUCT.sha256,
            "selected_ephemeris": selection_rows,
            "semantics": "BROADCAST_EPHEMERIS_MODEL_NOT_RECEIVER_OBSERVATION",
        }
    except PrimaryEvaluationError:
        raise
    except Exception as exc:
        raise PrimaryEvaluationError("NAVIGATION_COMPILATION_FAILED") from exc
    finally:
        compressed[:] = b"\x00" * len(compressed)
        raw[:] = b"\x00" * len(raw)
        for value in positions.values():
            value.fill(0.0)
        for value in fractional.values():
            value.fill(0.0)


def prefix_calibration(observed: np.ndarray, hypothesis: np.ndarray) -> dict[str, object]:
    if observed.shape != (RECORDS,) or hypothesis.shape != observed.shape:
        raise PrimaryEvaluationError("SCORE_GRID_CHANGED")
    residual = observed - hypothesis
    elapsed = np.arange(RECORDS, dtype=np.float64) * STEP_S
    matrix = np.column_stack((np.ones(CALIBRATION_RECORDS), elapsed[:CALIBRATION_RECORDS]))
    coefficients, *_ = np.linalg.lstsq(matrix, residual[:CALIBRATION_RECORDS], rcond=None)
    projected_prefix = residual[:CALIBRATION_RECORDS] - matrix @ coefficients
    result: dict[str, object] = {
        "coefficients": coefficients.copy(),
        "prefix_constant_hz": float(coefficients[0]),
        "prefix_slope_hz_s": float(coefficients[1]),
        "calibration_peak_to_peak_hz": float(np.ptp(projected_prefix)),
        "calibration_rms_hz": float(np.sqrt(np.mean(projected_prefix * projected_prefix))),
    }
    residual.fill(0.0)
    elapsed.fill(0.0)
    matrix.fill(0.0)
    coefficients.fill(0.0)
    projected_prefix.fill(0.0)
    return result


def score_hypothesis(
    observed: np.ndarray,
    hypothesis: np.ndarray,
    calibration: dict[str, object] | None = None,
) -> dict[str, float]:
    fitted = calibration or prefix_calibration(observed, hypothesis)
    coefficients = np.asarray(fitted["coefficients"], dtype=np.float64).copy()
    residual = observed - hypothesis
    elapsed = np.arange(RECORDS, dtype=np.float64) * STEP_S
    projected = residual - (coefficients[0] + coefficients[1] * elapsed)
    heldout = projected[CALIBRATION_RECORDS:]
    result = {
        "prefix_constant_hz": float(fitted["prefix_constant_hz"]),
        "prefix_slope_hz_s": float(fitted["prefix_slope_hz_s"]),
        "calibration_peak_to_peak_hz": float(fitted["calibration_peak_to_peak_hz"]),
        "calibration_rms_hz": float(fitted["calibration_rms_hz"]),
        "heldout_peak_to_peak_hz": float(np.ptp(heldout)),
        "heldout_rms_hz": float(np.sqrt(np.mean(heldout * heldout))),
    }
    coefficients.fill(0.0)
    residual.fill(0.0)
    elapsed.fill(0.0)
    projected.fill(0.0)
    if calibration is None:
        original = fitted.get("coefficients")
        if isinstance(original, np.ndarray):
            original.fill(0.0)
    return result


def evaluate_observed(
    observed: np.ndarray,
    orbital: np.ndarray,
    health: dict[str, object],
) -> tuple[str, dict[str, dict[str, float]], dict[str, float], dict[str, object]]:
    nominal = prefix_calibration(observed, orbital)
    try:
        detectability = {
            "nominal_prefix_peak_to_peak_hz": float(nominal["calibration_peak_to_peak_hz"]),
            "nominal_prefix_limit_hz": PREFIX_MODEL_RESIDUAL_LIMIT_HZ,
            "prefix_dispersive_clause": health["prefix_dispersive_clause"],
            "heldout_dispersive_clause": health["heldout_dispersive_clause"],
            "same_link_snr_non_degradation_clause": health["same_link_snr_non_degradation_clause"],
        }
        clauses_ok = (
            detectability["nominal_prefix_peak_to_peak_hz"] <= PREFIX_MODEL_RESIDUAL_LIMIT_HZ
            and all(detectability[item] == "SATISFIED" for item in (
                "prefix_dispersive_clause",
                "heldout_dispersive_clause",
                "same_link_snr_non_degradation_clause",
            ))
        )
        detectability["clause"] = "SATISFIED" if clauses_ok else "UNSATISFIED"
        if not clauses_ok:
            return "NOT_DETECTABLE", {}, {}, detectability
        affine = np.zeros_like(orbital)
        try:
            scores = {
                "H_ORBITAL": score_hypothesis(observed, orbital, nominal),
                "H_AFFINE": score_hypothesis(observed, affine),
            }
        finally:
            affine.fill(0.0)
    finally:
        coefficients = nominal.get("coefficients")
        if isinstance(coefficients, np.ndarray):
            coefficients.fill(0.0)
    margins = {
        "H_ORBITAL": float(scores["H_AFFINE"]["heldout_peak_to_peak_hz"] - scores["H_ORBITAL"]["heldout_peak_to_peak_hz"]),
        "H_AFFINE": float(scores["H_ORBITAL"]["heldout_peak_to_peak_hz"] - scores["H_AFFINE"]["heldout_peak_to_peak_hz"]),
    }
    if margins["H_ORBITAL"] > PAIRWISE_DECISION_GUARD_HZ:
        outcome = "ORBITAL_MODEL_PREDICTIVELY_PREFERRED"
    elif margins["H_AFFINE"] > PAIRWISE_DECISION_GUARD_HZ:
        outcome = "PREFIX_AFFINE_NULL_PREFERRED"
    else:
        outcome = "AMBIGUOUS"
    return outcome, scores, margins, detectability


def load_strict_json(path: Path, failure: str) -> tuple[dict[str, object], str]:
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise PrimaryEvaluationError(failure) from exc
    digest = sha256(raw).hexdigest()
    try:
        value = json.loads(raw.decode("ascii"), parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)))
    except (UnicodeError, ValueError, TypeError) as exc:
        raise PrimaryEvaluationError(failure) from exc
    if not isinstance(value, dict):
        raise PrimaryEvaluationError(failure)
    return value, digest


def verify_seal(seal_path: Path, source_path: Path) -> tuple[dict[str, object], str]:
    seal, seal_sha256 = load_strict_json(seal_path, "FROZEN_EVALUATOR_SEAL_INVALID")
    expected = {
        "schema": "gnss-native-doppler-primary-evaluator-seal-v1",
        "plan_sha256": PLAN_SHA256,
        "evaluator_source_sha256": file_sha256(source_path),
        "runtime_manifest_sha256": runtime_manifest_sha256(),
    }
    for name, value in expected.items():
        if seal.get(name) != value:
            raise PrimaryEvaluationError(f"EVALUATOR_SEAL_BINDING_CHANGED:{name}")
    if re.fullmatch(r"[0-9a-f]{40}", str(seal.get("source_commit", ""))) is None:
        raise PrimaryEvaluationError("SOURCE_COMMIT_BINDING_INVALID")
    return seal, seal_sha256


def verify_authority(
    authority_path: Path,
    seal: dict[str, object],
    seal_sha256: str,
) -> tuple[dict[str, object], str]:
    authority, authority_sha256 = load_strict_json(authority_path, "PRIMARY_ACCESS_AUTHORITY_INVALID")
    expected = {
        "schema": "gnss-native-doppler-primary-access-authority-v1",
        "state": "PRIMARY_ACCESS_AUTHORIZED",
        "plan_sha256": PLAN_SHA256,
        "prospective_markdown_sha256": PLAN_SHA256,
        "evaluator_seal_sha256": seal_sha256,
        "evaluator_source_sha256": seal["evaluator_source_sha256"],
        "source_commit": seal["source_commit"],
        "single_run": True,
        "products": [item["name"] for item in PRIMARY_PRODUCTS],
    }
    for name, value in expected.items():
        if authority.get(name) != value:
            raise PrimaryEvaluationError(f"PRIMARY_ACCESS_AUTHORITY_BINDING_CHANGED:{name}")
    return authority, authority_sha256


def validate_materialization(
    receipt_path: Path,
    product_paths: dict[str, Path],
    seal_sha256: str,
    authority_sha256: str,
) -> tuple[tuple[ProductAuthority, ...], str]:
    try:
        receipt, receipt_sha256 = load_strict_json(receipt_path, "PRIMARY_MATERIALIZATION_RECEIPT_INVALID")
    except PrimaryEvaluationError as exc:
        raise ArtifactMaterializationFailed(str(exc)) from exc
    required = {
        "schema": "gnss-native-doppler-primary-materialization-v1",
        "state": "PRIMARY_ARTIFACTS_MATERIALIZED",
        "plan_sha256": PLAN_SHA256,
        "evaluator_seal_sha256": seal_sha256,
        "authority_receipt_sha256": authority_sha256,
        "hashes_completed_before_decompression": True,
    }
    for name, value in required.items():
        if receipt.get(name) != value:
            raise ArtifactMaterializationFailed(f"PRIMARY_MATERIALIZATION_BINDING_CHANGED:{name}")
    entries = receipt.get("artifacts")
    if not isinstance(entries, list) or len(entries) != len(PRIMARY_PRODUCTS):
        raise ArtifactMaterializationFailed("PRIMARY_MATERIALIZATION_ARTIFACTS_INVALID")
    by_station = {item.get("station_id"): item for item in entries if isinstance(item, dict)}
    authorities: list[ProductAuthority] = []
    for spec in PRIMARY_PRODUCTS:
        station_id = str(spec["station_id"])
        entry = by_station.get(station_id)
        path = Path(product_paths[station_id])
        if not isinstance(entry, dict):
            raise ArtifactMaterializationFailed(f"MATERIALIZATION_STATION_MISSING:{station_id}")
        digest = entry.get("sha256")
        byte_count = entry.get("bytes")
        if type(byte_count) is not int or byte_count <= 0 or not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ArtifactMaterializationFailed(f"MATERIALIZATION_IDENTITY_INVALID:{station_id}")
        if entry.get("name") != spec["name"] or path.name != spec["name"] or not path.is_file():
            raise ArtifactMaterializationFailed(f"PRIMARY_PRODUCT_IDENTITY_CHANGED:{station_id}")
        if path.stat().st_size != byte_count or file_sha256(path) != digest:
            raise ArtifactMaterializationFailed(f"PRIMARY_COMPLETE_HASH_CHANGED:{station_id}")
        authorities.append(ProductAuthority(station_id, str(spec["name"]), "SEALED_PRODUCT_NO_NETWORK_SURFACE", byte_count, digest))
    if len(by_station) != len(PRIMARY_PRODUCTS):
        raise ArtifactMaterializationFailed("PRIMARY_MATERIALIZATION_PRODUCT_SET_CHANGED")
    return tuple(authorities), receipt_sha256


def decode_exact_station(path: Path, authority: ProductAuthority) -> StationRun:
    try:
        immutable = hatanaka.decompress(Path(path), strict=True)
    except Exception as exc:
        raise PrimaryEvaluationError(f"HATANAKA_DECODING_FAILED:{authority.station_id}") from exc
    decoded = bytearray(immutable)
    del immutable
    try:
        return parse_plain_rinex_primary(decoded, authority.station_id)
    finally:
        decoded[:] = b"\x00" * len(decoded)


def claim_scope(outcome: str) -> dict[str, object]:
    compared = outcome in {
        "ORBITAL_MODEL_PREDICTIVELY_PREFERRED",
        "PREFIX_AFFINE_NULL_PREFERRED",
        "AMBIGUOUS",
    }
    return {
        "authorized": "FROZEN_ORBITAL_VERSUS_AFFINE_COMPARISON" if compared else "MEASUREMENT_PATH_OUTCOME_ONLY",
        "not_authorized": [
            "SATELLITE_IDENTITY",
            "SPECIFIC_ORBIT_IDENTITY",
            "ORBIT_RECONSTRUCTION",
            "REPEATED_PASS_GENERALIZATION",
            "CLAIM_OUTSIDE_KIRU_MAT1_G15_G22_DOY219_COORDINATE",
        ],
    }


def materialization_failure_receipt(reason: str, seal_sha256: str, authority_sha256: str) -> dict[str, object]:
    return {
        "schema": "gnss-native-doppler-primary-premeasurement-outcome-v1",
        "plan_sha256": PLAN_SHA256,
        "evaluator_seal_sha256": seal_sha256,
        "authority_receipt_sha256": authority_sha256,
        "outcome": "ARTIFACT_MATERIALIZATION_FAILED",
        "reason": reason,
        "physical_decision": "NOT_EVALUATED",
        "decompression_started": False,
        "clauses": {
            "artifact_materialization": "UNSATISFIED",
            "measurement_admission": "NOT_EVALUATED",
            "prefix_detectability": "NOT_EVALUATED",
            "heldout_health": "NOT_EVALUATED",
            "heldout_model_comparison": "NOT_EVALUATED",
        },
        "claims": claim_scope("MEASUREMENT_INVALID"),
        "retry": "SAME_PRODUCTS_TRANSPORT_RESUME_ONLY_BEFORE_COMPLETE_HASH_AND_DECODE",
    }


def run_once(
    kiru_path: Path,
    mat1_path: Path,
    navigation_path: Path,
    seal_path: Path,
    authority_path: Path,
    materialization_path: Path,
    output_path: Path,
) -> dict[str, object]:
    """Execute the sealed comparison once; never overwrite an outcome."""
    output_path = Path(output_path)
    if output_path.exists():
        raise PrimaryEvaluationError("PRIMARY_OUTPUT_ALREADY_EXISTS")
    seal, seal_sha256 = verify_seal(seal_path, Path(__file__))
    _, authority_sha256 = verify_authority(authority_path, seal, seal_sha256)
    try:
        authorities, materialization_sha256 = validate_materialization(
            materialization_path,
            {"KIRU00SWE": Path(kiru_path), "MAT100ITA": Path(mat1_path)},
            seal_sha256,
            authority_sha256,
        )
    except ArtifactMaterializationFailed as exc:
        receipt = materialization_failure_receipt(str(exc), seal_sha256, authority_sha256)
        write_receipt_exclusive(output_path, receipt)
        return receipt
    orbital: np.ndarray | None = None
    observed: np.ndarray | None = None
    runs: list[StationRun] = []
    decompression_started = False
    try:
        orbital, navigation = compile_model(navigation_path)
        try:
            decompression_started = True
            left = decode_exact_station(kiru_path, authorities[0])
            runs.append(left)
            right = decode_exact_station(mat1_path, authorities[1])
            runs.append(right)
            station_health = [validate_station(run) for run in runs]
            health = same_path_health(left, right)
            observed = observed_coordinate(left, right)
            outcome, scores, margins, detectability = evaluate_observed(observed, orbital, health)
            receipt: dict[str, object] = {
                "schema": "gnss-native-doppler-primary-outcome-v1",
                "plan_sha256": PLAN_SHA256,
                "evaluator_seal": {
                    "sha256": seal_sha256,
                    "source_commit": seal["source_commit"],
                    "evaluator_source_sha256": seal["evaluator_source_sha256"],
                    "runtime_manifest_sha256": seal["runtime_manifest_sha256"],
                },
                "authority_receipt_sha256": authority_sha256,
                "materialization_receipt_sha256": materialization_sha256,
                "artifacts": [
                    {"station_id": item.station_id, "name": item.name, "bytes": item.bytes, "sha256": item.sha256}
                    for item in authorities
                ],
                "navigation": navigation,
                "measurement_health": station_health,
                "same_path_health": health,
                "records": RECORDS,
                "calibration_records": CALIBRATION_RECORDS,
                "heldout_records": HELDOUT_RECORDS,
                "scores": scores,
                "preference_margins_hz": margins,
                "pairwise_decision_guard_hz": PAIRWISE_DECISION_GUARD_HZ,
                "detectability": detectability,
                "clauses": {
                    "artifact_hashes": "SATISFIED",
                    "measurement_admission": "SATISFIED",
                    "prefix_detectability": detectability["clause"],
                    "heldout_health": detectability["clause"],
                    "heldout_model_comparison": "NOT_EVALUATED" if outcome == "NOT_DETECTABLE" else "EVALUATED",
                },
                "outcome": outcome,
                "claims": claim_scope(outcome),
                "decompression_started": decompression_started,
                "raw_or_derived_measurement_persisted": False,
                "alternate_run_authorized": False,
            }
        except MeasurementInvalid as exc:
            outcome = "MEASUREMENT_INVALID"
            receipt = {
                "schema": "gnss-native-doppler-primary-outcome-v1",
                "plan_sha256": PLAN_SHA256,
                "evaluator_seal_sha256": seal_sha256,
                "authority_receipt_sha256": authority_sha256,
                "materialization_receipt_sha256": materialization_sha256,
                "outcome": outcome,
                "reason": str(exc),
                "physical_decision": "MEASUREMENT_INVALID",
                "clauses": {
                    "measurement_admission": "UNSATISFIED",
                    "prefix_detectability": "NOT_EVALUATED",
                    "heldout_health": "NOT_EVALUATED",
                    "heldout_model_comparison": "NOT_EVALUATED",
                },
                "claims": claim_scope(outcome),
                "decompression_started": decompression_started,
                "raw_or_derived_measurement_persisted": False,
                "alternate_run_authorized": False,
            }
        except PrimaryEvaluationError as exc:
            outcome = "PRIMARY_EVALUATION_ERROR"
            receipt = nonphysical_error_receipt(str(exc), seal_sha256, authority_sha256, decompression_started)
        except Exception as exc:
            outcome = "PRIMARY_EVALUATION_ERROR"
            receipt = nonphysical_error_receipt(f"UNEXPECTED_EVALUATOR_FAILURE:{type(exc).__name__}", seal_sha256, authority_sha256, decompression_started)
        if outcome not in ALLOWED_PHYSICAL_OUTCOMES and outcome != "PRIMARY_EVALUATION_ERROR":
            raise PrimaryEvaluationError("NON_FROZEN_TERMINAL_OUTCOME")
        strict_json(receipt)
        write_receipt_exclusive(output_path, receipt)
        return receipt
    finally:
        for run in runs:
            run.erase()
        if observed is not None:
            observed.fill(0.0)
        if orbital is not None:
            orbital.fill(0.0)


def nonphysical_error_receipt(reason: str, seal_sha256: str, authority_sha256: str, decompression_started: bool) -> dict[str, object]:
    return {
        "schema": "gnss-native-doppler-primary-nonphysical-outcome-v1",
        "plan_sha256": PLAN_SHA256,
        "evaluator_seal_sha256": seal_sha256,
        "authority_receipt_sha256": authority_sha256,
        "outcome": "PRIMARY_EVALUATION_ERROR",
        "reason": reason,
        "physical_decision": "NOT_EVALUATED",
        "clauses": {
            "measurement_admission": "NOT_EVALUATED",
            "prefix_detectability": "NOT_EVALUATED",
            "heldout_health": "NOT_EVALUATED",
            "heldout_model_comparison": "NOT_EVALUATED",
        },
        "decompression_started": decompression_started,
        "raw_or_derived_measurement_persisted": False,
        "alternate_run_authorized": False,
    }


def write_receipt_exclusive(path: Path, receipt: dict[str, object]) -> None:
    payload = strict_json(receipt) + "\n"
    with Path(path).open("x", encoding="ascii", newline="\n") as stream:
        stream.write(payload)


def format_gps(value: datetime) -> str:
    return f"{value.isoformat(timespec='seconds').replace('+00:00', '')} GPS"


def file_sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def strict_json(value: object) -> str:
    _validate_standard_json(value)
    return json.dumps(value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _validate_standard_json(value: object) -> None:
    if isinstance(value, np.generic):
        raise TypeError("NUMPY_SCALAR_NOT_ALLOWED_IN_RECEIPT")
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("NONFINITE_SCALAR_NOT_ALLOWED_IN_RECEIPT")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if type(key) is not str:
                raise TypeError("NON_STRING_JSON_KEY")
            _validate_standard_json(item)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _validate_standard_json(item)
        return
    raise TypeError(f"NON_STANDARD_JSON_VALUE:{type(value).__name__}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kiru", type=Path, required=True)
    parser.add_argument("--mat1", type=Path, required=True)
    parser.add_argument("--navigation", type=Path, required=True)
    parser.add_argument("--seal", type=Path, required=True)
    parser.add_argument("--authority", type=Path, required=True)
    parser.add_argument("--materialization", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = run_once(args.kiru, args.mat1, args.navigation, args.seal, args.authority, args.materialization, args.output)
    print(strict_json(receipt))


if __name__ == "__main__":
    main()
