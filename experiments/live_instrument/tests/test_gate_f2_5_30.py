"""Offline post-commit sealability tests for Gate F2.5.30."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict
import inspect
import json
import math
import struct

import numpy as np

from experiments.live_instrument import kiwi_gate_f2_5_27 as f2527
from experiments.live_instrument import kiwi_gate_f2_5_28 as f2528
from experiments.live_instrument import kiwi_gate_f2_5_29 as f2529
from experiments.live_instrument import kiwi_gate_f2_5_30 as f2530


SAMPLE_RATE_HZ = 12_000.0
SAMPLE_COUNT = 512
FRAME_DURATION_NS = round(SAMPLE_COUNT * 1_000_000_000 / SAMPLE_RATE_HZ)


def _snd(sequence: int, start_ns: int) -> bytes:
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
    values = np.zeros(SAMPLE_COUNT * 2, dtype=">i2")
    return b"SND" + header + values.tobytes()


class _Socket:
    def __init__(self, channel: int, arrival_offset_ns: int = 0) -> None:
        messages = [
            (
                950_000_000 + arrival_offset_ns,
                (
                    f"MSG badp=0 is_local={channel},0,0 "
                    "audio_rate=12000 sample_rate=12000"
                ).encode(),
            )
        ]
        messages.extend(
            (
                1_000_000_000 + index * 50_000_000 + arrival_offset_ns,
                _snd(
                    index + 1,
                    100_000_000_000 + index * FRAME_DURATION_NS,
                ),
            )
            for index in range(8)
        )
        self.frames = deque(
            f2529._InjectedFrameLease(2, arrival, bytearray(payload))
            for arrival, payload in messages
        )
        self.sent: list[str] = []
        self.closed = False

    def settimeout(self, _value: float) -> None:
        pass

    def send(self, command: str) -> None:
        self.sent.append(command)

    def recv_data_frame(self, *, control_frame: bool):
        assert control_frame is True
        frame = self.frames.popleft()
        return frame.opcode, frame

    def close(self) -> None:
        self.closed = True


def _assert_finite(value: object) -> None:
    if isinstance(value, dict):
        for item in value.values():
            _assert_finite(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _assert_finite(item)
    elif isinstance(value, float):
        assert math.isfinite(value)


def test_reviewed_commit_source_envelope_and_audit_surface_are_exact() -> None:
    assessment = f2530.assess()

    assert assessment.exit is f2530.F2530Exit.LIVE_SURFACE_NOT_SEALABLE
    assert assessment.envelope is not None
    assert assessment.envelope.envelope_hash == f2530.AUDIT_ENVELOPE_HASH
    assert assessment.reviewed_commit_is_ancestor is True
    assert assessment.reviewed_source_git_diff_clean is True
    assert assessment.reviewed_source_hash_matches is True
    assert assessment.reviewed_parent_assessment_ready is True
    assert assessment.reviewed_parent_envelope_matches is True
    assert assessment.reviewed_integration_surface_matches is True
    assert assessment.audit_surface_matches is True
    assert assessment.audit_envelope_hash_matches is True
    assert assessment.blockers == ()


def test_clauses_separate_reusable_timing_from_unsealable_control_lifetime() -> None:
    assessment = f2530.assess()
    states = {item.clause: item.state for item in assessment.clauses}

    assert tuple(item.clause for item in assessment.clauses) == f2530.CLAUSE_ORDER
    assert states["post_commit_lineage_exact"] == "SATISFIED"
    assert states["relative_dual_snd_boundary_reusable"] == "SATISFIED"
    assert states["channels_open_through_discovery"] == "UNSATISFIED"
    assert states["channels_open_through_a1_b_a2"] == "UNSATISFIED"
    assert states["retune_callback_has_control_handle"] == "UNSATISFIED"
    assert states["public_authority_surface_sealable"] == "NOT_EVALUATED"
    assert assessment.authority_surface_sealable is False
    assert assessment.live_execution_authorised is False


def test_both_sockets_are_already_closed_inside_discovery_and_retune_callbacks() -> None:
    reference = _Socket(0)
    perturbed = _Socket(1, 1_000_000)
    observed: list[tuple[str, bool, bool]] = []

    def discovery(_view: object) -> f2528.DiscoveryProbeResult:
        observed.append(("discovery", reference.closed, perturbed.closed))
        return f2528.DiscoveryProbeResult(True, (), "synthetic eligible view")

    def retune(_view: object) -> f2528.RetuneProbeResult:
        observed.append(("retune", reference.closed, perturbed.closed))
        return f2528.RetuneProbeResult(False, (), (), "no live control handle")

    result = f2529._run_injected_phase_aware(
        reference_socket=reference,
        perturbed_socket=perturbed,
        discovery_probe=discovery,
        retune_probe=retune,
    )

    assert result.outcome == "INJECTED_ONE_SHOT_COMPLETED"
    assert observed == [
        ("discovery", True, True),
        ("retune", True, True),
    ]
    assert result.one_shot_result is not None
    assert result.one_shot_result.outcome == "INTERVENTION_NOT_QUALIFIED"
    assert result.physical_hypothesis_state == "NOT_EVALUATED"


def test_source_order_proves_collectors_finish_before_one_shot() -> None:
    collector = inspect.getsource(f2529._collect_injected_branch)
    wrapper = inspect.getsource(f2529._run_injected_phase_aware)

    assert collector.index("finally:") < collector.index("socket.close()")
    assert wrapper.index("reference_future.result()") < wrapper.index(
        "f2528.run_one_shot_injected("
    )
    assert wrapper.index("perturbed_future.result()") < wrapper.index(
        "f2528.run_one_shot_injected("
    )
    assert f2530._collector_closes_before_return() is True
    assert f2530._one_shot_after_collections() is True
    assert f2530._callback_has_control_handle() is False


def test_no_nominal_authority_surface_is_created() -> None:
    assert not hasattr(f2530, "run_reviewed_once")
    assert f2530.build_audit_envelope().public_execution_surface_materialized is False
    assert f2530.build_audit_envelope().permitted_public_caller_overrides == (
        "live_authorised",
    )
    assert "run_reviewed_once" not in f2530.__all__


def test_source_mismatch_becomes_seal_mismatch_not_lifetime_reclassification(
    monkeypatch,
) -> None:
    monkeypatch.setattr(f2530, "current_f2529_source_sha256", lambda: "0" * 64)

    assessment = f2530.assess()

    assert assessment.exit is f2530.F2530Exit.POST_COMMIT_SEAL_MISMATCH
    assert assessment.envelope is None
    assert assessment.reviewed_source_hash_matches is False
    assert assessment.authority_surface_sealable is False
    assert assessment.live_execution_authorised is False


def test_assessment_is_strict_finite_json_without_rf() -> None:
    value = asdict(f2530.assess())

    _assert_finite(value)
    encoded = json.dumps(value, allow_nan=False, default=str, sort_keys=True)
    assert "NaN" not in encoded
    assert "Infinity" not in encoded
    assert value["raw_rf_persistence"] == "ZERO"
    assert value["envelope"]["raw_rf_persistence"] == "ZERO"


def test_audit_module_has_no_network_connector_writer_or_execution_surface() -> None:
    source = inspect.getsource(f2530)

    assert "import websocket" not in source
    assert "urlopen" not in source
    assert "requests." not in source
    assert "create_connection" not in source
    assert "TerminalReceiptEmitter" not in source
    assert "def run_reviewed_once" not in source
    assert "session_receipts" not in source
