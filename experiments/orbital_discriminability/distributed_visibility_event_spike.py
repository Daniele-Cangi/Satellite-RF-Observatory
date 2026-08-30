"""Bounded offline spike for observer-coupled visibility state.

This is deliberately a geometry experiment, not a receiver adapter and not a
new gate.  It asks whether one frozen LEO fixture can produce intervals in
which one observer is conservatively visible while another is geometrically
occulted, followed by the opposite ordering.  No RF product, carrier, network
endpoint, or signal value enters the calculation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from itertools import combinations
import json
from typing import Mapping

import numpy as np

from experiments.live_instrument.orbital_kernel import Observer

from .synthetic import (
    ISS_PLAUSIBLE_MISMATCH_OMM,
    ISS_TLE,
    PASS_START,
)
from .trajectory import OrbitalTrajectory, sample_observer_network


OUTCOME_ADMITTED = "DISTRIBUTED_VISIBILITY_MECHANISM_DISCRIMINATIVE"
OUTCOME_NOT_ADMITTED = "NO_DISTRIBUTED_VISIBILITY_GEOMETRY_ADMITTED"

FIXTURE_START = PASS_START - timedelta(minutes=20)
FIXTURE_END = PASS_START + timedelta(minutes=25)
CADENCE_S = 5.0

# These are conservative geometry states, not claims about any receiver mask.
# The four-degree dead band is excluded rather than treated as observable.
VISIBLE_MINIMUM_ELEVATION_DEG = 5.0
OCCULTED_MAXIMUM_ELEVATION_DEG = -2.0
PROVISIONAL_EVENT_TIME_ERROR_S = 5.0
MINIMUM_STATE_DWELL_S = 30.0
REQUIRED_CONFIRMATION_FRAMES = 3

# A bounded scientific geometry lattice.  Names denote WGS-84 observer
# positions only; they do not imply a receiver, station, or capability exists.
OBSERVER_GEOMETRIES: dict[str, Observer] = {
    "DUBLIN_GEOMETRY": Observer(53.3498, -6.2603, 20.0),
    "MADRID_GEOMETRY": Observer(40.4168, -3.7038, 667.0),
    "ROME_GEOMETRY": Observer(41.9028, 12.4964, 21.0),
    "WARSAW_GEOMETRY": Observer(52.2297, 21.0122, 100.0),
}


@dataclass(frozen=True, slots=True)
class StateSegment:
    state: str
    start: datetime
    end: datetime
    conservative_duration_s: float


@dataclass(frozen=True, slots=True)
class PairResult:
    left: str
    right: str
    topology: str
    left_only_duration_s: float
    joint_visible_duration_s: float
    right_only_duration_s: float
    controlling_duration_after_timing_s: float
    dwell_margin_s: float
    maximum_frame_cadence_s: float
    common_schedule_contradicted: bool
    observer_permutation_contradicted: bool
    admitted: bool


def evaluate_visibility_event_spike() -> dict[str, object]:
    """Evaluate the fixed geometry lattice and return one strict receipt."""

    nominal = sample_observer_network(
        ISS_TLE,
        OBSERVER_GEOMETRIES,
        FIXTURE_START,
        FIXTURE_END,
        CADENCE_S,
    )
    mismatch = sample_observer_network(
        ISS_PLAUSIBLE_MISMATCH_OMM,
        OBSERVER_GEOMETRIES,
        FIXTURE_START,
        FIXTURE_END,
        CADENCE_S,
    )
    pairs = tuple(
        _evaluate_pair(left, nominal[left], right, nominal[right])
        for left, right in combinations(sorted(nominal), 2)
    )
    ranked = tuple(
        sorted(
            pairs,
            key=lambda item: (
                item.admitted,
                item.dwell_margin_s,
                item.controlling_duration_after_timing_s,
                item.left,
                item.right,
            ),
            reverse=True,
        )
    )
    best = ranked[0]
    identity = _specific_orbit_check(best, nominal, mismatch)
    plan = _plan_payload()
    outcome = OUTCOME_ADMITTED if best.admitted else OUTCOME_NOT_ADMITTED
    receipt: dict[str, object] = {
        "outcome": outcome,
        "scope": "OFFLINE_GEOMETRY_SPIKE_ONLY",
        "plan": plan,
        "plan_sha256": _strict_hash(plan),
        "ranked_pairs": [asdict(item) for item in ranked],
        "selected_geometry": asdict(best),
        "specific_orbit_identity_check": identity,
        "null_ledger": {
            "COMMON_TRANSMITTER_SCHEDULE": (
                "predicts the same target-presence state at both witnessed roots"
            ),
            "COLOCATED_OBSERVER_GEOMETRY": (
                "destroys observer-dependent visibility ordering"
            ),
            "OBSERVER_PERMUTATION": (
                "reverses the station-bound transition order"
            ),
            "PLAUSIBLE_ADJACENT_ORBIT": (
                "physical alternative orbit, evaluated separately from generic nulls"
            ),
        },
        "claim_scope": (
            "observer-coupled orbital visibility can be discriminative; "
            "specific orbit identity is not implied"
        ),
        "capability_requirements_not_yet_qualified": {
            "independent_hardware_roots": 2,
            "server_or_adc_bound_event_time_error_s_max": (
                PROVISIONAL_EVENT_TIME_ERROR_S
            ),
            "simultaneous_target_state_frames_min": REQUIRED_CONFIRMATION_FRAMES,
            "target_present_root_is_transmitter_on_witness": True,
            "occulted_root_requires_same_path_receiver_witness": True,
            "predeclared_directional_horizon_mask": True,
            "target_emission_continuity_over_test_interval": True,
        },
        "network_connections": 0,
        "rf_bytes_accessed": 0,
        "observation_values_accessed": 0,
    }
    # Refuse non-standard JSON at the scientific receipt boundary.
    json.dumps(receipt, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return receipt


def _evaluate_pair(
    left_name: str,
    left: OrbitalTrajectory,
    right_name: str,
    right: OrbitalTrajectory,
) -> PairResult:
    segments = _state_segments(left, right)
    left_only = _maximum_duration(segments, "LEFT_VISIBLE_RIGHT_OCCULTED")
    joint = _maximum_duration(segments, "BOTH_VISIBLE")
    right_only = _maximum_duration(segments, "RIGHT_VISIBLE_LEFT_OCCULTED")

    ordered_forward = _ordered_states(
        segments,
        (
            "LEFT_VISIBLE_RIGHT_OCCULTED",
            "BOTH_VISIBLE",
            "RIGHT_VISIBLE_LEFT_OCCULTED",
        ),
    )
    ordered_reverse = _ordered_states(
        segments,
        (
            "RIGHT_VISIBLE_LEFT_OCCULTED",
            "BOTH_VISIBLE",
            "LEFT_VISIBLE_RIGHT_OCCULTED",
        ),
    )
    if ordered_forward:
        topology = "LEFT_ONLY_TO_BOTH_TO_RIGHT_ONLY"
    elif ordered_reverse:
        topology = "RIGHT_ONLY_TO_BOTH_TO_LEFT_ONLY"
    else:
        topology = "NO_COMPLETE_ORDERED_TRANSITION"

    timing_guard = 2.0 * PROVISIONAL_EVENT_TIME_ERROR_S
    controlling = max(
        0.0,
        min(left_only, joint, right_only) - timing_guard,
    )
    margin = controlling - MINIMUM_STATE_DWELL_S
    admitted = bool((ordered_forward or ordered_reverse) and margin > 0.0)
    cadence = (
        controlling / float(REQUIRED_CONFIRMATION_FRAMES)
        if admitted
        else 0.0
    )
    return PairResult(
        left=left_name,
        right=right_name,
        topology=topology,
        left_only_duration_s=left_only,
        joint_visible_duration_s=joint,
        right_only_duration_s=right_only,
        controlling_duration_after_timing_s=controlling,
        dwell_margin_s=margin,
        maximum_frame_cadence_s=cadence,
        common_schedule_contradicted=admitted,
        observer_permutation_contradicted=admitted,
        admitted=admitted,
    )


def _state_segments(
    left: OrbitalTrajectory,
    right: OrbitalTrajectory,
) -> tuple[StateSegment, ...]:
    if left.timestamps != right.timestamps:
        raise ValueError("visibility trajectories must share one event-time grid")
    states = tuple(
        _state(left_elevation, right_elevation)
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
        # Using first-to-last sample span is conservative by one cadence.  No
        # interpolation into the excluded transition band is performed.
        duration = (
            left.timestamps[index - 1] - left.timestamps[start]
        ).total_seconds()
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


def _state(left_elevation_deg: float, right_elevation_deg: float) -> str:
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


def _maximum_duration(segments: tuple[StateSegment, ...], state: str) -> float:
    return max(
        (segment.conservative_duration_s for segment in segments if segment.state == state),
        default=0.0,
    )


def _ordered_states(
    segments: tuple[StateSegment, ...],
    required: tuple[str, str, str],
) -> bool:
    # Transition-band and both-occulted gaps are allowed between the three
    # robust states, but their order may not be changed.
    cursor = 0
    for segment in segments:
        if segment.state == required[cursor]:
            cursor += 1
            if cursor == len(required):
                return True
    return False


def _specific_orbit_check(
    pair: PairResult,
    nominal: Mapping[str, OrbitalTrajectory],
    mismatch: Mapping[str, OrbitalTrajectory],
) -> dict[str, object]:
    nominal_events = _relative_events(nominal[pair.left], nominal[pair.right])
    mismatch_events = _relative_events(mismatch[pair.left], mismatch[pair.right])
    deltas = {
        name: float(abs(nominal_events[name] - mismatch_events[name]))
        for name in nominal_events
    }
    maximum = max(deltas.values())
    bound = 2.0 * PROVISIONAL_EVENT_TIME_ERROR_S + CADENCE_S
    return {
        "alternative": "PLAUSIBLE_ADJACENT_ORBIT",
        "relative_aos_los_event_differences_s": deltas,
        "maximum_difference_s": maximum,
        "comparison_bound_s": bound,
        "classification": (
            "SPECIFIC_ORBIT_EVENT_TIMING_DISCRIMINATIVE"
            if maximum > bound
            else "SPECIFIC_ORBIT_NOT_DISCRIMINATIVE_AT_THIS_BOUND"
        ),
    }


def _relative_events(
    left: OrbitalTrajectory,
    right: OrbitalTrajectory,
) -> dict[str, float]:
    left_aos, left_los = _visible_event_seconds(left)
    right_aos, right_los = _visible_event_seconds(right)
    return {
        "relative_aos": left_aos - right_aos,
        "relative_los": left_los - right_los,
        "relative_duration": (left_los - left_aos) - (right_los - right_aos),
    }


def _visible_event_seconds(trajectory: OrbitalTrajectory) -> tuple[float, float]:
    indices = np.flatnonzero(
        np.asarray(trajectory.elevation_deg, dtype=np.float64)
        >= VISIBLE_MINIMUM_ELEVATION_DEG
    )
    if indices.size == 0:
        raise ValueError("observer has no conservative visible interval")
    return (
        float(trajectory.elapsed_s[int(indices[0])]),
        float(trajectory.elapsed_s[int(indices[-1])]),
    )


def _plan_payload() -> dict[str, object]:
    return {
        "fixture": "G0_ISS_FIXED_ORBIT_GEOMETRY_ONLY",
        "fixture_start": FIXTURE_START.isoformat(),
        "fixture_end": FIXTURE_END.isoformat(),
        "cadence_s": CADENCE_S,
        "visible_minimum_elevation_deg": VISIBLE_MINIMUM_ELEVATION_DEG,
        "occulted_maximum_elevation_deg": OCCULTED_MAXIMUM_ELEVATION_DEG,
        "provisional_event_time_error_s": PROVISIONAL_EVENT_TIME_ERROR_S,
        "minimum_state_dwell_s": MINIMUM_STATE_DWELL_S,
        "required_confirmation_frames": REQUIRED_CONFIRMATION_FRAMES,
        "observer_geometries": {
            name: asdict(observer)
            for name, observer in sorted(OBSERVER_GEOMETRIES.items())
        },
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
    print(
        json.dumps(
            evaluate_visibility_event_spike(),
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
