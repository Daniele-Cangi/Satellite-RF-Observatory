"""Bounded header-only evaluation of exactly two Cassini DSS-14 products.

Only disjoint 260-byte SFDU header ranges are requested. A non-range response
is closed before its body is read. No IQ/sample or amplitude value exists in
this module, which stops after a real-NCO affine-null ranking.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from math import ceil, isfinite, sqrt
from pathlib import Path
import re
from typing import Final, Iterator, Mapping, Sequence
import urllib.request

import numpy as np

from experiments.orbital_discriminability import cassini_dss26_one_way as one_way
from experiments.orbital_discriminability.cassini_dss14_header_candidates import (
    CANDIDATES,
    CassiniDss14HeaderReceipt,
    HeaderCandidateRole,
    RSR_HEADER_BYTES,
    RSR_RECORD_BYTES,
    parse_candidate_header,
    parser_manifest_sha256,
    strict_json,
)


EVALUATION_VERSION: Final = "cassini-dss14-bounded-header-evaluation-v1"
CALIBRATION_FRACTION: Final = 0.2
REPRESENTATIVE_SAMPLE_OFFSET_S: Final = 0.5005
SCREENING_REST_FREQUENCY_HZ: Final = 8_425_000_000.0
DSS26_REFERENCE_AFFINE_P2P_HZ: Final = 0.06391264328448062
HEADER_RANGES_PER_REQUEST: Final = 100
USER_AGENT: Final = "Satellite-RF-Observatory-DSS14-header-only/1"
DATA_URLS: Final = {
    "HEADER_CANDIDATE_A": (
        "https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-sagr/"
        "data-rsr01/2006/s23sags2006_251_1200nnnx14rd.dat"
    ),
    "HEADER_CANDIDATE_B": (
        "https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-sagr/"
        "data-rsr01/2005/s10sags2005_122_1955nnnx14rd.dat"
    ),
}


class CassiniDss14EvaluationError(RuntimeError):
    """A frozen header path or baseband compilation precondition failed."""


@dataclass(frozen=True, slots=True)
class KernelSpec:
    name: str
    bytes: int
    sha256: str
    url: str
    role: str
    independence: str


SHARED_KERNELS: Final = (
    KernelSpec(
        "naif0012.tls", 5_257,
        "678e32bdb5a744117a467cd9601cd6b373f0e9bc9bbde1371d5eee39600a039b",
        "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/lsk/naif0012.tls",
        "UTC_TO_ET_TDB", "TIME_SCALE_CONTROL",
    ),
    KernelSpec(
        "earth_720101_070426.bpc", 8_603_648,
        "1fa3670679bcd3d1978bea7653a34e68d1518f832124412c766faf454d77205e",
        "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/a_old_versions/earth_720101_070426.bpc",
        "HISTORICAL_EARTH_ORIENTATION", "POST_PASS_EOP_INDEPENDENT_OF_TARGET_RF",
    ),
    KernelSpec(
        "earthstns_itrf93_050714.bsp", 38_912,
        "371fb58d19dd757de7b31cac80b5e61d5eaa26dc3437a009eece1c47792cee5c",
        "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/stations/a_old_versions/earthstns_itrf93_050714.bsp",
        "DSS14_STATION_STATE", "STATION_MODEL_INDEPENDENT_OF_TARGET_RF",
    ),
)

TRAJECTORY_KERNELS: Final = {
    "HEADER_CANDIDATE_A": KernelSpec(
        "060901AP_SCPSE_06244_06255.bsp", 3_169_280,
        "0b7cc35d94b956602593106ed8aa62ce5f33cb178b8544036a841c5e53fc81dd",
        "https://naif.jpl.nasa.gov/pub/naif/CASSINI/kernels/spk/060901AP_SCPSE_06244_06255.bsp",
        "CASSINI_TRAJECTORY", "PREDICT_CREATED_2006_09_01_BEFORE_PASS",
    ),
    "HEADER_CANDIDATE_B": KernelSpec(
        "050426AP_SCPSE_05116_05216.bsp", 3_832_832,
        "065258e6982b10488604d97f02f9b5110d6b1e4760ff340211b50973ab8228f5",
        "https://naif.jpl.nasa.gov/pub/naif/CASSINI/kernels/spk/050426AP_SCPSE_05116_05216.bsp",
        "CASSINI_TRAJECTORY", "PREDICT_CREATED_2005_04_26_BEFORE_PASS",
    ),
}


@dataclass(frozen=True, slots=True)
class CalibrationFit:
    constant_offset_hz: float
    affine_aging_hz_s: float
    calibration_rmse_hz: float


def fetch_candidate_headers(role: HeaderCandidateRole) -> tuple[CassiniDss14HeaderReceipt, ...]:
    """Fetch every header in bounded disjoint multipart ranges, never data."""

    spec = CANDIDATES[role]
    receipts: list[CassiniDss14HeaderReceipt] = []
    for first_index in range(0, spec.record_count, HEADER_RANGES_PER_REQUEST):
        indices = tuple(range(first_index, min(first_index + HEADER_RANGES_PER_REQUEST, spec.record_count)))
        expected_ranges = tuple(
            (index * RSR_RECORD_BYTES, index * RSR_RECORD_BYTES + RSR_HEADER_BYTES - 1)
            for index in indices
        )
        request = urllib.request.Request(
            DATA_URLS[role],
            headers={
                "Range": "bytes=" + ",".join(f"{start}-{end}" for start, end in expected_ranges),
                "User-Agent": USER_AGENT,
            },
        )
        response = urllib.request.urlopen(request, timeout=60)
        try:
            parts = _read_exact_range_response(response, expected_ranges, spec.file_bytes)
        finally:
            response.close()
        for index in indices:
            key = (index * RSR_RECORD_BYTES, index * RSR_RECORD_BYTES + RSR_HEADER_BYTES - 1)
            raw = bytearray(parts.pop(key))
            try:
                receipts.append(parse_candidate_header(raw, role))
            finally:
                raw[:] = bytes(len(raw))
        if parts:
            raise CassiniDss14EvaluationError("server returned an unauthorized extra range")
    return tuple(receipts)


def _read_exact_range_response(response, expected_ranges, total_bytes: int) -> dict[tuple[int, int], bytes]:
    """Validate 206 metadata before reading; a 200 body is never touched."""

    if response.getcode() != 206:
        raise CassiniDss14EvaluationError("SERVER_IGNORED_RANGE_BODY_NOT_READ")
    content_type = response.headers.get("Content-Type", "")
    content_length_text = response.headers.get("Content-Length", "")
    if len(expected_ranges) == 1:
        start, end = expected_ranges[0]
        if not content_length_text.isdigit():
            raise CassiniDss14EvaluationError("single range lacks an exact byte count")
        content_length = int(content_length_text)
        if response.headers.get("Content-Range") != f"bytes {start}-{end}/{total_bytes}" or content_length != RSR_HEADER_BYTES:
            raise CassiniDss14EvaluationError("single range does not match the authorized header")
        body = response.read(RSR_HEADER_BYTES + 1)
        if len(body) != RSR_HEADER_BYTES:
            raise CassiniDss14EvaluationError("single header response has unexpected length")
        return {(start, end): body}
    match = re.fullmatch(r'multipart/byteranges;\s*boundary=(?:"([^"]+)"|([^;\s]+))', content_type)
    if match is None:
        raise CassiniDss14EvaluationError("multi-range response is not multipart/byteranges")
    maximum = len(expected_ranges) * (RSR_HEADER_BYTES + 512) + 512
    if content_length_text.isdigit() and int(content_length_text) > maximum:
        raise CassiniDss14EvaluationError("multipart response exceeds the header-only byte bound")
    body = response.read(maximum + 1)
    if len(body) > maximum:
        raise CassiniDss14EvaluationError("chunked multipart response exceeded the client byte cap")
    if content_length_text.isdigit() and len(body) != int(content_length_text):
        raise CassiniDss14EvaluationError("multipart response length changed during read")
    return _parse_multipart_ranges(body, match.group(1) or match.group(2), expected_ranges, total_bytes)


def _parse_multipart_ranges(body: bytes, boundary: str, expected_ranges, total_bytes: int) -> dict[tuple[int, int], bytes]:
    expected = set(expected_ranges)
    result: dict[tuple[int, int], bytes] = {}
    marker = b"--" + boundary.encode("ascii")
    for segment in body.split(marker)[1:]:
        if segment.startswith(b"--"):
            break
        if segment.startswith(b"\r\n"):
            segment = segment[2:]
        headers, separator, payload = segment.partition(b"\r\n\r\n")
        if not separator or not payload.endswith(b"\r\n"):
            raise CassiniDss14EvaluationError("malformed multipart range")
        payload = payload[:-2]
        content_range = None
        for line in headers.split(b"\r\n"):
            if line.lower().startswith(b"content-range:"):
                content_range = line.split(b":", 1)[1].strip().decode("ascii")
        match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", content_range or "")
        if match is None:
            raise CassiniDss14EvaluationError("multipart part lacks exact Content-Range")
        start, end, total = map(int, match.groups())
        key = (start, end)
        if total != total_bytes or key not in expected or key in result:
            raise CassiniDss14EvaluationError("multipart part is outside the authorized set")
        if len(payload) != RSR_HEADER_BYTES or end - start + 1 != RSR_HEADER_BYTES:
            raise CassiniDss14EvaluationError("multipart part is not exactly one SFDU header")
        result[key] = payload
    if set(result) != expected:
        raise CassiniDss14EvaluationError("multipart response omitted an authorized header")
    return result


def summarize_headers(role: HeaderCandidateRole, receipts: Sequence[CassiniDss14HeaderReceipt]) -> dict[str, object]:
    spec = CANDIDATES[role]
    if len(receipts) != spec.record_count:
        raise CassiniDss14EvaluationError("header count differs from the frozen PDS label")
    instants = [_parse_utc(receipt.first_sample_utc) for receipt in receipts]
    sequence_steps = [
        (right.record_sequence_number - left.record_sequence_number) % 65_536
        for left, right in zip(receipts, receipts[1:])
    ]
    time_steps = [(right - left).total_seconds() for left, right in zip(instants, instants[1:])]
    if receipts[0].first_sample_utc != spec.first_sample_utc or receipts[-1].first_sample_utc != spec.last_first_sample_utc:
        raise CassiniDss14EvaluationError("header endpoints differ from the frozen label")
    if any(step != 1 for step in sequence_steps) or any(step != 1.0 for step in time_steps):
        raise CassiniDss14EvaluationError("complete header grid is discontinuous")
    ordered_digest = sha256()
    for receipt in receipts:
        ordered_digest.update(strict_json(receipt.as_json_object()).encode("ascii"))
        ordered_digest.update(b"\n")
    frequency = [_finite_coefficients(receipt.frequency_polynomial.coefficients) for receipt in receipts]
    nco_boundary = [
        _polynomial(right, 0.0005) - _polynomial(left, 1.0005)
        for left, right in zip(frequency, frequency[1:])
    ]
    return {
        "role": role,
        "record_count": len(receipts),
        "ordered_whitelist_receipts_sha256": ordered_digest.hexdigest(),
        "event_time": {
            "first_sample_utc": receipts[0].first_sample_utc,
            "last_first_sample_utc": receipts[-1].first_sample_utc,
            "non_one_second_steps": sum(step != 1.0 for step in time_steps),
        },
        "record_sequence": {
            "first": receipts[0].record_sequence_number,
            "last": receipts[-1].record_sequence_number,
            "non_unit_steps": sum(step != 1 for step in sequence_steps),
        },
        "sample_resolution_bits": _unique(receipts, "sample_resolution_bits"),
        "sample_rate_hz": _unique(receipts, "sample_rate_hz"),
        "station": _unique(receipts, "station_id"),
        "rsr": _unique(receipts, "rsr_id"),
        "subchannel": _unique(receipts, "subchannel_id"),
        "rf_to_if_lo_hz": _unique(receipts, "rf_to_if_lo_hz"),
        "ddc_lo_hz": _unique(receipts, "ddc_lo_hz"),
        "frequency_override_active": _unique(receipts, "frequency_override_active"),
        "frequency_polynomial_coefficient_ranges_hz": _coefficient_ranges(frequency),
        "frequency_polynomial_maximum_absolute_boundary_residual_hz": max(abs(value) for value in nco_boundary),
        "data_chdo_policy": "NEVER_REQUESTED_NOT_READ_NOT_DECODED_NOT_REPRESENTED",
    }


def compile_candidate_signature(
    role: HeaderCandidateRole,
    receipts: Sequence[CassiniDss14HeaderReceipt],
    kernel_paths: Mapping[str, Path],
    *,
    spice,
) -> dict[str, object]:
    spec = CANDIDATES[role]
    if len(receipts) != spec.record_count:
        raise CassiniDss14EvaluationError("signature requires the complete header grid")
    factors: list[float] = []
    transmit: list[float] = []
    receive_et: list[float] = []
    nco: list[float] = []
    lo: list[float] = []
    with _loaded_exact_kernels(spice, role, kernel_paths) as lineage:
        station = one_way._spice_state_provider(spice, "DSS-14")
        cassini = one_way._spice_state_provider(spice, "CASSINI")
        for receipt in receipts:
            epoch_utc = _offset_utc(receipt.first_sample_utc, REPRESENTATIVE_SAMPLE_OFFSET_S)
            epoch_et = float(spice.utc2et(epoch_utc))
            event = one_way.solve_one_way_event(epoch_et, station, cassini)
            receive_et.append(epoch_et)
            factors.append(event.kinematic_frequency_factor)
            transmit.append(event.transmit_et_tdb_s)
            nco.append(receipt.nco_frequency_hz(REPRESENTATIVE_SAMPLE_OFFSET_S))
            lo.append(float(receipt.rf_to_if_lo_hz + receipt.ddc_lo_hz))
    split = int(ceil(len(receipts) * CALIBRATION_FRACTION))
    orbital, calibration = _calibrated_curve(factors, transmit, lo, nco, split)
    elapsed = np.asarray(receive_et, dtype=np.float64) - receive_et[0]
    affine_coefficients = _fit_affine(elapsed[:split], orbital[:split])
    affine = affine_coefficients[0] + affine_coefficients[1] * elapsed
    metrics = _difference_metrics(orbital, affine, slice(split, len(receipts)))
    result = {
        "role": role,
        "lidvid": spec.lidvid,
        "grid": {
            "records": len(receipts),
            "representative_sample_offset_s": REPRESENTATIVE_SAMPLE_OFFSET_S,
            "calibration_records": split,
            "holdout_records": len(receipts) - split,
            "calibration_fraction": CALIBRATION_FRACTION,
            "suffix_refit": "PROHIBITED",
            "free_time_phase": "PROHIBITED",
        },
        "kernel_lineage": list(lineage),
        "receiver_transform": "sky - RF_TO_IF_LO - DDC_LO + exact header NCO",
        "calibration": {
            "allowed_parameters": ["USO_CONSTANT_OFFSET_HZ", "USO_AFFINE_AGING_HZ_S"],
            "fit": asdict(calibration),
            "screening_rest_frequency_hz": SCREENING_REST_FREQUENCY_HZ,
            "semantics": "REFERENCE_ONLY_NOT_AN_ASSERTED_CASSINI_CARRIER",
        },
        "controlling_null": "CALIBRATION_PREFIX_AFFINE_RECORDED_BASEBAND",
        "heldout_orbital_vs_affine_baseband_hz": metrics,
        "dss26_reference_peak_to_peak_hz": DSS26_REFERENCE_AFFINE_P2P_HZ,
        "signature_improvement_over_dss26": metrics["peak_to_peak_hz"] > DSS26_REFERENCE_AFFINE_P2P_HZ,
        "open_terms_without_candidate_specific_bounds": [term.name for term in one_way.initial_open_terms()],
        "physical_margin_admitted": False,
        "detector_access_authorized": False,
        "iq_access_authorized": False,
    }
    strict_json(result)
    return result


def evaluation_manifest() -> dict[str, object]:
    return {
        "evaluation_version": EVALUATION_VERSION,
        "parser_manifest_sha256": parser_manifest_sha256(),
        "candidate_roles": [asdict(CANDIDATES[role]) for role in sorted(CANDIDATES)],
        "header_ranges_per_request": HEADER_RANGES_PER_REQUEST,
        "calibration_fraction": CALIBRATION_FRACTION,
        "representative_sample_offset_s": REPRESENTATIVE_SAMPLE_OFFSET_S,
        "screening_rest_frequency_hz": SCREENING_REST_FREQUENCY_HZ,
        "controlling_null": "CALIBRATION_PREFIX_AFFINE_RECORDED_BASEBAND",
        "dss26_reference_affine_peak_to_peak_hz": DSS26_REFERENCE_AFFINE_P2P_HZ,
        "kernel_specs": {
            role: [asdict(spec) for spec in (*SHARED_KERNELS, TRAJECTORY_KERNELS[role])]
            for role in sorted(CANDIDATES)
        },
        "forbidden": [
            "data CHDO byte requests", "complete RSR materialization",
            "IQ/sample/amplitude diagnostics", "detector development",
            "free time phase", "heldout nuisance refit",
        ],
    }


def evaluation_manifest_sha256() -> str:
    return sha256(strict_json(evaluation_manifest()).encode("ascii")).hexdigest()


@contextmanager
def _loaded_exact_kernels(spice, role: HeaderCandidateRole, kernel_paths: Mapping[str, Path]) -> Iterator[tuple[dict[str, object], ...]]:
    specs = (*SHARED_KERNELS, TRAJECTORY_KERNELS[role])
    lineage = []
    spice.kclear()
    try:
        for spec in specs:
            path = Path(kernel_paths[spec.name])
            if not path.is_file() or path.stat().st_size != spec.bytes:
                raise CassiniDss14EvaluationError(f"kernel byte count mismatch: {spec.name}")
            digest = _file_sha256(path)
            if digest != spec.sha256:
                raise CassiniDss14EvaluationError(f"kernel SHA-256 mismatch: {spec.name}")
            spice.furnsh(str(path))
            lineage.append({
                "name": spec.name, "bytes": spec.bytes, "sha256": digest,
                "role": spec.role, "independence": spec.independence,
            })
        yield tuple(lineage)
    finally:
        spice.kclear()


def _calibrated_curve(factors, transmit_et, lo, nco, split):
    factor = np.asarray(factors, dtype=np.float64)
    epoch = np.asarray(transmit_et, dtype=np.float64)
    steering_sky = np.asarray(lo, dtype=np.float64) - np.asarray(nco, dtype=np.float64)
    target_rest = steering_sky / factor
    elapsed = epoch - epoch[0]
    residual = target_rest - SCREENING_REST_FREQUENCY_HZ
    offset, aging = _fit_affine(elapsed[:split], residual[:split])
    emitted = SCREENING_REST_FREQUENCY_HZ + offset + aging * elapsed
    baseband = emitted * factor - np.asarray(lo) + np.asarray(nco)
    calibration_error = baseband[:split]
    return baseband, CalibrationFit(
        constant_offset_hz=float(offset),
        affine_aging_hz_s=float(aging),
        calibration_rmse_hz=float(sqrt(float(np.mean(calibration_error * calibration_error)))),
    )


def _fit_affine(x, y) -> tuple[float, float]:
    x_array = np.asarray(x, dtype=np.float64)
    y_array = np.asarray(y, dtype=np.float64)
    design = np.column_stack((np.ones(x_array.size), x_array))
    coefficients, *_ = np.linalg.lstsq(design, y_array, rcond=None)
    return float(coefficients[0]), float(coefficients[1])


def _difference_metrics(left, right, interval: slice) -> dict[str, float]:
    difference = np.asarray(left)[interval] - np.asarray(right)[interval]
    return {
        "minimum_hz": float(np.min(difference)),
        "maximum_hz": float(np.max(difference)),
        "peak_to_peak_hz": float(np.ptp(difference)),
        "maximum_absolute_hz": float(np.max(np.abs(difference))),
        "rms_hz": float(sqrt(float(np.mean(difference * difference)))),
    }


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _offset_utc(value: str, offset_s: float) -> str:
    instant = _parse_utc(value) + timedelta(seconds=offset_s)
    return instant.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _finite_coefficients(values) -> tuple[float, ...]:
    result = tuple(value.value for value in values)
    if any(value is None or not isfinite(value) for value in result):
        raise CassiniDss14EvaluationError("frequency polynomial is not calculable")
    return tuple(float(value) for value in result)


def _polynomial(coefficients: Sequence[float], u: float) -> float:
    return sum(coefficient * u**power for power, coefficient in enumerate(coefficients))


def _coefficient_ranges(rows: Sequence[Sequence[float]]) -> list[dict[str, float]]:
    return [
        {"minimum": min(row[index] for row in rows), "maximum": max(row[index] for row in rows)}
        for index in range(len(rows[0]))
    ]


def _unique(receipts, attribute: str) -> list[object]:
    return sorted({getattr(receipt, attribute) for receipt in receipts})
