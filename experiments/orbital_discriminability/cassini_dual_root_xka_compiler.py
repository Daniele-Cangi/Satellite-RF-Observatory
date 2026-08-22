"""Exact metadata-only compiler for the frozen 2005 Cassini X/Ka topology.

Only 260-byte SFDU control headers may enter. NCO is receiver steering, not
measured RF; data CHDO, IQ, amplitude and detector output are excluded.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from math import ceil, floor, sqrt
from pathlib import Path
from typing import Final, Mapping, Sequence
import urllib.request

import numpy as np

from experiments.orbital_discriminability import (
    cassini_dss14_header_evaluation as header_eval,
)
from experiments.orbital_discriminability import cassini_dss26_one_way as one_way
from experiments.orbital_discriminability import cassini_dual_root_headers as headers
from experiments.orbital_discriminability import (
    cassini_sagr3_distributed_geometry as forward,
)
from experiments.orbital_discriminability import (
    cassini_sagr3_pretransition_open_term_audit as prior_audit,
)


COMPILER_VERSION: Final = "cassini-sroc-2005-dual-root-xka-compiler-v1"
OUTCOME_BLOCKED: Final = "CASSINI_DUAL_ROOT_PHYSICAL_ENVELOPE_UNAVAILABLE"
OUTCOME_ADMITTED: Final = "CASSINI_DUAL_ROOT_PHYSICAL_MARGIN_ADMITTED"
REFERENCE_X_HZ: Final = 8_425_000_000.0
REFERENCE_KA_HZ: Final = 32_028_000_000.0
CALIBRATION_FRACTION: Final = 0.2
GRID_STEP_S: Final = 1.0
REPRESENTATIVE_SAMPLE_OFFSET_S: Final = 0.5005
HEADER_TIMING_BOUND_S: Final = 1e-6
HALF_OUTPUT_BANDWIDTH_HZ: Final = 500.0
DETECTOR_BINS_REQUIRED: Final = 3.0
TRAJECTORY_ROLE: Final = "HEADER_CANDIDATE_B"
PARENT_RECEIPT_SHA256: Final = {
    "CASSINI_DUAL_ROOT_PASS_SELECTION_RECEIPT.json": (
        "40741d086d500611d482279c6537192011c03df684e3286662dfd84e6ab7f317"
    ),
    "CASSINI_DUAL_ROOT_HEADER_RECEIPT.json": (
        "b9154fb068f08f16b2b0f055b7320cfd95b8fd211273cc65d80d20055132385e"
    ),
}
OPEN_TERM_NAMES: Final = (
    "PROPER_TIME_AND_GRAVITATIONAL_FREQUENCY",
    "RELATIVISTIC_PROPAGATION_LIGHT_TIME",
    "EARTH_TROPOSPHERE",
    "EARTH_IONOSPHERE",
    "INTERPLANETARY_PLASMA",
    "STATION_HARDWARE_DELAY",
    "AVAILABLE_MEDIA_CALIBRATION",
)
MEDIA_PRODUCTS: Final = {
    "ION": {
        "lidvid": (
            "urn:nasa:pds:cassini.rss.raw.sroc:calib.ion:"
            "s11sroc2005_152_2005_181::1.0"
        ),
        "bytes": 23_660,
        "published_md5": "f749ee7c577d704401ead253a4ac7ffe",
        "coverage": ["2005-06-01T00:20:00Z", "2005-07-01T08:27:00Z"],
    },
    "TRO": {
        "lidvid": (
            "urn:nasa:pds:cassini.rss.raw.sroc:calib.tro:"
            "s11sroc2005_152_2005_184::1.0"
        ),
        "bytes": 86_788,
        "published_md5": "0ebfe025ce4ffafe52b7a1c6f69f28df",
        "coverage": ["2005-06-01T06:00:00.001Z", "2005-07-03T00:00:00Z"],
    },
}


class CassiniDualRootCompilerError(ValueError):
    """Frozen metadata, transform, or causal ledger is inconsistent."""


@dataclass(frozen=True, slots=True)
class ControlRecord:
    first_sample_utc: str
    record_sequence_number: int
    rf_to_if_lo_hz: float
    ddc_lo_hz: float
    nco_coefficients_hz: tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class ControlStream:
    role: headers.ProductRole
    records: tuple[ControlRecord, ...]
    ordered_receipts_sha256: str
    derived_coordinate_sha256: str

    def validate(self) -> None:
        spec = headers.PRODUCTS[self.role]
        if len(self.records) != spec.window_records or not self.records:
            raise CassiniDualRootCompilerError("control stream length changed")
        if self.records[0].first_sample_utc != spec.window_first_sample_utc:
            raise CassiniDualRootCompilerError("control stream start changed")
        if self.records[-1].first_sample_utc != spec.window_last_first_sample_utc:
            raise CassiniDualRootCompilerError("control stream stop changed")


def control_record(receipt: headers.HeaderReceipt) -> ControlRecord:
    coefficients = headers._finite_polynomial(receipt.frequency_polynomial)
    if len(coefficients) != 3:
        raise CassiniDualRootCompilerError("NCO polynomial order changed")
    return ControlRecord(
        receipt.first_sample_utc,
        receipt.record_sequence_number,
        float(receipt.rf_to_if_lo_hz),
        float(receipt.ddc_lo_hz),
        tuple(float(value) for value in coefficients),
    )


def evaluate_tuning_sky_hz(stream, receive_et, record_start_et) -> np.ndarray:
    """Evaluate RF+DDC-NCO on arbitrary receive epochs without interpolation."""

    stream.validate()
    query = _vector("receive epochs", receive_et)
    starts = _vector("record starts", record_start_et)
    if starts.size != len(stream.records) or not np.all(np.diff(starts) > 0.0):
        raise CassiniDualRootCompilerError("record ET grid is invalid")
    indices = np.searchsorted(starts, query, side="right") - 1
    if np.any(indices < 0) or np.any(indices >= starts.size):
        raise CassiniDualRootCompilerError("query is outside control stream")
    offsets = query - starts[indices]
    if np.any(offsets < 0.0) or np.any(offsets >= 1.0):
        raise CassiniDualRootCompilerError("query crosses an uncovered second")
    result = np.empty(query.size, dtype=np.float64)
    for out, (index, offset) in enumerate(zip(indices, offsets)):
        record = stream.records[int(index)]
        f1, f2, f3 = record.nco_coefficients_hz
        nco = f1 + f2 * float(offset) + f3 * float(offset) ** 2
        result[out] = record.rf_to_if_lo_hz + record.ddc_lo_hz - nco
    if not np.all(np.isfinite(result)) or np.any(result <= 0.0):
        raise CassiniDualRootCompilerError("tuning coordinate is invalid")
    return result


def composition_weights(x_hz, ka_hz) -> tuple[np.ndarray, np.ndarray]:
    """Preserve a common fraction and cancel exact first-order p/f^2."""

    x, ka = np.broadcast_arrays(
        np.asarray(x_hz, dtype=np.float64),
        np.asarray(ka_hz, dtype=np.float64),
    )
    if (
        not np.all(np.isfinite(x))
        or not np.all(np.isfinite(ka))
        or np.any(x <= 0.0)
        or np.any(ka <= x)
    ):
        raise CassiniDualRootCompilerError("carrier coordinates are invalid")
    denominator = ka * ka - x * x
    return -(x * x) / denominator, (ka * ka) / denominator


def compose_four_stream_fraction(x25, ka25, x55, ka55, carriers):
    values = {
        "DSS25_X": _vector("DSS25_X", x25),
        "DSS25_KA": _vector("DSS25_KA", ka25),
        "DSS55_X": _vector("DSS55_X", x55),
        "DSS55_KA": _vector("DSS55_KA", ka55),
    }
    if len({value.shape for value in values.values()}) != 1:
        raise CassiniDualRootCompilerError("four-stream shape changed")
    if set(carriers) != set(values):
        raise CassiniDualRootCompilerError("carrier topology changed")
    wx25, wk25 = composition_weights(carriers["DSS25_X"], carriers["DSS25_KA"])
    wx55, wk55 = composition_weights(carriers["DSS55_X"], carriers["DSS55_KA"])
    result = (
        wx25 * values["DSS25_X"] + wk25 * values["DSS25_KA"]
        - wx55 * values["DSS55_X"] - wk55 * values["DSS55_KA"]
    )
    if not np.all(np.isfinite(result)):
        raise CassiniDualRootCompilerError("composite is non-finite")
    return np.asarray(result, dtype=np.float64)


def prefix_affine_projection(curve_hz, calibration_records):
    """Fit one composite constant+slope on the prefix, never on the suffix."""

    values = _vector("projected curve", curve_hz)
    if calibration_records < 2 or calibration_records >= values.size:
        raise CassiniDualRootCompilerError("invalid calibration prefix")
    elapsed = np.arange(values.size, dtype=np.float64)
    design = np.column_stack(
        (np.ones(calibration_records), elapsed[:calibration_records])
    )
    coefficients, *_ = np.linalg.lstsq(
        design, values[:calibration_records], rcond=None
    )
    residual = values - (coefficients[0] + coefficients[1] * elapsed)
    heldout = residual[calibration_records:]
    return residual, {
        "constant_hz": float(coefficients[0]),
        "slope_hz_s": float(coefficients[1]),
        "heldout_peak_to_peak_hz": float(np.ptp(heldout)),
        "heldout_rms_hz": float(sqrt(float(np.mean(heldout * heldout)))),
        "heldout_maximum_absolute_hz": float(np.max(np.abs(heldout))),
        "calibration_prefix_rmse_hz": float(
            sqrt(float(np.mean(residual[:calibration_records] ** 2)))
        ),
    }


def fetch_control_stream(role: headers.ProductRole) -> ControlStream:
    """Read frozen header ranges once, reduce in RAM, and zero each buffer."""

    spec = headers.PRODUCTS[role]
    records = []
    receipt_digest = sha256()
    coordinate_digest = sha256()
    first = spec.window_first_record_index
    stop = first + spec.window_records
    for batch in range(first, stop, headers.HEADER_RANGES_PER_REQUEST):
        indices = tuple(
            range(batch, min(batch + headers.HEADER_RANGES_PER_REQUEST, stop))
        )
        ranges = tuple(
            (
                index * headers.RSR_RECORD_BYTES,
                index * headers.RSR_RECORD_BYTES + headers.RSR_HEADER_BYTES - 1,
            )
            for index in indices
        )
        request = urllib.request.Request(
            spec.data_url,
            headers={
                "Range": "bytes="
                + ",".join(f"{start}-{end}" for start, end in ranges),
                "User-Agent": "Satellite-RF-Observatory-SROC2005-XKa-header/1",
            },
        )
        response = urllib.request.urlopen(request, timeout=60)
        try:
            parts = header_eval._read_exact_range_response(
                response, ranges, spec.file_bytes
            )
        finally:
            response.close()
        for index in indices:
            key = (
                index * headers.RSR_RECORD_BYTES,
                index * headers.RSR_RECORD_BYTES + headers.RSR_HEADER_BYTES - 1,
            )
            raw = bytearray(parts.pop(key))
            try:
                receipt = headers.parse_header(raw, role)
                receipt_digest.update(
                    headers.strict_json(receipt.as_json_object()).encode("ascii")
                )
                receipt_digest.update(b"\n")
                reduced = control_record(receipt)
                records.append(reduced)
                coordinate_digest.update(
                    strict_json(asdict(reduced)).encode("ascii")
                )
                coordinate_digest.update(b"\n")
            finally:
                raw[:] = bytes(len(raw))
        if parts:
            raise CassiniDualRootCompilerError("unauthorized extra byte range")
    result = ControlStream(
        role,
        tuple(records),
        receipt_digest.hexdigest(),
        coordinate_digest.hexdigest(),
    )
    result.validate()
    return result


def validate_parent_receipts() -> dict[str, dict[str, object]]:
    directory = Path(__file__).parent
    loaded = {}
    for name, expected in PARENT_RECEIPT_SHA256.items():
        raw = (directory / name).read_bytes()
        if sha256(raw.replace(b"\r\n", b"\n")).hexdigest() != expected:
            raise CassiniDualRootCompilerError(f"parent receipt changed: {name}")
        loaded[name] = json.loads(
            raw,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )
    return loaded


def validate_streams(streams, parents) -> None:
    if set(streams) != set(headers.PRODUCTS):
        raise CassiniDualRootCompilerError("exactly four frozen streams required")
    expected = {
        item["role"]: item["ordered_whitelist_receipts_sha256"]
        for item in parents["CASSINI_DUAL_ROOT_HEADER_RECEIPT.json"]["products"]
    }
    for role, stream in streams.items():
        stream.validate()
        if stream.ordered_receipts_sha256 != expected[role]:
            raise CassiniDualRootCompilerError(
                f"whitelist receipt digest changed for {role}"
            )


def compile_exact_metadata(*, spice, kernel_paths, streams, source_commit):
    """Compile the exact coordinate, geometry, nulls, and causal envelope."""

    if len(source_commit) != 40:
        raise CassiniDualRootCompilerError("full pre-access commit required")
    parents = validate_parent_receipts()
    validate_streams(streams, parents)
    screen = _compile_geometry(spice, kernel_paths, streams)
    terms = physical_term_ledger(screen["central_diagnostics"])
    unresolved = [
        term["name"] for term in terms if term["bound_state"] != "BOUNDED"
    ]
    controlling = screen["receipt"]["controlling_heldout_peak_to_peak_hz"]
    timing = screen["receipt"]["timing_envelope"]["four_stream_weighted_hz"]
    remaining = None if unresolved else controlling - timing
    detector = (
        remaining / DETECTOR_BINS_REQUIRED
        if remaining is not None and remaining > 0.0
        else None
    )
    result = {
        "compiler_version": COMPILER_VERSION,
        "compiler_manifest_sha256": compiler_manifest_sha256(),
        "canonical_compiler_source_sha256": canonical_source_sha256(),
        "source_commit": source_commit,
        "scope": "FOUR_FROZEN_SROC_2005_HEADERS_NO_DATA_CHDO_NO_IQ",
        "outcome": OUTCOME_ADMITTED if detector is not None else OUTCOME_BLOCKED,
        "maximum_authorized_claim": (
            "EXACT_METADATA_COORDINATE_AND_DETECTABILITY_SCREEN_ONLY;"
            "NO_CARRIER_PLASMA_OR_ORBITAL_RF_MEASUREMENT"
        ),
        "coordinate_artifacts": [
            {
                "role": role,
                "records": len(streams[role].records),
                "ordered_whitelist_receipts_sha256": (
                    streams[role].ordered_receipts_sha256
                ),
                "derived_coordinate_artifact_sha256": (
                    streams[role].derived_coordinate_sha256
                ),
                "raw_headers_persisted": False,
            }
            for role in headers.PRODUCTS
        ],
        "transform_ledger": [
            "future model-blind baseband ridge per stream",
            "add RF-to-IF plus DDC minus exact NCO to reconstruct sky frequency",
            "map both roots to one common Cassini transmit-time coordinate",
            "form fractional X/Ka coordinate independently at each root",
            "cancel first-order p/f^2 at DSS25 and DSS55",
            "subtract roots and scale by frozen X reference",
            "fit one composite affine on first 20 percent only",
            "score untouched suffix against both frozen nulls",
        ],
        "nco_semantics": "RECEIVER_STEERING_METADATA_NOT_RF_MEASUREMENT",
        "geometry_and_nulls": screen["receipt"],
        "seven_term_physical_ledger": terms,
        "correlated_envelope": {
            "representation": "NON_PROBABILISTIC_CAUSAL_STATE_ENVELOPE",
            "combination": "MINKOWSKI_SUM_OF_BOUNDED_CORRELATED_FAMILIES",
            "unresolved_terms": unresolved,
            "unresolved_is_zero": False,
            "root_sum_square_used": False,
            "remaining_physical_margin_hz": remaining,
            "maximum_admissible_detector_resolution_hz": detector,
            "criterion": "signature > timing + physical envelope + 3*R_f",
        },
        "access": {
            "sfdu_control_header_bytes": (
                len(headers.PRODUCTS)
                * headers.FROZEN_WINDOW_RECORDS
                * headers.RSR_HEADER_BYTES
            ),
            "data_chdo_bytes_requested": 0,
            "data_chdo_bytes_read": 0,
            "iq_bytes_accessed": 0,
            "amplitude_or_signal_diagnostics_represented": False,
            "raw_headers_persisted": False,
            "detector_implemented": False,
        },
        "iq_access_authorized": False,
        "new_gate_created": False,
    }
    strict_json(result)
    return result


def run_once(*, spice, kernel_paths, source_commit):
    streams = {role: fetch_control_stream(role) for role in headers.PRODUCTS}
    return compile_exact_metadata(
        spice=spice,
        kernel_paths=kernel_paths,
        streams=streams,
        source_commit=source_commit,
    )


def _compile_geometry(spice, kernel_paths, streams):
    record_et = {}
    with header_eval._loaded_exact_kernels(
        spice, TRAJECTORY_ROLE, kernel_paths
    ) as lineage:
        for role, stream in streams.items():
            record_et[role] = np.asarray(
                [
                    float(spice.utc2et(record.first_sample_utc))
                    for record in stream.records
                ]
            )
        cassini = one_way._spice_state_provider(spice, "CASSINI")
        saturn = one_way._spice_state_provider(spice, "SATURN BARYCENTER")
        earth = one_way._spice_state_provider(spice, "EARTH")
        station25 = one_way._spice_state_provider(spice, "DSS-25")
        station55 = one_way._spice_state_provider(spice, "DSS-55")
        first = record_et["DSS25_X"][0] + REPRESENTATIVE_SAMPLE_OFFSET_S
        last = record_et["DSS25_X"][-1] + REPRESENTATIVE_SAMPLE_OFFSET_S
        common_start = max(
            one_way.solve_one_way_event(first, station25, cassini).transmit_et_tdb_s,
            one_way.solve_one_way_event(first, station55, cassini).transmit_et_tdb_s,
        )
        common_stop = min(
            one_way.solve_one_way_event(last, station25, cassini).transmit_et_tdb_s,
            one_way.solve_one_way_event(last, station55, cassini).transmit_et_tdb_s,
        )
        count = floor(common_stop - common_start) + 1
        transmit = common_start + np.arange(count, dtype=np.float64)
        arrays = {
            name: np.empty(count)
            for name in (
                "factor25", "factor55", "null25", "null55",
                "receive25", "receive55", "elevation25", "elevation55",
                "timing25", "timing55",
            )
        }
        for index, epoch in enumerate(transmit):
            left = forward.solve_forward_event(epoch, station25, cassini, earth)
            right = forward.solve_forward_event(epoch, station55, cassini, earth)
            left_null = forward.solve_forward_event(epoch, station25, saturn, earth)
            right_null = forward.solve_forward_event(epoch, station55, saturn, earth)
            arrays["factor25"][index] = left.kinematic_frequency_factor
            arrays["factor55"][index] = right.kinematic_frequency_factor
            arrays["null25"][index] = left_null.kinematic_frequency_factor
            arrays["null55"][index] = right_null.kinematic_frequency_factor
            arrays["receive25"][index] = left.receive_et_tdb_s
            arrays["receive55"][index] = right.receive_et_tdb_s
            arrays["elevation25"][index] = left.elevation_rad
            arrays["elevation55"][index] = right.elevation_rad
            arrays["timing25"][index] = _timing_delta(
                epoch, station25, cassini, earth, left.kinematic_frequency_factor
            )
            arrays["timing55"][index] = _timing_delta(
                epoch, station55, cassini, earth, right.kinematic_frequency_factor
            )
        carriers = {
            "DSS25_X": evaluate_tuning_sky_hz(
                streams["DSS25_X"], arrays["receive25"], record_et["DSS25_X"]
            ),
            "DSS25_KA": evaluate_tuning_sky_hz(
                streams["DSS25_KA"], arrays["receive25"], record_et["DSS25_KA"]
            ),
            "DSS55_X": evaluate_tuning_sky_hz(
                streams["DSS55_X"], arrays["receive55"], record_et["DSS55_X"]
            ),
            "DSS55_KA": evaluate_tuning_sky_hz(
                streams["DSS55_KA"], arrays["receive55"], record_et["DSS55_KA"]
            ),
        }
        first_utc = spice.et2utc(float(transmit[0]), "ISOC", 6) + "Z"
        last_utc = spice.et2utc(float(transmit[-1]), "ISOC", 6) + "Z"

    split = ceil(count * CALIBRATION_FRACTION)
    orbital = REFERENCE_X_HZ * (arrays["factor25"] - arrays["factor55"])
    null = REFERENCE_X_HZ * (arrays["null25"] - arrays["null55"])
    _, affine = prefix_affine_projection(orbital, split)
    _, saturn_metrics = prefix_affine_projection(orbital - null, split)
    controlling = min(
        affine["heldout_peak_to_peak_hz"],
        saturn_metrics["heldout_peak_to_peak_hz"],
    )
    wx25, wk25 = composition_weights(carriers["DSS25_X"], carriers["DSS25_KA"])
    wx55, wk55 = composition_weights(carriers["DSS55_X"], carriers["DSS55_KA"])
    timing = REFERENCE_X_HZ * (
        (np.abs(wx25) + np.abs(wk25)) * arrays["timing25"]
        + (np.abs(wx55) + np.abs(wk55)) * arrays["timing55"]
    )
    plasma25 = wx25 / carriers["DSS25_X"] ** 2 + wk25 / carriers["DSS25_KA"] ** 2
    plasma55 = wx55 / carriers["DSS55_X"] ** 2 + wk55 / carriers["DSS55_KA"] ** 2
    receipt = {
        "event_axis": "COMMON_CASSINI_TRANSMIT_ET_TDB",
        "grid_step_s": GRID_STEP_S,
        "records": count,
        "calibration_records": split,
        "holdout_records": count - split,
        "first_transmit_utc": first_utc,
        "last_transmit_utc": last_utc,
        "suffix_refit": "PROHIBITED",
        "kernel_lineage": [
            {
                **item,
                "role": (
                    "DSN_STATION_STATES_DSS25_DSS55"
                    if item["name"] == "earthstns_itrf93_050714.bsp"
                    else item["role"]
                ),
            }
            for item in lineage
        ],
        "joint_visibility": bool(
            np.all(arrays["elevation25"] > 0.0)
            and np.all(arrays["elevation55"] > 0.0)
        ),
        "elevation_deg": {
            "DSS25": _range(np.degrees(arrays["elevation25"])),
            "DSS55": _range(np.degrees(arrays["elevation55"])),
        },
        "carrier_coordinates_hz": {
            role: {
                **_range(values),
                "semantics": "RF_PLUS_DDC_MINUS_NCO_STEERING_NOT_MEASURED_RF",
            }
            for role, values in carriers.items()
        },
        "composition_weights": {
            "DSS25_X": _range(wx25),
            "DSS25_KA": _range(wk25),
            "DSS55_X": _range(wx55),
            "DSS55_KA": _range(wk55),
            "maximum_first_order_plasma_coefficient_abs": {
                "DSS25": float(np.max(np.abs(plasma25))),
                "DSS55": float(np.max(np.abs(plasma55))),
            },
            "carrier_coordinate_uncertainty_basis_hz": (
                HALF_OUTPUT_BANDWIDTH_HZ
            ),
        },
        "orbital_observable": _metrics(orbital),
        "nulls": {
            "prefix_affine": affine,
            "saturn_barycenter_geometry_destroying": saturn_metrics,
            "same_transform_and_projection": True,
        },
        "controlling_heldout_peak_to_peak_hz": controlling,
        "timing_envelope": {
            "per_stream_bound_s": HEADER_TIMING_BOUND_S,
            "method": "DIRECT_TRAJECTORY_AT_T_MINUS_AND_PLUS_BOUND",
            "four_stream_weighted_hz": float(np.max(timing)),
            "shared_station_clock_correlation_assumed": False,
        },
        "rf_or_plasma_observed": False,
    }
    return {
        "receipt": receipt,
        "central_diagnostics": {
            "proper_time_gravity": None,
            "relativistic_path": None,
            "troposphere_partial": None,
            "ionosphere_first_order": None,
        },
    }


def _timing_delta(epoch, station, target, earth, nominal):
    return max(
        abs(
            forward.solve_forward_event(epoch + offset, station, target, earth)
            .kinematic_frequency_factor
            - nominal
        )
        for offset in (-HEADER_TIMING_BOUND_S, HEADER_TIMING_BOUND_S)
    )


def physical_term_ledger(central):
    """Keep central models, uncertainty families, and observations distinct."""

    rows = (
        (
            OPEN_TERM_NAMES[0],
            "MODELED_CENTRAL_UNCERTAINTY_UNRESOLVED",
            "INDEPENDENT_OF_TARGET_RF",
            central["proper_time_gravity"],
            "Receiver proper-time/gravity differential survives X/Ka; a central "
            "model is not its pass-specific uncertainty.",
        ),
        (
            OPEN_TERM_NAMES[1],
            "MODELED_CENTRAL_UNCERTAINTY_UNRESOLVED",
            "INDEPENDENT_OF_TARGET_RF",
            central["relativistic_path"],
            "Moving-body and higher-order path remainders lack a frozen hard bound.",
        ),
        (
            OPEN_TERM_NAMES[2],
            "PARTIAL_MODEL_UNRESOLVED",
            "INDEPENDENT_OF_TARGET_RF",
            central["troposphere_partial"],
            "C10/C60 TRO covers the window, but not with a complete slant model "
            "and deterministic residual-frequency bound.",
        ),
        (
            OPEN_TERM_NAMES[3],
            "FIRST_ORDER_NOT_EVALUATED_WITHOUT_IQ_HIGHER_ORDER_UNRESOLVED",
            "INDEPENDENT_OF_TARGET_RF",
            central["ionosphere_first_order"],
            "First-order 1/f^2 is structurally observable at both roots only after "
            "four RF ridges exist; FITSIG is not a hard bound.",
        ),
        (
            OPEN_TERM_NAMES[4],
            "FIRST_ORDER_NOT_EVALUATED_WITHOUT_IQ_HIGHER_ORDER_UNRESOLVED",
            "UNKNOWN",
            None,
            "The same future X/Ka coordinate can expose first-order interplanetary "
            "plasma; higher-order and scintillation curvature remain open.",
        ),
        (
            OPEN_TERM_NAMES[5],
            "UNRESOLVED",
            "UNKNOWN",
            None,
            "Weighted X/Ka hardware, cross-root reference curvature, FIR group "
            "delay and cable drift have no outcome-independent hard bound.",
        ),
        (
            OPEN_TERM_NAMES[6],
            "PARTIAL_CALIBRATION_UNRESOLVED",
            "INDEPENDENT_OF_TARGET_RF",
            None,
            "Applicable ION/TRO products exist, but central corrections and FITSIG "
            "cannot reduce the envelope.",
        ),
    )
    return [
        {
            "name": name,
            "state": state,
            "provenance": provenance,
            "central_or_partial_heldout_non_affine": diagnostic,
            "central_model_reduces_envelope": False,
            "bound_state": "UNAVAILABLE",
            "admitted_heldout_peak_to_peak_bound_hz": None,
            "combination_role": (
                "NON_ADDITIVE_CONTROL_DO_NOT_DOUBLE_COUNT"
                if name == OPEN_TERM_NAMES[6]
                else "ADDITIVE_PHYSICAL_TERM"
            ),
            "reason": reason,
        }
        for name, state, provenance, diagnostic, reason in rows
    ]


def compiler_manifest() -> dict[str, object]:
    return {
        "compiler_version": COMPILER_VERSION,
        "parent_receipt_repository_text_sha256": PARENT_RECEIPT_SHA256,
        "header_parser_manifest_sha256": headers.parser_manifest_sha256(),
        "roles": list(headers.PRODUCTS),
        "window": {
            "start_utc": headers.FROZEN_WINDOW_START_UTC,
            "stop_utc": headers.FROZEN_WINDOW_STOP_UTC,
            "records_per_stream": headers.FROZEN_WINDOW_RECORDS,
        },
        "event_axis": "COMMON_CASSINI_TRANSMIT_ET_TDB",
        "grid_step_s": GRID_STEP_S,
        "representative_sample_offset_s": REPRESENTATIVE_SAMPLE_OFFSET_S,
        "calibration_fraction": CALIBRATION_FRACTION,
        "reference_frequencies_hz": [REFERENCE_X_HZ, REFERENCE_KA_HZ],
        "header_timing_bound_s": HEADER_TIMING_BOUND_S,
        "projection": "ONE_COMPOSITE_PREFIX_CONSTANT_PLUS_SLOPE_ONLY",
        "nulls": ["PREFIX_AFFINE", "SATURN_BARYCENTER_GEOMETRY_DESTROYING"],
        "seven_open_terms": list(OPEN_TERM_NAMES),
        "media_products": MEDIA_PRODUCTS,
        "causal_state_policy": {
            "states": ["OBSERVABLE", "MODELED", "BOUNDED", "UNRESOLVED"],
            "combination": "CORRELATED_INTERVAL_ENVELOPE",
            "probabilities": "NOT_USED",
        },
        "forbidden": [
            "data CHDO or IQ access",
            "amplitude or signal diagnostics",
            "NCO treated as measured RF",
            "per-band affine fit",
            "suffix refit",
            "free time phase",
            "FITSIG promoted to deterministic bound",
            "central model promoted to uncertainty",
            "unresolved term set to zero",
            "root-sum-square without documented independence",
            "detector implementation",
        ],
    }


def compiler_manifest_sha256() -> str:
    return sha256(strict_json(compiler_manifest()).encode("ascii")).hexdigest()


def canonical_source_sha256() -> str:
    return sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def strict_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _vector(name, values) -> np.ndarray:
    result = np.asarray(values, dtype=np.float64)
    if result.ndim != 1 or result.size == 0 or not np.all(np.isfinite(result)):
        raise CassiniDualRootCompilerError(f"{name} must be a finite vector")
    return result


def _range(values) -> dict[str, float]:
    array = _vector("range", values)
    return {"minimum": float(np.min(array)), "maximum": float(np.max(array))}


def _metrics(values) -> dict[str, float]:
    array = _vector("metrics", values)
    return {
        "minimum_hz": float(np.min(array)),
        "maximum_hz": float(np.max(array)),
        "peak_to_peak_hz": float(np.ptp(array)),
        "rms_hz": float(sqrt(float(np.mean(array * array)))),
    }


if __name__ == "__main__":
    raise SystemExit(
        "Import run_once after freezing the source commit; no implicit network run."
    )
