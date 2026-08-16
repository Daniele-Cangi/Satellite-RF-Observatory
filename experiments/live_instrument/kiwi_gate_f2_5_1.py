"""Gate F2.5.1: remove status bandwidth from the pre-SND causal path.

This module is prepared and tested offline. It does not run on import. The
bootstrap interval is a frozen, conservative Kiwi protocol-family invariant;
the selected center is a qualification coordinate, not a target identity or
an experimental RF claim.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from hashlib import sha256
import re
from typing import Callable

from . import kiwi_gate_f2 as f2
from . import kiwi_gate_f2_2 as f22
from . import kiwi_gate_f2_4 as f24
from . import kiwi_gate_f2_5 as f25
from . import kiwi_probe as kiwi
from .models import strict_json_value


F251_TRANSFORM_VERSION = "gate-f2.5.1-protocol-invariant-bootstrap-v1"
CENTER_POLICY = "kiwi-0-30mhz-interior-endpoint-hash-v2"
PARENT_RUNTIME_COMMIT = "14000c285aa7a427c52befbadbd8631e8adc484a"
PARENT_OUTCOME_COMMIT = "dd713e993df40e35c23fadbf824e2df193b0aef7"


@dataclass(frozen=True, slots=True)
class BootstrapTuningInvariant:
    family_low_hz: float = 0.0
    family_high_hz: float = 30_000_000.0
    selection_fraction_low: float = 0.25
    selection_fraction_high: float = 0.75
    role: str = "QUALIFICATION_BOOTSTRAP_ONLY"
    status_bandwidth_required: bool = False
    waterfall_required: bool = False
    evidence: tuple[str, ...] = (
        "CHECKPOINT_1.md:166-169 records a live public Kiwi 0-30 MHz status and successful 10 MHz IQ",
        "kiwi_gate_f2.py:1228-1250 records the frozen 30 MHz client-family default and later W/F override",
        "GATE_F2_5_OUTCOME_1.md:67-74 attributes status.bandwidth to the wrong descriptive surface",
    )
    caveats: tuple[str, ...] = (
        "the invariant is scoped to the frozen Kiwi candidate family, not arbitrary Internet radios",
        "a requested center is not evidence that tuned samples were delivered",
        "stream samples and witness behavior must establish the usable coordinate",
        "the endpoint-derived center selects no target, transmitter or phenomenon",
    )

    def __post_init__(self) -> None:
        if (self.family_low_hz, self.family_high_hz) != (0.0, 30_000_000.0):
            raise ValueError("Gate F2.5.1 protocol-family interval changed")
        if (self.selection_fraction_low, self.selection_fraction_high) != (0.25, 0.75):
            raise ValueError("Gate F2.5.1 interior selection changed")
        if self.status_bandwidth_required or self.waterfall_required:
            raise ValueError("descriptive status bandwidth and W/F cannot re-enter the pre-SND path")
        if self.role != "QUALIFICATION_BOOTSTRAP_ONLY":
            raise ValueError("bootstrap tuning cannot become the physical target")

    @property
    def selected_low_hz(self) -> float:
        return self.family_low_hz + self.selection_fraction_low * (
            self.family_high_hz - self.family_low_hz
        )

    @property
    def selected_high_hz(self) -> float:
        return self.family_low_hz + self.selection_fraction_high * (
            self.family_high_hz - self.family_low_hz
        )

    @property
    def receipt_hash(self) -> str:
        return f2._hash(asdict(self))


def bootstrap_center(
    endpoint: kiwi.KiwiEndpoint,
    _status: dict[str, str],
    *,
    invariant: BootstrapTuningInvariant | None = None,
) -> float:
    """Return a data-independent interior center without reading status fields."""

    frozen = invariant or BootstrapTuningInvariant()
    identity = f"{endpoint.host.lower()}:{endpoint.port}".encode("utf-8")
    unit = int.from_bytes(sha256(identity).digest()[:8], "big") / float(2**64 - 1)
    return float(
        frozen.selected_low_hz
        + unit * (frozen.selected_high_hz - frozen.selected_low_hz)
    )


@dataclass(frozen=True, slots=True)
class F251BootstrapReceipt:
    created_at: datetime
    candidate_set_hash: str
    candidate_order: tuple[str, ...]
    runtime_commit: str
    parent_runtime_commit: str
    parent_outcome_commit: str
    phase_order: tuple[str, ...]
    center_policy: str
    tuning_invariant: BootstrapTuningInvariant
    ext_api_semantics: str
    waterfall_semantics: str
    retry_budget: int
    maximum_retry_per_endpoint: int
    transform_versions: tuple[str, ...]

    def __post_init__(self) -> None:
        f2._utc(self.created_at)
        if self.candidate_set_hash != f24.candidate_set_hash():
            raise ValueError("Gate F2.5.1 candidate set changed")
        if self.candidate_order != f24.ordered_candidate_identities():
            raise ValueError("Gate F2.5.1 candidate order changed")
        if re.fullmatch(r"[0-9a-f]{40}", self.runtime_commit) is None:
            raise ValueError("runtime commit must be a full Git SHA-1")
        if self.parent_runtime_commit != PARENT_RUNTIME_COMMIT:
            raise ValueError("Gate F2.5 frozen runtime lineage changed")
        if self.parent_outcome_commit != PARENT_OUTCOME_COMMIT:
            raise ValueError("Gate F2.5 outcome lineage changed")
        if self.phase_order != f25.PHASE_ORDER or self.center_policy != CENTER_POLICY:
            raise ValueError("Gate F2.5.1 phase or center policy changed")
        if self.ext_api_semantics != "DESCRIPTIVE_HINT_ONLY":
            raise ValueError("ext_api cannot become a qualification gate")
        if self.waterfall_semantics != "ABSENT_FROM_CAUSAL_PATH":
            raise ValueError("W/F cannot return to the Gate F2.5.1 causal path")
        if self.retry_budget != f24.RETRY_BUDGET:
            raise ValueError("Gate F2.5.1 retry budget changed")
        if self.maximum_retry_per_endpoint != f24.MAX_RETRY_PER_ENDPOINT:
            raise ValueError("Gate F2.5.1 endpoint retry limit changed")
        if self.transform_versions != (
            f2.TRANSFORM_VERSION,
            f24.F24_TRANSFORM_VERSION,
            f25.F25_TRANSFORM_VERSION,
            F251_TRANSFORM_VERSION,
        ):
            raise ValueError("Gate F2.5.1 transform ledger changed")

    @property
    def receipt_hash(self) -> str:
        return f2._hash(asdict(self))


def build_bootstrap_receipt(
    *,
    runtime_commit: str,
    created_at: datetime,
) -> F251BootstrapReceipt:
    return F251BootstrapReceipt(
        f2._utc(created_at),
        f24.candidate_set_hash(),
        f24.ordered_candidate_identities(),
        runtime_commit,
        PARENT_RUNTIME_COMMIT,
        PARENT_OUTCOME_COMMIT,
        f25.PHASE_ORDER,
        CENTER_POLICY,
        BootstrapTuningInvariant(),
        "DESCRIPTIVE_HINT_ONLY",
        "ABSENT_FROM_CAUSAL_PATH",
        f24.RETRY_BUDGET,
        f24.MAX_RETRY_PER_ENDPOINT,
        (
            f2.TRANSFORM_VERSION,
            f24.F24_TRANSFORM_VERSION,
            f25.F25_TRANSFORM_VERSION,
            F251_TRANSFORM_VERSION,
        ),
    )


def direct_dual_snd_qualification(
    endpoint: kiwi.KiwiEndpoint,
    mother: f2.MotherPlan,
) -> f25._TopologyContext | f25.PhaseReceipt:
    """Run the F2.5 physical probe with only the corrected bootstrap policy."""

    invariant = BootstrapTuningInvariant()
    result = f25.direct_dual_snd_qualification(
        endpoint,
        mother,
        center_resolver=lambda candidate, status: bootstrap_center(
            candidate,
            status,
            invariant=invariant,
        ),
    )
    receipt = result.phase_receipt if isinstance(result, f25._TopologyContext) else result
    # Access rejection and status transport errors precede center materialization.
    if not isinstance(result, f25._TopologyContext) and not (
        receipt.direct_reference_attempted or receipt.direct_perturbed_attempted
    ):
        return result
    center = bootstrap_center(endpoint, {}, invariant=invariant)
    decorated = replace(
        receipt,
        properties=receipt.properties
        + (
            ("bootstrap_center_policy", CENTER_POLICY),
            ("bootstrap_center_hz", f"{center:.9f}"),
            ("bootstrap_invariant_hash", invariant.receipt_hash),
            ("status_bandwidth_used_as_gate", "FALSE"),
            ("bootstrap_role", invariant.role),
        ),
    )
    if isinstance(result, f25._TopologyContext):
        result.phase_receipt = decorated
        return result
    return decorated


def run_once(
    *,
    mother: f2.MotherPlan | None = None,
    runtime_commit: str | None = None,
    sink: Callable[[str], None] = print,
) -> f25.F25Result:
    """Materialize one future Gate F2.5.1 session; never called by offline Gate."""

    commit = runtime_commit or f22.runtime_commit()
    bootstrap = build_bootstrap_receipt(
        runtime_commit=commit,
        created_at=datetime.now(timezone.utc),
    )
    strict_json_value(bootstrap)
    return f25.run_once(
        mother=mother,
        runtime_commit=commit,
        sink=sink,
        bootstrap_receipt=bootstrap,  # type: ignore[arg-type]
        direct_qualifier=direct_dual_snd_qualification,
        event_prefix="gate_f2_5_1",
        terminal_instrument="gate-f2.5.1-direct-dual-snd",
    )


def main() -> None:
    run_once()


if __name__ == "__main__":
    main()
