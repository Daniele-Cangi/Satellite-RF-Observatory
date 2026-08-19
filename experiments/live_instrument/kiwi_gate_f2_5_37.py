"""Gate F2.5.37: full-session leading-zero normalization, offline only.

The frozen F2.5.31--36 sources and the F2.5.36 live outcome are not modified.
This narrow successor applies the already-reviewed F2.5.27 timestamp
normalization to the final full-session continuity evaluator.  It exposes no
connector, live authority, retry, threshold or experiment dimension.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
import math
from pathlib import Path
from threading import RLock
from typing import Iterator

from . import kiwi_gate_f2_5_27 as f2527
from . import kiwi_gate_f2_5_31 as f2531
from . import kiwi_gate_f2_5_35 as f2535


TRANSFORM_VERSION = "gate-f2.5.37-full-session-leading-zero-normalization-v1"
REVIEWED_OUTCOME_COMMIT = "91df4965efee9b1b8935fe03b2b5be99b285320e"
REVIEWED_RECEIPT_SHA256 = (
    "9c976fabf725eb509f71308d19125b31e1360c1ea0994c2c4d6b679b46628246"
)
REVIEWED_PREFIX_SHA256 = (
    "2229c39dcec6fa342f8ab3350ae65a422f7a800af5c75b89875eb89aa05202e6"
)
REVIEWED_F2531_SOURCE_SHA256 = (
    "dd447450510bd17d5b7ad1502fab84f86f5b129194d3b97550842ab5f8257672"
)
REVIEWED_F2535_SOURCE_SHA256 = (
    "b13523f10edaab9b7eda9615f05ecfd6ab611bd40a499a28005dcaf087e46c86"
)
RAW_RF_PERSISTENCE = "ZERO"

_RECEIPT_PATH = (
    Path(__file__).resolve().parent
    / "session_receipts"
    / "gate-f2-5-36-20260819T082846.463772Z.jsonl"
)
_FROZEN_CONTINUITY_EVALUATOR = f2531._continuity
_INSTALL_LOCK = RLock()


class F2537Exit(str, Enum):
    CONTINUITY_NORMALIZATION_INTEGRATED_OFFLINE = (
        "CONTINUITY_NORMALIZATION_INTEGRATED_OFFLINE"
    )
    FROZEN_LINEAGE_MISMATCH = "FROZEN_LINEAGE_MISMATCH"


def _strict_hash(value: object) -> str:
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
            default=lambda item: item.value if isinstance(item, Enum) else str(item),
        ).encode("utf-8")
    ).hexdigest()


def _canonical_source_sha256(path: Path) -> str:
    return sha256(
        path.read_text(encoding="utf-8").replace("\r\n", "\n").encode()
    ).hexdigest()


def current_f2531_source_sha256() -> str:
    return _canonical_source_sha256(
        Path(__file__).resolve().parent / "kiwi_gate_f2_5_31.py"
    )


def current_f2535_source_sha256() -> str:
    return _canonical_source_sha256(
        Path(__file__).resolve().parent / "kiwi_gate_f2_5_35.py"
    )


@dataclass(frozen=True, slots=True)
class F2537Plan:
    reviewed_outcome_commit: str
    reviewed_receipt_sha256: str
    reviewed_prefix_sha256: str
    reviewed_f2531_source_sha256: str
    reviewed_f2535_source_sha256: str
    change_scope: str
    normalization_rule: str
    retained_receipt_type: str
    threshold_policy: str
    connector_surface_present: bool
    prefreeze_retry_budget: int
    postfreeze_retry_budget: int
    live_execution_authorised: bool
    raw_rf_persistence: str
    transform_versions: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.reviewed_outcome_commit != REVIEWED_OUTCOME_COMMIT:
            raise ValueError("reviewed outcome commit changed")
        if self.reviewed_receipt_sha256 != REVIEWED_RECEIPT_SHA256:
            raise ValueError("reviewed receipt changed")
        if self.reviewed_prefix_sha256 != REVIEWED_PREFIX_SHA256:
            raise ValueError("reviewed receipt prefix changed")
        if self.reviewed_f2531_source_sha256 != REVIEWED_F2531_SOURCE_SHA256:
            raise ValueError("reviewed F2.5.31 source changed")
        if self.reviewed_f2535_source_sha256 != REVIEWED_F2535_SOURCE_SHA256:
            raise ValueError("reviewed F2.5.35 source changed")
        if self.change_scope != "FULL_SESSION_CONTINUITY_NORMALIZATION_ONLY":
            raise ValueError("the repair scope expanded")
        if self.normalization_rule != "REUSE_F2527_UNWRAP_START_TIMES_EXACTLY":
            raise ValueError("a second timestamp rule was introduced")
        if self.retained_receipt_type != "F2531_SESSION_CONTINUITY_RECEIPT":
            raise ValueError("the receipt boundary changed")
        if self.threshold_policy != "ALL_RF_THRESHOLDS_INHERITED_UNCHANGED":
            raise ValueError("an RF threshold changed")
        if self.connector_surface_present:
            raise ValueError("offline repair cannot expose a connector")
        if self.prefreeze_retry_budget or self.postfreeze_retry_budget:
            raise ValueError("the repair cannot add retry")
        if self.live_execution_authorised:
            raise ValueError("offline repair cannot grant authority")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")
        if self.transform_versions != (
            f2527.TRANSFORM_VERSION,
            f2535.TRANSFORM_VERSION,
            TRANSFORM_VERSION,
        ):
            raise ValueError("transform lineage changed")

    @property
    def plan_hash(self) -> str:
        return _strict_hash(asdict(self))


@dataclass(frozen=True, slots=True)
class F2537Assessment:
    exit: F2537Exit
    plan: F2537Plan
    receipt_hash_matches: bool
    prefix_hash_matches: bool
    strict_json_complete: bool
    frozen_outcome_preserved: bool
    frozen_physical_state_preserved: bool
    leading_zero_failure_attribution_exact: bool
    f2531_source_hash_matches: bool
    f2535_source_hash_matches: bool
    one_existing_normalization_rule: bool
    frozen_sources_untouched: bool
    no_public_execution_surface: bool
    live_execution_authorised: bool
    blockers: tuple[str, ...]
    raw_rf_persistence: str


def build_plan() -> F2537Plan:
    return F2537Plan(
        REVIEWED_OUTCOME_COMMIT,
        REVIEWED_RECEIPT_SHA256,
        REVIEWED_PREFIX_SHA256,
        REVIEWED_F2531_SOURCE_SHA256,
        REVIEWED_F2535_SOURCE_SHA256,
        "FULL_SESSION_CONTINUITY_NORMALIZATION_ONLY",
        "REUSE_F2527_UNWRAP_START_TIMES_EXACTLY",
        "F2531_SESSION_CONTINUITY_RECEIPT",
        "ALL_RF_THRESHOLDS_INHERITED_UNCHANGED",
        False,
        0,
        0,
        False,
        RAW_RF_PERSISTENCE,
        (f2527.TRANSFORM_VERSION, f2535.TRANSFORM_VERSION, TRANSFORM_VERSION),
    )


def _parse_frozen_receipt() -> tuple[bytes, tuple[dict[str, object], ...]]:
    raw = _RECEIPT_PATH.read_bytes()
    documents = tuple(
        json.loads(
            line,
            parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
        )
        for line in raw.splitlines()
    )
    return raw, documents


def _failure_attribution_is_exact(documents: tuple[dict[str, object], ...]) -> bool:
    try:
        payload = documents[1]["payload"]
        assert isinstance(payload, dict)
        physical = payload["physical_result"]
        assert isinstance(physical, dict)
        temporal = physical["temporal_admission"]
        cleanup = physical["cleanup"]
        continuity = physical["session_continuity"]
        assert isinstance(temporal, dict) and isinstance(cleanup, dict)
        assert isinstance(continuity, list)
        branches = temporal["branches"]
        assert isinstance(branches, list)
        decoded_frames = int(cleanup["decoded_frame_count"])
        decoded_samples = int(cleanup["decoded_sample_count"])
        if decoded_frames <= 0 or decoded_samples % decoded_frames:
            return False
        sample_count = decoded_samples // decoded_frames
        by_role = {str(item["role"]): item for item in branches}
        for item in continuity:
            role = str(item["branch_role"])
            branch = by_role[role]
            rate = float(branch["sample_rate_hz"])
            first_valid_start = int(branch["unwrapped_start_ns"])
            duration = round(sample_count * 1_000_000_000 / rate)
            reconstructed = abs(first_valid_start - duration) / (
                1_000_000_000 / rate
            )
            if int(branch["leading_zero_timestamp_count"]) != 1:
                return False
            if int(item["timestamp_step_violation_count"]) != 1:
                return False
            if int(item["sequence_gap_count"]) != 0:
                return False
            if not math.isclose(
                reconstructed,
                float(item["maximum_timestamp_step_residual_samples"]),
                rel_tol=0.0,
                abs_tol=1e-6,
            ):
                return False
        return len(continuity) == 2
    except (AssertionError, KeyError, TypeError, ValueError, IndexError):
        return False


def assess() -> F2537Assessment:
    plan = build_plan()
    receipt_hash_matches = False
    prefix_hash_matches = False
    strict_complete = False
    outcome_preserved = False
    physical_preserved = False
    attribution_exact = False
    try:
        raw, documents = _parse_frozen_receipt()
        lines = raw.splitlines(keepends=True)
        receipt_hash_matches = sha256(raw).hexdigest() == REVIEWED_RECEIPT_SHA256
        prefix_hash_matches = (
            sha256(b"".join(lines[:-1])).hexdigest() == REVIEWED_PREFIX_SHA256
        )
        strict_complete = (
            tuple(item["event"] for item in documents)
            == (
                "gate_f2_5_36_authority_envelope_frozen",
                "gate_f2_5_36_one_outcome",
                "gate_f2_5_3_1_receipt_artifact_terminal",
            )
            and documents[-1]["payload"]["state"] == "COMPLETE"  # type: ignore[index]
            and documents[-1]["payload"]["raw_rf_persistence"] == RAW_RF_PERSISTENCE  # type: ignore[index]
        )
        physical = documents[1]["payload"]["physical_result"]  # type: ignore[index]
        outcome_preserved = physical["outcome"] == "INTERVENTION_INVALID"
        physical_preserved = physical["physical_hypothesis_state"] == "NOT_EVALUATED"
        attribution_exact = _failure_attribution_is_exact(documents)
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        pass
    f2531_match = current_f2531_source_sha256() == REVIEWED_F2531_SOURCE_SHA256
    f2535_match = current_f2535_source_sha256() == REVIEWED_F2535_SOURCE_SHA256
    checks = (
        (receipt_hash_matches, "frozen receipt hash changed"),
        (prefix_hash_matches, "frozen receipt prefix changed"),
        (strict_complete, "frozen receipt is not complete strict JSONL"),
        (outcome_preserved, "frozen emitted outcome changed"),
        (physical_preserved, "frozen physical state changed"),
        (attribution_exact, "leading-zero attribution is no longer exact"),
        (f2531_match, "frozen F2.5.31 source changed"),
        (f2535_match, "frozen F2.5.35 source changed"),
    )
    blockers = tuple(message for condition, message in checks if not condition)
    return F2537Assessment(
        (
            F2537Exit.CONTINUITY_NORMALIZATION_INTEGRATED_OFFLINE
            if not blockers
            else F2537Exit.FROZEN_LINEAGE_MISMATCH
        ),
        plan,
        receipt_hash_matches,
        prefix_hash_matches,
        strict_complete,
        outcome_preserved,
        physical_preserved,
        attribution_exact,
        f2531_match,
        f2535_match,
        True,
        f2531_match and f2535_match,
        True,
        False,
        blockers,
        RAW_RF_PERSISTENCE,
    )


def evaluate_full_session_continuity(
    handle: f2531._Handle,
) -> f2531.SessionContinuityReceipt:
    """Apply the F2.5.27 leading-zero and GPS-week rule to all session frames."""

    plan = f2527.build_plan()
    ordered = tuple(handle.scalar_receipts)
    usable, starts, _leading_zero_count = f2527._unwrap_start_times(ordered)
    sequence_gaps = sum(
        current.sequence != ((previous.sequence + 1) % f2527.SEQUENCE_MODULUS)
        for previous, current in zip(usable, usable[1:])
    )
    residuals: list[float] = []
    timestamp_violations = 0
    for previous, _current, previous_start, current_start in zip(
        usable, usable[1:], starts, starts[1:]
    ):
        residual = abs(
            (current_start - previous_start) - previous.sample_duration_ns
        ) / (1_000_000_000 / previous.sample_rate_hz)
        residuals.append(residual)
        timestamp_violations += int(
            residual > plan.maximum_timestamp_step_residual_samples
        )
    satisfied = bool(usable) and sequence_gaps == 0 and timestamp_violations == 0
    return f2531.SessionContinuityReceipt(
        handle.branch_role,
        len(ordered),
        sequence_gaps,
        timestamp_violations,
        max(residuals, default=0.0),
        "SATISFIED" if satisfied else "UNSATISFIED",
        tuple(item.artifact_hash_before_analysis for item in ordered),
    )


@contextmanager
def _corrected_continuity_scope() -> Iterator[None]:
    """Install the narrow evaluator only for one isolated offline vertical."""

    with _INSTALL_LOCK:
        if f2531._continuity is not _FROZEN_CONTINUITY_EVALUATOR:
            raise RuntimeError("frozen continuity seam is already modified")
        f2531._continuity = evaluate_full_session_continuity
        try:
            yield
        finally:
            f2531._continuity = _FROZEN_CONTINUITY_EVALUATOR


def _run_corrected_audited_injected(
    *,
    reference_socket: object,
    perturbed_socket: object,
) -> f2535.F2535RunResult:
    """Private synthetic seam; no connector, authority or caller experiment controls."""

    assessment = assess()
    if assessment.exit is not F2537Exit.CONTINUITY_NORMALIZATION_INTEGRATED_OFFLINE:
        raise RuntimeError("frozen lineage mismatch: " + "; ".join(assessment.blockers))
    with _corrected_continuity_scope():
        return f2535._run_audited_open_handle_rf_injected(
            reference_socket=reference_socket,
            perturbed_socket=perturbed_socket,
        )


__all__ = [
    "F2537Assessment",
    "F2537Exit",
    "F2537Plan",
    "assess",
    "build_plan",
    "evaluate_full_session_continuity",
]
