"""Development-only, amplitude-blind Cassini DSS-26 header spike.

The module is intentionally bound to one PDS product.  It first verifies the
complete artifact, then reads only each 260-byte SFDU header and seeks across
the data CHDO.  It never decodes or represents sample or amplitude data.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import md5, sha256
import json
from math import ceil, isfinite, sqrt
from pathlib import Path
from typing import Final, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import cassini_dss26_one_way as one_way
from experiments.orbital_discriminability.cassini_dss26_one_way import (
    CASSINI_DSS26_KERNELS,
    StateVector,
    solve_one_way_event,
)
from experiments.orbital_discriminability.cassini_dss26_rsr_header import (
    CassiniDss26HeaderReceipt,
    DEVELOPMENT_LIDVID,
    DEVELOPMENT_PRODUCT_NAME,
    DEVELOPMENT_SOURCE_PRODUCT_ID,
    RSR_HEADER_BYTES,
    RSR_RECORD_BYTES,
    parse_dss26_header,
    parser_manifest_sha256,
    strict_json,
)


SPIKE_VERSION: Final = "cassini-dss26-development-header-spike-v1"
EXPECTED_BYTES: Final = 41_113_260
EXPECTED_RECORDS: Final = 9_651
PUBLISHED_MD5: Final = "ce672e2258ffe8466389db36f9f6668f"
DEVELOPMENT_SHA256: Final = (
    "dee30d34255f17c20f6aea7072bfd4b156db0d0e3378720e377f7bcec16ed424"
)
LABEL_SHA256: Final = "b02dd0ff1aaa355fbe6faca191b898c91b2d99532864750ac6a50e30d93b70c1"
CALIBRATION_FRACTION: Final = 0.2
REPRESENTATIVE_SAMPLE_OFFSET_S: Final = 0.5005
SCREENING_REST_FREQUENCY_HZ: Final = 8_425_000_000.0
GEOMETRY_DESTROYING_TARGET: Final = "SATURN BARYCENTER"
TYPED_REFUSAL_OPEN_TERM: Final = "CASSINI_OPEN_TERM_CAN_ABSORB_HELDOUT_SEPARATION"


class CassiniHeaderSpikeError(ValueError):
    """The frozen DSS-26 metadata path is inconsistent or incomplete."""


@dataclass(frozen=True, slots=True)
class ArtifactIdentity:
    lidvid: str
    source_product_id: str
    product_name: str
    bytes: int
    published_md5: str
    sha256: str
    label_sha256: str


@dataclass(frozen=True, slots=True)
class CalibrationFit:
    constant_offset_hz: float
    affine_aging_hz_s: float
    calibration_rmse_hz: float


def verify_development_artifact(path: Path) -> ArtifactIdentity:
    """Verify the complete file before any header parsing is permitted."""

    path = Path(path)
    if path.name != DEVELOPMENT_PRODUCT_NAME or not path.is_file():
        raise CassiniHeaderSpikeError("development product identity is not the frozen DSS-26 file")
    if path.stat().st_size != EXPECTED_BYTES:
        raise CassiniHeaderSpikeError("development product byte count differs from the PDS label")
    md5_digest, sha256_digest = _file_hashes(path)
    if md5_digest != PUBLISHED_MD5:
        raise CassiniHeaderSpikeError("development product published MD5 verification failed")
    if sha256_digest != DEVELOPMENT_SHA256:
        raise CassiniHeaderSpikeError("development product full SHA-256 verification failed")
    return ArtifactIdentity(
        lidvid=DEVELOPMENT_LIDVID,
        source_product_id=DEVELOPMENT_SOURCE_PRODUCT_ID,
        product_name=DEVELOPMENT_PRODUCT_NAME,
        bytes=EXPECTED_BYTES,
        published_md5=md5_digest,
        sha256=sha256_digest,
        label_sha256=LABEL_SHA256,
    )


def read_verified_headers(path: Path) -> tuple[CassiniDss26HeaderReceipt, ...]:
    """Read only frozen whitelist headers after full-file verification."""

    verify_development_artifact(path)
    receipts: list[CassiniDss26HeaderReceipt] = []
    with Path(path).open("rb") as stream:
        for _ in range(EXPECTED_RECORDS):
            header = stream.read(RSR_HEADER_BYTES)
            if len(header) != RSR_HEADER_BYTES:
                raise CassiniHeaderSpikeError("truncated SFDU header")
            receipts.append(parse_dss26_header(header))
            # The data CHDO is not read, decoded, hashed separately, or exposed.
            stream.seek(RSR_RECORD_BYTES - RSR_HEADER_BYTES, 1)
        if stream.tell() != EXPECTED_BYTES or stream.read(1):
            raise CassiniHeaderSpikeError("SFDU traversal does not end at the verified file boundary")
    return tuple(receipts)


def summarize_headers(
    receipts: Sequence[CassiniDss26HeaderReceipt],
) -> dict[str, object]:
    if len(receipts) != EXPECTED_RECORDS:
        raise CassiniHeaderSpikeError("header count differs from the PDS label")
    sequence_steps = [
        right.record_sequence_number - left.record_sequence_number
        for left, right in zip(receipts, receipts[1:])
    ]
    instants = [_parse_utc(receipt.first_sample_utc) for receipt in receipts]
    time_steps = [
        (right - left).total_seconds() for left, right in zip(instants, instants[1:])
    ]
    ordered_digest = sha256()
    for receipt in receipts:
        ordered_digest.update(strict_json(receipt.as_json_object()).encode("ascii"))
        ordered_digest.update(b"\n")

    frequency = [_finite_coefficients(receipt.frequency_polynomial.coefficients) for receipt in receipts]
    phase = [_finite_coefficients(receipt.phase_polynomial.coefficients) for receipt in receipts]
    nco_boundary = [
        _polynomial(right, 0.0005) - _polynomial(left, 1.0005)
        for left, right in zip(frequency, frequency[1:])
    ]
    absolute_phase_boundary = [
        (
            receipts[index + 1].accumulated_phase_cycles.value
            + _polynomial(phase[index + 1], 0.0005)
            - receipts[index].accumulated_phase_cycles.value
            - _polynomial(phase[index], 1.0005)
        )
        for index in range(len(receipts) - 1)
    ]
    if any(value is None for value in (
        receipts[index].accumulated_phase_cycles.value for index in range(len(receipts))
    )):
        raise CassiniHeaderSpikeError("accumulated phase is not calculable")

    return {
        "record_count": len(receipts),
        "ordered_whitelist_receipts_sha256": ordered_digest.hexdigest(),
        "record_sequence": {
            "first": receipts[0].record_sequence_number,
            "last": receipts[-1].record_sequence_number,
            "unique_count": len({receipt.record_sequence_number for receipt in receipts}),
            "non_unit_steps": sum(step != 1 for step in sequence_steps),
            "minimum_step": min(sequence_steps),
            "maximum_step": max(sequence_steps),
        },
        "event_time": {
            "first_sample_utc": receipts[0].first_sample_utc,
            "last_first_sample_utc": receipts[-1].first_sample_utc,
            "non_one_second_steps": sum(step != 1.0 for step in time_steps),
            "minimum_step_s": min(time_steps),
            "maximum_step_s": max(time_steps),
        },
        "sample_mode": {
            "representation": "COMPLEX_I_THEN_Q_MSB16",
            "sample_resolution_bits": _unique(receipts, "sample_resolution_bits"),
            "sample_rate_hz": _unique(receipts, "sample_rate_hz"),
            "source": "PDS label plus per-SFDU whitelisted resolution/rate",
        },
        "receiver_configuration": {
            "station": _unique(receipts, "station_id"),
            "rsr": _unique(receipts, "rsr_id"),
            "channel": _unique(receipts, "channel_id"),
            "subchannel": _unique(receipts, "subchannel_id"),
            "rf_to_if_lo_hz": _unique(receipts, "rf_to_if_lo_hz"),
            "ddc_lo_hz": _unique(receipts, "ddc_lo_hz"),
            "frequency_override_active": _unique(receipts, "frequency_override_active"),
            "predicts_time_shift_s": _numeric_unique(receipts, "predicts_time_shift_s"),
            "predicts_frequency_override_hz": _numeric_unique(
                receipts, "predicts_frequency_override_hz"
            ),
            "predicts_frequency_rate_hz_s": _numeric_unique(
                receipts, "predicts_frequency_rate_hz_s"
            ),
            "predicts_frequency_offset_hz": _numeric_unique(
                receipts, "predicts_frequency_offset_hz"
            ),
            "subchannel_frequency_offset_hz": _numeric_unique(
                receipts, "subchannel_frequency_offset_hz"
            ),
        },
        "frequency_polynomial": {
            "all_coefficients_finite": True,
            "coefficient_ranges_hz": _coefficient_ranges(frequency),
            "maximum_absolute_boundary_residual_hz": max(abs(value) for value in nco_boundary),
        },
        "phase_polynomial": {
            "all_coefficients_finite": True,
            "coefficient_ranges_cycles": _coefficient_ranges(phase),
            "maximum_absolute_boundary_residual_cycles": max(
                abs(value) for value in absolute_phase_boundary
            ),
        },
        "filter_decimation": {
            "input_rate_hz": _nested_unique(receipts, "input_rate_hz"),
            "output_rate_hz": _nested_unique(receipts, "output_rate_hz"),
            "output_bandwidth_hz": _nested_unique(receipts, "output_bandwidth_hz"),
            "decimation": _nested_unique(receipts, "decimation"),
            "fir_coefficients": "NOT_ENCODED_IN_SFDU",
            "amplitude_response_claim": "PROHIBITED",
        },
        "data_chdo_policy": "SEEKED_NOT_READ_NOT_DECODED_NOT_REPRESENTED",
    }


def compile_baseband_signature(
    receipts: Sequence[CassiniDss26HeaderReceipt],
    kernel_paths: Mapping[str, Path],
    *,
    spice,
) -> dict[str, object]:
    """Compile three frozen geometries and one affine baseband null."""

    if len(receipts) != EXPECTED_RECORDS:
        raise CassiniHeaderSpikeError("baseband compilation requires the complete header grid")
    orbital_factor: list[float] = []
    orbital_transmit: list[float] = []
    alternate_factor: list[float] = []
    alternate_transmit: list[float] = []
    nco: list[float] = []
    lo: list[float] = []
    receive_et: list[float] = []
    with one_way._loaded_frozen_kernels(spice, kernel_paths) as lineage:
        station = one_way._spice_state_provider(spice, one_way.DEVELOPMENT_STATION)
        cassini = one_way._spice_state_provider(spice, one_way.SPACECRAFT)
        saturn = one_way._spice_state_provider(spice, GEOMETRY_DESTROYING_TARGET)
        for receipt in receipts:
            epoch_utc = _offset_utc(receipt.first_sample_utc, REPRESENTATIVE_SAMPLE_OFFSET_S)
            epoch_et = float(spice.utc2et(epoch_utc))
            nominal_event = solve_one_way_event(epoch_et, station, cassini)
            alternate_event = solve_one_way_event(epoch_et, station, saturn)
            receive_et.append(epoch_et)
            orbital_factor.append(nominal_event.kinematic_frequency_factor)
            orbital_transmit.append(nominal_event.transmit_et_tdb_s)
            alternate_factor.append(alternate_event.kinematic_frequency_factor)
            alternate_transmit.append(alternate_event.transmit_et_tdb_s)
            nco.append(receipt.nco_frequency_hz(REPRESENTATIVE_SAMPLE_OFFSET_S))
            lo.append(float(receipt.rf_to_if_lo_hz + receipt.ddc_lo_hz))

    split = int(ceil(len(receipts) * CALIBRATION_FRACTION))
    orbital, orbital_fit = _calibrated_curve(orbital_factor, orbital_transmit, lo, nco, split)
    steering, steering_fit = _calibrated_curve(
        [1.0] * len(receipts), orbital_transmit, lo, nco, split
    )
    alternate, alternate_fit = _calibrated_curve(
        alternate_factor, alternate_transmit, lo, nco, split
    )
    elapsed = np.asarray(receive_et, dtype=np.float64) - receive_et[0]
    affine_coefficients = _fit_affine(elapsed[:split], np.asarray(orbital[:split]))
    affine = affine_coefficients[0] + affine_coefficients[1] * elapsed
    holdout = slice(split, len(receipts))

    # Constant USO offset and affine aging are the only fitted prefix nuisance
    # and are therefore applied, not counted again as open physical terms.
    open_terms = [term.name for term in one_way.initial_open_terms()]
    result = {
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
        "calibration": {
            "allowed_parameters": ["USO_CONSTANT_OFFSET_HZ", "USO_AFFINE_AGING_HZ_S"],
            "orbital": asdict(orbital_fit),
            "steering_only": asdict(steering_fit),
            "saturn_barycenter": asdict(alternate_fit),
            "screening_rest_frequency_hz": SCREENING_REST_FREQUENCY_HZ,
            "screening_reference_semantics": "REFERENCE_ONLY_NOT_AN_ASSERTED_CASSINI_CARRIER",
        },
        "nulls": {
            "steering_only": "unit kinematic factor; identical header/NCO grid",
            "affine_baseband": (
                "sky=RF_IF_LO+DDC_LO-NCO+(a+b*t); exact NCO transform yields the "
                "two-parameter prefix fit extrapolated unchanged"
            ),
            "geometry_destroying": (
                "Cassini state replaced by Saturn barycenter from the same frozen pre-pass SPK"
            ),
        },
        "heldout_separation_hz": {
            "orbital_vs_steering_only": _difference_metrics(orbital, steering, holdout),
            "orbital_vs_affine_baseband": _difference_metrics(orbital, affine, holdout),
            "orbital_vs_saturn_barycenter": _difference_metrics(orbital, alternate, holdout),
        },
        "recorded_baseband_ranges_hz": {
            "orbital_calibration": _range_metrics(orbital[:split]),
            "orbital_holdout": _range_metrics(orbital[split:]),
            "steering_only_holdout": _range_metrics(steering[split:]),
            "affine_baseband_holdout": _range_metrics(affine[holdout]),
            "saturn_barycenter_holdout": _range_metrics(alternate[split:]),
        },
        "bounded_correction_envelope_hz": 0.0,
        "open_terms_without_numerical_bound": open_terms,
        "causal_scope": {
            "header_nco": "MODEL_CONDITIONED_BY_DSN_FREQUENCY_PREDICTS",
            "steering_only_comparison": "NOT_INDEPENDENT_ORBIT_IDENTITY_EVIDENCE",
            "controlling_nonorbital_comparison": "AFFINE_RECORDED_BASEBAND_NULL",
        },
        "nonlinear_separation_positive_before_open_terms": all(
            metrics["peak_to_peak_hz"] > 0.0
            for metrics in (
                _difference_metrics(orbital, steering, holdout),
                _difference_metrics(orbital, affine, holdout),
                _difference_metrics(orbital, alternate, holdout),
            )
        ),
        "outcome": TYPED_REFUSAL_OPEN_TERM if open_terms else "CASSINI_BASEBAND_SIGNATURE_ADMITTED",
        "detector_access_authorized": False,
        "iq_access_authorized": False,
    }
    strict_json(result)
    return result


def spike_manifest() -> dict[str, object]:
    return {
        "spike_version": SPIKE_VERSION,
        "development_lidvid": DEVELOPMENT_LIDVID,
        "artifact_sha256": DEVELOPMENT_SHA256,
        "parser_manifest_sha256": parser_manifest_sha256(),
        "calibration_fraction": CALIBRATION_FRACTION,
        "representative_sample_offset_s": REPRESENTATIVE_SAMPLE_OFFSET_S,
        "geometry_destroying_target": GEOMETRY_DESTROYING_TARGET,
        "forbidden": [
            "IQ decoding",
            "amplitude/RMS/peak/signal diagnostics",
            "free time phase",
            "heldout nuisance refit",
            "DSS-14 primary or reserve access",
        ],
    }


def spike_manifest_sha256() -> str:
    return sha256(strict_json(spike_manifest()).encode("ascii")).hexdigest()


def _calibrated_curve(
    factors: Sequence[float],
    transmit_et: Sequence[float],
    lo: Sequence[float],
    nco: Sequence[float],
    split: int,
) -> tuple[np.ndarray, CalibrationFit]:
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


def _fit_affine(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    design = np.column_stack((np.ones(x.size), x))
    coefficients, *_ = np.linalg.lstsq(design, y, rcond=None)
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


def _range_metrics(values) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "minimum_hz": float(np.min(array)),
        "maximum_hz": float(np.max(array)),
        "peak_to_peak_hz": float(np.ptp(array)),
    }


def _file_hashes(path: Path) -> tuple[str, str]:
    md5_digest = md5(usedforsecurity=False)
    sha256_digest = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            md5_digest.update(chunk)
            sha256_digest.update(chunk)
    return md5_digest.hexdigest(), sha256_digest.hexdigest()


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _offset_utc(value: str, offset_s: float) -> str:
    instant = _parse_utc(value) + timedelta(seconds=offset_s)
    return instant.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _finite_coefficients(values) -> tuple[float, ...]:
    result = tuple(value.value for value in values)
    if any(value is None or not isfinite(value) for value in result):
        raise CassiniHeaderSpikeError("polynomial contains a non-calculable coefficient")
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


def _numeric_unique(receipts, attribute: str) -> list[float | None]:
    values = {getattr(receipt, attribute).value for receipt in receipts}
    return sorted(values, key=lambda value: (value is None, value if value is not None else 0.0))


def _nested_unique(receipts, attribute: str) -> list[object]:
    return sorted({getattr(receipt.filter_decimation, attribute) for receipt in receipts})


def strict_report_json(value: object) -> str:
    return json.dumps(value, allow_nan=False, ensure_ascii=True, indent=2, sort_keys=True)
