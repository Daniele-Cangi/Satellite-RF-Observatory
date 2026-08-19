"""Gate F2.5.2: atomic dual-SND branch admission, prepared offline.

The module changes only the opening receipt boundary exposed by the frozen
F2.5.1 outcome.  Each branch hashes every ephemeral SND frame before decode,
preserves the readiness witness hash, and reports its own result before a
dual-channel topology can be composed.  Importing this module performs no
network activity.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import math
import re
import time
from typing import Callable

from . import kiwi_gate_f2 as f2
from . import kiwi_gate_f2_2 as f22
from . import kiwi_gate_f2_4 as f24
from . import kiwi_gate_f2_5 as f25
from . import kiwi_gate_f2_5_1 as f251
from . import kiwi_probe as kiwi
from .models import strict_json_value


F252_TRANSFORM_VERSION = "gate-f2.5.2-atomic-snd-branch-receipts-v1"
PARENT_RUNTIME_COMMIT = "892aa26dd7018e8d86c1eaedad0d0ae64b9a7273"
PARENT_OUTCOME_COMMIT = "706f581767fd543d4faf36b83adce8387245cb8e"
BRANCH_ROLES = ("reference", "perturbed")
BRANCH_TRANSFORMS = (
    "raw SND frame -> length-delimited incremental SHA-256 before decode",
    "raw SND frame -> per-frame SHA-256 before decode",
    "Kiwi IQ decode -> GNSS readiness predicate",
    "readiness metadata + hashes -> atomic branch receipt",
)


class BranchOpenState(str, Enum):
    READY = "READY"
    CAPABILITY_REJECTED = "CAPABILITY_REJECTED"
    QUALIFICATION_ERROR = "QUALIFICATION_ERROR"


class PairDisposition(str, Enum):
    BRANCH_READY_UNCOMPOSED = "BRANCH_READY_UNCOMPOSED"
    CLOSED_ON_BRANCH_FAILURE = "CLOSED_ON_BRANCH_FAILURE"
    CLOSED_AFTER_PEER_FAILURE = "CLOSED_AFTER_PEER_FAILURE"
    CLOSED_AFTER_TOPOLOGY_REJECTION = "CLOSED_AFTER_TOPOLOGY_REJECTION"
    ADMITTED_TO_PAIR = "ADMITTED_TO_PAIR"


@dataclass(frozen=True, slots=True)
class BranchOpenReceipt:
    endpoint_identity: str
    role: str
    state: BranchOpenState
    started_at: datetime
    completed_at: datetime
    attempted: bool
    websocket_opened: bool
    handshake_message_count: int
    handshake_hash: str | None
    configuration_sent: bool
    sample_rate_hz: float | None
    channel_id: str | None
    channel_id_basis: str | None
    iq_frame_count: int
    iq_raw_bytes: int
    iq_stream_artifact_hash: str | None
    readiness_frame_artifact_hash: str | None
    readiness_event_start: datetime | None
    readiness_event_end: datetime | None
    readiness_sequence: int | None
    readiness_gps_solution_age_s: int | None
    error_type: str | None
    error_message: str | None
    error_description_hash: str | None
    pair_disposition: PairDisposition
    transforms: tuple[str, ...] = BRANCH_TRANSFORMS

    def __post_init__(self) -> None:
        if self.role not in BRANCH_ROLES:
            raise ValueError("branch role must be reference or perturbed")
        if f2._utc(self.completed_at) < f2._utc(self.started_at):
            raise ValueError("branch receipt time runs backwards")
        if not self.attempted:
            raise ValueError("an atomic branch receipt requires a real attempt")
        if self.handshake_message_count < 0 or self.iq_frame_count < 0 or self.iq_raw_bytes < 0:
            raise ValueError("branch counters cannot be negative")
        if self.iq_frame_count == 0 and (
            self.iq_raw_bytes != 0 or self.iq_stream_artifact_hash is not None
        ):
            raise ValueError("an empty branch cannot expose an IQ stream artifact")
        if self.iq_frame_count > 0 and (
            self.iq_raw_bytes == 0 or self.iq_stream_artifact_hash is None
        ):
            raise ValueError("received IQ frames require bytes and an incremental artifact hash")
        if self.state is BranchOpenState.READY:
            required = (
                self.websocket_opened,
                self.configuration_sent,
                self.sample_rate_hz is not None
                and math.isfinite(self.sample_rate_hz)
                and self.sample_rate_hz > 0,
                self.channel_id is not None,
                self.channel_id_basis is not None,
                self.iq_frame_count > 0,
                self.iq_stream_artifact_hash is not None,
                self.readiness_frame_artifact_hash is not None,
                self.readiness_event_start is not None,
                self.readiness_event_end is not None,
                self.readiness_sequence is not None,
                self.readiness_gps_solution_age_s is not None,
            )
            if not all(required) or self.error_description_hash is not None:
                raise ValueError("READY requires witnessed IQ readiness and no error")
            if f2._utc(self.readiness_event_end) < f2._utc(self.readiness_event_start):  # type: ignore[arg-type]
                raise ValueError("readiness event time runs backwards")
        else:
            if self.error_type is None or self.error_message is None or self.error_description_hash is None:
                raise ValueError("a failed branch requires an explicit descriptive error")
            if self.pair_disposition is PairDisposition.ADMITTED_TO_PAIR:
                raise ValueError("a failed branch cannot be admitted to the pair")
            if any(
                value is not None
                for value in (
                    self.readiness_frame_artifact_hash,
                    self.readiness_event_start,
                    self.readiness_event_end,
                    self.readiness_sequence,
                    self.readiness_gps_solution_age_s,
                )
            ):
                raise ValueError("a failed opening cannot claim a readiness witness")

    @property
    def artifact_hashes(self) -> tuple[str, ...]:
        return tuple(
            value
            for value in (
                self.handshake_hash,
                self.iq_stream_artifact_hash,
                self.readiness_frame_artifact_hash,
                self.error_description_hash,
            )
            if value is not None
        )

    @property
    def receipt_hash(self) -> str:
        return f2._hash(asdict(self))


@dataclass(slots=True)
class _BranchOpenResult:
    connection: f24._ChannelConnection | None
    receipt: BranchOpenReceipt


class AtomicDualOpenError(RuntimeError):
    def __init__(self, receipts: tuple[BranchOpenReceipt, BranchOpenReceipt], reason: str):
        self.receipts = receipts
        detail = "; ".join(
            f"{item.role}={item.state.value}:{item.error_type or item.pair_disposition.value}:"
            f"{item.error_message or 'ready'}"
            for item in receipts
        )
        super().__init__(f"{reason}; {detail}")


class BranchCapabilityRejected(RuntimeError):
    """Explicit server/operator refusal, never inferred from descriptive text."""


@dataclass(slots=True)
class _EphemeralSndHasher:
    digest: object
    frame_count: int = 0
    raw_bytes: int = 0

    @classmethod
    def create(cls) -> "_EphemeralSndHasher":
        return cls(sha256())

    def observe_before_decode(self, raw_frame: bytes) -> str:
        frame_hash = sha256(raw_frame).hexdigest()
        self.digest.update(len(raw_frame).to_bytes(8, "big"))  # type: ignore[attr-defined]
        self.digest.update(raw_frame)  # type: ignore[attr-defined]
        self.frame_count += 1
        self.raw_bytes += len(raw_frame)
        return frame_hash

    @property
    def stream_hash(self) -> str | None:
        if self.frame_count == 0:
            return None
        return self.digest.hexdigest()  # type: ignore[attr-defined]


def _endpoint_identity(endpoint: kiwi.KiwiEndpoint) -> str:
    return f"{endpoint.host.lower()}:{endpoint.port}"


def _is_capability_rejection(error: Exception) -> bool:
    return isinstance(error, (BranchCapabilityRejected, PermissionError))


def _atomic_open_channel(
    endpoint: kiwi.KiwiEndpoint,
    role: str,
    center_hz: float,
    status: dict[str, str],
    mother: f2.MotherPlan,
) -> _BranchOpenResult:
    """Open one branch and return its receipt instead of erasing partial evidence."""

    import websocket

    started = datetime.now(timezone.utc)
    token = (time.time_ns() ^ hash((endpoint.host, endpoint.port, role))) & 0xFFFFFFFF
    ws: object | None = None
    websocket_opened = False
    sample_rate = 0.0
    handshake: dict[str, str | None] = {}
    handshake_messages = 0
    configured = False
    hasher = _EphemeralSndHasher.create()
    try:
        ws = websocket.create_connection(
            f"ws://{endpoint.host}:{endpoint.port}/{token}/SND",
            timeout=8.0,
            origin=f"http://{endpoint.host}:{endpoint.port}",
            http_proxy_host=None,
            enable_multithread=True,
        )
        websocket_opened = True
        ws.send("SET auth t=kiwi p=")  # type: ignore[attr-defined]
        deadline = time.monotonic() + 12.0
        while time.monotonic() < deadline:
            message = ws.recv()  # type: ignore[attr-defined]
            arrival = datetime.now(timezone.utc)
            if isinstance(message, str):
                message = message.encode("latin-1")
            if not isinstance(message, bytes) or len(message) < 3:
                continue
            tag, body = message[:3], message[3:]
            if tag == b"MSG":
                handshake_messages += 1
                params = kiwi._msg_params(body[1:])
                handshake.update(params)
                if params.get("too_busy") is not None:
                    raise BranchCapabilityRejected(f"{endpoint.name} is busy")
                if params.get("badp") not in (None, "0"):
                    raise BranchCapabilityRejected(f"{endpoint.name} rejected public SND access")
                if "audio_rate" in params:
                    ws.send(f"SET AR OK in={int(float(params['audio_rate']))} out=44100")  # type: ignore[attr-defined]
                if "sample_rate" in params and not configured:
                    sample_rate = float(params["sample_rate"])
                    if not math.isfinite(sample_rate) or sample_rate <= 0.0:
                        raise ValueError("SND handshake exposed an invalid sample rate")
                    for command in f24._initial_channel_commands(center_hz):
                        ws.send(command)  # type: ignore[attr-defined]
                    configured = True
            elif tag == b"SND":
                raw_frame = tag + body
                frame_hash = hasher.observe_before_decode(raw_frame)
                if sample_rate <= 0.0:
                    raise RuntimeError("SND frame preceded sample-rate negotiation")
                block = kiwi._decode_iq_block(body, sample_rate, arrival)
                if (
                    block.gps_timestamp_available
                    and block.gps_solution_age_s <= mother.maximum_gps_solution_age_s
                ):
                    explicit = next(
                        (
                            str(handshake[key])
                            for key in ("rx_chan", "chan", "channel")
                            if handshake.get(key) not in (None, "")
                        ),
                        None,
                    )
                    if explicit is not None:
                        channel_id = f"rx:{explicit}"
                        basis = "explicit server handshake channel identifier"
                    else:
                        channel_id = f"snd-allocation:{token:08x}"
                        basis = (
                            "distinct simultaneous SND allocation token plus frozen "
                            "one-connection/one-RX-channel server audit"
                        )
                    receipt = BranchOpenReceipt(
                        _endpoint_identity(endpoint),
                        role,
                        BranchOpenState.READY,
                        started,
                        datetime.now(timezone.utc),
                        True,
                        websocket_opened,
                        handshake_messages,
                        f2._hash(handshake),
                        configured,
                        sample_rate,
                        channel_id,
                        basis,
                        hasher.frame_count,
                        hasher.raw_bytes,
                        hasher.stream_hash,
                        frame_hash,
                        block.event_start,
                        block.event_end,
                        block.sequence,
                        block.gps_solution_age_s,
                        None,
                        None,
                        None,
                        PairDisposition.BRANCH_READY_UNCOMPOSED,
                    )
                    del block
                    connection = f24._ChannelConnection(
                        endpoint,
                        role,
                        token,
                        channel_id,
                        basis,
                        ws,
                        sample_rate,
                        status,
                        handshake,
                        receipt.handshake_hash or f2._hash({}),
                        [],
                    )
                    return _BranchOpenResult(connection, receipt)
            ws.send("SET keepalive")  # type: ignore[attr-defined]
        raise TimeoutError(f"{endpoint.name} did not reach GNSS IQ readiness")
    except Exception as error:
        if ws is not None:
            try:
                ws.close()  # type: ignore[attr-defined]
            except Exception:
                pass
        description = {
            "endpoint": _endpoint_identity(endpoint),
            "role": role,
            "operation": "atomic_snd_branch_open",
            "error_type": type(error).__name__,
            "error": str(error),
        }
        receipt = BranchOpenReceipt(
            _endpoint_identity(endpoint),
            role,
            (
                BranchOpenState.CAPABILITY_REJECTED
                if _is_capability_rejection(error)
                else BranchOpenState.QUALIFICATION_ERROR
            ),
            started,
            datetime.now(timezone.utc),
            True,
            websocket_opened,
            handshake_messages,
            f2._hash(handshake) if handshake_messages > 0 else None,
            configured,
            sample_rate if sample_rate > 0.0 else None,
            None,
            None,
            hasher.frame_count,
            hasher.raw_bytes,
            hasher.stream_hash,
            None,
            None,
            None,
            None,
            None,
            type(error).__name__,
            str(error),
            f2._hash(description),
            PairDisposition.CLOSED_ON_BRANCH_FAILURE,
        )
        return _BranchOpenResult(None, receipt)


def _atomic_open_dual(
    endpoint: kiwi.KiwiEndpoint,
    center_hz: float,
    status: dict[str, str],
    mother: f2.MotherPlan,
) -> tuple[f24._DualConnections, tuple[BranchOpenReceipt, BranchOpenReceipt]]:
    """Compose a pair only after two independent atomic branch outcomes exist."""

    results: dict[str, _BranchOpenResult] = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            role: pool.submit(_atomic_open_channel, endpoint, role, center_hz, status, mother)
            for role in BRANCH_ROLES
        }
        for role in BRANCH_ROLES:
            results[role] = futures[role].result()

    receipts = tuple(results[role].receipt for role in BRANCH_ROLES)
    if any(results[role].connection is None for role in BRANCH_ROLES):
        adjusted: list[BranchOpenReceipt] = []
        for role, receipt in zip(BRANCH_ROLES, receipts):
            connection = results[role].connection
            if connection is not None:
                connection.close()
                receipt = replace(receipt, pair_disposition=PairDisposition.CLOSED_AFTER_PEER_FAILURE)
            adjusted.append(receipt)
        frozen = (adjusted[0], adjusted[1])
        raise AtomicDualOpenError(frozen, "atomic branches did not produce an admissible pair")

    reference = results["reference"].connection
    perturbed = results["perturbed"].connection
    assert reference is not None and perturbed is not None
    dual = f24._DualConnections(reference, perturbed)
    if reference.channel_id == perturbed.channel_id:
        dual.close()
        rejected = tuple(
            replace(item, pair_disposition=PairDisposition.CLOSED_AFTER_TOPOLOGY_REJECTION)
            for item in receipts
        )
        raise AtomicDualOpenError(
            (rejected[0], rejected[1]),
            "server did not expose distinct channel allocations",
        )
    admitted = tuple(replace(item, pair_disposition=PairDisposition.ADMITTED_TO_PAIR) for item in receipts)
    return dual, (admitted[0], admitted[1])


def _decorate_direct_result(
    result: f25._TopologyContext | f25.PhaseReceipt,
    branch_receipts: tuple[BranchOpenReceipt, ...],
) -> f25._TopologyContext | f25.PhaseReceipt:
    if not branch_receipts:
        return result
    receipt = result.phase_receipt if isinstance(result, f25._TopologyContext) else result
    by_role = {item.role: item for item in branch_receipts}
    reference = by_role["reference"]
    perturbed = by_role["perturbed"]
    hashes = list(receipt.artifact_hashes)
    for item in branch_receipts:
        hashes.extend(item.artifact_hashes)
        hashes.append(item.receipt_hash)
    state = receipt.state
    statement = receipt.statement
    if not isinstance(result, f25._TopologyContext):
        states = tuple(item.state for item in branch_receipts)
        if BranchOpenState.QUALIFICATION_ERROR in states:
            state = f25.F25PhaseState.QUALIFICATION_ERROR
            statement = (
                "atomic branch receipts leave pair availability indeterminate: "
                + "; ".join(f"{item.role}={item.state.value}" for item in branch_receipts)
            )
        elif BranchOpenState.CAPABILITY_REJECTED in states:
            state = f25.F25PhaseState.UNSATISFIED
            statement = (
                "atomic branch receipts show that the simultaneous pair was not admitted: "
                + "; ".join(f"{item.role}={item.state.value}" for item in branch_receipts)
            )
    properties = receipt.properties + tuple(
        value
        for item in branch_receipts
        for value in (
            (f"{item.role}_branch_state", item.state.value),
            (f"{item.role}_pair_disposition", item.pair_disposition.value),
            (f"{item.role}_iq_frame_count", str(item.iq_frame_count)),
            (
                f"{item.role}_readiness_frame_hashed",
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
        direct_reference_opened=reference.state is BranchOpenState.READY,
        direct_perturbed_opened=perturbed.state is BranchOpenState.READY,
        atomic_branch_receipts=branch_receipts,
        qualification_error_types=tuple(
            dict.fromkeys(
                receipt.qualification_error_types
                + tuple(
                    item.error_type
                    for item in branch_receipts
                    if item.state is BranchOpenState.QUALIFICATION_ERROR
                    and item.error_type is not None
                )
            )
        ),
    )
    if isinstance(result, f25._TopologyContext):
        result.phase_receipt = decorated
        return result
    return decorated


def direct_dual_snd_qualification(
    endpoint: kiwi.KiwiEndpoint,
    mother: f2.MotherPlan,
) -> f25._TopologyContext | f25.PhaseReceipt:
    """Use the F2.5.1 center while preserving both branch histories."""

    captured: tuple[BranchOpenReceipt, ...] = ()

    def opener(
        candidate: kiwi.KiwiEndpoint,
        center: float,
        status: dict[str, str],
        frozen_mother: f2.MotherPlan,
    ) -> f24._DualConnections:
        nonlocal captured
        try:
            dual, receipts = _atomic_open_dual(candidate, center, status, frozen_mother)
            captured = receipts
            return dual
        except AtomicDualOpenError as error:
            captured = error.receipts
            raise

    result = f25.direct_dual_snd_qualification(
        endpoint,
        mother,
        center_resolver=f251.bootstrap_center,
        dual_opener=opener,
    )
    return _decorate_direct_result(result, captured)


@dataclass(frozen=True, slots=True)
class F252BootstrapReceipt:
    inherited_f251: f251.F251BootstrapReceipt
    runtime_commit: str
    parent_runtime_commit: str
    parent_outcome_commit: str
    atomic_branch_receipts_required: bool
    readiness_frame_hash_required: bool
    stream_hash_before_decode_required: bool
    raw_rf_persistence: str
    transform_versions: tuple[str, ...]

    def __post_init__(self) -> None:
        if re.fullmatch(r"[0-9a-f]{40}", self.runtime_commit) is None:
            raise ValueError("runtime commit must be a full Git SHA-1")
        if self.inherited_f251.runtime_commit != self.runtime_commit:
            raise ValueError("inherited F2.5.1 bootstrap must bind the same runtime")
        if self.parent_runtime_commit != PARENT_RUNTIME_COMMIT:
            raise ValueError("Gate F2.5.1 runtime lineage changed")
        if self.parent_outcome_commit != PARENT_OUTCOME_COMMIT:
            raise ValueError("Gate F2.5.1 outcome lineage changed")
        if not all(
            (
                self.atomic_branch_receipts_required,
                self.readiness_frame_hash_required,
                self.stream_hash_before_decode_required,
            )
        ):
            raise ValueError("Gate F2.5.2 cannot weaken the atomic receipt boundary")
        if self.raw_rf_persistence != "ZERO":
            raise ValueError("raw RF persistence is forbidden")
        if self.transform_versions[-1] != F252_TRANSFORM_VERSION:
            raise ValueError("Gate F2.5.2 transform ledger changed")

    @property
    def retry_budget(self) -> int:
        return self.inherited_f251.retry_budget

    @property
    def receipt_hash(self) -> str:
        return f2._hash(asdict(self))


def build_bootstrap_receipt(*, runtime_commit: str, created_at: datetime) -> F252BootstrapReceipt:
    inherited = f251.build_bootstrap_receipt(runtime_commit=runtime_commit, created_at=created_at)
    return F252BootstrapReceipt(
        inherited,
        runtime_commit,
        PARENT_RUNTIME_COMMIT,
        PARENT_OUTCOME_COMMIT,
        True,
        True,
        True,
        "ZERO",
        inherited.transform_versions + (F252_TRANSFORM_VERSION,),
    )


def run_once(
    *,
    mother: f2.MotherPlan | None = None,
    runtime_commit: str | None = None,
    sink: Callable[[str], None] = print,
) -> f25.F25Result:
    """Materialize a future F2.5.2 session; never invoked by this offline gate."""

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
        event_prefix="gate_f2_5_2",
        terminal_instrument="gate-f2.5.2-atomic-dual-snd",
    )


def main() -> None:
    run_once()


if __name__ == "__main__":
    main()
