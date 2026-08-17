"""Gate F2.5.9: pre-live materialisation of the ordered one-shot runner.

This disposable successor connects the ordered F2.5.8 branch opener to the
existing one-outcome F2.5 control flow.  Importing and assessing the module do
no I/O.  ``run_once`` also refuses before I/O unless a later caller supplies a
separate live authorisation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import re
from typing import Callable

from . import kiwi_gate_f2 as f2
from . import kiwi_gate_f2_2 as f22
from . import kiwi_gate_f2_4 as f24
from . import kiwi_gate_f2_5 as f25
from . import kiwi_gate_f2_5_1 as f251
from . import kiwi_gate_f2_5_3 as f253
from . import kiwi_gate_f2_5_3_1 as f2531
from . import kiwi_gate_f2_5_8 as f258
from . import kiwi_probe as kiwi


F259_TRANSFORM_VERSION = "gate-f2.5.9-ordered-one-shot-runner-v1"
PARENT_GATE_COMMIT = "a427a44914205d18c80eba566e75c8a41e67c44b"
EVENT_PREFIX = "gate_f2_5_9"
TERMINAL_INSTRUMENT = "gate-f2.5.9-ordered-dual-snd"


class F259Exit(str, Enum):
    ORDERED_ONE_SHOT_RUNNER_MATERIALIZED = "ORDERED_ONE_SHOT_RUNNER_MATERIALIZED"
    ORDERED_RECEIPT_PREREQUISITE_FAILED = "ORDERED_RECEIPT_PREREQUISITE_FAILED"


@dataclass(frozen=True, slots=True)
class F259BootstrapReceipt:
    inherited_f2531: f2531.F2531BootstrapReceipt
    runtime_commit: str
    parent_gate_commit: str
    active_branch_receipt_transform: str
    active_runner_transform: str
    ordered_branch_opener_required: bool
    legacy_branch_opener_enabled: bool
    retry_basis: str
    terminal_manifest_required: bool
    raw_rf_persistence: str
    transform_versions: tuple[str, ...]

    def __post_init__(self) -> None:
        if re.fullmatch(r"[0-9a-f]{40}", self.runtime_commit) is None:
            raise ValueError("runtime commit must be a full Git SHA-1")
        if self.inherited_f2531.runtime_commit != self.runtime_commit:
            raise ValueError("inherited terminal receipt must bind the same runtime")
        if self.parent_gate_commit != PARENT_GATE_COMMIT:
            raise ValueError("Gate F2.5.8 lineage changed")
        if self.active_branch_receipt_transform != f258.F258_TRANSFORM_VERSION:
            raise ValueError("the ordered branch receipt transform changed")
        if self.active_runner_transform != F259_TRANSFORM_VERSION:
            raise ValueError("the ordered one-shot runner transform changed")
        if not self.ordered_branch_opener_required or self.legacy_branch_opener_enabled:
            raise ValueError("the legacy branch opener cannot re-enter the runner")
        if self.retry_basis != "ORDERED_BRANCH_STATE_AND_TYPED_ERROR_ONLY":
            raise ValueError("ordered retries cannot depend on aggregate prose")
        if not self.terminal_manifest_required:
            raise ValueError("terminal receipt closure cannot be weakened")
        if self.raw_rf_persistence != "ZERO":
            raise ValueError("raw RF persistence is forbidden")
        if self.transform_versions[-2:] != (
            f258.F258_TRANSFORM_VERSION,
            F259_TRANSFORM_VERSION,
        ):
            raise ValueError("Gate F2.5.9 active transform ledger changed")

    @property
    def retry_budget(self) -> int:
        return self.inherited_f2531.retry_budget

    @property
    def receipt_hash(self) -> str:
        return f2._hash(asdict(self))


@dataclass(frozen=True, slots=True)
class F259Assessment:
    exit: F259Exit
    ordered_receipt_prerequisite_satisfied: bool
    ordered_opener_is_active: bool
    legacy_opener_is_unreachable: bool
    typed_retry_is_ordered_receipt_aware: bool
    terminal_receipt_closure_preserved: bool
    one_outcome_stop_preserved: bool
    live_execution_authorised: bool
    authorised_claims: tuple[str, ...]
    unauthorised_claims: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class F259Result:
    physical_result: f25.F25Result
    receipt_artifact: f2531.ClosedArtifactReceipt


def build_bootstrap_receipt(
    *, runtime_commit: str, created_at: datetime
) -> F259BootstrapReceipt:
    inherited = f2531.build_bootstrap_receipt(
        runtime_commit=runtime_commit,
        created_at=created_at,
    )
    return F259BootstrapReceipt(
        inherited,
        runtime_commit,
        PARENT_GATE_COMMIT,
        f258.F258_TRANSFORM_VERSION,
        F259_TRANSFORM_VERSION,
        True,
        False,
        "ORDERED_BRANCH_STATE_AND_TYPED_ERROR_ONLY",
        True,
        "ZERO",
        inherited.transform_versions
        + (f258.F258_TRANSFORM_VERSION, F259_TRANSFORM_VERSION),
    )


def _receipt_artifact_hashes(receipt: f258.F258BranchReceipt) -> tuple[str, ...]:
    return tuple(
        value
        for value in (
            receipt.incoming_stream_artifact_hash,
            receipt.readiness_frame_artifact_hash,
            receipt.error_description_hash,
            receipt.receipt_hash,
        )
        if value is not None
    )


def _decorate_ordered_result(
    result: f25._TopologyContext | f25.PhaseReceipt,
    branch_receipts: tuple[f258.F258BranchReceipt, ...],
) -> f25._TopologyContext | f25.PhaseReceipt:
    """Bind atomic ordered transcripts to the existing physical phase receipt."""

    if not branch_receipts:
        return result
    if (
        len(branch_receipts) != len(f258.BRANCH_ROLES)
        or {item.role for item in branch_receipts} != set(f258.BRANCH_ROLES)
    ):
        raise ValueError("ordered qualification requires both frozen branch roles")
    receipt = result.phase_receipt if isinstance(result, f25._TopologyContext) else result
    by_role = {item.role: item for item in branch_receipts}
    reference = by_role["reference"]
    perturbed = by_role["perturbed"]
    hashes = list(receipt.artifact_hashes)
    for item in branch_receipts:
        hashes.extend(_receipt_artifact_hashes(item))

    state = receipt.state
    statement = receipt.statement
    if not isinstance(result, f25._TopologyContext):
        states = {item.state for item in branch_receipts}
        dispositions = {item.pair_disposition for item in branch_receipts}
        if f258.F258BranchState.QUALIFICATION_ERROR in states:
            state = f25.F25PhaseState.QUALIFICATION_ERROR
            statement = "ordered branch receipts leave simultaneous availability indeterminate"
        elif f258.F258BranchState.CAPABILITY_REJECTED in states:
            state = f25.F25PhaseState.UNSATISFIED
            statement = "an explicit server response rejected the simultaneous pair"
        elif any(
            item.value == "CLOSED_AFTER_TOPOLOGY_REJECTION"
            for item in dispositions
        ):
            state = f25.F25PhaseState.UNSATISFIED
            statement = "two ready ordered branches did not establish distinct channel allocations"

    properties = receipt.properties + tuple(
        value
        for item in branch_receipts
        for value in (
            (f"{item.role}_branch_state", item.state.value),
            (f"{item.role}_pair_disposition", item.pair_disposition.value),
            (f"{item.role}_wire_frame_count", str(item.incoming_frame_count)),
            (
                f"{item.role}_ordered_iq_readiness",
                str(item.readiness_frame_artifact_hash is not None).upper(),
            ),
        )
    )
    decorated = replace(
        receipt,
        state=state,
        statement=statement,
        artifact_hashes=tuple(dict.fromkeys(hashes)),
        properties=properties,
        direct_reference_attempted=True,
        direct_perturbed_attempted=True,
        direct_reference_opened=reference.state is f258.F258BranchState.READY,
        direct_perturbed_opened=perturbed.state is f258.F258BranchState.READY,
        atomic_branch_receipts=branch_receipts,
        qualification_error_types=tuple(
            dict.fromkeys(
                receipt.qualification_error_types
                + tuple(
                    item.error_type
                    for item in branch_receipts
                    if item.state is f258.F258BranchState.QUALIFICATION_ERROR
                    and item.error_type is not None
                )
            )
        ),
    )
    if isinstance(result, f25._TopologyContext):
        result.phase_receipt = decorated
        return result
    return decorated


def direct_ordered_snd_qualification(
    endpoint: kiwi.KiwiEndpoint,
    mother: f2.MotherPlan,
) -> f25._TopologyContext | f25.PhaseReceipt:
    """Qualify only through the ordered server-wire opener from Gate F2.5.8."""

    captured: tuple[f258.F258BranchReceipt, ...] = ()

    def opener(
        candidate: kiwi.KiwiEndpoint,
        center: float,
        status: dict[str, str],
        frozen_mother: f2.MotherPlan,
    ) -> f24._DualConnections:
        nonlocal captured
        try:
            dual, receipts = f258._open_dual_ordered(
                candidate,
                center,
                status,
                frozen_mother,
            )
            captured = receipts
            return dual
        except f258.OrderedDualOpenError as error:
            captured = error.receipts
            raise

    result = f25.direct_dual_snd_qualification(
        endpoint,
        mother,
        center_resolver=f251.bootstrap_center,
        dual_opener=opener,
    )
    return _decorate_ordered_result(result, captured)


def ordered_retryable_phase(receipt: f25.PhaseReceipt) -> bool:
    """Retry only typed software/transport failures in ordered branch receipts."""

    if receipt.state is not f25.F25PhaseState.QUALIFICATION_ERROR:
        return False
    ordered = tuple(
        item
        for item in receipt.atomic_branch_receipts
        if isinstance(item, f258.F258BranchReceipt)
        and item.state is f258.F258BranchState.QUALIFICATION_ERROR
        and item.error_type is not None
    )
    error_types = (
        tuple(item.error_type for item in ordered)
        if ordered
        else receipt.qualification_error_types
    )
    return any(
        error_type in f253.STRUCTURED_RETRYABLE_ERROR_TYPES
        for error_type in error_types
    )


def default_receipt_path(created_at: datetime) -> Path:
    stamp = f2._utc(created_at).strftime("%Y%m%dT%H%M%S.%fZ")
    return (
        Path("experiments")
        / "live_instrument"
        / "session_receipts"
        / f"gate-f2-5-9-{stamp}.jsonl"
    )


def run_once(
    *,
    live_authorised: bool = False,
    mother: f2.MotherPlan | None = None,
    runtime_commit: str | None = None,
    receipt_path: Path | None = None,
    mirror_sink: Callable[[str], None] | None = print,
) -> F259Result:
    """Run one future session, but only after a separate explicit authority."""

    if not live_authorised:
        raise PermissionError("Gate F2.5.9 live execution requires separate authorisation")
    commit = runtime_commit or f22.runtime_commit()
    created_at = datetime.now(timezone.utc)
    bootstrap = build_bootstrap_receipt(runtime_commit=commit, created_at=created_at)
    emitter = f2531.TerminalReceiptEmitter(
        receipt_path or default_receipt_path(created_at),
        mirror_sink=mirror_sink,
    )
    try:
        physical = f25.run_once(
            mother=mother,
            runtime_commit=commit,
            bootstrap_receipt=bootstrap,  # type: ignore[arg-type]
            direct_qualifier=direct_ordered_snd_qualification,
            event_prefix=EVENT_PREFIX,
            terminal_instrument=TERMINAL_INSTRUMENT,
            retry_selector=ordered_retryable_phase,
            event_emitter=emitter,
        )
    except BaseException as error:
        emitter.record_runtime_error(error)
        emitter.finalize()
        raise
    return F259Result(physical, emitter.finalize())


def assess_gate_f2_5_9(
    prerequisite: f258.F258Assessment | None = None,
) -> F259Assessment:
    prior = prerequisite or f258.assess_gate_f2_5_8()
    ready = (
        prior.exit is f258.F258Exit.ORDERED_WIRE_RECEIPT_IMPLEMENTED
        and prior.receipt_implementation_complete
    )
    return F259Assessment(
        F259Exit.ORDERED_ONE_SHOT_RUNNER_MATERIALIZED
        if ready
        else F259Exit.ORDERED_RECEIPT_PREREQUISITE_FAILED,
        ready,
        ready,
        ready,
        ready,
        ready,
        ready,
        False,
        (
            "the one-shot control path injects the ordered F2.5.8 opener",
            "typed retries inspect ordered atomic branch receipts",
            "terminal receipt closure and the first-outcome stop are preserved",
            "an unauthorised call refuses before opening a receipt or network surface",
        )
        if ready
        else ("the ordered receipt prerequisite failed closed",),
        (
            "a live endpoint has been contacted",
            "a dual-channel capability is currently available",
            "a DDC hypothesis has been evaluated",
            "live execution is authorised by this gate",
        ),
    )
