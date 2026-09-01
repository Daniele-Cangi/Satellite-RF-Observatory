"""Bounded, metadata-only METEOR-M N2-4 SatNOGS forward selection.

The candidate transmitter, two development observations and four sealed
primary roots are explicit constants.  This module performs no discovery,
network access, artifact access or RF decoding.  It ranks only the declared
primary roots by the G0/G1 observer-coupled geometry and records why geometry
alone cannot admit the measurement transform.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from itertools import combinations
import json
from math import asin, cos, isfinite, radians, sin, sqrt
from typing import Mapping

import numpy as np

from experiments.live_instrument.models import strict_json_value
from experiments.live_instrument.orbital_kernel import Observer, TLEElements

from .nuisance import (
    affine_shape_residual,
    differential_network_heldout_rmse,
    make_calibration_split,
)
from .null_models import fit_frozen_nulls
from .trajectory import apply_carrier_hz, sample_observer_network


OUTCOME = "SATNOGS_GEOMETRY_SHORTLISTED_MEASUREMENT_TRANSFORM_UNRESOLVED"
NORAD_ID = 59051
CARRIER_HZ = 137_900_000.0
TRANSMITTER_UUID = "dP82t5VrQC6hQDC39wxPo8"
CADENCE_S = 1.0
MINIMUM_ELEVATION_DEG = 10.0
CALIBRATION_FRACTION = 0.2
MINIMUM_CALIBRATION_SAMPLES = 6
MINIMUM_HOLDOUT_SAMPLES = 16
MINIMUM_SIGNATURE_BINS = 3.0
METADATA_EVALUATED_AT = "2026-09-01T07:43:38.576Z"

PRIMARY_TLE = TLEElements(
    "1 59051U 24039A   26243.87120958 -.00000002  00000-0  18821-4 0  9992",
    "2 59051  98.7087 202.2433 0006318 318.9944  41.0758 14.22436263130027",
    "METEOR M2-4",
)


@dataclass(frozen=True, slots=True)
class SatnogsRecord:
    observation_id: int
    station_id: int
    station_name: str
    observer: Observer
    start: datetime
    end: datetime
    status: str
    client_version: str
    radio_version: str | None
    sample_rate_hz: float | None
    lo_offset_hz: float | None
    coordinate_note: str
    role: str

    @property
    def capability_id(self) -> str:
        return f"SATNOGS_{self.station_id}_{self.station_name}"


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc)


DEVELOPMENT_RECORDS = (
    SatnogsRecord(
        14904366,
        4545,
        "OE9BKJ",
        Observer(47.4675556, 9.6692303, 412.0),
        _utc("2026-08-29T13:21:42Z"),
        _utc("2026-08-29T13:29:17Z"),
        "good",
        "1.9.3+5.g4eedaa1",
        "v2.3-compat-xxx-v2.3.5.0",
        3_000_000.0,
        None,
        "network API and client metadata agree",
        "DETECTOR_DEVELOPMENT_ONLY_PAYLOAD_SEALED",
    ),
    SatnogsRecord(
        14907984,
        5066,
        "SA1CKW",
        Observer(57.276, 18.471, 38.0),
        _utc("2026-08-29T13:22:44Z"),
        _utc("2026-08-29T13:32:58Z"),
        "good",
        "2.1.2",
        None,
        2_048_000.0,
        None,
        "network API and client metadata agree",
        "DETECTOR_DEVELOPMENT_ONLY_PAYLOAD_SEALED",
    ),
)


PRIMARY_RECORDS = (
    SatnogsRecord(
        14919555,
        1768,
        "EA3AGB",
        Observer(40.688, 0.573, 8.0),
        _utc("2026-09-01T04:10:35Z"),
        _utc("2026-09-01T04:24:41Z"),
        "unknown",
        "1.6",
        "2.3.1.1",
        2_048_000.0,
        None,
        "network API and client metadata agree",
        "PRIMARY_CANDIDATE_PAYLOAD_SEALED",
    ),
    SatnogsRecord(
        14919561,
        5140,
        "hyperlink",
        Observer(51.883, 0.813, 50.0),
        _utc("2026-09-01T04:09:45Z"),
        _utc("2026-09-01T04:19:52Z"),
        "unknown",
        "2.1.2",
        None,
        2_048_000.0,
        None,
        "network API and client metadata agree",
        "PRIMARY_CANDIDATE_PAYLOAD_SEALED",
    ),
    SatnogsRecord(
        14919551,
        147,
        "F6KKR",
        Observer(48.635, 1.829, 100.0),
        _utc("2026-09-01T04:08:12Z"),
        _utc("2026-09-01T04:22:51Z"),
        "unknown",
        "0.8",
        None,
        None,
        None,
        "network API altitude 100 m conflicts with client metadata altitude 200 m",
        "PRIMARY_CANDIDATE_PAYLOAD_SEALED",
    ),
    SatnogsRecord(
        14919554,
        949,
        "SM0KOT-VHF",
        Observer(59.273, 17.788, 55.0),
        _utc("2026-09-01T04:05:58Z"),
        _utc("2026-09-01T04:17:23Z"),
        "unknown",
        "1.9.3",
        "v2.3-compat-xxx-v2.3.5.0",
        2_048_000.0,
        100_000.0,
        "network API and client metadata agree",
        "PRIMARY_CANDIDATE_PAYLOAD_SEALED",
    ),
)


def evaluate_selection() -> dict[str, object]:
    """Return a strict geometry receipt for the frozen capability set."""

    pairs = tuple(
        _evaluate_pair(left, right)
        for left, right in combinations(PRIMARY_RECORDS, 2)
    )
    ranked = sorted(
        pairs,
        key=lambda item: (
            item["geometry_only_resolution_ceiling_hz"],
            item["controlling_null_heldout_rmse_hz"],
            item["differential_signature_span_hz"],
            item["pair"],
        ),
        reverse=True,
    )
    ranked = [dict(item, rank=index) for index, item in enumerate(ranked, 1)]

    receipt: dict[str, object] = {
        "outcome": OUTCOME,
        "scope": "METADATA_SOURCE_AUDIT_AND_GEOMETRY_ONLY",
        "metadata_evaluated_at": METADATA_EVALUATED_AT,
        "physical_question": (
            "can a frozen METEOR orbit predict station-coupled carrier structure "
            "in two independent SatNOGS products better than frozen nulls"
        ),
        "candidate": {
            "name": "METEOR-M N2-4",
            "norad_id": NORAD_ID,
            "carrier_hz": CARRIER_HZ,
            "transmitter_uuid": TRANSMITTER_UUID,
            "orbit_role": "MODEL_CONDITIONED_PRIMARY_RECORD_TLE",
            "tle_sha256": _strict_hash(
                {"name": PRIMARY_TLE.name, "line1": PRIMARY_TLE.line1, "line2": PRIMARY_TLE.line2}
            ),
            "claim_limit": "not independent satellite identity evidence",
        },
        "frozen_geometry_policy": {
            "cadence_s": CADENCE_S,
            "minimum_elevation_deg": MINIMUM_ELEVATION_DEG,
            "calibration_fraction": CALIBRATION_FRACTION,
            "minimum_calibration_samples": MINIMUM_CALIBRATION_SAMPLES,
            "minimum_holdout_samples": MINIMUM_HOLDOUT_SAMPLES,
            "minimum_signature_bins": MINIMUM_SIGNATURE_BINS,
            "joint_visibility": "required on calibration and heldout samples",
            "rank_key": (
                "minimum of affine-residual span/3 and controlling frozen-null "
                "heldout RMSE, before instrument envelopes"
            ),
        },
        "development_records": [_record_payload(item) for item in DEVELOPMENT_RECORDS],
        "sealed_primary_records": [_record_payload(item) for item in PRIMARY_RECORDS],
        "ranked_primary_pairs": ranked,
        "source_transform_audit": _source_transform_audit(),
        "measurement_admission": {
            "state": "UNRESOLVED",
            "exact_blockers": [
                "the waterfall is downstream of model-driven Doppler compensation",
                "the exact applied correction time series is not exposed in the observation metadata",
                "the deployed satnogs-flowgraphs revision is not identified by client_metadata radio.version",
                "actual FFT nchan, nfft_per_row and absolute row times require unopened artifact metadata",
                "PNG-only clients do not all expose a reversible pixel-to-native-bin mapping",
                "primary observation status remains unknown and cannot be promoted to good",
            ],
            "required_before_any_plan_freeze": [
                "development-only artifact metadata must expose native row time and frequency axes",
                "the post-Doppler receiver transform must be reconstructible with a bounded error",
                "one model-blind ridge detector must be frozen on development products only",
                "the selected primary pair and all of its RF payloads remain unopened until then",
            ],
        },
        "stop_condition": (
            "do not access any SatNOGS RF product while the applied Doppler-control "
            "ledger or native raster coordinates remain unresolved"
        ),
        "network_activity": "METADATA_AND_OFFICIAL_SOURCE_ONLY",
        "rf_artifact_requests": 0,
        "rf_bytes_accessed": 0,
        "audio_requests": 0,
        "decoded_data_requests": 0,
    }
    receipt["receipt_sha256"] = _strict_hash(receipt)
    strict_json(receipt)
    return receipt


def _evaluate_pair(left: SatnogsRecord, right: SatnogsRecord) -> dict[str, object]:
    start = max(left.start, right.start)
    end = min(left.end, right.end)
    if end <= start:
        raise ValueError("the declared primary pair has no common observation interval")
    trajectories = sample_observer_network(
        PRIMARY_TLE,
        {left.capability_id: left.observer, right.capability_id: right.observer},
        start,
        end,
        CADENCE_S,
        minimum_elevation_deg=MINIMUM_ELEVATION_DEG,
    )
    identifiers = tuple(sorted(trajectories))
    left_id, right_id = identifiers
    left_trajectory = trajectories[left_id]
    right_trajectory = trajectories[right_id]
    full_predictions: Mapping[str, np.ndarray] = {
        left_id: np.asarray(
            apply_carrier_hz(left_trajectory.fractional_doppler, CARRIER_HZ),
            dtype=np.float64,
        ),
        right_id: np.asarray(
            apply_carrier_hz(right_trajectory.fractional_doppler, CARRIER_HZ),
            dtype=np.float64,
        ),
    }
    full_masks: Mapping[str, np.ndarray] = {
        left_id: np.asarray(left_trajectory.visibility_mask, dtype=bool),
        right_id: np.asarray(right_trajectory.visibility_mask, dtype=bool),
    }
    joint = full_masks[left_id] & full_masks[right_id]
    visible_indices = np.flatnonzero(joint)
    if visible_indices.size < MINIMUM_CALIBRATION_SAMPLES + MINIMUM_HOLDOUT_SAMPLES:
        raise ValueError("primary pair lacks one usable jointly visible segment")
    if not np.all(np.diff(visible_indices) == 1):
        raise ValueError("primary pair has fragmented joint visibility")

    # Segment selection depends only on frozen orbit, station geometry and the
    # observation interval.  No RF value can move the calibration boundary.
    segment = slice(int(visible_indices[0]), int(visible_indices[-1]) + 1)
    segment_timestamps = left_trajectory.timestamps[segment]
    elapsed = np.asarray(
        [
            (timestamp - segment_timestamps[0]).total_seconds()
            for timestamp in segment_timestamps
        ],
        dtype=np.float64,
    )
    predictions: Mapping[str, np.ndarray] = {
        identifier: values[segment]
        for identifier, values in full_predictions.items()
    }
    masks: Mapping[str, np.ndarray] = {
        identifier: np.ones(elapsed.size, dtype=bool) for identifier in identifiers
    }
    joint_segment = np.ones(elapsed.size, dtype=bool)
    split = make_calibration_split(
        elapsed.size,
        CALIBRATION_FRACTION,
        minimum_calibration_samples=MINIMUM_CALIBRATION_SAMPLES,
        minimum_holdout_samples=MINIMUM_HOLDOUT_SAMPLES,
    )
    calibration = np.asarray(split.calibration_indices, dtype=np.int64)
    holdout = np.asarray(split.holdout_indices, dtype=np.int64)
    visible_calibration = calibration[joint_segment[calibration]]
    visible_holdout = holdout[joint_segment[holdout]]
    if visible_calibration.size < MINIMUM_CALIBRATION_SAMPLES:
        raise ValueError("primary pair lacks jointly visible calibration samples")
    if visible_holdout.size < MINIMUM_HOLDOUT_SAMPLES:
        raise ValueError("primary pair lacks jointly visible heldout samples")

    differential = predictions[left_id] - predictions[right_id]
    residual = np.asarray(
        affine_shape_residual(elapsed, differential, split, valid_mask=joint_segment),
        dtype=np.float64,
    )
    signature = _peak_to_peak(residual[visible_holdout])
    nulls = fit_frozen_nulls(
        elapsed,
        predictions,
        predictions,
        split,
        visibility_masks=masks,
    )
    null_scores = []
    for model in nulls:
        score, count = differential_network_heldout_rmse(
            predictions,
            model.prediction_hz,
            split,
            visibility_masks=masks,
            minimum_pair_samples=MINIMUM_HOLDOUT_SAMPLES,
        )
        null_scores.append(
            {
                "name": model.name,
                "model_family": model.model_family,
                "parameter_count": model.parameter_count,
                "heldout_rmse_hz": score,
                "joint_heldout_count": count,
            }
        )
    controlling = min(null_scores, key=lambda item: (item["heldout_rmse_hz"], item["name"]))
    signature_ceiling = signature / MINIMUM_SIGNATURE_BINS
    geometry_ceiling = min(signature_ceiling, float(controlling["heldout_rmse_hz"]))
    numeric = (
        signature,
        signature_ceiling,
        geometry_ceiling,
        *(float(item["heldout_rmse_hz"]) for item in null_scores),
    )
    if not all(isfinite(value) for value in numeric):
        raise ValueError("pair ranking produced a non-finite value")

    return {
        "pair": [left_id, right_id],
        "observation_ids": sorted((left.observation_id, right.observation_id)),
        "common_start": start.isoformat(),
        "common_end": end.isoformat(),
        "common_duration_s": (end - start).total_seconds(),
        "baseline_km": _surface_distance_km(left.observer, right.observer),
        "joint_visible_start": segment_timestamps[0].isoformat(),
        "joint_visible_end": segment_timestamps[-1].isoformat(),
        "joint_visible_calibration_samples": int(visible_calibration.size),
        "joint_visible_holdout_samples": int(visible_holdout.size),
        "left_maximum_elevation_deg": float(np.max(left_trajectory.elevation_deg)),
        "right_maximum_elevation_deg": float(np.max(right_trajectory.elevation_deg)),
        "differential_signature_span_hz": signature,
        "signature_only_resolution_ceiling_hz": signature_ceiling,
        "controlling_null": controlling["name"],
        "controlling_null_heldout_rmse_hz": controlling["heldout_rmse_hz"],
        "geometry_only_resolution_ceiling_hz": geometry_ceiling,
        "frozen_null_scores": null_scores,
        "instrument_envelope": "UNKNOWN_NOT_SUBTRACTED",
        "geometry_classification": "POSITIVE_BEFORE_INSTRUMENT_ENVELOPE",
    }


def _record_payload(record: SatnogsRecord) -> dict[str, object]:
    payload: dict[str, object] = {
        "observation_id": record.observation_id,
        "station_id": record.station_id,
        "station_name": record.station_name,
        "hardware_root": f"satnogs-station:{record.station_id}",
        "coordinates": asdict(record.observer),
        "coordinate_note": record.coordinate_note,
        "start": record.start.isoformat(),
        "end": record.end.isoformat(),
        "status": record.status,
        "client_version": record.client_version,
        "radio_version": record.radio_version,
        "declared_sample_rate_hz": record.sample_rate_hz,
        "declared_lo_offset_hz": record.lo_offset_hz,
        "role": record.role,
        "payload_access": "ZERO",
    }
    payload["metadata_snapshot_sha256"] = _strict_hash(payload)
    return payload


def _source_transform_audit() -> dict[str, object]:
    return {
        "native_waterfall_dat": {
            "header_fields": [
                "timestamp",
                "nchan",
                "samp_rate",
                "nfft_per_row",
                "center_freq",
                "endianness",
            ],
            "row_fields": ["tabs_microseconds", "spectrum_float32_per_channel"],
            "frequency_spacing": "samp_rate/nchan",
            "nominal_row_spacing": "nfft_per_row*nchan/samp_rate",
            "actual_row_time": "tabs/1e6 relative to header timestamp",
        },
        "hdf5_artifact": {
            "artifact_v1_client": "1.6",
            "artifact_v2_clients": ["1.9.3", "2.1.2"],
            "preserved_coordinates": ["relative_time", "absolute_time", "frequency"],
            "start_time_warning": "not necessarily equal to observation start",
            "amplitude_transform": (
                "per-frequency offset/scale followed by clipping to uint8; reversible "
                "only within the non-clipped range when offset and scale are retained"
            ),
            "availability_for_frozen_records": "NOT_CHECKED_PAYLOADS_SEALED",
        },
        "png_raster": {
            "client_1_6_and_1_9": (
                "matplotlib raster with display extent; no embedded native header "
                "metadata demonstrated by those versioned sources"
            ),
            "client_2_1_family": (
                "PNG supports satnogs:wf-dat and satnogs:wf-plot textual metadata; "
                "presence in the sealed record is not yet observed"
            ),
            "native_bin_equivalence": False,
        },
        "doppler_control": {
            "topology": "soapy source -> Doppler compensation -> waterfall sink",
            "verified_release_families": {
                "satnogs-flowgraphs-1.3-generic-fsk_sha256": (
                    "f09a26a33b2ea7cd215a01db63d8a79e6a54b619e5c329a6234640b548f96b2c"
                ),
                "satnogs-flowgraphs-1.5-generic-fsk_sha256": (
                    "dda3c64161bdffacbf516a86e81e87fce6294815ec22c24770e747d0b9f38032"
                ),
                "satnogs-flowgraphs-2.5.2-generic-fsk-ax25_sha256": (
                    "d7e17b2583d9513d3de14baa2b21414e0183a24563a0350f52362e3d1c4f22cf"
                ),
            },
            "exact_deployed_flowgraph_per_record": "UNKNOWN",
            "applied_control_samples_or_polynomial": "NOT_EXPOSED_IN_OBSERVATION_METADATA",
            "scientific_consequence": (
                "the recorded ridge is in model-controlled baseband, not an absolute-RF "
                "Doppler coordinate; every orbital and null prediction must receive the "
                "same applied control transform"
            ),
        },
    }


def _surface_distance_km(left: Observer, right: Observer) -> float:
    left_lat = radians(left.latitude_deg)
    right_lat = radians(right.latitude_deg)
    latitude_delta = right_lat - left_lat
    longitude_delta = radians(right.longitude_deg - left.longitude_deg)
    term = sin(latitude_delta / 2.0) ** 2 + (
        cos(left_lat) * cos(right_lat) * sin(longitude_delta / 2.0) ** 2
    )
    return 2.0 * 6371.0088 * asin(sqrt(term))


def _peak_to_peak(values: np.ndarray) -> float:
    if values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("peak-to-peak requires a non-empty finite vector")
    return float(np.max(values) - np.min(values))


def _strict_hash(payload: Mapping[str, object]) -> str:
    return sha256(strict_json(payload).encode("utf-8")).hexdigest()


def strict_json(payload: Mapping[str, object]) -> str:
    return json.dumps(
        strict_json_value(payload),
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


if __name__ == "__main__":
    print(strict_json(evaluate_selection()))
