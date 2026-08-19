"""Gate F2.5.29: phase-aware injected dual-SND bridge, offline only.

The module joins the reviewed phase-aware Kiwi control ordering to the frozen
F2.5.28 relative-time one-shot.  Both branch transports and every incoming
frame are injected.  There is no connector, endpoint override, live runner or
network import.  The private injection seam exists only for deterministic
tests of ownership, ordering and downstream gating.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from enum import Enum
from hashlib import sha256
import inspect
import json
import math
from pathlib import Path
from typing import Sequence

from . import kiwi_gate_f2_5_7 as f257
from . import kiwi_gate_f2_5_17 as f2517
from . import kiwi_gate_f2_5_20 as f2520
from . import kiwi_gate_f2_5_27 as f2527
from . import kiwi_gate_f2_5_28 as f2528


TRANSFORM_VERSION = "gate-f2.5.29-phase-aware-injected-dual-snd-bridge-v1"
REVIEWED_F2528_COMMIT = "d6c2ae756f58dca6a8fc5b2039d4879c5ecfaccb"
EXPECTED_CAUSAL_SOURCE_SHA256 = (
    (
        "experiments/live_instrument/kiwi_gate_f2_5_17.py",
        "a50791d750f2f4605f2d185b88d22364c8686ac465ceb0193c0c868c77cf2c3c",
    ),
    (
        "experiments/live_instrument/kiwi_gate_f2_5_20.py",
        "60067ab416089f32c7bbf7edcda1c859b595ca02b9ffbc2511ffca8dc181f662",
    ),
    (
        "experiments/live_instrument/kiwi_gate_f2_5_27.py",
        "abc0da606b4d78228643c93672b6fe9a436e7da28418df5c9e0b47765fdba76d",
    ),
    (
        "experiments/live_instrument/kiwi_gate_f2_5_28.py",
        "2ca320b3ecc506b11b2d5940b96d033698c2ba18918378003995fae4557d8f70",
    ),
)
EXPECTED_F2528_ENVELOPE_HASH = (
    "46acfc458f727d71a04660012b21b2d45beaec349c475f8c2ce6ece06ad72ea4"
)
EXPECTED_INTEGRATION_SURFACE_HASH = (
    "8421c14c66d965451d63ecb78b6e3b513a7884a3ac609ec4809984dbc7cb940d"
)

AUTH_COMMAND = "SET auth t=kiwi p="
AUTH_RECEIPT_COMMAND = "SET auth t=kiwi p=<redacted>"
FROZEN_SND_FRAME_COUNT_PER_BRANCH = 8
FROZEN_CONTROL_TIMEOUT_S = 8.0
RAW_RF_PERSISTENCE = "ZERO"
BRANCH_ROLES = ("reference", "perturbed")
CONTROL_PHASES = (
    "AUTH_EMITTED_LOCAL",
    "REQUIRED_METADATA_OBSERVED",
    "REQUIRED_SETUP_EMITTED_LOCAL",
    "SND_FRAMES_TRANSFERRED_TO_ONE_SHOT",
)

_FORBIDDEN_RECEIPT_KEYS = f2528._FORBIDDEN_RECEIPT_KEYS | {
    "data",
    "payload",
    "raw_bytes",
    "transient_inputs",
}


class F2529Exit(str, Enum):
    INJECTED_PHASE_BRIDGE_READY = "INJECTED_PHASE_BRIDGE_READY"
    SEAL_MISMATCH = "SEAL_MISMATCH"


class BranchControlState(str, Enum):
    READY_FOR_RELATIVE_GATE = "READY_FOR_RELATIVE_GATE"
    CAPABILITY_REJECTED = "CAPABILITY_REJECTED"
    QUALIFICATION_ERROR = "QUALIFICATION_ERROR"


class PairControlState(str, Enum):
    DUAL_CONTROL_READY = "DUAL_CONTROL_READY"
    CAPABILITY_REJECTED = "CAPABILITY_REJECTED"
    TOPOLOGY_NOT_ADMITTED = "TOPOLOGY_NOT_ADMITTED"
    QUALIFICATION_ERROR = "QUALIFICATION_ERROR"


class WrapperOutcome(str, Enum):
    INJECTED_ONE_SHOT_COMPLETED = "INJECTED_ONE_SHOT_COMPLETED"
    CAPABILITY_REJECTED = "CAPABILITY_REJECTED"
    TOPOLOGY_NOT_ADMITTED = "TOPOLOGY_NOT_ADMITTED"
    QUALIFICATION_ERROR = "QUALIFICATION_ERROR"


class _CapabilityRejected(RuntimeError):
    pass


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


def _sha256(value: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError("a lowercase SHA-256 string is required")


def _command_hash(command: str) -> str:
    return sha256(command.encode("utf-8")).hexdigest()


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _canonical_source_sha256(path: Path) -> str:
    return sha256(path.read_text(encoding="utf-8").replace("\r\n", "\n").encode()).hexdigest()


def current_causal_source_sha256() -> tuple[tuple[str, str], ...]:
    root = _repository_root()
    return tuple(
        (relative, _canonical_source_sha256(root / relative))
        for relative, _expected in EXPECTED_CAUSAL_SOURCE_SHA256
    )


@dataclass(frozen=True, slots=True)
class F2529Envelope:
    reviewed_f2528_commit: str
    causal_source_sha256: tuple[tuple[str, str], ...]
    reviewed_f2528_envelope_hash: str
    integration_surface_hash: str
    selected_endpoint_identity: str
    bootstrap_center_hz: float
    bootstrap_center_role: str
    control_plan_hash: str
    control_phases: tuple[str, ...]
    snd_frames_per_branch: int
    absolute_gnss_freshness_role: str
    socket_mode: str
    byte_ownership: str
    public_execution_surface: str
    public_runtime_overrides: tuple[str, ...]
    live_execution_authorised: bool
    prefreeze_retry_budget: int
    postfreeze_retry_budget: int
    raw_rf_persistence: str
    transform_versions: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.reviewed_f2528_commit != REVIEWED_F2528_COMMIT:
            raise ValueError("Gate F2.5.28 lineage changed")
        if self.causal_source_sha256 != EXPECTED_CAUSAL_SOURCE_SHA256:
            raise ValueError("causal source seal changed")
        if self.reviewed_f2528_envelope_hash != EXPECTED_F2528_ENVELOPE_HASH:
            raise ValueError("Gate F2.5.28 envelope changed")
        if self.integration_surface_hash != EXPECTED_INTEGRATION_SURFACE_HASH:
            raise ValueError("phase-aware integration surface changed")
        if self.selected_endpoint_identity != f2520.SELECTED_ENDPOINT_IDENTITY:
            raise ValueError("the reviewed capability identity changed")
        if not math.isclose(
            self.bootstrap_center_hz,
            f2520.SELECTED_BOOTSTRAP_CENTER_HZ,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise ValueError("the reviewed bootstrap coordinate changed")
        if self.bootstrap_center_role != "CONTROL_BOOTSTRAP_NOT_FEATURE":
            raise ValueError("the bootstrap coordinate cannot become a target")
        if self.control_plan_hash != f2517.control_plan_hash():
            raise ValueError("the reviewed phase-aware control plan changed")
        if self.control_phases != CONTROL_PHASES:
            raise ValueError("phase-aware control order changed")
        if self.snd_frames_per_branch != FROZEN_SND_FRAME_COUNT_PER_BRANCH:
            raise ValueError("bounded SND transfer count changed")
        if self.absolute_gnss_freshness_role != "NOT_REQUIRED_FOR_SAME_ADC_RELATIVE_TIME":
            raise ValueError("absolute GNSS freshness re-entered admission")
        if self.socket_mode != "INJECTED_ALREADY_OPEN_DUAL_SND_ONLY":
            raise ValueError("a connector entered the offline bridge")
        if self.byte_ownership != "LEASE_RELEASE_PER_FRAME_THEN_CLEAR_TRANSIENT_INPUTS":
            raise ValueError("byte ownership boundary changed")
        if self.public_execution_surface != "ABSENT_PENDING_SEPARATE_LIVE_AUTHORITY":
            raise ValueError("offline bridge cannot expose execution")
        if self.public_runtime_overrides:
            raise ValueError("runtime overrides cannot enter the public surface")
        if self.live_execution_authorised:
            raise ValueError("Gate F2.5.29 cannot grant live authority")
        if self.prefreeze_retry_budget or self.postfreeze_retry_budget:
            raise ValueError("the bridge permits no retry")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")
        if self.transform_versions != (
            f2527.TRANSFORM_VERSION,
            f2528.TRANSFORM_VERSION,
            TRANSFORM_VERSION,
        ):
            raise ValueError("transform ledger changed")

    @property
    def envelope_hash(self) -> str:
        return _strict_hash(asdict(self))


@dataclass(slots=True)
class _InjectedFrameLease:
    """One injected frame whose transport-owned payload can be relinquished."""

    opcode: int
    monotonic_arrival_ns: int
    payload: bytes | bytearray | memoryview | str | None = field(repr=False)
    released: bool = False

    def take_payload(self) -> bytes:
        if self.released or self.payload is None:
            raise RuntimeError("injected frame lease was already released")
        value = self.payload
        if isinstance(value, str):
            owned = value.encode("latin-1")
        elif isinstance(value, (bytes, bytearray, memoryview)):
            owned = bytes(value)
        else:
            raise TypeError("injected frame has an unsupported payload type")
        if isinstance(value, bytearray):
            value[:] = b"\x00" * len(value)
        elif isinstance(value, memoryview) and not value.readonly:
            value[:] = b"\x00" * len(value)
        self.payload = None
        self.released = True
        return owned


@dataclass(frozen=True, slots=True)
class BranchControlReceipt:
    endpoint_identity: str
    branch_role: str
    state: str
    channel_id: int | None
    sample_rate_hz: float | None
    audio_rate_hz: float | None
    control_phases: tuple[str, ...]
    local_command_hashes: tuple[str, ...]
    setup_command_hashes: tuple[str, ...]
    incoming_frame_artifact_hashes: tuple[str, ...]
    snd_frame_artifact_hashes: tuple[str, ...]
    socket_frame_lease_count: int
    socket_frame_release_count: int
    error_type: str | None
    error_description_hash: str | None
    raw_rf_persistence: str = RAW_RF_PERSISTENCE

    def __post_init__(self) -> None:
        if self.endpoint_identity != f2520.SELECTED_ENDPOINT_IDENTITY:
            raise ValueError("branch receipt endpoint changed")
        if self.branch_role not in BRANCH_ROLES:
            raise ValueError("unknown branch role")
        if self.state not in {item.value for item in BranchControlState}:
            raise ValueError("unknown branch control state")
        if self.control_phases:
            if self.control_phases[0] != CONTROL_PHASES[0]:
                raise ValueError("auth must be the first observed control phase")
            if len(set(self.control_phases)) != len(self.control_phases):
                raise ValueError("control phases cannot repeat")
            indexes = tuple(CONTROL_PHASES.index(item) for item in self.control_phases)
            if indexes != tuple(sorted(indexes)):
                raise ValueError("control phases are out of order")
        if self.socket_frame_lease_count != len(self.incoming_frame_artifact_hashes):
            raise ValueError("every incoming frame requires one ownership lease")
        if self.socket_frame_release_count != self.socket_frame_lease_count:
            raise ValueError("every received frame lease must be released")
        for digest in (
            *self.local_command_hashes,
            *self.setup_command_hashes,
            *self.incoming_frame_artifact_hashes,
            *self.snd_frame_artifact_hashes,
            self.error_description_hash,
        ):
            if digest is not None:
                _sha256(digest)
        ready = self.state == BranchControlState.READY_FOR_RELATIVE_GATE.value
        if ready:
            expected_setup_hashes = (
                tuple(
                    _command_hash(command)
                    for command in f2517.setup_commands(
                        f2520.SELECTED_BOOTSTRAP_CENTER_HZ,
                        self.audio_rate_hz,
                    )
                )
                if self.audio_rate_hz is not None
                else ()
            )
            if (
                self.control_phases != CONTROL_PHASES
                or self.channel_id is None
                or self.sample_rate_hz is None
                or self.audio_rate_hz is None
                or len(self.snd_frame_artifact_hashes)
                != FROZEN_SND_FRAME_COUNT_PER_BRANCH
                or self.error_type is not None
                or self.error_description_hash is not None
                or self.local_command_hashes
                != (_command_hash(AUTH_RECEIPT_COMMAND), *expected_setup_hashes)
                or self.setup_command_hashes != expected_setup_hashes
            ):
                raise ValueError("ready control receipt lacks its complete witness chain")
        elif self.error_type is None or self.error_description_hash is None:
            raise ValueError("failed control receipt requires a typed description")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")

    @property
    def receipt_hash(self) -> str:
        return _strict_hash(asdict(self))


@dataclass(frozen=True, slots=True)
class ByteReleaseReceipt:
    socket_frame_lease_count: int
    socket_frame_release_count: int
    transient_snd_input_count: int
    transient_snd_input_clear_count: int
    artifact_set_hash: str
    all_socket_frame_leases_released: bool
    all_transient_snd_inputs_cleared: bool
    wrapper_payload_references_after_return: int
    raw_rf_persistence: str = RAW_RF_PERSISTENCE

    def __post_init__(self) -> None:
        _sha256(self.artifact_set_hash)
        if (
            self.socket_frame_lease_count != self.socket_frame_release_count
            or not self.all_socket_frame_leases_released
        ):
            raise ValueError("socket frame leases were not all released")
        if (
            self.transient_snd_input_count != self.transient_snd_input_clear_count
            or not self.all_transient_snd_inputs_cleared
        ):
            raise ValueError("transient SND inputs were not all cleared")
        if self.wrapper_payload_references_after_return != 0:
            raise ValueError("wrapper cannot retain payload references")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")


@dataclass(frozen=True, slots=True)
class F2529RunResult:
    envelope_hash: str
    outcome: str
    pair_control_state: str
    branch_receipts: tuple[BranchControlReceipt, BranchControlReceipt]
    one_shot_result: f2528.F2528RunResult | None
    byte_release: ByteReleaseReceipt
    live_execution_authorised: bool
    physical_hypothesis_state: str
    authorised_claims: tuple[str, ...]
    unauthorised_claims: tuple[str, ...]
    raw_rf_persistence: str = RAW_RF_PERSISTENCE

    def __post_init__(self) -> None:
        _sha256(self.envelope_hash)
        if self.outcome not in {item.value for item in WrapperOutcome}:
            raise ValueError("unknown wrapper outcome")
        if self.pair_control_state not in {item.value for item in PairControlState}:
            raise ValueError("unknown pair control state")
        if tuple(item.branch_role for item in self.branch_receipts) != BRANCH_ROLES:
            raise ValueError("branch receipt order changed")
        if self.live_execution_authorised:
            raise ValueError("offline result cannot grant live authority")
        if self.physical_hypothesis_state != "NOT_EVALUATED":
            raise ValueError("offline bridge cannot decide the physical hypothesis")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")


@dataclass(frozen=True, slots=True)
class F2529Assessment:
    exit: F2529Exit
    envelope: F2529Envelope | None
    causal_source_hashes_match: bool
    parent_gate_ready: bool
    integration_surface_matches: bool
    exact_control_order_bound: bool
    absolute_freshness_absent_from_admission: bool
    public_execution_surface_absent: bool
    live_execution_authorised: bool
    blockers: tuple[str, ...]
    raw_rf_persistence: str


@dataclass(slots=True)
class _BranchCollection:
    receipt: BranchControlReceipt
    transient_inputs: list[f2528.TransientSNDInput]


def _append_once(values: list[float | int], value: float | int, name: str) -> None:
    if values and values[0] != value:
        raise RuntimeError(f"conflicting {name} metadata")
    if not values:
        values.append(value)


def _send(socket: object, command: str, hashes: list[str], *, redacted: str | None = None) -> None:
    socket.send(command)  # type: ignore[attr-defined]
    hashes.append(_command_hash(redacted or command))


def _collect_injected_branch(socket: object, branch_role: str) -> _BranchCollection:
    """Collect one already-open injected SND branch in the reviewed order."""

    commands: list[str] = []
    setup_hashes: tuple[str, ...] = ()
    incoming_hashes: list[str] = []
    snd_hashes: list[str] = []
    phases: list[str] = []
    inputs: list[f2528.TransientSNDInput] = []
    channel_values: list[int] = []
    sample_rates: list[float] = []
    audio_rates: list[float] = []
    release_count = 0
    error: Exception | None = None
    configured = False

    try:
        if branch_role not in BRANCH_ROLES:
            raise ValueError("unknown branch role")
        socket.settimeout(FROZEN_CONTROL_TIMEOUT_S)  # type: ignore[attr-defined]
        _send(socket, AUTH_COMMAND, commands, redacted=AUTH_RECEIPT_COMMAND)
        phases.append(CONTROL_PHASES[0])

        while len(inputs) < FROZEN_SND_FRAME_COUNT_PER_BRANCH:
            opcode, frame = socket.recv_data_frame(control_frame=True)  # type: ignore[attr-defined]
            if opcode not in {1, 2}:
                raise RuntimeError("non-data WebSocket frame ended injected collection")
            if not hasattr(frame, "take_payload"):
                raise RuntimeError("InjectedFrameOwnershipMissing")
            arrival_ns = int(frame.monotonic_arrival_ns)
            payload = frame.take_payload()
            if not bool(frame.released) or frame.payload is not None:
                raise RuntimeError("InjectedFrameLeaseNotReleased")
            release_count += 1
            artifact_hash = sha256(payload).hexdigest()
            incoming_hashes.append(artifact_hash)

            if len(payload) < 3:
                raise RuntimeError("short injected WebSocket data frame")
            tag, body = payload[:3], payload[3:]
            if tag == b"MSG":
                fields = f257.decode_allowlisted_server_fields(
                    body[1:].decode("ascii", errors="replace")
                )
                for field_value in fields:
                    if field_value.name == "badp":
                        if field_value.state != "OK":
                            raise _CapabilityRejected(
                                f"server reported badp={int(field_value.numeric_value or -1)}"
                            )
                    elif field_value.name == "too_busy":
                        raise _CapabilityRejected("server reported too_busy")
                    elif field_value.name == "is_local":
                        assert field_value.channel_id is not None
                        _append_once(channel_values, field_value.channel_id, "channel")
                    elif field_value.name == "sample_rate":
                        assert field_value.numeric_value is not None
                        _append_once(sample_rates, field_value.numeric_value, "sample rate")
                    elif field_value.name == "audio_rate":
                        assert field_value.numeric_value is not None
                        _append_once(audio_rates, field_value.numeric_value, "audio rate")

                if not configured and channel_values and sample_rates and audio_rates:
                    phases.append(CONTROL_PHASES[1])
                    setup = f2517.setup_commands(
                        f2520.SELECTED_BOOTSTRAP_CENTER_HZ,
                        audio_rates[0],
                    )
                    f2517.validate_setup_commands(
                        setup,
                        f2520.SELECTED_BOOTSTRAP_CENTER_HZ,
                        audio_rates[0],
                    )
                    for command in setup:
                        _send(socket, command, commands)
                    setup_hashes = tuple(_command_hash(command) for command in setup)
                    configured = True
                    phases.append(CONTROL_PHASES[2])
            elif tag == b"SND":
                if not configured:
                    raise RuntimeError("SND frame preceded the complete local setup")
                snd_hashes.append(artifact_hash)
                inputs.append(f2528.TransientSNDInput(arrival_ns, payload))
            else:
                raise RuntimeError("unsupported injected Kiwi data tag")

        phases.append(CONTROL_PHASES[3])
    except Exception as caught:
        error = caught
    finally:
        try:
            socket.close()  # type: ignore[attr-defined]
        except Exception:
            pass

    if error is None:
        state = BranchControlState.READY_FOR_RELATIVE_GATE
        error_type = None
        error_hash = None
    else:
        state = (
            BranchControlState.CAPABILITY_REJECTED
            if isinstance(error, _CapabilityRejected)
            else BranchControlState.QUALIFICATION_ERROR
        )
        error_type = type(error).__name__
        error_hash = _strict_hash(
            {
                "endpoint": f2520.SELECTED_ENDPOINT_IDENTITY,
                "branch_role": branch_role,
                "stage": "INJECTED_PHASE_AWARE_COLLECTION",
                "error_type": error_type,
            }
        )

    return _BranchCollection(
        BranchControlReceipt(
            endpoint_identity=f2520.SELECTED_ENDPOINT_IDENTITY,
            branch_role=branch_role,
            state=state.value,
            channel_id=channel_values[0] if channel_values else None,
            sample_rate_hz=sample_rates[0] if sample_rates else None,
            audio_rate_hz=audio_rates[0] if audio_rates else None,
            control_phases=tuple(phases),
            local_command_hashes=tuple(commands),
            setup_command_hashes=setup_hashes,
            incoming_frame_artifact_hashes=tuple(incoming_hashes),
            snd_frame_artifact_hashes=tuple(snd_hashes),
            socket_frame_lease_count=len(incoming_hashes),
            socket_frame_release_count=release_count,
            error_type=error_type,
            error_description_hash=error_hash,
        ),
        inputs,
    )


def _run_injected_phase_aware(
    *,
    reference_socket: object,
    perturbed_socket: object,
    discovery_probe: f2528.DiscoveryProbe,
    retune_probe: f2528.RetuneProbe,
) -> F2529RunResult:
    """Private deterministic bridge. It cannot construct or select a socket."""

    with ThreadPoolExecutor(max_workers=2) as executor:
        reference_future = executor.submit(
            _collect_injected_branch, reference_socket, "reference"
        )
        perturbed_future = executor.submit(
            _collect_injected_branch, perturbed_socket, "perturbed"
        )
        reference = reference_future.result()
        perturbed = perturbed_future.result()

    collections = (reference, perturbed)
    receipts = (reference.receipt, perturbed.receipt)
    all_inputs = reference.transient_inputs + perturbed.transient_inputs
    artifact_hashes = tuple(
        sha256(item.raw_message).hexdigest() for item in all_inputs
    )
    one_shot: f2528.F2528RunResult | None = None

    try:
        states = {item.state for item in receipts}
        if BranchControlState.CAPABILITY_REJECTED.value in states:
            pair_state = PairControlState.CAPABILITY_REJECTED
            outcome = WrapperOutcome.CAPABILITY_REJECTED
        elif states != {BranchControlState.READY_FOR_RELATIVE_GATE.value}:
            pair_state = PairControlState.QUALIFICATION_ERROR
            outcome = WrapperOutcome.QUALIFICATION_ERROR
        elif (
            receipts[0].channel_id == receipts[1].channel_id
            or receipts[0].sample_rate_hz is None
            or receipts[1].sample_rate_hz is None
            or not math.isclose(
                receipts[0].sample_rate_hz,
                receipts[1].sample_rate_hz,
                rel_tol=0.0,
                abs_tol=f2527.build_plan().maximum_sample_rate_difference_hz,
            )
        ):
            pair_state = PairControlState.TOPOLOGY_NOT_ADMITTED
            outcome = WrapperOutcome.TOPOLOGY_NOT_ADMITTED
        else:
            pair_state = PairControlState.DUAL_CONTROL_READY
            one_shot = f2528.run_one_shot_injected(
                reference_inputs=reference.transient_inputs,
                perturbed_inputs=perturbed.transient_inputs,
                endpoint_identity=f2520.SELECTED_ENDPOINT_IDENTITY,
                reference_channel_id=receipts[0].channel_id,
                perturbed_channel_id=receipts[1].channel_id,
                sample_rate_hz=receipts[0].sample_rate_hz,
                discovery_probe=discovery_probe,
                retune_probe=retune_probe,
            )
            outcome = WrapperOutcome.INJECTED_ONE_SHOT_COMPLETED
    finally:
        cleared = 0
        for item in all_inputs:
            item.raw_message = b""
            cleared += 1
        reference.transient_inputs.clear()
        perturbed.transient_inputs.clear()

    lease_count = sum(item.socket_frame_lease_count for item in receipts)
    release_count = sum(item.socket_frame_release_count for item in receipts)
    release = ByteReleaseReceipt(
        socket_frame_lease_count=lease_count,
        socket_frame_release_count=release_count,
        transient_snd_input_count=len(all_inputs),
        transient_snd_input_clear_count=cleared,
        artifact_set_hash=_strict_hash(tuple(sorted(artifact_hashes))),
        all_socket_frame_leases_released=lease_count == release_count,
        all_transient_snd_inputs_cleared=all(
            item.raw_message == b"" for item in all_inputs
        ),
        wrapper_payload_references_after_return=0,
    )
    all_inputs.clear()

    return F2529RunResult(
        envelope_hash=build_envelope().envelope_hash,
        outcome=outcome.value,
        pair_control_state=pair_state.value,
        branch_receipts=receipts,
        one_shot_result=one_shot,
        byte_release=release,
        live_execution_authorised=False,
        physical_hypothesis_state="NOT_EVALUATED",
        authorised_claims=(
            "two injected branch transcripts obeyed or failed the reviewed control order",
            "every injected frame was hashed and its transport lease was released",
            "absolute GNSS freshness did not replace same-ADC relative-time admission",
            "downstream feature analysis ran only after dual control and temporal admission",
        ),
        unauthorised_claims=(
            "a live Kiwi accepted either branch",
            "the selected endpoint is currently reachable",
            "a physical feature was discovered",
            "a per-channel retune occurred on a live receiver",
            "the physical hypothesis was evaluated",
        ),
    )


def _integration_surface_hash() -> str:
    return sha256(inspect.getsource(_run_injected_phase_aware).encode()).hexdigest()


def build_envelope() -> F2529Envelope:
    return F2529Envelope(
        reviewed_f2528_commit=REVIEWED_F2528_COMMIT,
        causal_source_sha256=EXPECTED_CAUSAL_SOURCE_SHA256,
        reviewed_f2528_envelope_hash=EXPECTED_F2528_ENVELOPE_HASH,
        integration_surface_hash=EXPECTED_INTEGRATION_SURFACE_HASH,
        selected_endpoint_identity=f2520.SELECTED_ENDPOINT_IDENTITY,
        bootstrap_center_hz=f2520.SELECTED_BOOTSTRAP_CENTER_HZ,
        bootstrap_center_role="CONTROL_BOOTSTRAP_NOT_FEATURE",
        control_plan_hash=f2517.control_plan_hash(),
        control_phases=CONTROL_PHASES,
        snd_frames_per_branch=FROZEN_SND_FRAME_COUNT_PER_BRANCH,
        absolute_gnss_freshness_role="NOT_REQUIRED_FOR_SAME_ADC_RELATIVE_TIME",
        socket_mode="INJECTED_ALREADY_OPEN_DUAL_SND_ONLY",
        byte_ownership="LEASE_RELEASE_PER_FRAME_THEN_CLEAR_TRANSIENT_INPUTS",
        public_execution_surface="ABSENT_PENDING_SEPARATE_LIVE_AUTHORITY",
        public_runtime_overrides=(),
        live_execution_authorised=False,
        prefreeze_retry_budget=0,
        postfreeze_retry_budget=0,
        raw_rf_persistence=RAW_RF_PERSISTENCE,
        transform_versions=(
            f2527.TRANSFORM_VERSION,
            f2528.TRANSFORM_VERSION,
            TRANSFORM_VERSION,
        ),
    )


def assess() -> F2529Assessment:
    parent = f2528.assess()
    causal_match = current_causal_source_sha256() == EXPECTED_CAUSAL_SOURCE_SHA256
    parent_ready = (
        parent.exit is f2528.F2528Exit.INJECTED_ONE_SHOT_INTEGRATED_OFFLINE
        and parent.envelope is not None
        and parent.envelope.envelope_hash == EXPECTED_F2528_ENVELOPE_HASH
    )
    surface_match = _integration_surface_hash() == EXPECTED_INTEGRATION_SURFACE_HASH
    blockers = tuple(
        message
        for condition, message in (
            (causal_match, "causal source seal mismatch"),
            (parent_ready, "Gate F2.5.28 prerequisite mismatch"),
            (surface_match, "integration surface mismatch"),
        )
        if not condition
    )
    envelope = build_envelope() if not blockers else None
    return F2529Assessment(
        exit=(
            F2529Exit.INJECTED_PHASE_BRIDGE_READY
            if not blockers
            else F2529Exit.SEAL_MISMATCH
        ),
        envelope=envelope,
        causal_source_hashes_match=causal_match,
        parent_gate_ready=parent_ready,
        integration_surface_matches=surface_match,
        exact_control_order_bound=True,
        absolute_freshness_absent_from_admission=True,
        public_execution_surface_absent=True,
        live_execution_authorised=False,
        blockers=blockers,
        raw_rf_persistence=RAW_RF_PERSISTENCE,
    )


__all__ = [
    "F2529Assessment",
    "F2529Envelope",
    "F2529Exit",
    "F2529RunResult",
    "assess",
    "build_envelope",
]
