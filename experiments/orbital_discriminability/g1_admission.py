"""Pass-specific capability admission for Gate G1.

This module has no discovery or network client. It evaluates caller-supplied
descriptive offers against one frozen orbital pass and returns strict scalar
receipts. No RF data enters this boundary.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import sha256
from itertools import combinations
import json
from math import isfinite
from typing import Mapping, Sequence

import numpy as np

from experiments.live_instrument.orbital_kernel import (
    Observer,
    OrbitalElements,
    TLEElements,
)
from experiments.live_instrument.models import strict_json_value

from .nuisance import NuisanceError, affine_shape_residual, make_calibration_split
from .trajectory import (
    OrbitalTrajectory,
    apply_carrier_hz,
    build_time_shift_frequency_envelope,
    differential_time_shift_uncertainty_hz,
    sample_observer_network,
)


class G1Outcome(str, Enum):
    NO_CAPABILITY_ADMITTED = "NO_CAPABILITY_ADMITTED"
    CAPABILITY_SET_ADMITTED = "CAPABILITY_SET_ADMITTED"


class ClauseState(str, Enum):
    SATISFIED = "SATISFIED"
    UNSATISFIED = "UNSATISFIED"


DEFAULT_REQUIRED_TRANSFORMS = (
    "antenna_to_iq",
    "sample_event_time",
    "local_frequency_grid",
)
DEFAULT_REQUIRED_WITNESSES = (
    "sample_sequence",
    "in_band_frequency_reference",
)


@dataclass(frozen=True, slots=True)
class OrbitalPassPlan:
    pass_id: str
    orbital_elements: OrbitalElements
    start_time: datetime
    end_time: datetime
    cadence_s: float
    carrier_hz: float
    minimum_elevation_deg: float = 10.0
    calibration_fraction: float = 0.2
    minimum_calibration_samples: int = 6
    minimum_holdout_samples: int = 16
    minimum_joint_holdout_samples: int = 12
    minimum_signature_bins: float = 3.0
    maximum_gap_s: float = 10.0
    carrier_relative_uncertainty: float = 0.0
    orbital_prediction_uncertainty_hz_per_station: float = 1.0
    required_transforms: tuple[str, ...] = DEFAULT_REQUIRED_TRANSFORMS
    required_same_path_witnesses: tuple[str, ...] = DEFAULT_REQUIRED_WITNESSES

    def validate(self) -> None:
        if not self.pass_id.strip():
            raise ValueError("pass_id must be non-empty")
        start = _aware_utc(self.start_time)
        end = _aware_utc(self.end_time)
        if end <= start:
            raise ValueError("pass end_time must be after start_time")
        positives = (
            self.cadence_s,
            self.carrier_hz,
            self.minimum_signature_bins,
            self.maximum_gap_s,
        )
        nonnegatives = (
            self.carrier_relative_uncertainty,
            self.orbital_prediction_uncertainty_hz_per_station,
        )
        if not all(isfinite(value) and value > 0.0 for value in positives):
            raise ValueError("pass scales must be finite and positive")
        if not all(isfinite(value) and value >= 0.0 for value in nonnegatives):
            raise ValueError("pass uncertainty bounds must be finite and non-negative")
        if not isfinite(self.minimum_elevation_deg) or not -90.0 <= self.minimum_elevation_deg <= 90.0:
            raise ValueError("minimum_elevation_deg must be in [-90, 90]")
        if not 0.0 < self.calibration_fraction < 1.0:
            raise ValueError("calibration_fraction must be in (0, 1)")
        if min(
            self.minimum_calibration_samples,
            self.minimum_holdout_samples,
            self.minimum_joint_holdout_samples,
        ) < 3:
            raise ValueError("sample-count requirements must be at least three")
        if not self.required_transforms or not self.required_same_path_witnesses:
            raise ValueError("transforms and same-path witnesses must be frozen")
        if len(set(self.required_transforms)) != len(self.required_transforms):
            raise ValueError("required transforms must be unique")
        if len(set(self.required_same_path_witnesses)) != len(
            self.required_same_path_witnesses
        ):
            raise ValueError("required witnesses must be unique")

    @property
    def plan_hash(self) -> str:
        self.validate()
        payload = {
            "pass_id": self.pass_id,
            "orbital_elements": _canonical_elements(self.orbital_elements),
            "start_time": _aware_utc(self.start_time).isoformat(),
            "end_time": _aware_utc(self.end_time).isoformat(),
            "cadence_s": self.cadence_s,
            "carrier_hz": self.carrier_hz,
            "minimum_elevation_deg": self.minimum_elevation_deg,
            "calibration_fraction": self.calibration_fraction,
            "minimum_calibration_samples": self.minimum_calibration_samples,
            "minimum_holdout_samples": self.minimum_holdout_samples,
            "minimum_joint_holdout_samples": self.minimum_joint_holdout_samples,
            "minimum_signature_bins": self.minimum_signature_bins,
            "maximum_gap_s": self.maximum_gap_s,
            "carrier_relative_uncertainty": self.carrier_relative_uncertainty,
            "orbital_prediction_uncertainty_hz_per_station": (
                self.orbital_prediction_uncertainty_hz_per_station
            ),
            "required_transforms": self.required_transforms,
            "required_same_path_witnesses": self.required_same_path_witnesses,
        }
        return _sha256_json(payload)


@dataclass(frozen=True, slots=True)
class OrbitalReceiverOffer:
    capability_id: str
    observer: Observer | None
    hardware_root: str | None
    described_at: datetime | None
    ttl_s: float | None
    availability_start: datetime | None
    availability_end: datetime | None
    band_low_hz: float | None
    band_high_hz: float | None
    frequency_resolution_hz: float | None
    event_time_source: str | None
    maximum_event_time_error_s: float | None
    sequence_continuity_exposed: bool
    maximum_gap_s: float | None
    transform_steps: tuple[str, ...]
    frequency_axis_preserved: bool
    ridge_shape_preserved: bool
    same_path_witnesses: tuple[str, ...]

    @property
    def offer_hash(self) -> str:
        return _sha256_json(_offer_payload(self))


@dataclass(frozen=True, slots=True)
class AdmissionClause:
    clause_id: str
    state: str
    observed: str
    required: str


@dataclass(frozen=True, slots=True)
class CapabilityAssessment:
    capability_id: str
    offer_hash: str
    qualified: bool
    clauses: tuple[AdmissionClause, ...]


@dataclass(frozen=True, slots=True)
class PairAssessment:
    capability_ids: tuple[str, str]
    hardware_roots: tuple[str, str]
    admitted: bool
    clauses: tuple[AdmissionClause, ...]
    joint_visible_calibration_samples: int
    joint_visible_holdout_samples: int
    differential_signature_span_hz: float
    frequency_resolution_envelope_hz: float
    event_time_envelope_hz: float
    carrier_envelope_hz: float
    orbital_envelope_hz: float
    detectability_threshold_hz: float
    detectability_margin_hz: float
    claim_scope: str


@dataclass(frozen=True, slots=True)
class G1AdmissionResult:
    outcome: str
    terminal_reason: str
    plan_hash: str
    evaluated_at: str
    capability_assessments: tuple[CapabilityAssessment, ...]
    pair_assessments: tuple[PairAssessment, ...]
    selected_pair: tuple[str, str] | None
    statement: str
    raw_rf_activity: str = "ZERO"
    calibrated_probability_used: bool = False

    def strict_json(self) -> str:
        return json.dumps(
            strict_json_value(asdict(self)),
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )


def evaluate_capability_admission(
    plan: OrbitalPassPlan,
    offers: Sequence[OrbitalReceiverOffer],
    *,
    evaluated_at: datetime,
) -> G1AdmissionResult:
    """Evaluate offers without discovery, network access or RF acquisition."""

    plan.validate()
    evaluation_time = _aware_utc(evaluated_at)
    ordered = tuple(sorted(offers, key=lambda item: item.capability_id))
    identifiers = tuple(item.capability_id for item in ordered)
    if any(not identifier.strip() for identifier in identifiers):
        raise ValueError("capability identifiers must be non-empty")
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("capability identifiers must be unique")

    assessments = tuple(
        _assess_capability(plan, offer, evaluation_time) for offer in ordered
    )
    qualified_ids = {
        assessment.capability_id
        for assessment in assessments
        if assessment.qualified
    }
    qualified = tuple(
        offer for offer in ordered if offer.capability_id in qualified_ids
    )

    pairs: list[PairAssessment] = []
    if len(qualified) >= 2:
        observers = {
            offer.capability_id: offer.observer
            for offer in qualified
            if offer.observer is not None
        }
        trajectories = sample_observer_network(
            plan.orbital_elements,
            observers,
            plan.start_time,
            plan.end_time,
            plan.cadence_s,
            minimum_elevation_deg=plan.minimum_elevation_deg,
        )
        for left, right in combinations(qualified, 2):
            pairs.append(_assess_pair(plan, left, right, trajectories))

    admitted = tuple(pair for pair in pairs if pair.admitted)
    selected = (
        max(
            admitted,
            key=lambda item: (
                item.detectability_margin_hz,
                item.joint_visible_holdout_samples,
                item.capability_ids,
            ),
        )
        if admitted
        else None
    )
    if selected is not None:
        outcome = G1Outcome.CAPABILITY_SET_ADMITTED
        terminal_reason = "PASS_SPECIFIC_DIFFERENTIAL_MARGIN_POSITIVE"
        statement = (
            "one independent capability pair preserves the frozen pass-specific "
            "differential orbital signature with positive conservative margin"
        )
    else:
        outcome = G1Outcome.NO_CAPABILITY_ADMITTED
        terminal_reason = _terminal_refusal_reason(assessments, tuple(pairs))
        statement = (
            "no supplied capability pair can make a negative result for this "
            "frozen orbital pass interpretable"
        )

    result = G1AdmissionResult(
        outcome=outcome.value,
        terminal_reason=terminal_reason,
        plan_hash=plan.plan_hash,
        evaluated_at=evaluation_time.isoformat(),
        capability_assessments=assessments,
        pair_assessments=tuple(pairs),
        selected_pair=selected.capability_ids if selected else None,
        statement=statement,
    )
    result.strict_json()
    return result


def _assess_capability(
    plan: OrbitalPassPlan,
    offer: OrbitalReceiverOffer,
    evaluated_at: datetime,
) -> CapabilityAssessment:
    observer_known = _observer_is_valid(offer.observer)
    root_known = bool(offer.hardware_root and offer.hardware_root.strip())
    fresh = _offer_is_fresh(offer, evaluated_at, plan.end_time)
    window = _window_covers(offer, plan)
    band = _band_covers(offer, plan.carrier_hz)
    resolution = _positive_optional(offer.frequency_resolution_hz)
    event_time = bool(offer.event_time_source and offer.event_time_source.strip()) and (
        _nonnegative_optional(offer.maximum_event_time_error_s)
    )
    continuity = offer.sequence_continuity_exposed and (
        _nonnegative_optional(offer.maximum_gap_s)
        and float(offer.maximum_gap_s) <= plan.maximum_gap_s
    )
    transforms = set(plan.required_transforms).issubset(offer.transform_steps)
    witnesses = set(plan.required_same_path_witnesses).issubset(
        offer.same_path_witnesses
    )
    clauses = (
        _clause("observer_coordinates", observer_known, _observer_text(offer.observer), "finite WGS-84 coordinates"),
        _clause("hardware_measurement_root", root_known, str(offer.hardware_root), "one named hardware root"),
        _clause("description_ttl", fresh, _freshness_text(offer, evaluated_at), "fresh at evaluation time and through pass end"),
        _clause("full_pass_window", window, _window_text(offer), "availability covers the complete pass"),
        _clause("carrier_band", band, _band_text(offer), f"contains {plan.carrier_hz:.6f} Hz"),
        _clause("frequency_resolution", resolution, str(offer.frequency_resolution_hz), "finite and positive"),
        _clause("event_time_bound", event_time, f"source={offer.event_time_source}; error_s={offer.maximum_event_time_error_s}", "named source and finite non-negative error"),
        _clause("sequence_continuity", continuity, f"exposed={offer.sequence_continuity_exposed}; max_gap_s={offer.maximum_gap_s}", f"exposed and gap <= {plan.maximum_gap_s:.6f} s"),
        _clause("transform_ledger", transforms, ",".join(offer.transform_steps), ",".join(plan.required_transforms)),
        _clause("frequency_axis_preserved", offer.frequency_axis_preserved, str(offer.frequency_axis_preserved), "True"),
        _clause("ridge_shape_preserved", offer.ridge_shape_preserved, str(offer.ridge_shape_preserved), "True"),
        _clause("same_path_witnesses", witnesses, ",".join(offer.same_path_witnesses), ",".join(plan.required_same_path_witnesses)),
    )
    return CapabilityAssessment(
        capability_id=offer.capability_id,
        offer_hash=offer.offer_hash,
        qualified=all(item.state == ClauseState.SATISFIED.value for item in clauses),
        clauses=clauses,
    )


def _assess_pair(
    plan: OrbitalPassPlan,
    left: OrbitalReceiverOffer,
    right: OrbitalReceiverOffer,
    trajectories: Mapping[str, OrbitalTrajectory],
) -> PairAssessment:
    left_trajectory = trajectories[left.capability_id]
    right_trajectory = trajectories[right.capability_id]
    elapsed = np.asarray(left_trajectory.elapsed_s, dtype=np.float64)
    left_prediction = np.asarray(
        apply_carrier_hz(left_trajectory.fractional_doppler, plan.carrier_hz),
        dtype=np.float64,
    )
    right_prediction = np.asarray(
        apply_carrier_hz(right_trajectory.fractional_doppler, plan.carrier_hz),
        dtype=np.float64,
    )
    split = make_calibration_split(
        len(elapsed),
        plan.calibration_fraction,
        minimum_calibration_samples=plan.minimum_calibration_samples,
        minimum_holdout_samples=plan.minimum_holdout_samples,
    )
    holdout = np.asarray(split.holdout_indices, dtype=np.int64)
    calibration = np.asarray(split.calibration_indices, dtype=np.int64)
    joint_visible = np.asarray(left_trajectory.visibility_mask, dtype=bool) & np.asarray(
        right_trajectory.visibility_mask,
        dtype=bool,
    )
    visible_calibration = calibration[joint_visible[calibration]]
    visible_holdout = holdout[joint_visible[holdout]]
    differential = left_prediction - right_prediction
    calibration_visibility_ok = (
        visible_calibration.size >= plan.minimum_calibration_samples
    )
    shape = (
        np.asarray(
            affine_shape_residual(
                elapsed,
                differential,
                split,
                valid_mask=joint_visible,
            ),
            dtype=np.float64,
        )
        if calibration_visibility_ok
        else np.zeros_like(differential)
    )
    signature = (
        float(np.max(shape[visible_holdout]) - np.min(shape[visible_holdout]))
        if visible_holdout.size
        else 0.0
    )
    left_clock_envelope = build_time_shift_frequency_envelope(
        plan.orbital_elements,
        left_trajectory,
        plan.carrier_hz,
        float(left.maximum_event_time_error_s),
    )
    right_clock_envelope = build_time_shift_frequency_envelope(
        plan.orbital_elements,
        right_trajectory,
        plan.carrier_hz,
        float(right.maximum_event_time_error_s),
    )
    resolution_envelope = plan.minimum_signature_bins * max(
        float(left.frequency_resolution_hz),
        float(right.frequency_resolution_hz),
    )
    envelope_mask = np.zeros(elapsed.size, dtype=bool)
    envelope_mask[visible_holdout] = True
    event_time_envelope = (
        differential_time_shift_uncertainty_hz(
            left_clock_envelope,
            right_clock_envelope,
            envelope_mask,
        )
        if visible_holdout.size
        else 0.0
    )
    carrier_envelope = (
        float(np.max(np.abs(differential[visible_holdout])))
        * plan.carrier_relative_uncertainty
        if visible_holdout.size
        else 0.0
    )
    orbital_envelope = 2.0 * plan.orbital_prediction_uncertainty_hz_per_station
    threshold = (
        resolution_envelope
        + event_time_envelope
        + carrier_envelope
        + orbital_envelope
    )
    margin = signature - threshold
    numeric = (
        signature,
        resolution_envelope,
        event_time_envelope,
        carrier_envelope,
        orbital_envelope,
        threshold,
        margin,
    )
    if not all(isfinite(value) for value in numeric):
        raise NuisanceError("G1 pair assessment produced a non-finite scalar")

    independent = left.hardware_root != right.hardware_root
    visibility_ok = visible_holdout.size >= plan.minimum_joint_holdout_samples
    detectable = calibration_visibility_ok and visibility_ok and margin > 0.0
    clauses = (
        _clause("independent_hardware_roots", independent, f"{left.hardware_root}|{right.hardware_root}", "two distinct roots"),
        _clause("joint_calibration_visibility", calibration_visibility_ok, str(int(visible_calibration.size)), f">= {plan.minimum_calibration_samples} samples"),
        _clause("joint_holdout_visibility", visibility_ok, str(int(visible_holdout.size)), f">= {plan.minimum_joint_holdout_samples} samples"),
        _clause("differential_detectability", detectable, f"margin_hz={margin:.12f}", "positive conservative margin"),
    )
    ids = tuple(sorted((left.capability_id, right.capability_id)))
    roots = tuple(sorted((str(left.hardware_root), str(right.hardware_root))))
    return PairAssessment(
        capability_ids=ids,
        hardware_roots=roots,
        admitted=all(item.state == ClauseState.SATISFIED.value for item in clauses),
        clauses=clauses,
        joint_visible_calibration_samples=int(visible_calibration.size),
        joint_visible_holdout_samples=int(visible_holdout.size),
        differential_signature_span_hz=signature,
        frequency_resolution_envelope_hz=resolution_envelope,
        event_time_envelope_hz=event_time_envelope,
        carrier_envelope_hz=carrier_envelope,
        orbital_envelope_hz=orbital_envelope,
        detectability_threshold_hz=threshold,
        detectability_margin_hz=margin,
        claim_scope=(
            "ability to test this pass-specific differential prediction; "
            "not signal presence, orbital origin or satellite identity"
        ),
    )


def _terminal_refusal_reason(
    capabilities: tuple[CapabilityAssessment, ...],
    pairs: tuple[PairAssessment, ...],
) -> str:
    if sum(item.qualified for item in capabilities) < 2:
        return "INDIVIDUAL_QUALIFICATION_FAILED"
    if pairs and all(
        _clause_state(pair.clauses, "independent_hardware_roots")
        == ClauseState.UNSATISFIED.value
        for pair in pairs
    ):
        return "NO_INDEPENDENT_HARDWARE_ROOT_PAIR"
    if pairs and all(
        _clause_state(pair.clauses, "joint_calibration_visibility")
        == ClauseState.UNSATISFIED.value
        for pair in pairs
    ):
        return "NO_JOINTLY_VISIBLE_CALIBRATION"
    if pairs and all(
        _clause_state(pair.clauses, "joint_holdout_visibility")
        == ClauseState.UNSATISFIED.value
        for pair in pairs
    ):
        return "NO_JOINTLY_VISIBLE_HOLDOUT"
    return "NO_PAIR_CLEARS_DETECTABILITY"


def _clause_state(clauses: tuple[AdmissionClause, ...], clause_id: str) -> str:
    return next(item.state for item in clauses if item.clause_id == clause_id)


def _clause(
    clause_id: str,
    satisfied: bool,
    observed: str,
    required: str,
) -> AdmissionClause:
    return AdmissionClause(
        clause_id,
        ClauseState.SATISFIED.value if bool(satisfied) else ClauseState.UNSATISFIED.value,
        observed,
        required,
    )


def _offer_is_fresh(
    offer: OrbitalReceiverOffer,
    evaluated_at: datetime,
    required_until: datetime,
) -> bool:
    if offer.described_at is None or not _positive_optional(offer.ttl_s):
        return False
    if offer.described_at.tzinfo is None or offer.described_at.utcoffset() is None:
        return False
    described = offer.described_at.astimezone(timezone.utc)
    expires = described + timedelta(seconds=float(offer.ttl_s))
    return described <= evaluated_at and expires >= _aware_utc(required_until)


def _window_covers(offer: OrbitalReceiverOffer, plan: OrbitalPassPlan) -> bool:
    if offer.availability_start is None or offer.availability_end is None:
        return False
    try:
        start = _aware_utc(offer.availability_start)
        end = _aware_utc(offer.availability_end)
    except ValueError:
        return False
    return start <= _aware_utc(plan.start_time) and end >= _aware_utc(plan.end_time)


def _band_covers(offer: OrbitalReceiverOffer, carrier_hz: float) -> bool:
    if not _finite_optional(offer.band_low_hz) or not _finite_optional(offer.band_high_hz):
        return False
    return float(offer.band_low_hz) <= carrier_hz <= float(offer.band_high_hz)


def _observer_is_valid(observer: Observer | None) -> bool:
    return bool(
        observer is not None
        and isfinite(observer.latitude_deg)
        and isfinite(observer.longitude_deg)
        and isfinite(observer.altitude_m)
        and -90.0 <= observer.latitude_deg <= 90.0
        and -180.0 <= observer.longitude_deg <= 180.0
    )


def _finite_optional(value: float | None) -> bool:
    return value is not None and isfinite(value)


def _positive_optional(value: float | None) -> bool:
    return _finite_optional(value) and float(value) > 0.0


def _nonnegative_optional(value: float | None) -> bool:
    return _finite_optional(value) and float(value) >= 0.0


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Gate G1 datetimes must be timezone-aware")
    return value.astimezone(timezone.utc)


def _canonical_elements(elements: OrbitalElements) -> dict[str, object]:
    if isinstance(elements, TLEElements):
        return {
            "format": "TLE",
            "name": elements.name,
            "line1": elements.line1,
            "line2": elements.line2,
        }
    if not isinstance(elements, Mapping):
        raise ValueError("unsupported orbital element representation")
    fields: dict[str, object] = {}
    for key, value in sorted(elements.items(), key=lambda item: str(item[0])):
        if not isinstance(value, (str, int, float, bool)) and value is not None:
            raise ValueError("OMM plan fields must be JSON scalars")
        if isinstance(value, float) and not isfinite(value):
            raise ValueError("OMM plan fields must be finite")
        fields[str(key)] = value
    return {"format": "OMM", "fields": fields}


def _offer_payload(offer: OrbitalReceiverOffer) -> dict[str, object]:
    observer = (
        None
        if offer.observer is None
        else {
            "latitude_deg": offer.observer.latitude_deg,
            "longitude_deg": offer.observer.longitude_deg,
            "altitude_m": offer.observer.altitude_m,
        }
    )
    payload = asdict(offer)
    payload["observer"] = observer
    for field in ("described_at", "availability_start", "availability_end"):
        value = getattr(offer, field)
        payload[field] = value.isoformat() if value is not None else None
    return payload


def _sha256_json(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(
        strict_json_value(payload),
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _observer_text(observer: Observer | None) -> str:
    if observer is None:
        return "missing"
    return f"{observer.latitude_deg},{observer.longitude_deg},{observer.altitude_m}"


def _freshness_text(offer: OrbitalReceiverOffer, evaluated_at: datetime) -> str:
    return f"described_at={offer.described_at}; ttl_s={offer.ttl_s}; evaluated_at={evaluated_at.isoformat()}"


def _window_text(offer: OrbitalReceiverOffer) -> str:
    return f"{offer.availability_start}..{offer.availability_end}"


def _band_text(offer: OrbitalReceiverOffer) -> str:
    return f"{offer.band_low_hz}..{offer.band_high_hz} Hz"
