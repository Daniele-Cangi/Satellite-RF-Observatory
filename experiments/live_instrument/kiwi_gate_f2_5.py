"""Gate F2.5: direct dual-SND first, entirely prepared offline.

The module contains a future one-shot runner, but Gate F2.5 itself does not
call it.  W/F is not on the causal path.  ``ext_api`` is retained as a
descriptive hint; only an actual simultaneous reference/perturbed SND attempt
can establish or reject multichannel availability.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import sha256
import math
import re
import time
from typing import Callable

from . import kiwi_gate_f2 as f2
from . import kiwi_gate_f2_2 as f22
from . import kiwi_gate_f2_3 as f23
from . import kiwi_gate_f2_4 as f24
from . import kiwi_probe as kiwi
from .models import Constraint, ConstraintReceipt, Transform, emit_jsonl, strict_json_value


F25_TRANSFORM_VERSION = "gate-f2.5-direct-dual-snd-v1"
CENTER_POLICY = "advertised-band-interior-endpoint-hash-v1"
PHASE_ORDER = (
    "DIRECT_DUAL_SND_QUALIFICATION",
    "LOCAL_IQ_FEATURE_DISCOVERY",
    "PER_CHANNEL_RETUNE_QUALIFICATION",
    "PLAN_FREEZE",
    "ONE_CONFIRMATION",
)
TOPOLOGY_DURATION_S = 1.5
DISCOVERY_DURATION_S = 4.0


class F25Phase(str, Enum):
    STATUS = "STATUS"
    DIRECT_DUAL_SND_QUALIFICATION = "DIRECT_DUAL_SND_QUALIFICATION"
    LOCAL_IQ_FEATURE_DISCOVERY = "LOCAL_IQ_FEATURE_DISCOVERY"
    PER_CHANNEL_RETUNE_QUALIFICATION = "PER_CHANNEL_RETUNE_QUALIFICATION"
    PLAN_FREEZE = "PLAN_FREEZE"
    ONE_CONFIRMATION = "ONE_CONFIRMATION"


class F25PhaseState(str, Enum):
    SATISFIED = "SATISFIED"
    UNSATISFIED = "UNSATISFIED"
    QUALIFICATION_ERROR = "QUALIFICATION_ERROR"
    CAPABILITY_REJECTED = "CAPABILITY_REJECTED"
    NOT_EVALUATED = "NOT_EVALUATED"


class F25Outcome(str, Enum):
    QUALIFICATION_INCOMPLETE = "QUALIFICATION_INCOMPLETE"
    NO_MULTI_CHANNEL_CAPABILITY = "NO_MULTI_CHANNEL_CAPABILITY"
    NO_ADMISSIBLE_CAUSAL_TOPOLOGY = "NO_ADMISSIBLE_CAUSAL_TOPOLOGY"
    NO_FALSIFIABLE_INTERVENTION = "NO_FALSIFIABLE_INTERVENTION"
    UPSTREAM_OF_CHANNEL_DDC_SUPPORTED = "UPSTREAM_OF_CHANNEL_DDC_SUPPORTED"
    DOWNSTREAM_CHANNEL_FIXED_SUPPORTED = "DOWNSTREAM_CHANNEL_FIXED_SUPPORTED"
    AMBIGUOUS = "AMBIGUOUS"
    INTERVENTION_INVALID = "INTERVENTION_INVALID"
    NOT_DETECTABLE = "NOT_DETECTABLE"


@dataclass(frozen=True, slots=True)
class F25BootstrapReceipt:
    created_at: datetime
    candidate_set_hash: str
    candidate_order: tuple[str, ...]
    runtime_commit: str
    phase_order: tuple[str, ...]
    center_policy: str
    ext_api_semantics: str
    waterfall_semantics: str
    retry_budget: int
    maximum_retry_per_endpoint: int
    transform_versions: tuple[str, ...]

    def __post_init__(self) -> None:
        f2._utc(self.created_at)
        if self.candidate_set_hash != f24.candidate_set_hash():
            raise ValueError("Gate F2.5 candidate set changed")
        if self.candidate_order != f24.ordered_candidate_identities():
            raise ValueError("Gate F2.5 candidate order changed")
        if re.fullmatch(r"[0-9a-f]{40}", self.runtime_commit) is None:
            raise ValueError("runtime commit must be full Git SHA-1")
        if self.phase_order != PHASE_ORDER or self.center_policy != CENTER_POLICY:
            raise ValueError("Gate F2.5 phase or center policy changed")
        if self.ext_api_semantics != "DESCRIPTIVE_HINT_ONLY":
            raise ValueError("ext_api cannot become a qualification gate")
        if self.waterfall_semantics != "OPTIONAL_AND_OUTSIDE_CAUSAL_PATH":
            raise ValueError("W/F cannot block direct dual-SND qualification")
        if self.retry_budget != f24.RETRY_BUDGET or self.maximum_retry_per_endpoint != f24.MAX_RETRY_PER_ENDPOINT:
            raise ValueError("Gate F2.5 retry budget changed")
        if self.transform_versions != (
            f2.TRANSFORM_VERSION,
            f24.F24_TRANSFORM_VERSION,
            F25_TRANSFORM_VERSION,
        ):
            raise ValueError("Gate F2.5 transform ledger changed")

    @property
    def receipt_hash(self) -> str:
        return f2._hash(asdict(self))


def build_bootstrap_receipt(*, runtime_commit: str, created_at: datetime) -> F25BootstrapReceipt:
    return F25BootstrapReceipt(
        f2._utc(created_at),
        f24.candidate_set_hash(),
        f24.ordered_candidate_identities(),
        runtime_commit,
        PHASE_ORDER,
        CENTER_POLICY,
        "DESCRIPTIVE_HINT_ONLY",
        "OPTIONAL_AND_OUTSIDE_CAUSAL_PATH",
        f24.RETRY_BUDGET,
        f24.MAX_RETRY_PER_ENDPOINT,
        (f2.TRANSFORM_VERSION, f24.F24_TRANSFORM_VERSION, F25_TRANSFORM_VERSION),
    )


@dataclass(frozen=True, slots=True)
class ExtApiHint:
    present: bool
    parsed_value: int | None
    raw_hash: str
    used_as_gate: bool = False


def ext_api_hint(status: dict[str, str]) -> ExtApiHint:
    raw = status.get("ext_api")
    try:
        parsed = None if raw is None else int(raw or 0)
    except (TypeError, ValueError):
        parsed = None
    return ExtApiHint(raw is not None, parsed, f2._hash({"ext_api": raw}), False)


def center_from_status(endpoint: kiwi.KiwiEndpoint, status: dict[str, str]) -> float:
    """Choose a data-independent interior center; never inspect W/F or IQ."""

    try:
        bandwidth = float(status["bandwidth"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("advertised bandwidth is required for the data-independent center policy") from error
    if not math.isfinite(bandwidth) or bandwidth <= 100_000.0:
        raise ValueError("advertised bandwidth is not a usable finite RF interval")
    identity = f"{endpoint.host.lower()}:{endpoint.port}".encode("utf-8")
    unit = int.from_bytes(sha256(identity).digest()[:8], "big") / float(2**64 - 1)
    fraction = 0.25 + 0.5 * unit
    center = bandwidth * fraction
    guard = 25_000.0
    return float(min(max(center, guard), bandwidth - guard))


@dataclass(frozen=True, slots=True)
class PhaseReceipt:
    endpoint_identity: str
    phase: F25Phase
    state: F25PhaseState
    started_at: datetime
    completed_at: datetime
    statement: str
    artifact_hashes: tuple[str, ...]
    properties: tuple[tuple[str, str], ...]
    ext_api_hint: ExtApiHint | None = None
    direct_reference_attempted: bool = False
    direct_perturbed_attempted: bool = False
    direct_reference_opened: bool = False
    direct_perturbed_opened: bool = False
    atomic_branch_receipts: tuple[object, ...] = ()
    qualification_error_types: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if f2._utc(self.completed_at) < f2._utc(self.started_at):
            raise ValueError("phase receipt time runs backwards")
        if self.phase is not F25Phase.DIRECT_DUAL_SND_QUALIFICATION and any(
            (
                self.direct_reference_attempted,
                self.direct_perturbed_attempted,
                self.direct_reference_opened,
                self.direct_perturbed_opened,
            )
        ):
            raise ValueError("only direct dual-SND qualification may describe channel attempts")
        if self.phase is not F25Phase.DIRECT_DUAL_SND_QUALIFICATION and self.atomic_branch_receipts:
            raise ValueError("only direct dual-SND qualification may contain atomic branch receipts")


@dataclass(frozen=True, slots=True)
class F25Result:
    outcome: F25Outcome
    phase_receipts: tuple[PhaseReceipt, ...]
    plan_hash: str | None
    physical_result: f24.F24Result | None
    evidence_receipt: ConstraintReceipt
    authorised_claims: tuple[str, ...]
    unauthorised_claims: tuple[str, ...]


@dataclass(slots=True)
class _TopologyContext:
    endpoint: kiwi.KiwiEndpoint
    status: dict[str, str]
    center_hz: float
    dual: f24._DualConnections
    topology_artifacts: f24._DualArtifacts
    phase_receipt: PhaseReceipt

    def close(self) -> None:
        self.dual.close()


@dataclass(frozen=True, slots=True)
class _DiscoverySelection:
    geometry: f24._PlanGeometry
    artifact_hashes: tuple[str, str]


@dataclass(slots=True)
class _DiscoveryContext:
    artifacts: f24._DualArtifacts
    selection: _DiscoverySelection
    phase_receipt: PhaseReceipt


@dataclass(frozen=True, slots=True)
class _RetuneQualification:
    axis_orientation: int
    witness_match: f2.FeatureMatch
    phase_receipt: PhaseReceipt
    endpoint_qualification: f24.EndpointQualification


def _endpoint_identity(endpoint: kiwi.KiwiEndpoint) -> str:
    return f"{endpoint.host.lower()}:{endpoint.port}"


def _relabel_baseline(artifacts: f24._DualArtifacts, phase: str) -> f24._DualArtifacts:
    reference_artifact = artifacts.reference["DISCOVERY_A"]
    perturbed_artifact = artifacts.perturbed["DISCOVERY_A"]
    reference_artifact.segment = phase
    perturbed_artifact.segment = phase
    return f24._DualArtifacts(
        {phase: reference_artifact},
        {phase: perturbed_artifact},
        artifacts.reference_all_blocks,
        artifacts.perturbed_all_blocks,
        artifacts.reference_commands,
        artifacts.perturbed_commands,
    )


def direct_dual_snd_qualification(
    endpoint: kiwi.KiwiEndpoint,
    mother: f2.MotherPlan,
    *,
    center_resolver: Callable[[kiwi.KiwiEndpoint, dict[str, str]], float] | None = None,
    dual_opener: Callable[
        [kiwi.KiwiEndpoint, float, dict[str, str], f2.MotherPlan],
        f24._DualConnections,
    ]
    | None = None,
) -> _TopologyContext | PhaseReceipt:
    """Attempt R and P directly. No ext_api value can short-circuit this call."""

    started = datetime.now(timezone.utc)
    identity = _endpoint_identity(endpoint)
    status_hash: str | None = None
    hint: ExtApiHint | None = None
    try:
        status = kiwi.fetch_kiwi_status(endpoint, timeout_s=5.0)
        status_hash = f2._hash(status)
        hint = ext_api_hint(status)
        if f24._declares_limited_access(status):
            completed = datetime.now(timezone.utc)
            return PhaseReceipt(
                identity,
                F25Phase.DIRECT_DUAL_SND_QUALIFICATION,
                F25PhaseState.CAPABILITY_REJECTED,
                started,
                completed,
                "endpoint explicitly declares restricted access; no bypass or channel attempt",
                (status_hash,),
                (("status_access", "SATISFIED"), ("public_access", "REJECTED")),
                hint,
            )
        center = (center_resolver or center_from_status)(endpoint, status)
    except Exception as error:
        completed = datetime.now(timezone.utc)
        error_hash = f2._hash(
            {"endpoint": identity, "operation": "status_and_center", "error_type": type(error).__name__, "error": str(error)}
        )
        return PhaseReceipt(
            identity,
            F25Phase.DIRECT_DUAL_SND_QUALIFICATION,
            F25PhaseState.QUALIFICATION_ERROR,
            started,
            completed,
            f"status/center qualification failed: {type(error).__name__}: {error}",
            tuple(item for item in (status_hash, error_hash) if item is not None),
            (("status_access", "NOT_EVALUATED" if status_hash is None else "SATISFIED"),),
            hint,
            qualification_error_types=(type(error).__name__,),
        )

    try:
        dual = (dual_opener or f24._open_dual)(endpoint, center, status, mother)
    except Exception as error:
        completed = datetime.now(timezone.utc)
        description = f"{type(error).__name__}: {error}"
        normalized = description.lower()
        opened_but_invalid = "distinct channel allocations" in normalized
        physical_refusal = any(
            token in normalized
            for token in ("busy", "rejected public snd", "permission", "restricted", "password")
        ) or opened_but_invalid
        error_hash = f2._hash(
            {"endpoint": identity, "operation": "direct_dual_snd", "error_type": type(error).__name__, "error": str(error)}
        )
        return PhaseReceipt(
            identity,
            F25Phase.DIRECT_DUAL_SND_QUALIFICATION,
            F25PhaseState.UNSATISFIED if physical_refusal else F25PhaseState.QUALIFICATION_ERROR,
            started,
            completed,
            (
                "both SND branches were attempted directly but the server did not admit a simultaneous pair: "
                if physical_refusal
                else "both SND branches were attempted directly but transport/software did not determine availability: "
            )
            + description,
            (status_hash, error_hash),
            (
                ("status_access", "SATISFIED"),
                ("ext_api_used_as_gate", "FALSE"),
                ("direct_second_channel_attempt", "COMPLETED"),
                ("dual_snd_pair", "UNSATISFIED"),
            ),
            hint,
            True,
            True,
            opened_but_invalid,
            opened_but_invalid,
            qualification_error_types=(type(error).__name__,),
        )

    try:
        raw = f24._capture_dual(
            dual,
            sequence=False,
            center_a_hz=center,
            delta_f_hz=0.0,
            segment_duration_s=TOPOLOGY_DURATION_S,
            settling_s=0.0,
        )
        topology = _relabel_baseline(raw, "TOPOLOGY_A")
        ref = topology.reference["TOPOLOGY_A"]
        pert = topology.perturbed["TOPOLOGY_A"]
        ref_event, ref_continuous, ref_clean = f24._integrity(
            topology.reference_all_blocks, dual.reference.sample_rate_hz, mother
        )
        pert_event, pert_continuous, pert_clean = f24._integrity(
            topology.perturbed_all_blocks, dual.perturbed.sample_rate_hz, mother
        )
        simultaneous = f24._simultaneous(ref, pert, minimum_s=min(1.0, TOPOLOGY_DURATION_S / 2.0))
        shared_clock = math.isclose(
            dual.reference.sample_rate_hz,
            dual.perturbed.sample_rate_hz,
            rel_tol=0.0,
            abs_tol=1e-6,
        ) and simultaneous
        valid = (
            dual.reference.channel_id != dual.perturbed.channel_id
            and ref_event
            and pert_event
            and ref_continuous
            and pert_continuous
            and ref_clean
            and pert_clean
            and shared_clock
        )
        completed = datetime.now(timezone.utc)
        receipts = topology.receipts
        phase_receipt = PhaseReceipt(
            identity,
            F25Phase.DIRECT_DUAL_SND_QUALIFICATION,
            F25PhaseState.SATISFIED if valid else F25PhaseState.UNSATISFIED,
            started,
            completed,
            "two simultaneous SND/IQ branches established directly" if valid else "two SND streams opened but their causal/time topology was not admissible",
            (status_hash,) + tuple(item.artifact_hash for item in receipts),
            (
                ("status_access", "SATISFIED"),
                ("ext_api_used_as_gate", "FALSE"),
                ("direct_second_channel_attempt", "COMPLETED"),
                ("same_server_instance", "SATISFIED"),
                ("reference_channel_id", dual.reference.channel_id),
                ("perturbed_channel_id", dual.perturbed.channel_id),
                ("distinct_channel_ids", str(dual.reference.channel_id != dual.perturbed.channel_id).upper()),
                ("simultaneous_IQ_streams", str(simultaneous).upper()),
                ("event_time_valid", str(ref_event and pert_event).upper()),
                ("shared_clock_alignment", str(shared_clock).upper()),
                ("both_streams_continuous", str(ref_continuous and pert_continuous).upper()),
                ("both_streams_overflow_free", str(ref_clean and pert_clean).upper()),
            ),
            hint,
            True,
            True,
            True,
            True,
        )
        if not valid:
            dual.close()
            return phase_receipt
        return _TopologyContext(endpoint, status, center, dual, topology, phase_receipt)
    except Exception as error:
        dual.close()
        completed = datetime.now(timezone.utc)
        error_hash = f2._hash(
            {"endpoint": identity, "operation": "direct_dual_iq_capture", "error_type": type(error).__name__, "error": str(error)}
        )
        return PhaseReceipt(
            identity,
            F25Phase.DIRECT_DUAL_SND_QUALIFICATION,
            F25PhaseState.QUALIFICATION_ERROR,
            started,
            completed,
            f"dual SND opened but IQ qualification failed: {type(error).__name__}: {error}",
            (status_hash, error_hash),
            (
                ("direct_second_channel_attempt", "COMPLETED"),
                ("dual_snd_pair", "OPENED"),
                ("simultaneous_IQ_streams", "NOT_EVALUATED"),
            ),
            hint,
            True,
            True,
            True,
            True,
            qualification_error_types=(type(error).__name__,),
        )


def no_topology_outcome(receipts: tuple[PhaseReceipt, ...]) -> F25Outcome:
    """NO_MULTI is legal only when every eligible direct second-channel probe ran."""

    latest_by_endpoint: dict[str, PhaseReceipt] = {}
    for item in receipts:
        if item.phase is F25Phase.DIRECT_DUAL_SND_QUALIFICATION:
            latest_by_endpoint[item.endpoint_identity] = item
    direct = tuple(latest_by_endpoint.values())
    eligible = tuple(item for item in direct if item.state is not F25PhaseState.CAPABILITY_REJECTED)
    if not eligible:
        return F25Outcome.QUALIFICATION_INCOMPLETE
    if any(item.state is F25PhaseState.QUALIFICATION_ERROR for item in eligible):
        return F25Outcome.QUALIFICATION_INCOMPLETE
    if any(item.direct_reference_opened and item.direct_perturbed_opened for item in eligible):
        return F25Outcome.NO_ADMISSIBLE_CAUSAL_TOPOLOGY
    if all(item.direct_reference_attempted and item.direct_perturbed_attempted for item in eligible):
        return F25Outcome.NO_MULTI_CHANNEL_CAPABILITY
    return F25Outcome.QUALIFICATION_INCOMPLETE


def _geometry_signature(geometry: f24._PlanGeometry) -> tuple[float, ...]:
    return (
        geometry.target.baseband_hz,
        geometry.witness.baseband_hz,
        geometry.delta_hz,
        geometry.tolerance_hz,
        geometry.spectral_resolution_hz,
    )


def _orientation_neutral_selection(
    artifacts: f24._DualArtifacts,
    mother: f2.MotherPlan,
) -> _DiscoverySelection:
    plus = f24._select_plan_geometry(artifacts, mother, 1)
    minus = f24._select_plan_geometry(artifacts, mother, -1)
    if any(
        not math.isclose(left, right, abs_tol=1e-9)
        for left, right in zip(_geometry_signature(plus), _geometry_signature(minus))
    ):
        raise ValueError("feature/delta selection depends on an axis orientation not yet qualified")
    return _DiscoverySelection(
        plus,
        (
            artifacts.reference["DISCOVERY_A"].artifact_hash,
            artifacts.perturbed["DISCOVERY_A"].artifact_hash,
        ),
    )


def discover_features_locally(
    context: _TopologyContext,
    mother: f2.MotherPlan,
) -> _DiscoveryContext | PhaseReceipt:
    """Build STFT/PSD only from ephemeral IQ already supplied by SND."""

    started = datetime.now(timezone.utc)
    identity = _endpoint_identity(context.endpoint)
    try:
        artifacts = f24._capture_dual(
            context.dual,
            sequence=False,
            center_a_hz=context.center_hz,
            delta_f_hz=0.0,
            segment_duration_s=DISCOVERY_DURATION_S,
            settling_s=0.0,
        )
        selection = _orientation_neutral_selection(artifacts, mother)
        completed = datetime.now(timezone.utc)
        receipt = PhaseReceipt(
            identity,
            F25Phase.LOCAL_IQ_FEATURE_DISCOVERY,
            F25PhaseState.SATISFIED,
            started,
            completed,
            "target and distinct witness selected from dual IQ by local in-RAM STFT/PSD",
            selection.artifact_hashes,
            (
                ("input_surface", "SND_IQ_ONLY"),
                ("waterfall_requested", "FALSE"),
                ("target_baseband_hz", f"{selection.geometry.target.baseband_hz:.9f}"),
                ("witness_baseband_hz", f"{selection.geometry.witness.baseband_hz:.9f}"),
                ("delta_hz", f"{selection.geometry.delta_hz:.9f}"),
                ("orientation_used_for_selection", "FALSE"),
                ("raw_RF_persistence", "ZERO"),
            ),
        )
        return _DiscoveryContext(artifacts, selection, receipt)
    except ValueError as error:
        completed = datetime.now(timezone.utc)
        error_hash = f2._hash(
            {"endpoint": identity, "phase": "local_iq_feature_discovery", "error_type": type(error).__name__, "error": str(error)}
        )
        return PhaseReceipt(
            identity,
            F25Phase.LOCAL_IQ_FEATURE_DISCOVERY,
            F25PhaseState.UNSATISFIED,
            started,
            completed,
            f"dual IQ exists but no frozen target/witness/delta envelope is available: {error}",
            (error_hash,),
            (("waterfall_requested", "FALSE"), ("feature_discovery", "UNSATISFIED")),
        )
    except Exception as error:
        completed = datetime.now(timezone.utc)
        error_hash = f2._hash(
            {"endpoint": identity, "phase": "local_iq_feature_discovery", "error_type": type(error).__name__, "error": str(error)}
        )
        return PhaseReceipt(
            identity,
            F25Phase.LOCAL_IQ_FEATURE_DISCOVERY,
            F25PhaseState.QUALIFICATION_ERROR,
            started,
            completed,
            f"local IQ transform failed: {type(error).__name__}: {error}",
            (error_hash,),
            (("waterfall_requested", "FALSE"), ("feature_discovery", "NOT_EVALUATED")),
        )


def _selected_witness_qualification(
    context: _TopologyContext,
    discovery: _DiscoveryContext,
    diagnostic: f24._DualArtifacts,
    mother: f2.MotherPlan,
) -> tuple[int, f2.FeatureMatch, f2.FeatureFingerprint]:
    geometry = discovery.selection.geometry
    provisional = f2._fingerprint_from_geometry(
        geometry.witness,
        geometry.target,
        context.center_hz,
        1,
    )
    profile_b = f2._capture_profile(diagnostic.perturbed["B"].capture, mother)
    orientation, witness_b = f2.learn_axis_orientation_from_witness(
        provisional,
        profile_b,
        geometry.delta_hz,
        geometry.tolerance_hz,
        mother,
    )
    witness = replace(
        provisional,
        absolute_rf_estimate_a_hz=context.center_hz + orientation * geometry.witness.baseband_hz,
    )
    reference_profiles = {
        name: f2._capture_profile(diagnostic.reference[name].capture, mother)
        for name in ("A1", "B", "A2")
    }
    perturbed_a1 = f2._capture_profile(diagnostic.perturbed["A1"].capture, mother)
    perturbed_a2 = f2._capture_profile(diagnostic.perturbed["A2"].capture, mother)
    fixed_reference = all(
        f2.match_feature(
            profile,
            witness,
            witness.baseband_position_a_hz,
            geometry.tolerance_hz,
            mother,
            witness=True,
        ).matched
        for profile in reference_profiles.values()
    )
    a1 = f2.match_feature(
        perturbed_a1,
        witness,
        witness.baseband_position_a_hz,
        geometry.tolerance_hz,
        mother,
        witness=True,
    ).matched
    a2 = f2.match_feature(
        perturbed_a2,
        witness,
        witness.baseband_position_a_hz,
        geometry.tolerance_hz,
        mother,
        witness=True,
    ).matched
    if not (witness_b.matched and fixed_reference and a1 and a2):
        raise ValueError("selected witness does not uniquely demonstrate perturbed translation, fixed reference and A2 return")
    return orientation, witness_b, witness


def qualify_retune(
    context: _TopologyContext,
    discovery: _DiscoveryContext,
    mother: f2.MotherPlan,
) -> _RetuneQualification | PhaseReceipt:
    started = datetime.now(timezone.utc)
    identity = _endpoint_identity(context.endpoint)
    geometry = discovery.selection.geometry
    try:
        diagnostic = f24._capture_dual(
            context.dual,
            sequence=True,
            center_a_hz=context.center_hz,
            delta_f_hz=geometry.delta_hz,
            segment_duration_s=mother.diagnostic_segment_s,
            settling_s=mother.settling_s,
        )
        orientation, witness_b, _witness = _selected_witness_qualification(
            context, discovery, diagnostic, mother
        )
        ref_event, ref_continuous, ref_clean = f24._integrity(
            diagnostic.reference_all_blocks,
            context.dual.reference.sample_rate_hz,
            mother,
        )
        pert_event, pert_continuous, pert_clean = f24._integrity(
            diagnostic.perturbed_all_blocks,
            context.dual.perturbed.sample_rate_hz,
            mother,
        )
        commands_valid = (
            not diagnostic.reference_commands and len(diagnostic.perturbed_commands) == 2
        )
        if not (
            ref_event
            and pert_event
            and ref_continuous
            and pert_continuous
            and ref_clean
            and pert_clean
            and commands_valid
        ):
            raise ValueError("retune diagnostic loses event time, continuity, ADC cleanliness or command isolation")
        hashes = (
            tuple(item.artifact_hash for item in context.topology_artifacts.receipts)
            + discovery.selection.artifact_hashes
            + tuple(item.artifact_hash for item in diagnostic.receipts)
        )
        states = {
            name: (f24.PropertyState.SATISFIED, "Gate F2.5 direct-SND phase receipt satisfied")
            for name in f24.QUALIFICATION_PROPERTIES
        }
        endpoint_qualification = f24._qualification_receipt(
            context.endpoint,
            0,
            states,
            artifact_hashes=hashes,
            status_hash=f2._hash(context.status),
            server=f24._server_instance_receipt(context.endpoint, context.status, context.dual),
            center_a_hz=context.center_hz,
            axis_orientation=orientation,
            reason="direct dual-SND topology, local IQ features and per-channel retune all qualified",
        )
        completed = datetime.now(timezone.utc)
        receipt = PhaseReceipt(
            identity,
            F25Phase.PER_CHANNEL_RETUNE_QUALIFICATION,
            F25PhaseState.SATISFIED,
            started,
            completed,
            "discovery witness translated only in perturbed branch and returned in A2; target was not evaluated",
            tuple(item.artifact_hash for item in diagnostic.receipts),
            (
                ("target_evaluated", "FALSE"),
                ("axis_orientation", str(orientation)),
                ("expected_translation_hz", f"{orientation * (-geometry.delta_hz):.9f}"),
                ("witness_match", str(witness_b.matched).upper()),
                ("reference_command_count", str(len(diagnostic.reference_commands))),
                ("perturbed_command_count", str(len(diagnostic.perturbed_commands))),
            ),
        )
        # Commands before freeze belong only to qualification. Confirmation
        # must start from a clean command ledger on the same allocated channels.
        context.dual.reference.command_ledger.clear()
        context.dual.perturbed.command_ledger.clear()
        del diagnostic
        return _RetuneQualification(orientation, witness_b, receipt, endpoint_qualification)
    except ValueError as error:
        completed = datetime.now(timezone.utc)
        error_hash = f2._hash(
            {"endpoint": identity, "phase": "retune_qualification", "error_type": type(error).__name__, "error": str(error)}
        )
        return PhaseReceipt(
            identity,
            F25Phase.PER_CHANNEL_RETUNE_QUALIFICATION,
            F25PhaseState.UNSATISFIED,
            started,
            completed,
            str(error),
            (error_hash,),
            (("target_evaluated", "FALSE"), ("retune_topology", "UNSATISFIED")),
        )
    except Exception as error:
        completed = datetime.now(timezone.utc)
        error_hash = f2._hash(
            {"endpoint": identity, "phase": "retune_qualification", "error_type": type(error).__name__, "error": str(error)}
        )
        return PhaseReceipt(
            identity,
            F25Phase.PER_CHANNEL_RETUNE_QUALIFICATION,
            F25PhaseState.QUALIFICATION_ERROR,
            started,
            completed,
            f"retune qualification error: {type(error).__name__}: {error}",
            (error_hash,),
            (("target_evaluated", "FALSE"), ("retune_topology", "NOT_EVALUATED")),
        )


def freeze_preselected_plan(
    context: _TopologyContext,
    discovery: _DiscoveryContext,
    retune: _RetuneQualification,
    mother: f2.MotherPlan,
    *,
    frozen_at: datetime,
) -> f24.F24Plan:
    """Freeze the exact local-IQ selection; no second search is permitted."""

    geometry = discovery.selection.geometry
    center = context.center_hz
    orientation = retune.axis_orientation
    target = f2._fingerprint_from_geometry(geometry.target, geometry.witness, center, orientation)
    witness = f2._fingerprint_from_geometry(geometry.witness, geometry.target, center, orientation)
    translation = orientation * (-geometry.delta_hz)
    upstream = target.baseband_position_a_hz + translation
    downstream = target.baseband_position_a_hz
    witness_b = witness.baseband_position_a_hz + translation
    tolerance = geometry.tolerance_hz
    frozen = f2._utc(frozen_at)
    return f24.F24Plan(
        context.endpoint,
        f24._server_instance_receipt(context.endpoint, context.status, context.dual),
        context.dual.reference.channel_id,
        context.dual.perturbed.channel_id,
        center,
        center + geometry.delta_hz,
        geometry.delta_hz,
        orientation,
        translation,
        target,
        witness,
        discovery.selection.artifact_hashes,
        mother.confirmation_segment_s,
        mother.settling_s,
        mother.confirmation_segment_s,
        mother.confirmation_segment_s,
        (
            ("TARGET_UPSTREAM_B", upstream - tolerance, upstream + tolerance),
            ("TARGET_DOWNSTREAM_B", downstream - tolerance, downstream + tolerance),
            ("WITNESS_UPSTREAM_B", witness_b - tolerance, witness_b + tolerance),
            (
                "TARGET_A_RETURN",
                target.baseband_position_a_hz - tolerance,
                target.baseband_position_a_hz + tolerance,
            ),
            (
                "WITNESS_A_RETURN",
                witness.baseband_position_a_hz - tolerance,
                witness.baseband_position_a_hz + tolerance,
            ),
        ),
        target.baseband_position_a_hz - translation,
        target.baseband_position_a_hz + translation / 2.0,
        target.baseband_position_a_hz + translation * 2.5,
        (
            ("minimum_contrast_db", mother.minimum_contrast_db),
            ("minimum_witness_contrast_db", mother.minimum_witness_contrast_db),
            ("minimum_fingerprint_correlation", mother.minimum_fingerprint_correlation),
            ("prediction_tolerance_hz", tolerance),
            ("spectral_resolution_hz", geometry.spectral_resolution_hz),
            ("maximum_arrival_latency_s", mother.maximum_arrival_latency_s),
        ),
        frozen,
        frozen + timedelta(seconds=mother.offer_ttl_s),
        mother.offer_ttl_s,
        (f2.TRANSFORM_VERSION, f24.F24_TRANSFORM_VERSION),
        "SHA-256 before analysis and destruction; zero RF persistence; receipts and hashes only",
    )


def downstream_not_evaluated(
    endpoint_identity: str,
    completed_phases: tuple[F25Phase, ...],
) -> tuple[PhaseReceipt, ...]:
    """Materialise every blocked downstream phase instead of silently omitting it."""

    now = datetime.now(timezone.utc)
    completed = set(completed_phases)
    return tuple(
        PhaseReceipt(
            endpoint_identity,
            phase,
            F25PhaseState.NOT_EVALUATED,
            now,
            now,
            "an upstream phase did not admit this phase",
            (),
            (("upstream_admission", "UNSATISFIED"),),
        )
        for phase in (
            F25Phase.LOCAL_IQ_FEATURE_DISCOVERY,
            F25Phase.PER_CHANNEL_RETUNE_QUALIFICATION,
            F25Phase.PLAN_FREEZE,
            F25Phase.ONE_CONFIRMATION,
        )
        if phase not in completed
    )


def _terminal_result(
    outcome: F25Outcome,
    phase_receipts: tuple[PhaseReceipt, ...],
    reason: str,
    *,
    instrument: str = "gate-f2.5-direct-dual-snd",
) -> F25Result:
    now = datetime.now(timezone.utc)
    starts = tuple(item.started_at for item in phase_receipts)
    ends = tuple(item.completed_at for item in phase_receipts)
    hashes = tuple(dict.fromkeys(item for receipt in phase_receipts for item in receipt.artifact_hashes))
    channel_roots = tuple(
        dict.fromkeys(
            f"kiwi:{receipt.endpoint_identity}:channel:{value}"
            for receipt in phase_receipts
            if receipt.phase is F25Phase.DIRECT_DUAL_SND_QUALIFICATION
            and receipt.state is F25PhaseState.SATISFIED
            for name, value in receipt.properties
            if name in ("reference_channel_id", "perturbed_channel_id")
        )
    )
    constraints = tuple(
        Constraint(
            f"{receipt.endpoint_identity}:{receipt.phase.value}",
            "phase_state",
            receipt.state,
            None,
            receipt.statement,
            "Gate F2.5 ordered causal admission",
        )
        for receipt in phase_receipts
    ) + (
        Constraint(
            "terminal_outcome",
            "first_outcome",
            outcome,
            None,
            reason,
            "Gate F2.5 outcome semantics",
        ),
    )
    evidence = ConstraintReceipt(
        instrument,
        min(starts, default=now),
        max(ends, default=now),
        constraints,
        (
            Transform("status.ext_api", "descriptive_hint", "never used as an admission gate"),
            Transform("SND_IQ", "ephemeral_hashed", "artifact bytes hashed before analysis and destroyed"),
            Transform("local_STFT_PSD", "derived_or_not_evaluated", "computed only in RAM; no W/F requested"),
        ),
        channel_roots,
        (f"kiwi-server:{f2.KIWI_SERVER_COMMIT}", f"kiwiclient:{f2.KIWI_CLIENT_COMMIT}"),
        hashes,
        (
            "no DDC-boundary hypothesis was evaluated before plan freeze",
            "ext_api and W/F do not establish or reject multichannel availability",
        ),
    )
    strict_json_value(evidence)
    if outcome is F25Outcome.NO_MULTI_CHANNEL_CAPABILITY:
        authorised = (
            "every eligible terminal candidate received a direct two-SND attempt and none admitted a simultaneous pair",
        )
    elif outcome is F25Outcome.NO_ADMISSIBLE_CAUSAL_TOPOLOGY:
        authorised = ("two streams opened, but the required simultaneous fixed/perturbed topology was not demonstrated",)
    elif outcome is F25Outcome.NO_FALSIFIABLE_INTERVENTION:
        authorised = ("an admitted dual-SND topology did not yield the frozen target/witness/retune envelope",)
    else:
        authorised = ("qualification ended descriptively before physical capability availability was determined",)
    return F25Result(
        outcome,
        phase_receipts,
        None,
        None,
        evidence,
        authorised,
        (
            "ext_api proves simultaneous SND availability",
            "waterfall availability is required for multichannel qualification",
            "either DDC-boundary hypothesis is supported",
            "external RF proven",
        ),
    )


def _f25_from_physical(
    physical: f24.F24Result,
    phase_receipts: tuple[PhaseReceipt, ...],
) -> F25Result:
    outcome = F25Outcome(physical.outcome.value)
    return F25Result(
        outcome,
        phase_receipts,
        physical.plan_hash,
        physical,
        physical.evidence_receipt,
        physical.authorised_claims,
        physical.unauthorised_claims,
    )


def _retryable_phase(receipt: PhaseReceipt) -> bool:
    if receipt.state is not F25PhaseState.QUALIFICATION_ERROR:
        return False
    normalized = receipt.statement.lower()
    return any(
        token in normalized
        for token in (
            "timeout",
            "timed out",
            "connection",
            "closed",
            "reset",
            "transport",
            "decode",
            "description",
            "serialization",
            "transform",
            "oserror",
            "urlerror",
        )
    )


def run_once(
    *,
    mother: f2.MotherPlan | None = None,
    runtime_commit: str | None = None,
    sink: Callable[[str], None] = print,
    bootstrap_receipt: F25BootstrapReceipt | None = None,
    direct_qualifier: Callable[[kiwi.KiwiEndpoint, f2.MotherPlan], _TopologyContext | PhaseReceipt] | None = None,
    event_prefix: str = "gate_f2_5",
    terminal_instrument: str = "gate-f2.5-direct-dual-snd",
    retry_selector: Callable[[PhaseReceipt], bool] | None = None,
    event_emitter: Callable[[str, object], None] | None = None,
) -> F25Result:
    """Future one-shot materialisation with Gate-specific evolution hooks."""

    mother = mother or f2.MotherPlan()
    commit = runtime_commit or f22.runtime_commit()
    bootstrap = bootstrap_receipt or build_bootstrap_receipt(
        runtime_commit=commit,
        created_at=datetime.now(timezone.utc),
    )
    qualifier = direct_qualifier or direct_dual_snd_qualification
    retryable = retry_selector or _retryable_phase
    event = lambda suffix: f"{event_prefix}_{suffix}"
    emit_event = event_emitter or (lambda event_type, payload: emit_jsonl(event_type, payload, sink=sink))
    if event_emitter is None:
        strict_json_value(bootstrap)
    emit_event(
        event("bootstrap_frozen"),
        {
            "receipt": bootstrap,
            "receipt_hash": bootstrap.receipt_hash,
            "root_topology_requirement": f23.gate_f2_root_topology_requirement(),
            f"network_activity_in_{event_prefix}": "NONE_UNTIL_SEPARATELY_AUTHORISED",
        },
    )
    deadline = time.monotonic() + f24.QUALIFICATION_BUDGET_S
    receipts: list[PhaseReceipt] = []
    retries_remaining = bootstrap.retry_budget
    retried: set[str] = set()
    saw_topology = False
    saw_discovery = False
    saw_retune = False

    for endpoint in f24.ordered_candidates():
        if time.monotonic() >= deadline:
            break
        identity = _endpoint_identity(endpoint)
        while True:
            topology_or_receipt = qualifier(endpoint, mother)
            direct_receipt = (
                topology_or_receipt.phase_receipt
                if isinstance(topology_or_receipt, _TopologyContext)
                else topology_or_receipt
            )
            receipts.append(direct_receipt)
            for atomic_branch_receipt in direct_receipt.atomic_branch_receipts:
                emit_event(event("atomic_snd_branch_receipt"), atomic_branch_receipt)
            emit_event(event("direct_dual_snd_qualification"), direct_receipt)
            if (
                not isinstance(topology_or_receipt, _TopologyContext)
                and retryable(direct_receipt)
                and retries_remaining > 0
                and identity not in retried
            ):
                retries_remaining -= 1
                retried.add(identity)
                emit_event(
                    event("prefreeze_retry"),
                    {
                        "endpoint": identity,
                        "global_retries_remaining": retries_remaining,
                        "qualification_error_types": direct_receipt.qualification_error_types,
                    },
                )
                continue
            break

        if not isinstance(topology_or_receipt, _TopologyContext):
            blocked = downstream_not_evaluated(identity, (F25Phase.DIRECT_DUAL_SND_QUALIFICATION,))
            receipts.extend(blocked)
            for item in blocked:
                emit_event(event("phase_not_evaluated"), item)
            continue

        context = topology_or_receipt
        saw_topology = True
        completed: list[F25Phase] = [F25Phase.DIRECT_DUAL_SND_QUALIFICATION]
        try:
            discovery_or_receipt = discover_features_locally(context, mother)
            discovery_receipt = (
                discovery_or_receipt.phase_receipt
                if isinstance(discovery_or_receipt, _DiscoveryContext)
                else discovery_or_receipt
            )
            receipts.append(discovery_receipt)
            completed.append(F25Phase.LOCAL_IQ_FEATURE_DISCOVERY)
            emit_event(event("local_iq_feature_discovery"), discovery_receipt)
            if not isinstance(discovery_or_receipt, _DiscoveryContext):
                blocked = downstream_not_evaluated(identity, tuple(completed))
                receipts.extend(blocked)
                for item in blocked:
                    emit_event(event("phase_not_evaluated"), item)
                continue
            discovery = discovery_or_receipt
            saw_discovery = True

            retune_or_receipt = qualify_retune(context, discovery, mother)
            retune_receipt = (
                retune_or_receipt.phase_receipt
                if isinstance(retune_or_receipt, _RetuneQualification)
                else retune_or_receipt
            )
            receipts.append(retune_receipt)
            completed.append(F25Phase.PER_CHANNEL_RETUNE_QUALIFICATION)
            emit_event(event("per_channel_retune_qualification"), retune_receipt)
            if not isinstance(retune_or_receipt, _RetuneQualification):
                blocked = downstream_not_evaluated(identity, tuple(completed))
                receipts.extend(blocked)
                for item in blocked:
                    emit_event(event("phase_not_evaluated"), item)
                continue
            retune = retune_or_receipt
            saw_retune = True
            frozen_at = datetime.now(timezone.utc)
            try:
                plan = freeze_preselected_plan(context, discovery, retune, mother, frozen_at=frozen_at)
            except Exception as error:
                freeze_receipt = PhaseReceipt(
                    identity,
                    F25Phase.PLAN_FREEZE,
                    (
                        F25PhaseState.UNSATISFIED
                        if isinstance(error, ValueError)
                        else F25PhaseState.QUALIFICATION_ERROR
                    ),
                    frozen_at,
                    datetime.now(timezone.utc),
                    f"exact preselected plan could not be frozen: {type(error).__name__}: {error}",
                    discovery.selection.artifact_hashes,
                    (("feature_reselection", "FORBIDDEN"),),
                )
                receipts.append(freeze_receipt)
                completed.append(F25Phase.PLAN_FREEZE)
                emit_event(event("plan_freeze_failed"), freeze_receipt)
                blocked = downstream_not_evaluated(identity, tuple(completed))
                receipts.extend(blocked)
                for item in blocked:
                    emit_event(event("phase_not_evaluated"), item)
                continue
            plan_receipt = PhaseReceipt(
                identity,
                F25Phase.PLAN_FREEZE,
                F25PhaseState.SATISFIED,
                frozen_at,
                frozen_at,
                "exact local-IQ target, witness, delta, transforms and controls frozen",
                plan.discovery_artifact_hashes,
                (("plan_hash", plan.plan_hash), ("zero_postfreeze_retry", "TRUE")),
            )
            receipts.append(plan_receipt)
            completed.append(F25Phase.PLAN_FREEZE)
            emit_event(
                event("plan_frozen"),
                {"plan": plan, "plan_hash": plan.plan_hash, "zero_postfreeze_retry": True},
            )
            confirmation_started = datetime.now(timezone.utc)
            try:
                confirmation = f24._capture_dual(
                    context.dual,
                    sequence=True,
                    center_a_hz=plan.center_a_hz,
                    delta_f_hz=plan.delta_f_hz,
                    segment_duration_s=plan.a1_duration_s,
                    settling_s=plan.settling_duration_s,
                    event_not_before=plan.frozen_at,
                )
                physical = f24.evaluate_confirmation(
                    plan,
                    confirmation,
                    (retune.endpoint_qualification,),
                    mother,
                )
                confirmation_hashes = tuple(item.artifact_hash for item in confirmation.receipts)
                del confirmation
                confirmation_state = F25PhaseState.SATISFIED
                statement = "one independent A1/B/A2 confirmation produced the first outcome"
            except Exception as error:
                physical = f24._postfreeze_failure(
                    plan,
                    (retune.endpoint_qualification,),
                    f"single confirmation failed with no retry: {type(error).__name__}: {error}",
                )
                confirmation_hashes = ()
                confirmation_state = F25PhaseState.UNSATISFIED
                statement = "one independent confirmation failed; no retry, endpoint, frequency or threshold change"
            confirmation_receipt = PhaseReceipt(
                identity,
                F25Phase.ONE_CONFIRMATION,
                confirmation_state,
                confirmation_started,
                datetime.now(timezone.utc),
                statement,
                confirmation_hashes,
                (("postfreeze_retry_count", "0"),),
            )
            receipts.append(confirmation_receipt)
            result = _f25_from_physical(physical, tuple(receipts))
            if event_emitter is None:
                strict_json_value(result)
            emit_event(event("first_outcome"), result)
            return result
        finally:
            context.close()

    frozen_receipts = tuple(receipts)
    if not saw_topology:
        outcome = no_topology_outcome(frozen_receipts)
        reason = "direct dual-SND qualification ended without an admitted simultaneous topology"
    elif not saw_discovery:
        has_error = any(
            item.phase is F25Phase.LOCAL_IQ_FEATURE_DISCOVERY
            and item.state is F25PhaseState.QUALIFICATION_ERROR
            for item in frozen_receipts
        )
        outcome = F25Outcome.QUALIFICATION_INCOMPLETE if has_error else F25Outcome.NO_FALSIFIABLE_INTERVENTION
        reason = "dual IQ was admitted but local in-RAM feature/witness discovery did not produce an envelope"
    elif not saw_retune:
        has_error = any(
            item.phase is F25Phase.PER_CHANNEL_RETUNE_QUALIFICATION
            and item.state is F25PhaseState.QUALIFICATION_ERROR
            for item in frozen_receipts
        )
        outcome = F25Outcome.QUALIFICATION_INCOMPLETE if has_error else F25Outcome.NO_ADMISSIBLE_CAUSAL_TOPOLOGY
        reason = "local features existed but the selected witness did not establish the per-channel retune topology"
    else:
        has_error = any(
            item.phase is F25Phase.PLAN_FREEZE
            and item.state is F25PhaseState.QUALIFICATION_ERROR
            for item in frozen_receipts
        )
        outcome = F25Outcome.QUALIFICATION_INCOMPLETE if has_error else F25Outcome.NO_FALSIFIABLE_INTERVENTION
        reason = "retune qualification existed but the exact preselected plan could not be frozen"
    result = _terminal_result(
        outcome,
        frozen_receipts,
        reason,
        instrument=terminal_instrument,
    )
    emit_event(event("first_outcome"), result)
    return result


def main() -> None:
    run_once()


if __name__ == "__main__":
    main()
