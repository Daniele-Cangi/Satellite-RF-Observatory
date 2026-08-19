"""Gate F2.5.22: offline discoverability and witness audit.

This module does not acquire data and has no connector surface. It explains
what the frozen F2.5.21 receipt can and cannot attribute, materialises the
descriptive receipt that a future discovery would need, and tests a narrower
causal alternative to the two-peak requirement: one target peak plus an
out-of-target distributed spectral fingerprint and the fixed reference branch.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Sequence

import numpy as np
from scipy import signal

from . import kiwi_gate_f2 as f2
from . import kiwi_gate_f2_4 as f24


TRANSFORM_VERSION = "gate-f2.5.22-offline-discoverability-audit-v1"
FROZEN_OUTCOME_PATH = (
    Path(__file__).parent
    / "session_receipts"
    / "gate-f2-5-21-20260818T111608.453433Z.jsonl"
)
FROZEN_OUTCOME_SHA256 = (
    "5307caa715a1f18199a5f933e16ad0c64fb0ce2cfa7753cd254e54e01e9b49fb"
)
FROZEN_DISCOVERY_ERROR_HASH = (
    "a7ed0ed8e619a33d90876404a1d469d68cd9fef2993a4c1ddea83f703d83d01e"
)
RAW_RF_PERSISTENCE = "ZERO"


class GateF2522Exit(str, Enum):
    OFFLINE_DISCOVERABILITY_AUDIT_COMPLETE = (
        "OFFLINE_DISCOVERABILITY_AUDIT_COMPLETE"
    )


class CandidateState(str, Enum):
    ADMITTED = "ADMITTED"
    PATCH_INCOMPLETE = "PATCH_INCOMPLETE"
    CORRELATION_BELOW_THRESHOLD = "CORRELATION_BELOW_THRESHOLD"
    HALF_STABILITY_BELOW_THRESHOLD = "HALF_STABILITY_BELOW_THRESHOLD"


class DiscoveryState(str, Enum):
    NO_PEAK_ABOVE_CONTRAST = "NO_PEAK_ABOVE_CONTRAST"
    CANDIDATES_REJECTED = "CANDIDATES_REJECTED"
    ONE_STABLE_FEATURE_ONLY = "ONE_STABLE_FEATURE_ONLY"
    TWO_FEATURES_NO_ORIENTATION_NEUTRAL_GEOMETRY = (
        "TWO_FEATURES_NO_ORIENTATION_NEUTRAL_GEOMETRY"
    )
    TWO_FEATURE_PLAN_ELIGIBLE = "TWO_FEATURE_PLAN_ELIGIBLE"


class WitnessState(str, Enum):
    QUALIFIED_AS_FUTURE_WITNESS = "QUALIFIED_AS_FUTURE_WITNESS"
    INTERVENTION_UNRESOLVED = "INTERVENTION_UNRESOLVED"
    NOT_DETECTABLE = "NOT_DETECTABLE"


@dataclass(frozen=True, slots=True)
class NumericObservation:
    state: str
    value: float | None
    unit: str
    reason: str

    def __post_init__(self) -> None:
        if self.state == "FINITE":
            if self.value is None or not math.isfinite(self.value):
                raise ValueError("FINITE numerical observations require a finite value")
        elif self.state == "NOT_EVALUATED":
            if self.value is not None:
                raise ValueError("NOT_EVALUATED numerical observations have no value")
        else:
            raise ValueError("unknown numerical state")


def _finite(value: float, unit: str, reason: str) -> NumericObservation:
    return NumericObservation("FINITE", float(value), unit, reason)


def _not_evaluated(unit: str, reason: str) -> NumericObservation:
    return NumericObservation("NOT_EVALUATED", None, unit, reason)


@dataclass(frozen=True, slots=True)
class FrozenDiscoveryAttribution:
    artifact_hash: str
    outcome: str
    dual_snd_state: str
    discovery_state: str
    downstream_states: tuple[tuple[str, str], ...]
    recorded_discovery_hash_kind: str
    capture_artifact_hashes_present: bool
    candidate_counts_present: bool
    candidate_margins_present: bool
    known: tuple[str, ...]
    unresolved: tuple[str, ...]
    classification: str
    authorised_claim: str
    unauthorised_claims: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CandidateReceipt:
    ordinal: int
    state: str
    baseband_hz: NumericObservation
    joint_contrast_db: NumericObservation
    contrast_margin_db: NumericObservation
    first_half_min_contrast_db: NumericObservation
    second_half_min_contrast_db: NumericObservation
    half_stability_margin_db: NumericObservation
    cross_branch_correlation: NumericObservation
    correlation_margin: NumericObservation
    bandwidth_hz: NumericObservation


@dataclass(frozen=True, slots=True)
class DiscoveryAuditReceipt:
    transform_version: str
    input_artifact_hashes: tuple[str, str]
    hashes_bound_before_first_spectral_transform: bool
    thresholds: tuple[tuple[str, float], ...]
    common_grid_low_hz: float
    common_grid_high_hz: float
    common_bin_hz: float
    common_bin_count: int
    peak_width_basis: str
    raw_peak_count: int
    patch_valid_count: int
    correlation_pass_count: int
    half_stability_pass_count: int
    admitted_feature_count: int
    eligible_pair_count_positive_axis: int
    eligible_pair_count_negative_axis: int
    selected_geometry_orientation_neutral: bool
    state: str
    candidates: tuple[CandidateReceipt, ...]
    raw_rf_persistence: str

    def __post_init__(self) -> None:
        if len(set(self.input_artifact_hashes)) != 2:
            raise ValueError("discovery audit requires two distinct input artifact hashes")
        if any(len(item) != 64 for item in self.input_artifact_hashes):
            raise ValueError("input artifact hashes must be SHA-256 hex strings")
        if not self.hashes_bound_before_first_spectral_transform:
            raise ValueError("post-transform-only hashing is not admissible")
        if not all(
            math.isfinite(item)
            for item in (
                self.common_grid_low_hz,
                self.common_grid_high_hz,
                self.common_bin_hz,
            )
        ):
            raise ValueError("common-grid coordinates must be finite")
        if self.common_grid_high_hz <= self.common_grid_low_hz:
            raise ValueError("common grid is empty")
        if self.peak_width_basis != "UNMASKED_JOINT_AT_PRESELECTED_PEAKS":
            raise ValueError("masked sentinel values cannot define peak width")
        counts = (
            self.common_bin_count,
            self.raw_peak_count,
            self.patch_valid_count,
            self.correlation_pass_count,
            self.half_stability_pass_count,
            self.admitted_feature_count,
            self.eligible_pair_count_positive_axis,
            self.eligible_pair_count_negative_axis,
        )
        if any(item < 0 for item in counts):
            raise ValueError("audit counts cannot be negative")
        if not (
            self.raw_peak_count
            >= self.patch_valid_count
            >= self.correlation_pass_count
            >= self.half_stability_pass_count
            == self.admitted_feature_count
        ):
            raise ValueError("candidate stage counts are inconsistent")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")


@dataclass(frozen=True, slots=True)
class DistributedWitnessReceipt:
    transform_version: str
    input_artifact_hashes: tuple[str, ...]
    hashes_bound_before_analysis: bool
    target_bins_excluded: bool
    usable_bin_count: int
    delta_bins: int
    tested_lags: tuple[int, ...]
    minimum_fingerprint_correlation: float
    correlations: tuple[tuple[str, float], ...]
    clauses: tuple[tuple[str, str], ...]
    learned_orientation: int | None
    state: str
    claim_scope: str
    does_not_prove: tuple[str, ...]
    raw_rf_persistence: str

    def __post_init__(self) -> None:
        if len(self.input_artifact_hashes) != 6:
            raise ValueError("six A1/B/A2 branch artifacts are required")
        if any(len(item) != 64 for item in self.input_artifact_hashes):
            raise ValueError("input artifact hashes must be SHA-256 hex strings")
        if not self.hashes_bound_before_analysis or not self.target_bins_excluded:
            raise ValueError("witness cannot use unbound or target-contaminated inputs")
        if self.usable_bin_count < 0 or self.delta_bins <= 0:
            raise ValueError("invalid witness geometry")
        if not 0 < self.minimum_fingerprint_correlation <= 1:
            raise ValueError("invalid inherited fingerprint threshold")
        if any(not math.isfinite(value) for _, value in self.correlations):
            raise ValueError("witness correlations must be finite")
        if self.learned_orientation not in (None, -1, 1):
            raise ValueError("orientation must be -1, +1 or unresolved")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")


@dataclass(frozen=True, slots=True)
class GateF2522Assessment:
    exit: GateF2522Exit
    frozen_attribution: FrozenDiscoveryAttribution
    two_peak_requirement: str
    orthogonal_witness_requirement: str
    alternative_witness: str
    alternative_live_qualified: bool
    extractor_finding: str
    old_thresholds_changed: bool
    old_outcome_changed: bool
    live_execution_authorised: bool
    maximum_future_claim: str
    abstraction_challenged: str
    raw_rf_persistence: str


def _strict_documents(path: Path) -> tuple[dict[str, object], ...]:
    return tuple(
        json.loads(
            line,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )
        for line in path.read_text(encoding="utf-8").splitlines()
    )


def audit_frozen_outcome() -> FrozenDiscoveryAttribution:
    """Attribute only what the immutable F2.5.21 receipt actually records."""

    raw = FROZEN_OUTCOME_PATH.read_bytes()
    if sha256(raw).hexdigest() != FROZEN_OUTCOME_SHA256:
        raise RuntimeError("the frozen Gate F2.5.21 artifact changed")
    documents = _strict_documents(FROZEN_OUTCOME_PATH)
    discovery = next(
        item["payload"]
        for item in documents
        if item["event"] == "gate_f2_5_20_local_iq_feature_discovery"
    )
    outcome = next(
        item["payload"]
        for item in documents
        if item["event"] == "gate_f2_5_20_first_outcome"
    )
    phases = {item["phase"]: item["state"] for item in outcome["phase_receipts"]}
    error_text = str(discovery["statement"]).rsplit(": ", 1)[-1]
    expected_error_hash = f2._hash(
        {
            "endpoint": discovery["endpoint_identity"],
            "phase": "local_iq_feature_discovery",
            "error_type": "ValueError",
            "error": error_text,
        }
    )
    recorded_hashes = tuple(discovery["artifact_hashes"])
    if recorded_hashes != (expected_error_hash,) or expected_error_hash != FROZEN_DISCOVERY_ERROR_HASH:
        raise RuntimeError("the frozen discovery hash is not the expected error-description hash")
    properties = dict(discovery["properties"])
    descriptive_keys = {
        "raw_peak_count",
        "patch_valid_count",
        "correlation_pass_count",
        "half_stability_pass_count",
        "admitted_feature_count",
    }
    return FrozenDiscoveryAttribution(
        artifact_hash=FROZEN_OUTCOME_SHA256,
        outcome=str(outcome["outcome"]),
        dual_snd_state=phases["DIRECT_DUAL_SND_QUALIFICATION"],
        discovery_state=phases["LOCAL_IQ_FEATURE_DISCOVERY"],
        downstream_states=tuple(
            (name, phases[name])
            for name in (
                "PER_CHANNEL_RETUNE_QUALIFICATION",
                "PLAN_FREEZE",
                "ONE_CONFIRMATION",
            )
        ),
        recorded_discovery_hash_kind="ERROR_DESCRIPTION_HASH_ONLY",
        capture_artifact_hashes_present=False,
        candidate_counts_present=bool(descriptive_keys & set(properties)),
        candidate_margins_present=False,
        known=(
            "dual-SND topology was admitted",
            "the unchanged discovery admitted fewer than two stable structures",
            "retune, freeze and confirmation were not entered",
        ),
        unresolved=(
            "whether zero or one stable feature survived",
            "how many raw peaks crossed the contrast threshold",
            "whether patches, cross-branch correlation or half-window stability rejected candidates",
            "the numerical margins to every frozen threshold",
            "whether the two ephemeral discovery artifacts were distinct after capture",
        ),
        classification="BLOCKER_LOCALIZED; UNDERLYING_CAUSE_NOT_ATTRIBUTABLE_FROM_FROZEN_RECEIPT",
        authorised_claim=(
            "the admitted capability did not produce the predeclared two-feature intervention envelope"
        ),
        unauthorised_claims=(
            "no RF signal existed",
            "exactly one stable feature existed",
            "the feature extractor caused the failure",
            "the physical passband caused the failure",
            "either DDC-boundary hypothesis was evaluated",
        ),
    )


def _thresholds(mother: f2.MotherPlan) -> tuple[tuple[str, float], ...]:
    return (
        ("minimum_contrast_db", mother.minimum_contrast_db),
        ("minimum_half_contrast_db", mother.minimum_half_contrast_db),
        ("minimum_fingerprint_correlation", mother.minimum_fingerprint_correlation),
        ("minimum_delta_hz", mother.minimum_delta_hz),
        ("maximum_delta_hz", mother.maximum_delta_hz),
        ("prediction_tolerance_bins", mother.prediction_tolerance_bins),
    )


def _candidate_pairs(
    geometries: Sequence[f2._FeatureGeometry],
    low: float,
    high: float,
    bin_hz: float,
    mother: f2.MotherPlan,
    orientation: int,
) -> tuple[tuple[tuple[float, ...], tuple[float, ...]], ...]:
    candidates: list[tuple[tuple[float, ...], tuple[float, ...]]] = []
    for target in geometries:
        for witness in geometries:
            if target is witness:
                continue
            tolerance = max(target.uncertainty_hz, witness.uncertainty_hz)
            separation = abs(target.baseband_hz - witness.baseband_hz)
            if separation <= 4.0 * tolerance:
                continue
            feature_scale = max(
                target.bandwidth_hz,
                witness.bandwidth_hz,
                bin_hz,
                target.uncertainty_hz,
                witness.uncertainty_hz,
            )
            lower = max(mother.minimum_delta_hz, 2.0 * feature_scale, 5.0 * tolerance)
            target_edge = min(target.baseband_hz - low, high - target.baseband_hz)
            witness_edge = min(witness.baseband_hz - low, high - witness.baseband_hz)
            guard = mother.guard_bins * bin_hz + feature_scale
            upper = min(
                mother.maximum_delta_hz,
                target_edge - guard,
                witness_edge - guard,
                (target_edge - guard) / 2.5,
            )
            if upper < lower:
                continue
            delta = math.floor(upper / bin_hz) * bin_hz
            if delta < lower:
                continue
            translation = orientation * (-delta)
            upstream = target.baseband_hz + translation
            downstream = target.baseband_hz
            wrong_sign = target.baseband_hz - translation
            wrong_magnitude = target.baseband_hz + translation / 2.0
            off_feature = target.baseband_hz + translation * 2.5
            positions = (
                upstream,
                downstream,
                wrong_sign,
                wrong_magnitude,
                off_feature,
                witness.baseband_hz + translation,
            )
            if any(not low + guard <= position <= high - guard for position in positions):
                continue
            if min(
                abs(upstream - downstream),
                abs(upstream - wrong_sign),
                abs(upstream - wrong_magnitude),
                abs(downstream - wrong_magnitude),
            ) <= 2.0 * tolerance:
                continue
            rank = (
                min(target.cross_root_correlation, witness.cross_root_correlation),
                -max(target.morphology_db[2], witness.morphology_db[2]),
                min(target_edge, witness_edge),
                delta / feature_scale,
                separation,
                min(target.contrast_interval_db[0], witness.contrast_interval_db[0]),
                target.contrast_interval_db[1] + witness.contrast_interval_db[1],
            )
            signature = (
                target.baseband_hz,
                witness.baseband_hz,
                float(delta),
                float(tolerance),
                float(bin_hz),
            )
            candidates.append((rank, signature))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return tuple(candidates)


def audit_profile_pair(
    left: f2._SpectralProfile,
    right: f2._SpectralProfile,
    input_artifact_hashes: tuple[str, str],
    mother: f2.MotherPlan | None = None,
) -> DiscoveryAuditReceipt:
    """Create scalar sufficient statistics from already-ephemeral profiles."""

    mother = mother or f2.MotherPlan()
    low = max(float(left.frequencies_hz[0]), float(right.frequencies_hz[0]))
    high = min(float(left.frequencies_hz[-1]), float(right.frequencies_hz[-1]))
    bin_hz = max(float(left.bin_hz), float(right.bin_hz))
    count = int(math.floor((high - low) / bin_hz)) + 1
    if count < 64:
        raise ValueError("no resolved common baseband grid")
    frequencies = low + np.arange(count, dtype=float) * bin_hz
    l_med, l_first, l_second = f2._profile_on_grid(left, frequencies)
    r_med, r_first, r_second = f2._profile_on_grid(right, frequencies)
    joint = np.minimum(l_med, r_med)
    margin = max(mother.guard_bins, 6)
    valid = np.ones(len(joint), dtype=bool)
    valid[:margin] = False
    valid[-margin:] = False
    valid[np.abs(frequencies) <= mother.guard_bins * bin_hz] = False
    masked = np.where(valid, joint, -1e9)
    peaks, _ = signal.find_peaks(
        masked,
        height=mother.minimum_contrast_db,
        distance=max(3, mother.guard_bins // 2),
    )
    # Peak admission still uses the frozen mask and thresholds. Width is a
    # morphology measurement, so it must not see the -1e9 admission sentinel:
    # doing so can inflate a peak to almost the entire passband.
    widths = (
        signal.peak_widths(joint, peaks, rel_height=0.5)[0]
        if len(peaks)
        else np.asarray([], dtype=float)
    )
    receipts: list[CandidateReceipt] = []
    geometries: list[f2._FeatureGeometry] = []
    patch_valid = 0
    correlation_pass = 0
    half_pass = 0
    for ordinal, raw_index in enumerate(peaks):
        index = int(raw_index)
        baseband = float(frequencies[index])
        joint_contrast = float(joint[index])
        first = float(min(l_first[index], r_first[index]))
        second = float(min(l_second[index], r_second[index]))
        width = float(max(bin_hz, widths[ordinal] * bin_hz))
        left_patch = f2._normalized_neighbourhood(l_med, index)
        right_patch = f2._normalized_neighbourhood(r_med, index)
        if left_patch is None or right_patch is None:
            receipts.append(
                CandidateReceipt(
                    ordinal,
                    CandidateState.PATCH_INCOMPLETE.value,
                    _finite(baseband, "Hz", "common baseband grid"),
                    _finite(joint_contrast, "dB", "minimum across branches"),
                    _finite(joint_contrast - mother.minimum_contrast_db, "dB", "relative to frozen threshold"),
                    _finite(first, "dB", "minimum across branches"),
                    _finite(second, "dB", "minimum across branches"),
                    _finite(min(first, second) - mother.minimum_half_contrast_db, "dB", "relative to frozen threshold"),
                    _not_evaluated("ratio", "normalised patch unavailable"),
                    _not_evaluated("ratio", "correlation unavailable"),
                    _finite(width, "Hz", "half-height peak width"),
                )
            )
            continue
        patch_valid += 1
        correlation = f2._correlation(left_patch, right_patch)
        correlation_margin = correlation - mother.minimum_fingerprint_correlation
        half_margin = min(first, second) - mother.minimum_half_contrast_db
        if correlation < mother.minimum_fingerprint_correlation:
            state = CandidateState.CORRELATION_BELOW_THRESHOLD
        else:
            correlation_pass += 1
            if min(first, second) < mother.minimum_half_contrast_db:
                state = CandidateState.HALF_STABILITY_BELOW_THRESHOLD
            else:
                state = CandidateState.ADMITTED
                half_pass += 1
                joint_patch = tuple(
                    float((a + b) / 2.0) for a, b in zip(left_patch, right_patch)
                )
                geometries.append(
                    f2._FeatureGeometry(
                        baseband,
                        width,
                        joint_patch,
                        (first, second, abs(first - second)),
                        (min(first, second), joint_contrast),
                        mother.prediction_tolerance_bins * bin_hz,
                        correlation,
                    )
                )
        receipts.append(
            CandidateReceipt(
                ordinal,
                state.value,
                _finite(baseband, "Hz", "common baseband grid"),
                _finite(joint_contrast, "dB", "minimum across branches"),
                _finite(joint_contrast - mother.minimum_contrast_db, "dB", "relative to frozen threshold"),
                _finite(first, "dB", "minimum across branches"),
                _finite(second, "dB", "minimum across branches"),
                _finite(half_margin, "dB", "relative to frozen threshold"),
                _finite(correlation, "ratio", "normalised neighbourhood correlation"),
                _finite(correlation_margin, "ratio", "relative to frozen threshold"),
                _finite(width, "Hz", "half-height peak width"),
            )
        )
    positive = _candidate_pairs(geometries, low, high, bin_hz, mother, 1)
    negative = _candidate_pairs(geometries, low, high, bin_hz, mother, -1)
    neutral = bool(positive and negative and positive[0][1] == negative[0][1])
    if not peaks.size:
        state = DiscoveryState.NO_PEAK_ABOVE_CONTRAST
    elif not geometries:
        state = DiscoveryState.CANDIDATES_REJECTED
    elif len(geometries) == 1:
        state = DiscoveryState.ONE_STABLE_FEATURE_ONLY
    elif not neutral:
        state = DiscoveryState.TWO_FEATURES_NO_ORIENTATION_NEUTRAL_GEOMETRY
    else:
        state = DiscoveryState.TWO_FEATURE_PLAN_ELIGIBLE
    return DiscoveryAuditReceipt(
        TRANSFORM_VERSION,
        input_artifact_hashes,
        True,
        _thresholds(mother),
        low,
        high,
        bin_hz,
        count,
        "UNMASKED_JOINT_AT_PRESELECTED_PEAKS",
        len(peaks),
        patch_valid,
        correlation_pass,
        half_pass,
        len(geometries),
        len(positive),
        len(negative),
        neutral,
        state.value,
        tuple(receipts),
        RAW_RF_PERSISTENCE,
    )


def audit_discovery_artifacts(
    artifacts: f24._DualArtifacts,
    mother: f2.MotherPlan | None = None,
) -> DiscoveryAuditReceipt:
    """Bind both pre-analysis artifact hashes, then derive scalar diagnostics."""

    left = artifacts.reference["DISCOVERY_A"]
    right = artifacts.perturbed["DISCOVERY_A"]
    hashes = (left.artifact_hash, right.artifact_hash)
    return audit_profile_pair(
        f2._capture_profile(left.capture, mother or f2.MotherPlan()),
        f2._capture_profile(right.capture, mother or f2.MotherPlan()),
        hashes,
        mother,
    )


def _lag_correlation(
    source: np.ndarray,
    observed: np.ndarray,
    lag: int,
    usable: np.ndarray,
) -> float:
    indices = np.flatnonzero(usable)
    shifted = indices + lag
    valid = (shifted >= 0) & (shifted < len(observed))
    indices = indices[valid]
    shifted = shifted[valid]
    observed_usable = usable[shifted]
    indices = indices[observed_usable]
    shifted = shifted[observed_usable]
    if len(indices) < 3:
        return 0.0
    left = source[indices]
    right = observed[shifted]
    if np.std(left) <= 1e-12 or np.std(right) <= 1e-12:
        return 0.0
    value = float(np.corrcoef(left, right)[0, 1])
    return value if math.isfinite(value) else 0.0


def _unique_best(scores: dict[int, float], eligible: tuple[int, ...]) -> int | None:
    ranked = sorted(((scores[item], item) for item in eligible), reverse=True)
    if not ranked:
        return None
    if len(ranked) > 1 and math.isclose(ranked[0][0], ranked[1][0], abs_tol=1e-12):
        return None
    return ranked[0][1]


def assess_distributed_witness(
    *,
    reference_a1: Sequence[float],
    reference_b: Sequence[float],
    reference_a2: Sequence[float],
    perturbed_a1: Sequence[float],
    perturbed_b: Sequence[float],
    perturbed_a2: Sequence[float],
    input_artifact_hashes: tuple[str, ...],
    delta_bins: int,
    target_index: int,
    target_exclusion_radius: int,
    minimum_fingerprint_correlation: float | None = None,
) -> DistributedWitnessReceipt:
    """Assess a target-excluded, distributed same-path retune witness.

    The function consumes derived profiles in RAM. It does not decide target
    physics. It only asks whether a stable out-of-target spectral fingerprint
    translates on the perturbed branch, remains fixed on the reference branch,
    and returns at A2 under predeclared lag controls.
    """

    threshold = (
        f2.MotherPlan().minimum_fingerprint_correlation
        if minimum_fingerprint_correlation is None
        else float(minimum_fingerprint_correlation)
    )
    arrays = tuple(
        np.asarray(item, dtype=float)
        for item in (
            reference_a1,
            reference_b,
            reference_a2,
            perturbed_a1,
            perturbed_b,
            perturbed_a2,
        )
    )
    lengths = {len(item) for item in arrays}
    if len(lengths) != 1 or not arrays[0].size:
        raise ValueError("all six witness profiles must share one non-empty grid")
    if any(not np.all(np.isfinite(item)) for item in arrays):
        raise ValueError("witness profiles must contain only finite values")
    if delta_bins <= 0 or target_exclusion_radius < 0:
        raise ValueError("invalid target exclusion or retune magnitude")
    count = len(arrays[0])
    usable = np.ones(count, dtype=bool)
    edge = max(delta_bins + 1, 6)
    usable[:edge] = False
    usable[-edge:] = False
    half = max(1, delta_bins // 2)
    tested = tuple(dict.fromkeys((0, delta_bins, -delta_bins, half, -half)))
    # Exclude the target at every predeclared control position. _lag_correlation
    # applies this mask to both the source and observed indices, so neither the
    # target nor a translated copy can determine the intervention witness.
    for lag in tested:
        centre = target_index + lag
        start = max(0, centre - target_exclusion_radius)
        stop = min(count, centre + target_exclusion_radius + 1)
        usable[start:stop] = False
    usable_count = int(np.count_nonzero(usable))
    labels: list[tuple[str, float]] = []

    def scores(source: np.ndarray, observed: np.ndarray, prefix: str) -> dict[int, float]:
        result = {
            lag: _lag_correlation(source, observed, lag, usable) for lag in tested
        }
        labels.extend((f"{prefix}:lag={lag}", value) for lag, value in result.items())
        return result

    ref_b_scores = scores(arrays[0], arrays[1], "reference_B")
    ref_a2_scores = scores(arrays[0], arrays[2], "reference_A2")
    pert_b_scores = scores(arrays[3], arrays[4], "perturbed_B")
    pert_a2_scores = scores(arrays[3], arrays[5], "perturbed_A2")
    cross_a1_scores = scores(arrays[0], arrays[3], "cross_branch_A1")
    cross_a2_scores = scores(arrays[2], arrays[5], "cross_branch_A2")
    positive_lags = (delta_bins, -delta_bins)
    winning_orientation = _unique_best(pert_b_scores, positive_lags)
    control_lags = tuple(item for item in tested if item != winning_orientation)
    reference_fixed = (
        ref_b_scores[0] >= threshold
        and ref_a2_scores[0] >= threshold
        and _unique_best(ref_b_scores, tested) == 0
        and _unique_best(ref_a2_scores, tested) == 0
    )
    perturbed_return = (
        pert_a2_scores[0] >= threshold
        and _unique_best(pert_a2_scores, tested) == 0
    )
    shared_a_state = (
        cross_a1_scores[0] >= threshold
        and cross_a2_scores[0] >= threshold
        and _unique_best(cross_a1_scores, tested) == 0
        and _unique_best(cross_a2_scores, tested) == 0
    )
    detectable = (
        usable_count >= 64
        and np.std(arrays[0][usable]) > 1e-12
        and np.std(arrays[3][usable]) > 1e-12
        and shared_a_state
        and reference_fixed
        and perturbed_return
    )
    translated = bool(
        winning_orientation is not None
        and pert_b_scores[winning_orientation] >= threshold
        and all(
            pert_b_scores[winning_orientation] > pert_b_scores[item]
            for item in control_lags
        )
    )
    even = usable.copy()
    even[1::2] = False
    odd = usable.copy()
    odd[0::2] = False
    fold_winners: list[int | None] = []
    for fold in (even, odd):
        fold_scores = {
            lag: _lag_correlation(arrays[3], arrays[4], lag, fold)
            for lag in positive_lags
        }
        winner = _unique_best(fold_scores, positive_lags)
        if winner is None or fold_scores[winner] < threshold:
            winner = None
        fold_winners.append(winner)
    fold_consistent = bool(
        winning_orientation is not None
        and tuple(fold_winners) == (winning_orientation, winning_orientation)
    )
    if not detectable:
        state = WitnessState.NOT_DETECTABLE
        learned = None
    elif not (translated and fold_consistent):
        state = WitnessState.INTERVENTION_UNRESOLVED
        learned = None
    else:
        state = WitnessState.QUALIFIED_AS_FUTURE_WITNESS
        learned = 1 if winning_orientation == delta_bins else -1
    clauses = (
        ("minimum_64_out_of_target_bins", "SATISFIED" if usable_count >= 64 else "UNSATISFIED"),
        ("cross_branch_A_state", "SATISFIED" if shared_a_state else "UNSATISFIED"),
        ("fixed_reference_branch", "SATISFIED" if reference_fixed else "UNSATISFIED"),
        ("perturbed_A2_return", "SATISFIED" if perturbed_return else "UNSATISFIED"),
        ("unique_nonzero_translation", "SATISFIED" if translated else "UNSATISFIED"),
        ("even_odd_translation_consistency", "SATISFIED" if fold_consistent else "UNSATISFIED"),
        ("target_bins_excluded", "SATISFIED"),
    )
    return DistributedWitnessReceipt(
        TRANSFORM_VERSION,
        input_artifact_hashes,
        True,
        True,
        usable_count,
        delta_bins,
        tested,
        threshold,
        tuple(labels),
        clauses,
        learned,
        state.value,
        "qualify a per-channel coordinate translation without evaluating the target",
        (
            "external RF origin",
            "transmitter identity",
            "target upstream/downstream hypothesis",
            "future live detectability",
        ),
        RAW_RF_PERSISTENCE,
    )


def assess_gate_f2_5_22() -> GateF2522Assessment:
    return GateF2522Assessment(
        GateF2522Exit.OFFLINE_DISCOVERABILITY_AUDIT_COMPLETE,
        audit_frozen_outcome(),
        "SUFFICIENT_BUT_NOT_CAUSALLY_NECESSARY",
        "STILL_REQUIRED_AND_MUST_NOT_USE_TARGET_BINS",
        "OUT_OF_TARGET_DISTRIBUTED_SPECTRAL_FINGERPRINT_PLUS_FIXED_REFERENCE",
        False,
        "MASK_SENTINEL_CAN_INFLATE_LEGACY_PEAK_WIDTH; NOT_CAUSAL_FOR_THE_FROZEN_LESS_THAN_TWO_FEATURE_EXIT",
        False,
        False,
        False,
        "a future pre-freeze diagnostic may qualify the channel translation; it cannot classify target physics",
        "a witness need not be represented as a second narrowband FeatureFingerprint",
        RAW_RF_PERSISTENCE,
    )


def strict_json(value: object) -> str:
    payload = asdict(value) if hasattr(value, "__dataclass_fields__") else value
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def main() -> None:
    print(strict_json(assess_gate_f2_5_22()))


if __name__ == "__main__":
    main()
