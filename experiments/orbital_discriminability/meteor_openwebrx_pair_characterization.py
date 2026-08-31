"""One-shot, amplitude-blind characterization of the frozen METEOR pair.

This is deliberately not an OpenWebRX adapter.  It knows exactly two endpoints
and exists only to decide whether their delivered spectrum products can support
the already-shortlisted visibility experiment.  Spectrum payloads are hashed
in RAM and discarded without decoding.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import struct
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable


SCHEMA = "SRO_METEOR_OPENWEBRX_PAIR_CHARACTERIZATION_V1"
TARGET_CARRIER_HZ = 137_900_000
CAPTURE_DURATION_S = 12.0
CONNECT_TIMEOUT_S = 12.0
PROFILE_TIMEOUT_S = 20.0

# The characterization must remain outside every frozen METEOR shortlist
# interval.  These are not used to select or interpret an RF feature.
FORBIDDEN_WINDOWS = (
    ("2026-08-30T11:15:00Z", "2026-08-30T11:33:45Z"),
    ("2026-08-30T12:54:15Z", "2026-08-30T13:14:05Z"),
    ("2026-08-31T12:32:25Z", "2026-08-31T12:52:25Z"),
)


@dataclass(frozen=True)
class FrozenEndpoint:
    capability_id: str
    websocket_url: str
    origin: str
    profile_name: str
    declared_center_hz: int
    declared_span_hz: int
    latitude_deg: float
    longitude_deg: float
    hardware_root: str


ENDPOINTS = (
    FrozenEndpoint(
        capability_id="OPENWEBRXNL_ALKMAAR",
        websocket_url="wss://openwebrx.nl/ws/",
        origin="https://openwebrx.nl",
        profile_name="AIR 136 - 142",
        declared_center_hz=139_000_000,
        declared_span_hz=6_000_000,
        latitude_deg=52.645858,
        longitude_deg=4.759133,
        hardware_root="Airspy at Alkmaar, Netherlands",
    ),
    FrozenEndpoint(
        capability_id="YO3BN_BUCHAREST",
        websocket_url="wss://rtlsdr.yo3bn.ro/ws/",
        origin="https://rtlsdr.yo3bn.ro",
        profile_name="24 MHz - 1.766 GHz",
        declared_center_hz=137_000_000,
        declared_span_hz=2_400_000,
        latitude_deg=44.52279019175457,
        longitude_deg=26.257646144666005,
        hardware_root="RTL-SDR at YO3BN Bucharest, Romania",
    ),
)


class CharacterizationError(RuntimeError):
    """Typed refusal for the one-shot characterization."""


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def outside_frozen_windows(instant: datetime) -> bool:
    if instant.tzinfo is None:
        raise ValueError("instant must be timezone-aware")
    return all(
        not (_parse_utc(start) <= instant <= _parse_utc(end))
        for start, end in FORBIDDEN_WINDOWS
    )


def profile_covers(center_hz: float, span_hz: float, carrier_hz: float) -> bool:
    if not all(math.isfinite(v) for v in (center_hz, span_hz, carrier_hz)):
        return False
    if span_hz <= 0:
        return False
    return center_hz - span_hz / 2 <= carrier_hz <= center_hz + span_hz / 2


def parse_wire_text(message: str) -> tuple[str, Any]:
    """Parse only descriptive OpenWebRX messages used by this probe."""

    if message.startswith("CLIENT DE SERVER"):
        return "handshake", message
    payload = message[4:] if message.startswith("MSG ") else message
    try:
        value = json.loads(payload)
    except json.JSONDecodeError:
        return "description", message
    if not isinstance(value, dict):
        return "description", message
    return str(value.get("type", "description")), value.get("value")


def wire_profile_label_matches(label: object, frozen_profile_name: str) -> bool:
    """Match the UI label without weakening the frozen profile identity.

    OpenWebRX constructs the wire label as ``<SDR name> <profile name>`` while
    status.json exposes only ``<profile name>``.  The delivered center/span and
    selected profile id are still checked independently after selection.
    """

    if not isinstance(label, str):
        return False
    return label == frozen_profile_name or label.endswith(" " + frozen_profile_name)


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    weight = index - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _strict_json(value: Any) -> str:
    return json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":"))


def validate_receipt(receipt: dict[str, Any]) -> None:
    encoded = _strict_json(receipt).lower()
    for forbidden in (
        '"samples"',
        '"iq"',
        '"spectrum_values"',
        '"waterfall"',
        '"raw_frame"',
        '"payload"',
    ):
        if forbidden in encoded:
            raise ValueError(f"forbidden RF persistence field: {forbidden}")


def _config_is_target(config: dict[str, Any], profile_id: str) -> bool:
    return (
        config.get("profile_id") == profile_id.split("|", 1)[1]
        and config.get("sdr_id") == profile_id.split("|", 1)[0]
    )


def _descriptive_config(config: dict[str, Any]) -> dict[str, Any]:
    allowed = (
        "sdr_id",
        "profile_id",
        "center_freq",
        "samp_rate",
        "fft_size",
        "fft_compression",
        "audio_compression",
    )
    return {key: config[key] for key in allowed if key in config}


def _run_endpoint(
    endpoint: FrozenEndpoint,
    ready: threading.Barrier,
    websocket_module: Any,
) -> dict[str, Any]:
    opened_utc = datetime.now(timezone.utc)
    if not outside_frozen_windows(opened_utc):
        raise CharacterizationError("FROZEN_METEOR_WINDOW_ACTIVE")

    ws = websocket_module.create_connection(
        endpoint.websocket_url,
        timeout=CONNECT_TIMEOUT_S,
        origin=endpoint.origin,
        enable_multithread=True,
    )
    ws.settimeout(1.0)
    descriptions: list[str] = []
    target_profile_id: str | None = None
    current_config: dict[str, Any] = {}
    selected = False
    target_ready = False
    profiles_seen = 0
    handshake = None

    try:
        ws.send("SERVER DE CLIENT client=openwebrx.js type=receiver")
        deadline = time.monotonic() + PROFILE_TIMEOUT_S
        while time.monotonic() < deadline and not target_ready:
            try:
                item = ws.recv()
            except websocket_module.WebSocketTimeoutException:
                continue
            if isinstance(item, bytes):
                continue
            kind, value = parse_wire_text(item)
            if kind == "handshake":
                handshake = value
            elif kind == "profiles" and isinstance(value, list):
                profiles_seen = len(value)
                matches = [
                    row for row in value
                    if isinstance(row, dict)
                    and wire_profile_label_matches(row.get("name"), endpoint.profile_name)
                ]
                if len(matches) != 1:
                    raise CharacterizationError("FROZEN_PROFILE_NOT_UNIQUE_OR_ABSENT")
                target_profile_id = str(matches[0]["id"])
                if not selected:
                    ws.send(_strict_json({
                        "type": "selectprofile",
                        "params": {"profile": target_profile_id},
                    }))
                    selected = True
            elif kind == "config" and isinstance(value, dict):
                current_config.update(_descriptive_config(value))
                if target_profile_id and _config_is_target(current_config, target_profile_id):
                    target_ready = True
            elif kind in {"log_message", "sdr_error", "description"}:
                descriptions.append(str(value)[:240])

        if not target_ready or target_profile_id is None:
            raise CharacterizationError("TARGET_PROFILE_NOT_DELIVERED")

        center_hz = float(current_config.get("center_freq", math.nan))
        span_hz = float(current_config.get("samp_rate", math.nan))
        fft_size = int(current_config.get("fft_size", 0))
        if not profile_covers(center_hz, span_hz, TARGET_CARRIER_HZ):
            raise CharacterizationError("DELIVERED_PROFILE_DOES_NOT_COVER_CARRIER")
        if fft_size <= 0:
            raise CharacterizationError("FFT_SIZE_NOT_EXPOSED")

        ready.wait(timeout=PROFILE_TIMEOUT_S)
        capture_start_utc = datetime.now(timezone.utc)
        capture_start = time.monotonic()
        arrival_utc: list[datetime] = []
        arrival_monotonic: list[float] = []
        frame_lengths: set[int] = set()
        spectrum_frames = 0
        other_binary_frames = 0
        stream_hash = hashlib.sha256()
        config_changed = False

        while time.monotonic() - capture_start < CAPTURE_DURATION_S:
            try:
                item = ws.recv()
            except websocket_module.WebSocketTimeoutException:
                continue
            received_mono = time.monotonic()
            received_utc = datetime.now(timezone.utc)
            if isinstance(item, bytes):
                if not item:
                    continue
                if item[0] != 0x01:
                    other_binary_frames += 1
                    continue
                spectrum_frames += 1
                frame_lengths.add(len(item))
                arrival_monotonic.append(received_mono)
                arrival_utc.append(received_utc)
                stream_hash.update(struct.pack(">Q", len(item)))
                stream_hash.update(item)
                del item
                continue
            kind, value = parse_wire_text(item)
            if kind == "config" and isinstance(value, dict):
                changed = _descriptive_config(value)
                if any(
                    key in current_config and current_config[key] != candidate
                    for key, candidate in changed.items()
                ):
                    config_changed = True
                current_config.update(changed)

        capture_end_utc = datetime.now(timezone.utc)
        gaps = [
            later - earlier
            for earlier, later in zip(arrival_monotonic, arrival_monotonic[1:])
        ]
        duration_s = (capture_end_utc - capture_start_utc).total_seconds()
        receipt: dict[str, Any] = {
            "schema": SCHEMA,
            "capability_id": endpoint.capability_id,
            "root": {
                "hardware": endpoint.hardware_root,
                "latitude_deg": endpoint.latitude_deg,
                "longitude_deg": endpoint.longitude_deg,
                "independent_of_other_root": True,
            },
            "session": {
                "purpose": "NON_TARGET_SPECIFIC_PRODUCT_CHARACTERIZATION",
                "opened_utc": opened_utc.isoformat(),
                "capture_start_utc": capture_start_utc.isoformat(),
                "capture_end_utc": capture_end_utc.isoformat(),
                "capture_duration_s": duration_s,
                "outside_all_frozen_meteor_windows": True,
                "retry_count": 0,
                "rf_or_orbital_claim": "NONE",
            },
            "wire": {
                "handshake": handshake,
                "profiles_seen": profiles_seen,
                "selected_profile_id": target_profile_id,
                "descriptions": descriptions,
            },
            "product": {
                "type": "OPENWEBRX_SERVER_SIDE_LOG_POWER_SPECTRUM",
                "profile_name": endpoint.profile_name,
                "center_hz": center_hz,
                "span_hz": span_hz,
                "frequency_low_hz": center_hz - span_hz / 2,
                "frequency_high_hz": center_hz + span_hz / 2,
                "fft_size_bins": fft_size,
                "frequency_bin_spacing_hz": span_hz / fft_size,
                "fft_compression": current_config.get("fft_compression"),
                "fft_overlap": {"state": "UNKNOWN_NOT_EXPOSED_TO_CLIENT"},
                "fft_averaging": {"state": "UNKNOWN_NOT_EXPOSED_TO_CLIENT"},
                "resampling": {"state": "UNKNOWN_UPSTREAM"},
                "configuration_changed_during_capture": config_changed,
            },
            "arrival_observation": {
                "spectrum_frame_count": spectrum_frames,
                "other_binary_frame_count": other_binary_frames,
                "frame_length_bytes": sorted(frame_lengths),
                "first_frame_client_receipt_utc": (
                    arrival_utc[0].isoformat() if arrival_utc else None
                ),
                "last_frame_client_receipt_utc": (
                    arrival_utc[-1].isoformat() if arrival_utc else None
                ),
                "overall_client_receipt_cadence_hz": (
                    spectrum_frames / duration_s if duration_s > 0 else None
                ),
                "median_client_interarrival_s": (
                    statistics.median(gaps) if gaps else None
                ),
                "p95_client_interarrival_s": _percentile(gaps, 0.95),
                "maximum_client_interarrival_s": max(gaps) if gaps else None,
            },
            "ephemeral_artifact": {
                "hash_input": "LENGTH_PREFIXED_RAW_SPECTRUM_FRAMES",
                "sha256_before_discard": stream_hash.hexdigest(),
                "spectrum_values_decoded": False,
                "rf_data_persisted": False,
            },
            "event_time": {
                "server_frame_timestamp_exposed": False,
                "finite_sample_to_utc_bound": None,
                "available_semantics": "CLIENT_RECEIPT_UTC_AND_MONOTONIC_ONLY",
                "classification": "UNKNOWN_EVENT_TIME",
            },
            "sequence": {
                "server_sequence_exposed": False,
                "sample_continuity": "UNKNOWN",
                "client_arrival_trace_role": "TRANSPORT_OBSERVATION_ONLY",
            },
            "same_path_witness": {
                "state": "NOT_AVAILABLE",
                "reason": (
                    "Frame delivery witnesses transport and spectrum production, "
                    "but no predeclared physical in-band witness was observed by "
                    "this amplitude-blind characterization."
                ),
            },
            "transform_ledger": [
                "ANTENNA_FRONT_END_ADC",
                "COMPLEX_SERVER_BUFFER",
                "FFT",
                "LOG_POWER_OR_LOG_AVERAGE_POWER_UNKNOWN",
                "FFT_SIDE_SWAP_TO_CENTERED_ORDER",
                "OPTIONAL_LOSSY_ADPCM",
                "WEBSOCKET_WITHOUT_FRAME_TIMESTAMP_OR_SEQUENCE",
                "CLIENT_RECEIPT_CLOCK",
            ],
        }
        if spectrum_frames == 0:
            raise CharacterizationError("NO_SPECTRUM_FRAMES_DELIVERED")
        validate_receipt(receipt)
        return receipt
    finally:
        ws.close()


def pair_outcome(receipts: Iterable[dict[str, Any]]) -> str:
    rows = list(receipts)
    if len(rows) != 2:
        return "MEASUREMENT_PATH_INSUFFICIENT"
    for row in rows:
        if row["event_time"]["finite_sample_to_utc_bound"] is None:
            return "MEASUREMENT_PATH_INSUFFICIENT"
        if row["sequence"]["sample_continuity"] != "BOUNDED":
            return "MEASUREMENT_PATH_INSUFFICIENT"
        if row["same_path_witness"]["state"] != "AVAILABLE":
            return "MEASUREMENT_PATH_INSUFFICIENT"
    return "PAIR_ADMISSIBLE_FOR_FORWARD_FREEZE"


def run_live(websocket_module: Any) -> dict[str, Any]:
    if not outside_frozen_windows(datetime.now(timezone.utc)):
        raise CharacterizationError("FROZEN_METEOR_WINDOW_ACTIVE")
    barrier = threading.Barrier(len(ENDPOINTS))
    with ThreadPoolExecutor(max_workers=len(ENDPOINTS)) as pool:
        futures = [
            pool.submit(_run_endpoint, endpoint, barrier, websocket_module)
            for endpoint in ENDPOINTS
        ]
        receipts = [future.result() for future in futures]
    result = {
        "schema": SCHEMA,
        "bounded_candidate_count": 3,
        "descriptively_admissible_pair": [row.capability_id for row in ENDPOINTS],
        "receipts": receipts,
        "outcome": pair_outcome(receipts),
        "authorized_claim": (
            "Delivered product properties were characterized outside the "
            "frozen target windows; no RF feature or orbital claim was made."
        ),
    }
    validate_receipt(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--live",
        action="store_true",
        help="perform the single pre-authorized live characterization",
    )
    args = parser.parse_args()
    if not args.live:
        raise SystemExit("live access requires the explicit --live flag")
    import websocket

    print(_strict_json(run_live(websocket)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
