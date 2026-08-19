"""Offline injected control-bridge tests for Gate F2.5.29."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict
from hashlib import sha256
import inspect
import json
import math
import struct

import numpy as np

from experiments.live_instrument import kiwi_gate_f2_5_17 as f2517
from experiments.live_instrument import kiwi_gate_f2_5_20 as f2520
from experiments.live_instrument import kiwi_gate_f2_5_27 as f2527
from experiments.live_instrument import kiwi_gate_f2_5_28 as f2528
from experiments.live_instrument import kiwi_gate_f2_5_29 as f2529


SAMPLE_RATE_HZ = 12_000.0
SAMPLE_COUNT = 512
FRAME_DURATION_NS = round(SAMPLE_COUNT * 1_000_000_000 / SAMPLE_RATE_HZ)


def _hash(label: str) -> str:
    return sha256(label.encode()).hexdigest()


def _snd(
    sequence: int,
    start_ns: int,
    *,
    age_s: int = 103,
    malformed: bool = False,
) -> bytes:
    if malformed:
        return b"SNDbad"
    raw_time = start_ns % f2527.GPS_WEEK_NS
    header = (
        struct.pack("<BI", 0x08, sequence)
        + b"\x00\x00"
        + struct.pack(
            "<BBII",
            age_s,
            0,
            raw_time // 1_000_000_000,
            raw_time % 1_000_000_000,
        )
    )
    values = np.empty(SAMPLE_COUNT * 2, dtype=">i2")
    values[0::2] = np.arange(SAMPLE_COUNT, dtype=np.int16) % 127
    values[1::2] = -(np.arange(SAMPLE_COUNT, dtype=np.int16) % 97)
    return b"SND" + header + values.tobytes()


class _InjectedSocket:
    def __init__(self, leases: list[f2529._InjectedFrameLease]) -> None:
        self.leases = leases
        self.remaining = deque(leases)
        self.sent: list[str] = []
        self.timeout: float | None = None
        self.closed = False

    def settimeout(self, value: float) -> None:
        self.timeout = value

    def send(self, command: str) -> None:
        self.sent.append(command)

    def recv_data_frame(self, *, control_frame: bool):
        assert control_frame is True
        if not self.remaining:
            raise EOFError("injected transcript exhausted")
        lease = self.remaining.popleft()
        return lease.opcode, lease

    def close(self) -> None:
        self.closed = True


def _socket(
    channel: int,
    *,
    start_ns: int = 100_000_000_000,
    arrival_offset_ns: int = 0,
    age_s: int = 103,
    sample_rate_hz: float = SAMPLE_RATE_HZ,
    badp: int = 0,
    snd_before_metadata: bool = False,
    malformed_index: int | None = None,
) -> _InjectedSocket:
    messages: list[tuple[int, bytes]] = []
    if snd_before_metadata:
        messages.append((900_000_000 + arrival_offset_ns, _snd(1, start_ns)))
    messages.append(
        (
            950_000_000 + arrival_offset_ns,
            (
                f"MSG badp={badp} is_local={channel},0,0 "
                f"audio_rate=12000 sample_rate={sample_rate_hz}"
            ).encode(),
        )
    )
    for index in range(8):
        messages.append(
            (
                1_000_000_000
                + index * 50_000_000
                + arrival_offset_ns,
                _snd(
                    index + 1,
                    start_ns + index * FRAME_DURATION_NS,
                    age_s=age_s,
                    malformed=malformed_index == index,
                ),
            )
        )
    leases = [
        f2529._InjectedFrameLease(2, arrival, bytearray(payload))
        for arrival, payload in messages
    ]
    return _InjectedSocket(leases)


def _discovery(calls: dict[str, int] | None = None):
    def probe(view: object) -> f2528.DiscoveryProbeResult:
        if calls is not None:
            calls["discovery"] += 1
        assert all(not item.flags.writeable for item in view.reference_iq)
        assert all(not item.flags.writeable for item in view.perturbed_iq)
        return f2528.DiscoveryProbeResult(
            True,
            (_hash("injected-discovery"),),
            "one injected target passed the deterministic test seam",
        )

    return probe


def _boundary(
    view: object,
    transition: str,
    before_index: int,
    after_index: int,
    command_ns: int,
    settling_ns: int,
) -> f2527.BoundaryWitnessReceipt:
    anchor = f2527.CommandBoundaryAnchor(
        transition=transition,
        command_hash=_hash(transition),
        command_issued_monotonic_ns=command_ns,
        settling_complete_monotonic_ns=settling_ns,
        last_precommand_perturbed_frame_hash=(
            view.perturbed_receipts[before_index].artifact_hash_before_analysis
        ),
        first_postsettling_perturbed_frame_hash=(
            view.perturbed_receipts[after_index].artifact_hash_before_analysis
        ),
        reference_before_frame_hash=(
            view.reference_receipts[before_index].artifact_hash_before_analysis
        ),
        reference_after_frame_hash=(
            view.reference_receipts[after_index].artifact_hash_before_analysis
        ),
    )
    return f2527.evaluate_command_boundary(
        anchor,
        last_precommand_perturbed=view.perturbed_receipts[before_index],
        first_postsettling_perturbed=view.perturbed_receipts[after_index],
        reference_before=view.reference_receipts[before_index],
        reference_after=view.reference_receipts[after_index],
    )


def _retune(calls: dict[str, int] | None = None):
    def probe(view: object) -> f2528.RetuneProbeResult:
        if calls is not None:
            calls["retune"] += 1
        return f2528.RetuneProbeResult(
            claimed_qualified=True,
            boundary_receipts=(
                _boundary(view, "A1_TO_B", 2, 4, 1_110_000_000, 1_130_000_000),
                _boundary(view, "B_TO_A2", 4, 6, 1_210_000_000, 1_230_000_000),
            ),
            witness_artifact_hashes=(_hash("injected-witness"),),
            statement="both injected command boundaries were witnessed",
        )

    return probe


def _run(
    reference: _InjectedSocket | None = None,
    perturbed: _InjectedSocket | None = None,
    calls: dict[str, int] | None = None,
) -> tuple[f2529.F2529RunResult, _InjectedSocket, _InjectedSocket]:
    left = reference or _socket(0)
    right = perturbed or _socket(1, arrival_offset_ns=1_000_000)
    result = f2529._run_injected_phase_aware(
        reference_socket=left,
        perturbed_socket=right,
        discovery_probe=_discovery(calls),
        retune_probe=_retune(calls),
    )
    return result, left, right


def _walk_keys(value: object) -> tuple[str, ...]:
    if isinstance(value, dict):
        return tuple(str(key) for key in value) + tuple(
            key for item in value.values() for key in _walk_keys(item)
        )
    if isinstance(value, (list, tuple)):
        return tuple(key for item in value for key in _walk_keys(item))
    return ()


def _assert_finite(value: object) -> None:
    if isinstance(value, dict):
        for item in value.values():
            _assert_finite(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _assert_finite(item)
    elif isinstance(value, float):
        assert math.isfinite(value)


def test_reviewed_parent_control_and_private_surface_are_sealed() -> None:
    assessment = f2529.assess()

    assert assessment.exit is f2529.F2529Exit.INJECTED_PHASE_BRIDGE_READY
    assert assessment.envelope is not None
    assert assessment.causal_source_hashes_match is True
    assert assessment.parent_gate_ready is True
    assert assessment.integration_surface_matches is True
    assert assessment.exact_control_order_bound is True
    assert assessment.absolute_freshness_absent_from_admission is True
    assert assessment.public_execution_surface_absent is True
    assert assessment.live_execution_authorised is False
    assert assessment.envelope.public_runtime_overrides == ()


def test_dual_control_orders_auth_metadata_setup_then_snd_and_runs_one_shot() -> None:
    calls = {"discovery": 0, "retune": 0}
    result, left, right = _run(calls=calls)
    setup = f2517.setup_commands(f2520.SELECTED_BOOTSTRAP_CENTER_HZ, 12_000.0)

    assert result.outcome == "INJECTED_ONE_SHOT_COMPLETED"
    assert result.pair_control_state == "DUAL_CONTROL_READY"
    assert result.one_shot_result is not None
    assert result.one_shot_result.outcome == "RETUNE_QUALIFIED_OFFLINE"
    assert calls == {"discovery": 1, "retune": 1}
    for socket, receipt in zip((left, right), result.branch_receipts):
        assert socket.sent == [f2529.AUTH_COMMAND, *setup]
        assert socket.timeout == f2529.FROZEN_CONTROL_TIMEOUT_S
        assert socket.closed is True
        assert receipt.control_phases == f2529.CONTROL_PHASES
        assert receipt.local_command_hashes[1:] == receipt.setup_command_hashes
        assert receipt.state == "READY_FOR_RELATIVE_GATE"
    assert result.branch_receipts[0].channel_id == 0
    assert result.branch_receipts[1].channel_id == 1


def test_transport_leases_release_per_frame_and_transient_copies_clear_after_gate() -> None:
    result, left, right = _run()

    assert all(lease.released and lease.payload is None for lease in left.leases)
    assert all(lease.released and lease.payload is None for lease in right.leases)
    assert result.byte_release.all_socket_frame_leases_released is True
    assert result.byte_release.socket_frame_lease_count == 18
    assert result.byte_release.socket_frame_release_count == 18
    assert result.byte_release.transient_snd_input_count == 16
    assert result.byte_release.transient_snd_input_clear_count == 16
    assert result.byte_release.all_transient_snd_inputs_cleared is True
    assert result.byte_release.wrapper_payload_references_after_return == 0
    assert result.one_shot_result is not None
    assert result.one_shot_result.zeroization.all_arrays_zeroized is True


def test_absolute_age_does_not_gate_but_reserved_clock_state_does() -> None:
    old_but_relative = _socket(0, age_s=103)
    old_but_relative_right = _socket(1, age_s=103, arrival_offset_ns=1_000_000)
    admitted, _left, _right = _run(old_but_relative, old_but_relative_right)

    calls = {"discovery": 0, "retune": 0}
    invalid = _socket(0, age_s=255)
    invalid_right = _socket(1, age_s=255, arrival_offset_ns=1_000_000)
    refused, _left, _right = _run(invalid, invalid_right, calls)

    assert admitted.one_shot_result is not None
    assert admitted.one_shot_result.temporal_admission is not None
    assert admitted.one_shot_result.temporal_admission.state == (
        "ADMISSIBLE_FOR_RELATIVE_TIME_EXPERIMENT"
    )
    assert refused.one_shot_result is not None
    assert refused.one_shot_result.outcome == "TEMPORAL_NOT_ADMITTED"
    assert refused.one_shot_result.discovery_call_count == 0
    assert refused.one_shot_result.retune_call_count == 0
    assert calls == {"discovery": 0, "retune": 0}


def test_snd_before_required_setup_is_qualification_error_and_blocks_downstream() -> None:
    calls = {"discovery": 0, "retune": 0}
    result, left, _right = _run(reference=_socket(0, snd_before_metadata=True), calls=calls)

    assert result.outcome == "QUALIFICATION_ERROR"
    assert result.pair_control_state == "QUALIFICATION_ERROR"
    assert result.one_shot_result is None
    assert result.branch_receipts[0].state == "QUALIFICATION_ERROR"
    assert result.branch_receipts[0].error_type == "RuntimeError"
    assert left.sent == [f2529.AUTH_COMMAND]
    assert left.leases[0].released is True
    assert calls == {"discovery": 0, "retune": 0}


def test_explicit_second_branch_rejection_remains_capability_rejection() -> None:
    calls = {"discovery": 0, "retune": 0}
    result, _left, right = _run(perturbed=_socket(1, badp=5), calls=calls)

    assert result.outcome == "CAPABILITY_REJECTED"
    assert result.pair_control_state == "CAPABILITY_REJECTED"
    assert result.one_shot_result is None
    assert result.branch_receipts[1].state == "CAPABILITY_REJECTED"
    assert result.branch_receipts[1].error_type == "_CapabilityRejected"
    assert right.sent == [f2529.AUTH_COMMAND]
    assert calls == {"discovery": 0, "retune": 0}


def test_same_channel_or_unequal_rate_cannot_enter_relative_gate() -> None:
    same, _left, _right = _run(perturbed=_socket(0, arrival_offset_ns=1_000_000))
    unequal, _left, _right = _run(
        perturbed=_socket(
            1,
            arrival_offset_ns=1_000_000,
            sample_rate_hz=SAMPLE_RATE_HZ + 1.0,
        )
    )

    assert same.outcome == "TOPOLOGY_NOT_ADMITTED"
    assert same.one_shot_result is None
    assert unequal.outcome == "TOPOLOGY_NOT_ADMITTED"
    assert unequal.one_shot_result is None


def test_malformed_snd_is_hashed_then_becomes_description_error_not_physical_result() -> None:
    result, _left, _right = _run(reference=_socket(0, malformed_index=3))

    assert result.outcome == "INJECTED_ONE_SHOT_COMPLETED"
    assert result.one_shot_result is not None
    assert result.one_shot_result.outcome == "QUALIFICATION_ERROR"
    assert len(result.one_shot_result.frame_errors) == 1
    assert result.one_shot_result.frame_errors[0].physical_decision_affected is False
    assert result.physical_hypothesis_state == "NOT_EVALUATED"
    assert result.byte_release.all_transient_snd_inputs_cleared is True


def test_result_is_strict_finite_json_and_contains_no_rf_payload() -> None:
    result, _left, _right = _run()
    value = asdict(result)

    _assert_finite(value)
    assert json.dumps(value, allow_nan=False, default=str)
    assert not set(_walk_keys(value)) & f2529._FORBIDDEN_RECEIPT_KEYS
    assert value["raw_rf_persistence"] == "ZERO"
    assert value["byte_release"]["raw_rf_persistence"] == "ZERO"


def test_module_has_no_network_surface_or_public_runtime_overrides() -> None:
    source = inspect.getsource(f2529)
    private_signature = inspect.signature(f2529._run_injected_phase_aware)

    assert "import websocket" not in source
    assert "urlopen" not in source
    assert "requests." not in source
    assert "run_live" not in source
    assert "live_authorised" not in private_signature.parameters
    assert "endpoint" not in private_signature.parameters
    assert "frequency" not in private_signature.parameters
    assert "threshold" not in private_signature.parameters
    assert "window" not in private_signature.parameters
    assert set(f2529.__all__) == {
        "F2529Assessment",
        "F2529Envelope",
        "F2529Exit",
        "F2529RunResult",
        "assess",
        "build_envelope",
    }
