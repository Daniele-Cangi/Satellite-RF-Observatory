"""Orbit-first METEOR-M N2-4 visibility shortlist, without RF access.

This bounded audit replaces the synthetic city lattice with one current
satellite, one exact descriptive OpenWebRX location, one exact-but-offline
candidate, and one deliberately broad Doncaster *geometry proxy*.  The proxy
is never promoted to a station coordinate or an admitted capability.

The module is intentionally a one-off physical vertical.  It is not a source
catalogue, adapter, scheduler, or new gate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Iterable

import numpy as np
from skyfield.api import EarthSatellite, load, wgs84

from experiments.live_instrument.orbital_kernel import Observer, TLEElements

from .distributed_visibility_event_spike import (
    MINIMUM_STATE_DWELL_S,
    OCCULTED_MAXIMUM_ELEVATION_DEG,
    REQUIRED_CONFIRMATION_FRAMES,
    StateSegment,
    VISIBLE_MINIMUM_ELEVATION_DEG,
    _maximum_duration,
    _ordered_states,
)


GEOMETRY_OUTCOME = "METEOR_M2_4_VISIBILITY_GEOMETRY_SHORTLISTED"
OVERALL_BLOCKED_OUTCOME = "NO_FALSIFIABLE_VISIBILITY_EXPERIMENT_AVAILABLE"

NORAD_ID = 59051
OBJECT_ID = "2024-039A"
CANDIDATE_CARRIER_HZ = 137_900_000.0
DISCOVERY_START = datetime(2026, 8, 30, 0, 0, tzinfo=timezone.utc)
DISCOVERY_END = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
DISCOVERY_CADENCE_S = 30.0
REFINEMENT_CADENCE_S = 5.0
REFINEMENT_PADDING_S = 600.0
_TIMESCALE = load.timescale(builtin=True)

CURRENT_OMM_DESCRIPTION: dict[str, object] = {
    "OBJECT_NAME": "METEOR-M2 4",
    "OBJECT_ID": OBJECT_ID,
    "EPOCH": "2026-08-29T06:26:44.437632",
    "MEAN_MOTION": "14.224360580000001",
    "ECCENTRICITY": "0.00064526999999999998",
    "INCLINATION": "98.708299999999994",
    "RA_OF_ASC_NODE": "199.6712",
    "ARG_OF_PERICENTER": "327.26549999999997",
    "MEAN_ANOMALY": "32.8123",
    "EPHEMERIS_TYPE": "0",
    "CLASSIFICATION_TYPE": "U",
    "NORAD_CAT_ID": "59051",
    "ELEMENT_SET_NO": "999",
    "REV_AT_EPOCH": "12965",
    "BSTAR": "2.0148397E-5",
    "MEAN_MOTION_DOT": "1.0E-8",
    "MEAN_MOTION_DDOT": "0",
}


# The latest element set found in the bounded audit is frozen nominally.  Two
# adjacent public sets are alternatives, not a statistically calibrated orbit
# covariance.  Their source and epoch remain explicit in the receipt.
NOMINAL_TLE = TLEElements(
    "1 59051U 24039A   26241.90164442  .00000009  00000-0  23815-4 0  9995",
    "2 59051  98.7084 200.2968 0006420 325.2574  34.8184 14.22436124129745",
    "METEOR-M2 4",
)
ADJACENT_TLES: dict[str, TLEElements] = {
    "CELESTRAK_MIRROR_2026_08_29T14_53_12Z": TLEElements(
        "1 59051U 24039A   26241.62027794  .00000005  00000+0  22113-4 0  9997",
        "2 59051  98.7083 200.0188 0006432 326.1535  33.9232 14.22436089129706",
        "METEOR-M2 4",
    ),
    "SPACE_TRACK_SATNOGS_2026_08_28T06_48_39Z": TLEElements(
        "1 59051U 24039A   26240.28378727 -.00000006  00000-0  17151-4 0  9992",
        "2 59051  98.7081 198.6980 0006510 330.3393  29.7415 14.22435971129516",
        "METEOR-M2 4",
    ),
}


YO3BN = Observer(44.52279019175457, 26.257646144666005, 80.0)
YO8TNB = Observer(47.957, 26.403, 180.0)

# AwareStation discloses Doncaster and latitude 53.5 N, but not a station
# longitude or ellipsoidal height.  This broad box is an analysis-only test of
# whether useful geometry survives the unresolved location.  It is not an
# inferred station location and cannot satisfy capability admission.
DONCASTER_GEOMETRY_ENVELOPE: tuple[Observer, ...] = tuple(
    Observer(latitude, longitude, altitude)
    for latitude in (53.2, 53.8)
    for longitude in (-1.5, -0.7)
    for altitude in (0.0, 250.0)
)
DONCASTER_GEOMETRY_PROXY = Observer(53.5, -1.1, 125.0)


@dataclass(frozen=True, slots=True)
class VisibilityEvent:
    start: datetime
    end: datetime
    topology: str
    left_only_duration_s: float
    both_visible_duration_s: float
    right_only_duration_s: float
    controlling_raw_duration_s: float


@dataclass(frozen=True, slots=True)
class VisibilitySamples:
    timestamps: tuple[datetime, ...]
    elevation_deg: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class ShortlistedEvent:
    rank: int
    start: datetime
    end: datetime
    topology: str
    nominal_controlling_duration_s: float
    robust_controlling_duration_s: float
    minimum_dwell_margin_s: float
    maximum_per_root_event_time_error_s: float
    maximum_frame_cadence_at_zero_timing_error_s: float
    event_time_frame_cadence_frontier: str
    coordinate_member_count: int
    orbit_member_count: int
    classification: str


def evaluate_meteor_m2_4_shortlist() -> dict[str, object]:
    """Return one strict metadata/geometric receipt with zero RF access."""

    observers = {
        "AWARESIGNAL_DONCASTER_GEOMETRY_PROXY": DONCASTER_GEOMETRY_PROXY,
        "YO3BN_BUCHAREST": YO3BN,
        "YO8TNB_DOROHOI": YO8TNB,
    }
    coarse = {
        name: _sample_elevations(
            NOMINAL_TLE,
            observer,
            DISCOVERY_START,
            DISCOVERY_END,
            DISCOVERY_CADENCE_S,
        )
        for name, observer in observers.items()
    }
    don_buc_events = _coarse_events(
        coarse["AWARESIGNAL_DONCASTER_GEOMETRY_PROXY"],
        coarse["YO3BN_BUCHAREST"],
    )
    buc_dor_events = _coarse_events(
        coarse["YO3BN_BUCHAREST"],
        coarse["YO8TNB_DOROHOI"],
    )
    shortlist = _robust_shortlist(don_buc_events)
    geometry_outcome = GEOMETRY_OUTCOME if len(shortlist) == 3 else (
        "NO_THREE_PASS_VISIBILITY_GEOMETRY_SHORTLIST"
    )

    plan = _plan_payload()
    receipt: dict[str, object] = {
        "outcome": OVERALL_BLOCKED_OUTCOME,
        "geometry_outcome": geometry_outcome,
        "scope": "METADATA_AND_GEOMETRY_ONLY",
        "candidate": {
            "name": "METEOR-M N2-4",
            "norad_id": NORAD_ID,
            "object_id": OBJECT_ID,
            "operational_status": "OPERATIONAL_PER_WMO_OSCAR_2026_01_23",
            "real_time_product": "LRPT_SELECTED_IMAGES_DATA",
            "candidate_carrier_hz": CANDIDATE_CARRIER_HZ,
            "carrier_role": "SATNOGS_REVIEWED_LRPT_TRANSMITTER_CANDIDATE",
            "emission_continuity": "DOCUMENTED_BY_CURRENT_PUBLIC_STATION_NOT_OPERATOR",
        },
        "plan": plan,
        "plan_sha256": _strict_hash(plan),
        "orbit_sources": _orbit_sources(),
        "bounded_capability_set": _capability_receipts(),
        "doncaster_bucharest_shortlist": [
            _shortlisted_payload(item) for item in shortlist
        ],
        "bucharest_dorohoi_geometry": [
            _visibility_payload(item) for item in buc_dor_events
        ],
        "claim_scope": (
            "the frozen METEOR-M N2-4 orbit admits robust observer-coupled "
            "visibility sequences for a Doncaster location envelope and the "
            "documented YO3BN position; no measurement path is admitted"
        ),
        "exact_blocker": {
            "type": "NO_PAIR_OF_MEASUREMENT_CAPABILITIES_ADMITTED",
            "details": [
                "AwareSignal exact station coordinates are not documented",
                "AwareSignal raw IQ is described as saved but no public immutable artifact path is documented",
                "AwareSignal first-sample/event-time semantics and continuity receipt are unknown",
                "YO3BN sample-zero/server event-time binding, sequence continuity, directional mask and same-path witness are unknown",
                "YO8TNB is not reachable in the bounded status check",
            ],
        },
        "next_action_if_reviewed": (
            "one non-target-specific YO3BN measurement-path characterization "
            "plus an independently accessible western root; stop if neither "
            "provides a same-path absence witness and event-time bound"
        ),
        "network_scope": "DESCRIPTIVE_HTTP_ONLY",
        "rf_connections": 0,
        "rf_bytes_accessed": 0,
        "observation_values_accessed": 0,
    }
    json.dumps(receipt, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return receipt


def _coarse_events(left, right) -> tuple[VisibilityEvent, ...]:
    return tuple(
        event
        for group in _pass_groups(_segments_from_samples(left, right))
        if (event := _event_from_segments(group)) is not None
    )


def _sample_elevations(
    elements: TLEElements,
    observer: Observer,
    start: datetime,
    end: datetime,
    cadence_s: float,
) -> VisibilitySamples:
    """Vectorized use of the same Skyfield/SGP4 model as the orbital kernel."""

    count = int((end - start).total_seconds() // cadence_s) + 1
    timestamps = tuple(
        start + timedelta(seconds=index * cadence_s) for index in range(count)
    )
    satellite = EarthSatellite(
        elements.line1,
        elements.line2,
        elements.name,
        _TIMESCALE,
    )
    site = wgs84.latlon(
        observer.latitude_deg,
        observer.longitude_deg,
        elevation_m=observer.altitude_m,
    )
    times = _TIMESCALE.from_datetimes(timestamps)
    elevation, _, _ = (satellite - site).at(times).altaz()
    values = np.asarray(elevation.degrees, dtype=np.float64)
    if values.shape != (count,) or not np.all(np.isfinite(values)):
        raise ValueError("visibility propagation produced invalid elevation samples")
    return VisibilitySamples(timestamps, tuple(float(value) for value in values))


def _segments_from_samples(
    left: VisibilitySamples,
    right: VisibilitySamples,
) -> tuple[StateSegment, ...]:
    if left.timestamps != right.timestamps:
        raise ValueError("visibility samples must share one event-time grid")
    states = tuple(
        _visibility_state(left_elevation, right_elevation)
        for left_elevation, right_elevation in zip(
            left.elevation_deg,
            right.elevation_deg,
            strict=True,
        )
    )
    segments: list[StateSegment] = []
    start = 0
    for index in range(1, len(states) + 1):
        if index < len(states) and states[index] == states[start]:
            continue
        duration = (left.timestamps[index - 1] - left.timestamps[start]).total_seconds()
        segments.append(
            StateSegment(
                state=states[start],
                start=left.timestamps[start],
                end=left.timestamps[index - 1],
                conservative_duration_s=float(duration),
            )
        )
        start = index
    return tuple(segments)


def _visibility_state(left_elevation_deg: float, right_elevation_deg: float) -> str:
    left_visible = left_elevation_deg >= VISIBLE_MINIMUM_ELEVATION_DEG
    right_visible = right_elevation_deg >= VISIBLE_MINIMUM_ELEVATION_DEG
    left_occulted = left_elevation_deg <= OCCULTED_MAXIMUM_ELEVATION_DEG
    right_occulted = right_elevation_deg <= OCCULTED_MAXIMUM_ELEVATION_DEG
    if left_visible and right_occulted:
        return "LEFT_VISIBLE_RIGHT_OCCULTED"
    if right_visible and left_occulted:
        return "RIGHT_VISIBLE_LEFT_OCCULTED"
    if left_visible and right_visible:
        return "BOTH_VISIBLE"
    if left_occulted and right_occulted:
        return "BOTH_OCCULTED"
    return "EXCLUDED_TRANSITION_BAND"


def _pass_groups(segments: Iterable[StateSegment]) -> tuple[tuple[StateSegment, ...], ...]:
    groups: list[tuple[StateSegment, ...]] = []
    current: list[StateSegment] = []
    for segment in segments:
        if segment.state == "BOTH_OCCULTED":
            if current:
                groups.append(tuple(current))
                current = []
            continue
        current.append(segment)
    if current:
        groups.append(tuple(current))
    return tuple(groups)


def _event_from_segments(segments: tuple[StateSegment, ...]) -> VisibilityEvent | None:
    forward = _ordered_states(
        segments,
        ("LEFT_VISIBLE_RIGHT_OCCULTED", "BOTH_VISIBLE", "RIGHT_VISIBLE_LEFT_OCCULTED"),
    )
    reverse = _ordered_states(
        segments,
        ("RIGHT_VISIBLE_LEFT_OCCULTED", "BOTH_VISIBLE", "LEFT_VISIBLE_RIGHT_OCCULTED"),
    )
    if not (forward or reverse):
        return None
    left_only = _maximum_duration(segments, "LEFT_VISIBLE_RIGHT_OCCULTED")
    both = _maximum_duration(segments, "BOTH_VISIBLE")
    right_only = _maximum_duration(segments, "RIGHT_VISIBLE_LEFT_OCCULTED")
    return VisibilityEvent(
        start=segments[0].start,
        end=segments[-1].end,
        topology=(
            "LEFT_ONLY_TO_BOTH_TO_RIGHT_ONLY"
            if forward
            else "RIGHT_ONLY_TO_BOTH_TO_LEFT_ONLY"
        ),
        left_only_duration_s=left_only,
        both_visible_duration_s=both,
        right_only_duration_s=right_only,
        controlling_raw_duration_s=min(left_only, both, right_only),
    )


def _evaluate_window(
    elements: TLEElements,
    left: Observer,
    right: Observer,
    start: datetime,
    end: datetime,
) -> VisibilityEvent | None:
    left_samples = _sample_elevations(
        elements, left, start, end, REFINEMENT_CADENCE_S
    )
    right_samples = _sample_elevations(
        elements, right, start, end, REFINEMENT_CADENCE_S
    )
    events = _coarse_events(left_samples, right_samples)
    if not events:
        return None
    return max(events, key=lambda item: item.controlling_raw_duration_s)


def _robust_shortlist(coarse_events: tuple[VisibilityEvent, ...]) -> tuple[ShortlistedEvent, ...]:
    candidates: list[tuple[VisibilityEvent, float, int, int]] = []
    orbit_members = (NOMINAL_TLE, *ADJACENT_TLES.values())
    coordinate_members = (DONCASTER_GEOMETRY_PROXY, *DONCASTER_GEOMETRY_ENVELOPE)
    for coarse in coarse_events:
        start = coarse.start - timedelta(seconds=REFINEMENT_PADDING_S)
        end = coarse.end + timedelta(seconds=REFINEMENT_PADDING_S)
        nominal = _evaluate_window(
            NOMINAL_TLE,
            DONCASTER_GEOMETRY_PROXY,
            YO3BN,
            start,
            end,
        )
        if nominal is None:
            continue
        controlling: list[float] = []
        for elements in orbit_members:
            for doncaster in coordinate_members:
                event = _evaluate_window(elements, doncaster, YO3BN, start, end)
                controlling.append(
                    0.0 if event is None else event.controlling_raw_duration_s
                )
        candidates.append(
            (nominal, min(controlling), len(coordinate_members), len(orbit_members))
        )

    ranked = sorted(
        candidates,
        key=lambda item: (item[1], item[0].controlling_raw_duration_s, item[0].start),
        reverse=True,
    )[:3]
    output: list[ShortlistedEvent] = []
    for rank, (event, robust, coordinate_count, orbit_count) in enumerate(ranked, 1):
        margin = robust - MINIMUM_STATE_DWELL_S
        output.append(
            ShortlistedEvent(
                rank=rank,
                start=event.start,
                end=event.end,
                topology=event.topology,
                nominal_controlling_duration_s=event.controlling_raw_duration_s,
                robust_controlling_duration_s=robust,
                minimum_dwell_margin_s=margin,
                maximum_per_root_event_time_error_s=max(0.0, margin / 2.0),
                maximum_frame_cadence_at_zero_timing_error_s=(
                    robust / float(REQUIRED_CONFIRMATION_FRAMES)
                ),
                event_time_frame_cadence_frontier=(
                    f"2*event_time_error_s + {REQUIRED_CONFIRMATION_FRAMES}*"
                    f"frame_cadence_s <= {robust:.3f}"
                ),
                coordinate_member_count=coordinate_count,
                orbit_member_count=orbit_count,
                classification=(
                    "GEOMETRY_MARGIN_POSITIVE"
                    if margin > 0.0
                    else "GEOMETRY_BOUNDARY_NOT_ADMITTED"
                ),
            )
        )
    return tuple(output)


def _orbit_sources() -> dict[str, object]:
    return {
        "current_omm_description": {
            "source": "https://isstracker.pl/en/satellites/59051",
            "source_role": "PUBLIC_CELESTRAK_OMM_MIRROR",
            "omm": CURRENT_OMM_DESCRIPTION,
            "omm_sha256": _strict_hash(CURRENT_OMM_DESCRIPTION),
            "propagation_role": "DESCRIPTION_ONLY; newer TLE is nominal",
        },
        "nominal": {
            "epoch": "2026-08-29T21:38:22.077Z",
            "source": "https://www.satcat.com/sats/59051",
            "source_role": "PUBLIC_CELESTRAK_SPACE_TRACK_MIRROR",
            "line1": NOMINAL_TLE.line1,
            "line2": NOMINAL_TLE.line2,
        },
        "alternatives": [
            {
                "id": name,
                "line1": elements.line1,
                "line2": elements.line2,
            }
            for name, elements in sorted(ADJACENT_TLES.items())
        ],
        "interpretation": "BOUNDED_ADJACENT_ELEMENT_ENSEMBLE_NOT_COVARIANCE",
    }


def _visibility_payload(event: VisibilityEvent) -> dict[str, object]:
    payload = asdict(event)
    payload["start"] = event.start.isoformat()
    payload["end"] = event.end.isoformat()
    return payload


def _shortlisted_payload(event: ShortlistedEvent) -> dict[str, object]:
    payload = asdict(event)
    payload["start"] = event.start.isoformat()
    payload["end"] = event.end.isoformat()
    return payload


def _capability_receipts() -> list[dict[str, object]]:
    return [
        {
            "id": "YO3BN_BUCHAREST",
            "state": "CAPABILITY_DISCOVERED_NOT_ADMITTED",
            "coordinates": asdict(YO3BN),
            "coordinate_provenance": "LIVE_STATUS_JSON",
            "product": "OPENWEBRX_PLUS_PROFILE",
            "center_hz": 137_000_000,
            "sample_rate_hz": 2_400_000,
            "covers_candidate_carrier": True,
            "status_http": 200,
            "measurement_event_time": "UNKNOWN",
            "sequence_continuity": "UNKNOWN",
            "same_path_absence_witness": "UNKNOWN",
        },
        {
            "id": "AWARESIGNAL_DONCASTER",
            "state": "CAPABILITY_DISCOVERED_NOT_ADMITTED",
            "coordinates": "UNRESOLVED; public description only says Doncaster and 53.5 N",
            "product": "AUTOMATED_137_MHZ_RAW_IQ_CAPTURE_AND_SATDUMP_DECODE",
            "station_status": "ONLINE_IN_BOUNDED_DESCRIPTIVE_CHECK",
            "public_immutable_iq_artifact": "UNKNOWN",
            "measurement_event_time": "UNKNOWN",
            "sequence_continuity": "UNKNOWN",
            "same_path_absence_witness": "UNKNOWN",
        },
        {
            "id": "YO8TNB_DOROHOI",
            "state": "CAPABILITY_DISCOVERED_NOT_ADMITTED",
            "coordinates": asdict(YO8TNB),
            "product": "OPENWEBRX_PLUS_RSP1A",
            "weather_satellite_band": "137_MHZ_DOCUMENTED",
            "bounded_status": "TRANSPORT_UNREACHABLE",
            "measurement_event_time": "NOT_EVALUATED",
            "sequence_continuity": "NOT_EVALUATED",
            "same_path_absence_witness": "NOT_EVALUATED",
        },
    ]


def _plan_payload() -> dict[str, object]:
    return {
        "candidate": "METEOR-M N2-4 / NORAD 59051",
        "discovery_start": DISCOVERY_START.isoformat(),
        "discovery_end": DISCOVERY_END.isoformat(),
        "discovery_cadence_s": DISCOVERY_CADENCE_S,
        "refinement_cadence_s": REFINEMENT_CADENCE_S,
        "visible_minimum_elevation_deg": VISIBLE_MINIMUM_ELEVATION_DEG,
        "occulted_maximum_elevation_deg": OCCULTED_MAXIMUM_ELEVATION_DEG,
        "minimum_state_dwell_s": MINIMUM_STATE_DWELL_S,
        "required_confirmation_frames": REQUIRED_CONFIRMATION_FRAMES,
        "doncaster_geometry_envelope": [
            asdict(observer) for observer in DONCASTER_GEOMETRY_ENVELOPE
        ],
        "yo3bn": asdict(YO3BN),
        "yo8tnb": asdict(YO8TNB),
        "rf_access_authorized": False,
    }


def _strict_hash(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def main() -> int:
    print(json.dumps(evaluate_meteor_m2_4_shortlist(), indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
