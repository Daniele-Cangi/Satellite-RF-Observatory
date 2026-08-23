"""Bounded DOY-214 numeric development for the native-Doppler vertical.

The RINEX extractor is deliberately model-blind.  It exposes only the six
frozen Doppler/code/SNR fields for G20/G22 on the exact 493-epoch development
grid.  Navigation enters only after extraction, in the development-envelope
diagnostic.  Observation arrays and decompressed RINEX are erased in finally
paths and can never be serialized by this module.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
from typing import Final, Sequence

import hatanaka
import numpy as np

from experiments.orbital_discriminability import gnss_double_difference_envelope as envelope
from experiments.orbital_discriminability import gnss_double_difference_screen as screen
from experiments.orbital_discriminability import gnss_independent_forward_review as review
from experiments.orbital_discriminability import gnss_independent_primary_evaluator as rinex
from experiments.orbital_discriminability import gnss_native_doppler_design as design
from experiments.orbital_discriminability.gnss_observation_header import ProductAuthority


DEVELOPMENT_VERSION: Final = "gnss-kiru-mat1-native-doppler-development-v1"
PLAN_NAME: Final = "GNSS_NATIVE_DOPPLER_DEVELOPMENT_PLAN.md"
PLAN_SHA256: Final = "4d70a1d560d524bb893ad0cd9065a42cbe1d4eabb67ee4fd5f9115942ce0b459"
AUTHORITY_NAME: Final = "GNSS_NATIVE_DOPPLER_DEVELOPMENT_AUTHORITY.json"
BASE_SOURCE_COMMIT: Final = "0ad1d61e2d85e95b1a0e8f1733172e803b682d01"
ORBITALITY_MANIFEST_SHA256: Final = "2d2e713bce2d4b766410bbd0658dca4ad3926d85549682cb3f99474df80ec853"
QUALIFICATION_RECEIPT_SHA256: Final = "5e2d319ba633dce788bfa0a8b8961fa228a4b6ffd0ed47787b92c59520b37f0d"
QUALIFICATION_MANIFEST_SHA256: Final = "bcd504f9e3a0e2b70bf62ee566fdcdc6154e43a7063d6bbe8921ad2ba292210c"

TARGET: Final = "G20"
REFERENCE: Final = "G22"
SATELLITES: Final = (TARGET, REFERENCE)
STATION_IDS: Final = ("KIRU00SWE", "MAT100ITA")
OBSERVABLES: Final = ("C1C", "D1C", "S1C", "C2W", "D2W", "S2W")
DOPPLER_OBSERVABLES: Final = ("D1C", "D2W")
SNR_OBSERVABLES: Final = ("S1C", "S2W")
CODE_OBSERVABLES: Final = ("C1C", "C2W")
STEP_S: Final = 30.0
START_GPS: Final = datetime(2026, 8, 2, 15, 41, tzinfo=timezone.utc)
STOP_GPS: Final = datetime(2026, 8, 2, 19, 47, tzinfo=timezone.utc)
RUN_RECORDS: Final = 493
WINDOW_RECORDS: Final = 380
CALIBRATION_RECORDS: Final = 76
HELDOUT_RECORDS: Final = 304
WINDOW_COUNT: Final = RUN_RECORDS - WINDOW_RECORDS + 1
GPS_MINUS_UTC_S: Final = 18.0
RINEX_DOPPLER_QUANTIZATION_HZ: Final = 0.001
NAVIGATION_NAME: Final = "BRDM00DLR_S_20262140000_01D_MN.rnx"
NAVIGATION_URL: Final = (
    "https://igs.bkg.bund.de/root_ftp/IGS/BRDC/2026/214/"
    "BRDM00DLR_S_20262140000_01D_MN.rnx.gz"
)

AUTHORITIES: Final = (
    ProductAuthority(
        station_id="KIRU00SWE",
        name="KIRU00SWE_R_20262140000_01D_30S_MO.crx.gz",
        url=(
            "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/214/"
            "KIRU00SWE_R_20262140000_01D_30S_MO.crx.gz"
        ),
        bytes=5_126_492,
        sha256="06db32b758483448fa4420758a0783a1ede144e6812e794f2b5311aeef0547c0",
    ),
    ProductAuthority(
        station_id="MAT100ITA",
        name="MAT100ITA_R_20262140000_01D_30S_MO.crx.gz",
        url=(
            "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/214/"
            "MAT100ITA_R_20262140000_01D_30S_MO.crx.gz"
        ),
        bytes=4_237_763,
        sha256="3e1a55a4be23ec5a6b7c62589366f444cd0d3777a9a7ad37daad4757e28dfae2",
    ),
)


class DevelopmentError(RuntimeError):
    """The bounded software or description path failed."""


class DevelopmentMeasurementInvalid(ValueError):
    """A frozen physical measurement-admission clause failed."""


@dataclass(slots=True)
class StationDopplerRun:
    station_id: str
    epochs_gps: tuple[datetime, ...]
    values: np.ndarray

    def erase(self) -> None:
        self.values.fill(0.0)


def development_epoch_grid() -> tuple[datetime, ...]:
    epochs = tuple(
        START_GPS + timedelta(seconds=STEP_S * index)
        for index in range(RUN_RECORDS)
    )
    if epochs[-1] != STOP_GPS:
        raise RuntimeError("FROZEN_DEVELOPMENT_GRID_CHANGED")
    return epochs


def runtime_manifest() -> dict[str, object]:
    alpha, beta = envelope.ionosphere_free_coefficients()
    return {
        "development_version": DEVELOPMENT_VERSION,
        "plan": {"name": PLAN_NAME, "sha256": PLAN_SHA256},
        "authority": {
            "name": AUTHORITY_NAME,
            "base_source_commit": BASE_SOURCE_COMMIT,
        },
        "lineage": {
            "orbitality_manifest_sha256": ORBITALITY_MANIFEST_SHA256,
            "qualification_receipt_sha256": QUALIFICATION_RECEIPT_SHA256,
            "qualification_manifest_sha256": QUALIFICATION_MANIFEST_SHA256,
        },
        "extractor_code_sha256": file_sha256(Path(__file__)),
        "dependencies": {
            "hatanaka": importlib.metadata.version("hatanaka"),
            "ncompress": importlib.metadata.version("ncompress"),
            "numpy": importlib.metadata.version("numpy"),
        },
        "products": [asdict(item) for item in AUTHORITIES],
        "parameters": {
            "stations": list(STATION_IDS),
            "satellites": list(SATELLITES),
            "observables": list(OBSERVABLES),
            "start_gps": format_gps(START_GPS),
            "stop_gps": format_gps(STOP_GPS),
            "step_s": STEP_S,
            "run_records": RUN_RECORDS,
            "window_records": WINDOW_RECORDS,
            "window_count": WINDOW_COUNT,
            "calibration_records": CALIBRATION_RECORDS,
            "heldout_records": HELDOUT_RECORDS,
            "window_stride_records": 1,
            "rinex_doppler_sign": "POSITIVE_FOR_APPROACHING_SATELLITES",
            "rinex_doppler_quantization_hz": RINEX_DOPPLER_QUANTIZATION_HZ,
            "ionosphere_free_coefficients": [alpha, beta],
            "l1_equivalent_formula": "alpha*D1C+beta*(GPS_L1_HZ/GPS_L2_HZ)*D2W",
            "network_order": "(KIRU_G20-KIRU_G22)-(MAT1_G20-MAT1_G22)",
            "navigation_name": NAVIGATION_NAME,
            "navigation_url": NAVIGATION_URL,
        },
        "model_blind_extractor": True,
        "evaluation": (
            "ALL_114_WINDOWS; OBSERVED_MINUS_BROADCAST_MODEL; PREFIX_ONLY_"
            "AFFINE_76; HELDOUT_304; MAXIMUM_PEAK_TO_PEAK_PLUS_ANALYTIC_"
            "F14_3_QUANTIZATION; NO_PROBABILITY"
        ),
        "outcomes": [
            "NATIVE_DOPPLER_DEVELOPMENT_ENVELOPE_FROZEN",
            "DEVELOPMENT_MEASUREMENT_INVALID",
            "DEVELOPMENT_ERROR",
        ],
        "zero_persistence": {
            "decompressed_rinex": "RAM_BYTEARRAY_OVERWRITTEN_IN_FINALLY",
            "observation_arrays": "OVERWRITTEN_IN_FINALLY",
            "persisted_measurement_series": 0,
        },
        "forbidden": [
            "DOY215 reopening",
            "DOY219-221 artifact or header access",
            "model trajectory supplied to the extractor",
            "post-value target reference epoch window or threshold selection",
            "measurement or per-epoch derived-series persistence",
            "primary outcome or orbital claim",
        ],
    }


def runtime_manifest_sha256() -> str:
    return sha256(strict_json(runtime_manifest()).encode("ascii")).hexdigest()


def parse_plain_rinex_development(
    decoded: bytearray,
    station_id: str,
    expected_epochs: Sequence[datetime] | None = None,
) -> StationDopplerRun:
    """Decode only the frozen numeric development surface, without a model."""
    epochs = tuple(expected_epochs or development_epoch_grid())
    reader = rinex._LineReader(decoded)
    system_types, header = rinex._read_header(reader)
    _validate_header(header, station_id)
    gps_types = system_types.get("G")
    if gps_types is None or any(item not in gps_types for item in OBSERVABLES):
        raise DevelopmentMeasurementInvalid("FROZEN_GPS_SIGNAL_FAMILY_MISSING")
    selected_index = {name: gps_types.index(name) for name in OBSERVABLES}
    epoch_index = {epoch: index for index, epoch in enumerate(epochs)}
    if len(epoch_index) != len(epochs):
        raise DevelopmentError("DUPLICATE_EXPECTED_EPOCH")
    values = np.full((len(epochs), 2, len(OBSERVABLES)), np.nan, dtype=np.float64)
    try:
        _fill_run(reader, system_types, selected_index, epochs, epoch_index, values)
    except Exception:
        values.fill(0.0)
        raise
    return StationDopplerRun(station_id, epochs, values)


def _validate_header(header: dict[str, object], station_id: str) -> None:
    marker = str(header.get("marker_name", "")).upper()
    if marker not in {station_id.upper(), station_id[:4].upper()}:
        raise DevelopmentMeasurementInvalid("STATION_MARKER_MISMATCH")
    if header.get("interval_s") != STEP_S:
        raise DevelopmentMeasurementInvalid("NON_30S_HEADER_INTERVAL")
    if header.get("time_system") != "GPS":
        raise DevelopmentMeasurementInvalid("NON_GPS_OBSERVATION_TIME_SYSTEM")
    if header.get("rcv_clock_offsets_applied") != 0:
        raise DevelopmentMeasurementInvalid("RECEIVER_CLOCK_OFFSETS_APPLIED")


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
                raise DevelopmentError("AMBIGUOUS_NON_EPOCH_RECORD")
            continue
        try:
            epoch, flag, satellite_count = rinex._parse_epoch(line)
        except rinex.MeasurementInvalid as exc:
            raise DevelopmentMeasurementInvalid(str(exc)) from exc
        except rinex.PrimaryEvaluationError as exc:
            raise DevelopmentError(str(exc)) from exc
        in_window = first_expected <= epoch <= last_expected
        if in_window:
            if epoch not in epoch_index:
                raise DevelopmentMeasurementInvalid("NON_30S_EPOCH_IN_FROZEN_RUN")
            if epoch in seen_epochs:
                raise DevelopmentMeasurementInvalid("DUPLICATE_EPOCH_IN_FROZEN_RUN")
            if flag != 0:
                raise DevelopmentMeasurementInvalid("NON_OBSERVATION_EPOCH_FLAG")
            seen_epochs.add(epoch)
        elif epoch > last_expected:
            break
        if flag in {2, 3, 4, 5}:
            for _ in range(satellite_count):
                if not reader.readline():
                    raise DevelopmentError("TRUNCATED_SPECIAL_EVENT_RECORD")
            continue
        if flag not in {0, 1, 6}:
            raise DevelopmentError(f"UNSUPPORTED_EPOCH_FLAG:{flag}")
        for _ in range(satellite_count):
            try:
                satellite, fields = rinex._read_satellite_record(reader, system_types)
            except rinex.PrimaryEvaluationError as exc:
                raise DevelopmentError(str(exc)) from exc
            if not in_window or satellite not in SATELLITES:
                continue
            link = (epoch, satellite)
            if link in seen_links:
                raise DevelopmentMeasurementInvalid("DUPLICATE_TARGET_SATELLITE_RECORD")
            seen_links.add(link)
            row = epoch_index[epoch]
            satellite_index = SATELLITES.index(satellite)
            for observation_index, observable in enumerate(OBSERVABLES):
                field_index = selected_index[observable]
                if field_index >= len(fields):
                    raise DevelopmentMeasurementInvalid("MISSING_REQUIRED_OBSERVATION_FIELD")
                value = _parse_scalar(fields[field_index])
                if value is None or not np.isfinite(value):
                    raise DevelopmentMeasurementInvalid("MISSING_OR_NONFINITE_REQUIRED_OBSERVATION")
                values[row, satellite_index, observation_index] = value
    if seen_epochs != set(expected_epochs):
        raise DevelopmentMeasurementInvalid("MISSING_FROZEN_EPOCH")
    required_links = {(epoch, satellite) for epoch in expected_epochs for satellite in SATELLITES}
    if seen_links != required_links or not np.all(np.isfinite(values)):
        raise DevelopmentMeasurementInvalid("MISSING_FROZEN_LINK_OR_OBSERVABLE")


def _parse_scalar(field: bytes) -> float | None:
    text = field[:14].strip()
    if not text:
        return None
    try:
        return float(text.replace(b"D", b"E"))
    except ValueError as exc:
        raise DevelopmentMeasurementInvalid("AMBIGUOUS_OBSERVATION_SCALAR") from exc


def validate_station(run: StationDopplerRun) -> dict[str, object]:
    expected = (len(run.epochs_gps), 2, len(OBSERVABLES))
    if run.values.shape != expected or not np.all(np.isfinite(run.values)):
        raise DevelopmentMeasurementInvalid("FROZEN_ARRAY_INVALID")
    snr = run.values[:, :, [OBSERVABLES.index(item) for item in SNR_OBSERVABLES]]
    code = run.values[:, :, [OBSERVABLES.index(item) for item in CODE_OBSERVABLES]]
    if np.any(snr <= 0.0) or np.any(code <= 0.0):
        raise DevelopmentMeasurementInvalid("SAME_PATH_WITNESS_NONPOSITIVE")
    return {
        "station_id": run.station_id,
        "epoch_records": len(run.epochs_gps),
        "selected_scalar_count": int(run.values.size),
        "doppler_scalar_count": int(len(run.epochs_gps) * 2 * len(DOPPLER_OBSERVABLES)),
        "same_path_witness_scalar_count": int(len(run.epochs_gps) * 2 * (len(CODE_OBSERVABLES) + len(SNR_OBSERVABLES))),
        "snr_min_db_hz": float(np.min(snr)),
        "snr_max_db_hz": float(np.max(snr)),
        "code_min_m": float(np.min(code)),
        "code_max_m": float(np.max(code)),
        "continuity": "COMPLETE_30S_ALL_FROZEN_LINKS",
    }


def observed_coordinate(left: StationDopplerRun, right: StationDopplerRun) -> np.ndarray:
    if left.epochs_gps != right.epochs_gps:
        raise DevelopmentMeasurementInvalid("STATION_EPOCH_GRIDS_DIFFER")

    def links(run: StationDopplerRun) -> np.ndarray:
        d1 = run.values[:, :, OBSERVABLES.index("D1C")]
        d2 = run.values[:, :, OBSERVABLES.index("D2W")]
        return design.ionosphere_free_doppler_l1_equivalent(d1, d2)

    left_links = links(left)
    right_links = links(right)
    coordinate = (left_links[:, 0] - left_links[:, 1]) - (right_links[:, 0] - right_links[:, 1])
    left_links.fill(0.0)
    right_links.fill(0.0)
    if coordinate.shape != (len(left.epochs_gps),) or not np.all(np.isfinite(coordinate)):
        coordinate.fill(0.0)
        raise DevelopmentMeasurementInvalid("OBSERVED_COORDINATE_INVALID")
    return coordinate


def dispersive_witness(left: StationDopplerRun, right: StationDopplerRun) -> dict[str, float]:
    ratio = envelope.GPS_L1_HZ / envelope.GPS_L2_HZ

    def station(run: StationDopplerRun) -> np.ndarray:
        d1 = run.values[:, :, OBSERVABLES.index("D1C")]
        d2 = run.values[:, :, OBSERVABLES.index("D2W")]
        link = d1 - ratio * d2
        return link[:, 0] - link[:, 1]

    left_value = station(left)
    right_value = station(right)
    network = left_value - right_value
    result = {
        "network_peak_to_peak_hz": float(np.ptp(network)),
        "network_rms_hz": float(np.sqrt(np.mean(network * network))),
    }
    left_value.fill(0.0)
    right_value.fill(0.0)
    network.fill(0.0)
    return result


def compile_model(navigation: Path) -> tuple[np.ndarray, dict[str, object]]:
    path = Path(navigation)
    if path.name != NAVIGATION_NAME or not path.is_file():
        raise DevelopmentError("FROZEN_NAVIGATION_PRODUCT_MISSING_OR_WRONG")
    try:
        records = screen.parse_gps_navigation(path)
        if any(item not in records for item in SATELLITES):
            raise DevelopmentError("FROZEN_NAVIGATION_SATELLITE_MISSING")
        epochs_gps = development_epoch_grid()
        epochs_utc = tuple(epoch - timedelta(seconds=GPS_MINUS_UTC_S) for epoch in epochs_gps)
        stations = tuple(review.STATIONS[item] for item in STATION_IDS)
        station_ecef = {item.station_id: screen.station_to_ecef(item) for item in stations}
        fractional: dict[tuple[str, str], np.ndarray] = {}
        for satellite in SATELLITES:
            positions = design.broadcast_positions_with_gaps(records[satellite], epochs_utc)
            if not np.all(np.isfinite(positions)):
                positions.fill(0.0)
                raise DevelopmentError("STALE_NAVIGATION_INSIDE_DEVELOPMENT_RUN")
            for station in stations:
                fractional[(station.station_id, satellite)] = screen.fractional_doppler(
                    positions, station_ecef[station.station_id], STEP_S
                )
            positions.fill(0.0)
        left, right = STATION_IDS
        curve = envelope.GPS_L1_HZ * (
            (fractional[(left, TARGET)] - fractional[(left, REFERENCE)])
            - (fractional[(right, TARGET)] - fractional[(right, REFERENCE)])
        )
        if curve.shape != (RUN_RECORDS,) or not np.all(np.isfinite(curve)):
            curve.fill(0.0)
            raise DevelopmentError("MODEL_CURVE_INVALID")
        source = {
            "name": path.name,
            "bytes": path.stat().st_size,
            "sha256": file_sha256(path),
            "url": NAVIGATION_URL,
            "semantics": "BROADCAST_EPHEMERIS_MODEL_NOT_RECEIVER_OBSERVATION",
        }
        return curve, source
    except DevelopmentError:
        raise
    except Exception as exc:
        raise DevelopmentError("NAVIGATION_COMPILATION_FAILED") from exc
    finally:
        if "fractional" in locals():
            for value in fractional.values():
                value.fill(0.0)


def doppler_quantization_bound_hz() -> dict[str, float]:
    alpha, beta = envelope.ionosphere_free_coefficients()
    per_link = 0.5 * RINEX_DOPPLER_QUANTIZATION_HZ * (
        abs(alpha) + abs(beta) * envelope.GPS_L1_HZ / envelope.GPS_L2_HZ
    )
    raw_network = 4.0 * per_link
    gain = envelope.affine_projection_peak_to_peak_gain(
        WINDOW_RECORDS, CALIBRATION_RECORDS, STEP_S
    )
    return {
        "per_link_absolute_bound_hz": float(per_link),
        "raw_network_absolute_bound_hz": float(raw_network),
        "affine_projection_peak_to_peak_gain": float(gain),
        "heldout_peak_to_peak_bound_hz": float(raw_network * gain),
    }


def characterize(
    observed: Sequence[float] | np.ndarray,
    model: Sequence[float] | np.ndarray,
) -> dict[str, object]:
    measured = np.asarray(observed, dtype=np.float64)
    predicted = np.asarray(model, dtype=np.float64)
    if measured.shape != (RUN_RECORDS,) or predicted.shape != measured.shape:
        raise DevelopmentError("DEVELOPMENT_COORDINATE_GRID_CHANGED")
    if not np.all(np.isfinite(measured)) or not np.all(np.isfinite(predicted)):
        raise DevelopmentError("NONFINITE_DEVELOPMENT_COORDINATE")
    residual = measured - predicted
    rows: list[dict[str, float | int]] = []
    for start in range(WINDOW_COUNT):
        window = residual[start : start + WINDOW_RECORDS]
        projected, coefficients = design.prefix_affine_projection(window)
        heldout = projected[CALIBRATION_RECORDS:]
        rows.append(
            {
                "start_index": start,
                "heldout_peak_to_peak_hz": float(np.ptp(heldout)),
                "heldout_rms_hz": float(np.sqrt(np.mean(heldout * heldout))),
                "prefix_constant_hz": coefficients[0],
                "prefix_slope_hz_s": coefficients[1],
            }
        )
        projected.fill(0.0)
    controlling = max(rows, key=lambda item: (float(item["heldout_peak_to_peak_hz"]), -int(item["start_index"])))
    quantization = doppler_quantization_bound_hz()
    empirical = float(controlling["heldout_peak_to_peak_hz"])
    transfer = empirical + quantization["heldout_peak_to_peak_bound_hz"]
    start = int(controlling["start_index"])
    result = {
        "windows_evaluated": len(rows),
        "window_selection": "ALL_WINDOWS_MAXIMUM_NO_MEASUREMENT_SELECTED_SUBSET",
        "development_residual_peak_to_peak_hz": empirical,
        "development_residual_rms_hz_at_controlling_window": float(controlling["heldout_rms_hz"]),
        "controlling_window": {
            "start_gps": format_gps(development_epoch_grid()[start]),
            "stop_gps": format_gps(development_epoch_grid()[start + WINDOW_RECORDS - 1]),
            "prefix_constant_hz": float(controlling["prefix_constant_hz"]),
            "prefix_slope_hz_s": float(controlling["prefix_slope_hz_s"]),
        },
        "rinex_quantization": quantization,
        "provisional_future_measurement_envelope_hz": float(transfer),
        "provisional_pairwise_guard_hz": float(2.0 * transfer),
        "envelope_semantics": (
            "NONPROBABILISTIC_DEVELOPMENT_UPPER_ENVELOPE_FOR_THIS_EXACT_"
            "MEASUREMENT_PATH; FUTURE_TRANSFER_REQUIRES_FROZEN_SAME_PATH_"
            "WITNESS_ADMISSION_AND_SEPARATE_MODEL_ERROR_SCOPE"
        ),
    }
    residual.fill(0.0)
    return result


def validate_exact_artifact(path: Path, authority: ProductAuthority) -> dict[str, object]:
    path = Path(path)
    if path.name != authority.name or not path.is_file():
        raise DevelopmentError(f"ARTIFACT_MATERIALIZATION_FAILED:{authority.station_id}:IDENTITY")
    size = path.stat().st_size
    digest = file_sha256(path)
    if size != authority.bytes or digest != authority.sha256:
        raise DevelopmentError(f"ARTIFACT_MATERIALIZATION_FAILED:{authority.station_id}:HASH_OR_SIZE")
    return {"station_id": authority.station_id, "name": authority.name, "bytes": size, "sha256": digest, "verified_before_decompression": True}


def decode_exact_station(path: Path, authority: ProductAuthority) -> StationDopplerRun:
    validate_exact_artifact(path, authority)
    try:
        immutable = hatanaka.decompress(Path(path), strict=True)
    except Exception as exc:
        raise DevelopmentError(f"DECOMPRESSION_FAILED:{authority.station_id}") from exc
    decoded = bytearray(immutable)
    del immutable
    try:
        return parse_plain_rinex_development(decoded, authority.station_id)
    finally:
        decoded[:] = b"\x00" * len(decoded)


def run_once(root: Path, navigation: Path, source_commit: str) -> dict[str, object]:
    root = Path(root)
    artifact_receipts = [validate_exact_artifact(root / item.name, item) for item in AUTHORITIES]
    left: StationDopplerRun | None = None
    right: StationDopplerRun | None = None
    observed: np.ndarray | None = None
    model: np.ndarray | None = None
    try:
        left = decode_exact_station(root / AUTHORITIES[0].name, AUTHORITIES[0])
        right = decode_exact_station(root / AUTHORITIES[1].name, AUTHORITIES[1])
        health = [validate_station(left), validate_station(right)]
        witness = dispersive_witness(left, right)
        observed = observed_coordinate(left, right)
        model, navigation_source = compile_model(navigation)
        characterization = characterize(observed, model)
        result = {
            "outcome": "NATIVE_DOPPLER_DEVELOPMENT_ENVELOPE_FROZEN",
            "development_version": DEVELOPMENT_VERSION,
            "source_commit": source_commit,
            "base_source_commit": BASE_SOURCE_COMMIT,
            "runtime_manifest_sha256": runtime_manifest_sha256(),
            "runtime_manifest": runtime_manifest(),
            "artifacts": artifact_receipts,
            "navigation_source": navigation_source,
            "station_health": health,
            "dispersive_witness": witness,
            "characterization": characterization,
            "measurement_access": {
                "development_products_opened": 2,
                "compressed_development_bytes_opened": sum(item.bytes for item in AUTHORITIES),
                "epochs_decoded_per_station": RUN_RECORDS,
                "doppler_scalars_decoded": RUN_RECORDS * 2 * len(DOPPLER_OBSERVABLES) * 2,
                "same_path_witness_scalars_decoded": RUN_RECORDS * 2 * (len(CODE_OBSERVABLES) + len(SNR_OBSERVABLES)) * 2,
                "phase_scalars_decoded": 0,
                "future_observation_products_opened": 0,
                "future_observation_bytes_opened": 0,
                "persisted_observation_or_derived_series": 0,
                "decompressed_rinex_persisted_bytes": 0,
            },
            "claim_scope": "DEVELOPMENT_MEASUREMENT_PATH_CHARACTERIZATION_ONLY_NO_ORBITAL_CLAIM",
            "future_primary_frozen": False,
            "future_primary_access_authorized": False,
            "closed_doy215_reopened": False,
            "next_exact_blocker": "FREEZE_PROSPECTIVE_PRIMARY_TRANSFORM_AND_SAME_PATH_WITNESS_ADMISSION_WITH_SEPARATE_MODEL_ERROR_SCOPE",
            "new_gate_created": False,
        }
        strict_json(result)
        return result
    finally:
        if observed is not None:
            observed.fill(0.0)
        if model is not None:
            model.fill(0.0)
        if left is not None:
            left.erase()
        if right is not None:
            right.erase()


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
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float:
        if not np.isfinite(value):
            raise ValueError("NONFINITE_JSON_SCALAR")
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _validate_standard_json(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if type(key) is not str:
                raise TypeError("NONSTRING_JSON_KEY")
            _validate_standard_json(item)
        return
    raise TypeError(f"NONSTANDARD_JSON_SCALAR:{type(value).__name__}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("navigation", type=Path)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    print(strict_json(run_once(args.root, args.navigation, args.source_commit)))


if __name__ == "__main__":
    main()
