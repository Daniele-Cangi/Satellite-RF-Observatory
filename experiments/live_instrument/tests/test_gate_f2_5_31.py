"""Offline open-handle lifecycle tests for Gate F2.5.31."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict
import inspect
import json
import math
import struct
import time

import numpy as np

from experiments.live_instrument import kiwi_gate_f2 as f2
from experiments.live_instrument import kiwi_gate_f2_5_17 as f2517
from experiments.live_instrument import kiwi_gate_f2_5_20 as f2520
from experiments.live_instrument import kiwi_gate_f2_5_27 as f2527
from experiments.live_instrument import kiwi_gate_f2_5_29 as f2529
from experiments.live_instrument import kiwi_gate_f2_5_31 as f2531


SAMPLE_RATE_HZ = 12_000.0
SAMPLE_COUNT = 512
FRAME_DURATION_NS = round(SAMPLE_COUNT * 1_000_000_000 / SAMPLE_RATE_HZ)
FRAME_COUNT = 100


def _snd(
    sequence: int,
    start_ns: int,
    *,
    tone_hz: float | None,
) -> bytes:
    raw_time = start_ns % f2527.GPS_WEEK_NS
    header = (
        struct.pack("<BI", 0x08, sequence)
        + b"\x00\x00"
        + struct.pack(
            "<BBII",
            103,
            0,
            raw_time // 1_000_000_000,
            raw_time % 1_000_000_000,
        )
    )
    if tone_hz is None:
        complex_samples = np.zeros(SAMPLE_COUNT, dtype=np.complex64)
    else:
        offset = (sequence - 1) * SAMPLE_COUNT
        sample_index = offset + np.arange(SAMPLE_COUNT)
        complex_samples = 12_000.0 * np.exp(
            2j * np.pi * tone_hz * sample_index / SAMPLE_RATE_HZ
        )
    words = np.empty(SAMPLE_COUNT * 2, dtype=">i2")
    words[0::2] = np.rint(complex_samples.real).astype(np.int16)
    words[1::2] = np.rint(complex_samples.imag).astype(np.int16)
    return b"SND" + header + words.tobytes()


class _Socket:
    def __init__(
        self,
        channel: int,
        *,
        tone_hz: float | None = 1_500.0,
        badp: int = 0,
        sequence_gap_at: int | None = None,
        arrival_offset_ns: int = 0,
    ) -> None:
        last_a1_arrival = time.monotonic_ns() - 20_000_000 + arrival_offset_ns
        first_arrival = last_a1_arrival - 7 * FRAME_DURATION_NS
        messages: list[tuple[int, bytes]] = [
            (
                first_arrival - FRAME_DURATION_NS,
                (
                    f"MSG badp={badp} is_local={channel},0,0 "
                    "audio_rate=12000 sample_rate=12000"
                ).encode(),
            )
        ]
        for index in range(FRAME_COUNT):
            sequence = index + 1
            if sequence_gap_at is not None and sequence >= sequence_gap_at:
                sequence += 1
            messages.append(
                (
                    first_arrival + index * FRAME_DURATION_NS,
                    _snd(
                        sequence,
                        100_000_000_000 + index * FRAME_DURATION_NS,
                        tone_hz=tone_hz,
                    ),
                )
            )
        self.leases = [
            f2529._InjectedFrameLease(2, arrival, bytearray(payload))
            for arrival, payload in messages
        ]
        self.remaining = deque(self.leases)
        self.sent: list[str] = []
        self.timeout: float | None = None
        self.closed = False

    def settimeout(self, value: float) -> None:
        self.timeout = value

    def send(self, command: str) -> None:
        if self.closed:
            raise RuntimeError("send after close")
        self.sent.append(command)

    def recv_data_frame(self, *, control_frame: bool):
        assert control_frame is True
        if self.closed:
            raise RuntimeError("receive after close")
        frame = self.remaining.popleft()
        return frame.opcode, frame

    def close(self) -> None:
        self.closed = True
        for lease in self.remaining:
            if isinstance(lease.payload, bytearray):
                lease.payload[:] = b"\x00" * len(lease.payload)
            lease.payload = None
            lease.released = True


def _run(
    reference: _Socket | None = None,
    perturbed: _Socket | None = None,
):
    left = reference or _Socket(0)
    right = perturbed or _Socket(1, arrival_offset_ns=1_000_000)
    result = f2531._run_open_handle_injected(
        reference_socket=left,
        perturbed_socket=right,
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


def test_parent_failure_is_repaired_by_one_outer_owner_plan() -> None:
    assessment = f2531.assess()

    assert assessment.exit is f2531.F2531Exit.OPEN_HANDLE_SUCCESSOR_MATERIALIZED_OFFLINE
    assert assessment.plan is not None
    assert assessment.parent_source_hash_matches is True
    assert assessment.parent_audit_ready is True
    assert assessment.integration_surface_matches is True
    assert assessment.one_outer_owner is True
    assert assessment.internal_retune_only is True
    assert assessment.no_public_execution_surface is True
    assert assessment.live_execution_authorised is False
    assert assessment.blockers == ()
    assert assessment.plan.public_runtime_overrides == ()


def test_handles_remain_open_through_discovery_and_both_command_boundaries() -> None:
    result, reference, perturbed = _run()
    setup = f2517.setup_commands(f2520.SELECTED_BOOTSTRAP_CENTER_HZ, 12_000.0)

    assert result.outcome == "OPEN_HANDLE_BOUNDARIES_WITNESSED_OFFLINE"
    assert [item.state for item in result.phases] == [
        "SATISFIED",
        "SATISFIED",
        "SATISFIED",
        "SATISFIED",
        "SATISFIED",
        "NOT_EVALUATED",
        "NOT_EVALUATED",
    ]
    assert result.discovery is not None
    assert result.discovery.state == "ONE_FEATURE_ADMITTED"
    assert len(result.command_receipts) == 2
    assert all(item.perturbed_handle_open_at_send for item in result.command_receipts)
    assert all(item.reference_retune_command_count == 0 for item in result.command_receipts)
    assert {item.transition for item in result.boundary_receipts} == {
        "A1_TO_B",
        "B_TO_A2",
    }
    assert all(item.state == "BOUNDARY_WITNESSED" for item in result.boundary_receipts)
    assert all(item.state == "SATISFIED" for item in result.session_continuity)
    assert reference.sent == [f2529.AUTH_COMMAND, *setup]
    assert perturbed.sent[: 1 + len(setup)] == [f2529.AUTH_COMMAND, *setup]
    assert perturbed.sent[-2:] == [
        f2._tune_command(f2520.SELECTED_BOOTSTRAP_CENTER_HZ + 750.0),
        f2._tune_command(f2520.SELECTED_BOOTSTRAP_CENTER_HZ),
    ]
    assert reference.closed is True and perturbed.closed is True


def test_internal_discovery_runs_before_any_retune_and_sees_open_handles(
    monkeypatch,
) -> None:
    reference = _Socket(0)
    perturbed = _Socket(1, arrival_offset_ns=1_000_000)
    original = f2531._discover_one_feature
    observed: list[tuple[bool, bool, int, int]] = []
    retained: list[np.ndarray] = []

    def wrapped(left, right):
        observed.append(
            (reference.closed, perturbed.closed, len(reference.sent), len(perturbed.sent))
        )
        retained.append(left[0].samples)
        return original(left, right)

    monkeypatch.setattr(f2531, "_discover_one_feature", wrapped)
    result, _left, _right = _run(reference, perturbed)

    setup_command_count = 1 + len(
        f2517.setup_commands(f2520.SELECTED_BOOTSTRAP_CENTER_HZ, 12_000.0)
    )
    assert result.outcome == "OPEN_HANDLE_BOUNDARIES_WITNESSED_OFFLINE"
    assert observed == [(False, False, setup_command_count, setup_command_count)]
    assert retained and np.all(retained[0] == 0)
    assert result.cleanup.all_iq_zeroized is True


def test_no_feature_stops_before_retune_but_outer_finally_still_closes() -> None:
    result, reference, perturbed = _run(_Socket(0, tone_hz=None), _Socket(1, tone_hz=None))

    assert result.outcome == "NO_FALSIFIABLE_INTERVENTION"
    assert result.discovery is not None
    assert result.discovery.state == "NO_FEATURE_ADMITTED"
    assert result.command_receipts == ()
    assert result.boundary_receipts == ()
    assert result.phases[2].state == "UNSATISFIED"
    assert all(item.state == "NOT_EVALUATED" for item in result.phases[3:])
    assert reference.closed is True and perturbed.closed is True
    assert result.cleanup.socket_close_count == 2
    assert result.cleanup.all_iq_zeroized is True


def test_explicit_rejection_is_not_a_qualification_error_or_physical_result() -> None:
    result, reference, perturbed = _run(_Socket(0), _Socket(1, badp=5))

    assert result.outcome == "CAPABILITY_REJECTED"
    assert result.branch_open_receipts[1].state == "CAPABILITY_REJECTED"
    assert result.phases[0].state == "UNSATISFIED"
    assert all(item.state == "NOT_EVALUATED" for item in result.phases[1:])
    assert result.physical_hypothesis_state == "NOT_EVALUATED"
    assert reference.closed is True and perturbed.closed is True
    assert result.cleanup.frame_lease_count == result.cleanup.frame_release_count


def test_full_session_sequence_gap_invalidates_return_boundary() -> None:
    result, _reference, _perturbed = _run(
        _Socket(0),
        _Socket(1, sequence_gap_at=45, arrival_offset_ns=1_000_000),
    )

    assert result.outcome == "INTERVENTION_INVALID"
    assert len(result.boundary_receipts) == 2
    assert result.boundary_receipts[1].state == "BOUNDARY_WITNESSED"
    assert result.session_continuity[1].state == "UNSATISFIED"
    assert result.session_continuity[1].sequence_gap_count == 1
    assert result.phases[4].state == "UNSATISFIED"
    assert result.physical_hypothesis_state == "NOT_EVALUATED"


def test_cleanup_releases_consumed_leases_zeroizes_iq_and_returns_strict_json() -> None:
    result, reference, perturbed = _run()
    value = asdict(result)

    assert result.cleanup.socket_count == result.cleanup.socket_close_count == 2
    assert result.cleanup.frame_lease_count == result.cleanup.frame_release_count
    assert result.cleanup.decoded_frame_count > 16
    assert result.cleanup.decoded_sample_count > 16 * SAMPLE_COUNT
    assert result.cleanup.all_iq_zeroized is True
    assert result.cleanup.transient_raw_references_after_return == 0
    assert all(lease.released and lease.payload is None for lease in reference.leases)
    assert all(lease.released and lease.payload is None for lease in perturbed.leases)
    _assert_finite(value)
    assert json.dumps(value, allow_nan=False, default=str)
    assert not set(_walk_keys(value)) & f2531._FORBIDDEN_RECEIPT_KEYS
    assert value["raw_rf_persistence"] == "ZERO"


def test_private_surface_has_no_callbacks_controls_network_or_authority() -> None:
    source = inspect.getsource(f2531)
    signature = inspect.signature(f2531._run_open_handle_injected)

    assert set(signature.parameters) == {"reference_socket", "perturbed_socket"}
    assert "callback" not in signature.parameters
    assert "endpoint" not in signature.parameters
    assert "frequency" not in signature.parameters
    assert "threshold" not in signature.parameters
    assert "live_authorised" not in signature.parameters
    assert "import websocket" not in source
    assert "urlopen" not in source
    assert "requests." not in source
    assert "def run_reviewed_once" not in source
    assert "run_reviewed_once" not in f2531.__all__
