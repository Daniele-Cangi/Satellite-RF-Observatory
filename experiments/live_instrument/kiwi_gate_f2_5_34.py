"""Gate F2.5.34: receipt-only attribution of the frozen F2.5.33 negative.

This module has no acquisition or connector surface.  It verifies the exact
outcome artifact and the two relevant frozen source transforms, then states
which discovery cuts are observable from the receipt.  It deliberately does
not reconstruct RF, change a threshold, or choose a cause for the negative.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any


TRANSFORM_VERSION = "gate-f2.5.34-receipt-only-failure-attribution-v1"
REVIEWED_F2533_OUTCOME_COMMIT = "51c43c78f7e69d937e2ac25cdbd60b84df415ecf"
REVIEWED_F2533_RUNTIME_SEAL_COMMIT = "77a5f733725e83e758560eb1af7db4ee1a4d3d25"
FROZEN_RECEIPT_PATH = (
    Path(__file__).parent
    / "session_receipts"
    / "gate-f2-5-33-20260819T001930.319362Z.jsonl"
)
FROZEN_RECEIPT_SHA256 = (
    "1d0b9c2ff97702f533f7944f2c23c7f782da4bb2427ec3d02a3d3e6279aad62c"
)
FROZEN_RECEIPT_PREFIX_SHA256 = (
    "08180d45a0cac8a0fd57b2f6934a3f8347114b416ca25368d8c40c576868ec44"
)
FROZEN_AUTHORITY_ENVELOPE_HASH = (
    "3f052af8686b37be6e04b85543a5fca30ad05e8536a8d57d796034cc98c6ab52"
)
FROZEN_F2531_DISCOVERY_SOURCE_SHA256 = (
    "64e0ece64596d7d6e28be2350e18a7598ca0ed1519588d37ebf18826aa7b97a3"
)
FROZEN_F2522_AUDIT_SOURCE_SHA256 = (
    "d698d04989dbd2f86def6ecb4223af8e492d60f94acb92787ac5c5cf7035cafa"
)
RAW_RF_PERSISTENCE = "ZERO"
EXPECTED_EVENTS = (
    "gate_f2_5_33_authority_envelope_frozen",
    "gate_f2_5_33_one_outcome",
    "gate_f2_5_3_1_receipt_artifact_terminal",
)
FROZEN_THRESHOLDS = (
    ("minimum_joint_contrast_db", 5.0),
    ("minimum_half_contrast_db", 3.0),
    ("minimum_cross_branch_correlation", 0.65),
)
FROZEN_STFT_GEOMETRY = (("nperseg", 1024), ("noverlap", 512))


class StageState(str, Enum):
    SATISFIED = "SATISFIED"
    EXECUTED = "EXECUTED"
    UNSATISFIED = "UNSATISFIED"
    UNRESOLVED_FROM_RECEIPT = "UNRESOLVED_FROM_RECEIPT"
    NOT_EVALUATED = "NOT_EVALUATED"


class EpistemicClassification(str, Enum):
    FALSIFYING = "FALSIFYING"
    INCONCLUSIVE = "INCONCLUSIVE"
    NOT_FALSIFIABLE_WITH_THIS_RECEIPT = "NOT_FALSIFIABLE_WITH_THIS_RECEIPT"


@dataclass(frozen=True, slots=True)
class DiscoveryStageAttribution:
    stage: str
    physical_to_feature_step: str
    frozen_rule: str
    minimum_detectable_structure: str
    receipt_observable: bool
    state: StageState
    receipt_evidence: str


@dataclass(frozen=True, slots=True)
class ScopedConclusion:
    scope: str
    classification: EpistemicClassification
    conclusion: str


@dataclass(frozen=True, slots=True)
class GateF2534Attribution:
    transform_version: str
    reviewed_outcome_commit: str
    reviewed_runtime_seal_commit: str
    receipt_path: str
    receipt_sha256: str
    receipt_prefix_sha256: str
    authority_envelope_hash: str
    receipt_event_order: tuple[str, ...]
    receipt_retention_state: str
    receipt_error_count: int
    outcome: str
    physical_hypothesis_state: str
    sensor_capability_state: str
    sensor_operational_evidence: tuple[str, ...]
    transform_ledger: tuple[str, ...]
    frozen_thresholds: tuple[tuple[str, float], ...]
    frozen_stft_geometry: tuple[tuple[str, int], ...]
    discovery_stages: tuple[DiscoveryStageAttribution, ...]
    possible_false_negative_conditions: tuple[str, ...]
    scoped_conclusions: tuple[ScopedConclusion, ...]
    authorised_claims: tuple[str, ...]
    unauthorised_claims: tuple[str, ...]
    minimal_future_descriptive_change: tuple[str, ...]
    legacy_audit_already_expresses_needed_fields: bool
    source_seals_match: bool
    thresholds_changed: bool
    physical_decision_affected: bool
    live_execution_authorised: bool
    raw_rf_persistence: str

    def __post_init__(self) -> None:
        if self.receipt_event_order != EXPECTED_EVENTS:
            raise ValueError("unexpected frozen receipt event order")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")
        if self.thresholds_changed:
            raise ValueError("failure attribution cannot change frozen thresholds")
        if self.physical_decision_affected:
            raise ValueError("description cannot alter the physical decision")
        if self.live_execution_authorised:
            raise ValueError("Gate F2.5.34 is exclusively offline")

    def to_strict_json(self) -> str:
        return json.dumps(
            _json_value(self),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return {
            name: _json_value(getattr(value, name))
            for name in value.__dataclass_fields__
        }
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite values cannot enter the attribution")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported strict JSON value: {type(value).__name__}")


def _reject_nonfinite(token: str) -> None:
    raise ValueError(f"non-finite JSON constant is forbidden: {token}")


def _strict_documents(raw: bytes, expected_sha256: str) -> tuple[dict[str, Any], ...]:
    if sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("frozen receipt SHA-256 mismatch")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("frozen receipt is not UTF-8") from error
    lines = text.splitlines()
    documents = tuple(
        json.loads(line, parse_constant=_reject_nonfinite) for line in lines
    )
    if tuple(item.get("event") for item in documents) != EXPECTED_EVENTS:
        raise ValueError("frozen receipt event sequence mismatch")
    return documents


def _function_source_sha256(path: Path, function_name: str) -> str:
    source = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    tree = ast.parse(source)
    node = next(
        (
            item
            for item in tree.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and item.name == function_name
        ),
        None,
    )
    if node is None or node.end_lineno is None:
        raise ValueError(f"missing source function: {function_name}")
    segment = "\n".join(source.splitlines()[node.lineno - 1 : node.end_lineno]) + "\n"
    return sha256(segment.encode("utf-8")).hexdigest()


def _source_seals_match() -> bool:
    directory = Path(__file__).parent
    return (
        _function_source_sha256(
            directory / "kiwi_gate_f2_5_31.py", "_discover_one_feature"
        )
        == FROZEN_F2531_DISCOVERY_SOURCE_SHA256
        and _function_source_sha256(
            directory / "kiwi_gate_f2_5_22.py", "audit_profile_pair"
        )
        == FROZEN_F2522_AUDIT_SOURCE_SHA256
    )


def _validate_frozen_payload(
    documents: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    authority = documents[0]["payload"]
    outcome = documents[1]["payload"]
    terminal = documents[2]["payload"]
    if authority.get("authority_envelope_hash") != FROZEN_AUTHORITY_ENVELOPE_HASH:
        raise ValueError("authority envelope mismatch")
    if authority.get("separate_live_authority_asserted") is not True:
        raise ValueError("the frozen authority was not asserted")
    if outcome.get("outcome") != "NO_FALSIFIABLE_INTERVENTION":
        raise ValueError("unexpected frozen physical outcome")
    if outcome.get("physical_hypothesis_state") != "NOT_EVALUATED":
        raise ValueError("physical hypothesis was unexpectedly evaluated")
    discovery = outcome.get("discovery", {})
    if discovery.get("state") != "NO_FEATURE_ADMITTED":
        raise ValueError("unexpected frozen discovery state")
    if discovery.get("threshold_source") != "UNCHANGED_MOTHER_PLAN":
        raise ValueError("frozen threshold provenance mismatch")
    scalar_fields = (
        "selected_baseband_hz",
        "joint_contrast_db",
        "first_half_contrast_db",
        "second_half_contrast_db",
        "cross_branch_correlation",
    )
    if any(discovery.get(field) is not None for field in scalar_fields):
        raise ValueError("negative discovery contains invented selected-feature scalars")
    phase_states = {
        item["phase"]: item["state"] for item in outcome.get("phases", ())
    }
    expected_phase_states = {
        "OPEN_DUAL_SND_HANDLES": "SATISFIED",
        "RELATIVE_TEMPORAL_ADMISSION": "SATISFIED",
        "LOCAL_ONE_FEATURE_DISCOVERY": "UNSATISFIED",
        "A1_TO_B_BOUNDARY": "NOT_EVALUATED",
        "B_TO_A2_BOUNDARY": "NOT_EVALUATED",
        "PLAN_FREEZE": "NOT_EVALUATED",
        "ONE_CONFIRMATION": "NOT_EVALUATED",
    }
    if phase_states != expected_phase_states:
        raise ValueError("frozen phase states mismatch")
    if any(
        (
            outcome.get("command_receipts"),
            outcome.get("boundary_receipts"),
            outcome.get("target_matches"),
        )
    ) or outcome.get("distributed_witness") is not None:
        raise ValueError("intervention evidence exists despite discovery stop")
    cleanup = outcome.get("cleanup", {})
    if not (
        cleanup.get("all_iq_zeroized") is True
        and cleanup.get("transient_raw_references_after_return") == 0
        and cleanup.get("raw_rf_persistence") == RAW_RF_PERSISTENCE
        and cleanup.get("frame_lease_count") == cleanup.get("frame_release_count")
        and cleanup.get("socket_count") == cleanup.get("socket_close_count")
    ):
        raise ValueError("frozen cleanup contract mismatch")
    if not (
        terminal.get("state") == "COMPLETE"
        and terminal.get("retention_complete") is True
        and terminal.get("error_count") == 0
        and terminal.get("prefix_hash") == FROZEN_RECEIPT_PREFIX_SHA256
        and terminal.get("raw_rf_persistence") == RAW_RF_PERSISTENCE
        and terminal.get("physical_decision_affected") is False
    ):
        raise ValueError("frozen terminal manifest mismatch")
    return outcome


def _stage_attributions() -> tuple[DiscoveryStageAttribution, ...]:
    return (
        DiscoveryStageAttribution(
            "spectral_residual_transform",
            "IQ -> STFT log-power -> temporal medians -> median-filter residual",
            "1024-sample STFT, 512-sample overlap, fixed log floor and median residual",
            "enough decoded samples for the frozen transform to return normally",
            True,
            StageState.EXECUTED,
            "discovery returned NO_FEATURE_ADMITTED and the terminal error ledger is empty",
        ),
        DiscoveryStageAttribution(
            "joint_contrast_peak",
            "left/right residuals -> pointwise minimum -> guarded local peaks",
            "a valid common local peak at or above 5.0 dB",
            "joint contrast >= 5.0 dB outside the DC and edge guards",
            False,
            StageState.UNRESOLVED_FROM_RECEIPT,
            "raw peak count and best contrast margin were not retained",
        ),
        DiscoveryStageAttribution(
            "normalised_patch_validity",
            "candidate peak -> one neighbourhood patch per DDC branch",
            "both fixed-size normalised patches must exist",
            "candidate must be far enough from every transform boundary for both patches",
            False,
            StageState.UNRESOLVED_FROM_RECEIPT,
            "patch-valid and patch-incomplete counts were not retained",
        ),
        DiscoveryStageAttribution(
            "cross_branch_structure",
            "paired normalised patches -> correlation",
            "cross-branch correlation at or above 0.65",
            "the local spectral morphology must correlate >= 0.65 across both simultaneous DDC branches",
            False,
            StageState.UNRESOLVED_FROM_RECEIPT,
            "no candidate correlation or margin was retained",
        ),
        DiscoveryStageAttribution(
            "half_window_stability",
            "each branch split into first/second temporal halves -> common residual contrast",
            "minimum contrast in both halves at or above 3.0 dB",
            "the feature must remain above 3.0 dB in both temporal halves and both branches",
            False,
            StageState.UNRESOLVED_FROM_RECEIPT,
            "no candidate half-window contrasts or margins were retained",
        ),
        DiscoveryStageAttribution(
            "composite_feature_admission",
            "all prior predicates -> ranked feature geometry",
            "at least one candidate must satisfy every frozen predicate",
            "one common, patch-valid, correlated and half-stable feature",
            True,
            StageState.UNSATISFIED,
            "state=NO_FEATURE_ADMITTED with all selected-feature scalars null",
        ),
        DiscoveryStageAttribution(
            "ddc_intervention_prediction",
            "admitted feature -> plan freeze -> A1/B/A2 retune outcome",
            "requires an admitted feature before any intervention",
            "not applicable because no feature entered the prospective experiment",
            True,
            StageState.NOT_EVALUATED,
            "zero commands, zero boundaries, no plan freeze and no confirmation",
        ),
    )


def assess_frozen() -> GateF2534Attribution:
    """Attribute only what the committed F2.5.33 receipt makes observable."""

    raw = FROZEN_RECEIPT_PATH.read_bytes()
    documents = _strict_documents(raw, FROZEN_RECEIPT_SHA256)
    outcome = _validate_frozen_payload(documents)
    source_seals_match = _source_seals_match()
    if not source_seals_match:
        raise ValueError("reviewed discovery or legacy audit source seal mismatch")
    temporal = outcome["temporal_admission"]
    branches = temporal["branches"]
    cleanup = outcome["cleanup"]
    return GateF2534Attribution(
        TRANSFORM_VERSION,
        REVIEWED_F2533_OUTCOME_COMMIT,
        REVIEWED_F2533_RUNTIME_SEAL_COMMIT,
        FROZEN_RECEIPT_PATH.name,
        FROZEN_RECEIPT_SHA256,
        FROZEN_RECEIPT_PREFIX_SHA256,
        FROZEN_AUTHORITY_ENVELOPE_HASH,
        tuple(item["event"] for item in documents),
        documents[-1]["payload"]["state"],
        int(documents[-1]["payload"]["error_count"]),
        outcome["outcome"],
        outcome["physical_hypothesis_state"],
        "MEASUREMENT_AVAILABLE_BUT_NO_FALSIFIABLE_FEATURE_ADMITTED",
        (
            "two distinct simultaneous SND/IQ channel handles were opened",
            f"both branches supplied {branches[0]['input_frame_count']} A1 frames",
            f"both branches retained {branches[0]['usable_frame_count']} usable timed frames",
            "both sequences had zero gaps, zero arrival-order violations and zero timestamp-step violations",
            f"common same-clock overlap was {temporal['common_duration_ns']} ns",
            f"all {cleanup['decoded_frame_count']} decoded frames and {cleanup['decoded_sample_count']} IQ samples were zeroized",
        ),
        (
            "antenna/front-end/ADC and two simultaneous channel DDC branches",
            "SND IQ decode and frame hash before analysis",
            "per-branch concatenation of eight 512-sample frames",
            "two-sided STFT with nperseg=1024 and noverlap=512",
            "log-power floor, full-window and half-window temporal medians",
            "median-filter spectral residual per branch",
            "pointwise minimum across branches and fixed edge/DC guards",
            "local peak, paired neighbourhood, correlation and half-window gates",
            "composite ranking or NO_FEATURE_ADMITTED",
        ),
        FROZEN_THRESHOLDS,
        FROZEN_STFT_GEOMETRY,
        _stage_attributions(),
        (
            "a physical feature narrower, broader or shorter than the frozen STFT/median representation can be suppressed",
            "a real feature in the guarded DC or edge bins cannot become a candidate",
            "a broad common change can be removed by the median-filter residual",
            "frequency-response differences or local channel artefacts can reduce the pointwise minimum or patch correlation",
            "a transient confined to one half fails the stability gate even if physically real",
            "the approximately 0.34 s capture and approximately 0.254 s timed overlap may not contain the feature's stable regime",
            "a relevant phenomenon may not map to the particular common spectral morphology required by the frozen feature",
        ),
        (
            ScopedConclusion(
                "frozen_composite_discovery_proposition",
                EpistemicClassification.FALSIFYING,
                "the single A1 window did not contain a feature admitted by every frozen discovery predicate",
            ),
            ScopedConclusion(
                "specific_discovery_rejection_stage",
                EpistemicClassification.INCONCLUSIVE,
                "the receipt cannot distinguish contrast, patch validity, correlation, half stability or a combination",
            ),
            ScopedConclusion(
                "upstream_vs_downstream_channel_ddc_hypothesis",
                EpistemicClassification.NOT_FALSIFIABLE_WITH_THIS_RECEIPT,
                "no prediction was frozen and no retune intervention occurred",
            ),
        ),
        (
            "the dual-SND capability and relative-time transform were operational in A1",
            "the exact composite feature-admission rule was unsatisfied in the one authorised A1 window",
            "the normal discovery path completed without a qualification or serialization error",
            "the physical DDC-location hypothesis remained NOT_EVALUATED",
        ),
        (
            "no RF energy or important signal existed in the passband",
            "any named discovery predicate was the cause of rejection",
            "the receiver, ADC or either DDC failed",
            "the physical feature was upstream or downstream of the channel DDC",
            "changing a threshold would recover a valid prospective experiment",
            "another window would reproduce or reverse this result",
        ),
        (
            "add a decision-independent scalar DiscoveryAuditReceipt beside the existing DiscoveryReceipt",
            "retain raw-peak, patch-valid, correlation-pass, half-stability-pass and admitted counts",
            "retain best finite margins to the three frozen thresholds with explicit numerical states",
            "bind those scalars to the same pre-analysis artifact hashes and transform version",
            "keep the selection result authoritative; the descriptive sibling must be unable to modify it",
            "persist no IQ, STFT, spectrum, candidate patch or waterfall",
        ),
        True,
        source_seals_match,
        False,
        bool(outcome["physical_decision_affected_by_description"]),
        False,
        outcome["raw_rf_persistence"],
    )


def main() -> None:
    print(assess_frozen().to_strict_json())


if __name__ == "__main__":
    main()
