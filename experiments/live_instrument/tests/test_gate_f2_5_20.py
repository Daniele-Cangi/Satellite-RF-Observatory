"""Offline tests for the Gate F2.5.20 prospective vertical seam."""

from __future__ import annotations

from dataclasses import dataclass, FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import inspect
import json
from pathlib import Path
import struct
from threading import Lock

import numpy as np
import pytest
import websocket

from experiments.live_instrument import kiwi_gate_f2 as f2
from experiments.live_instrument import kiwi_gate_f2_3 as f23
from experiments.live_instrument import kiwi_gate_f2_4 as f24
from experiments.live_instrument import kiwi_gate_f2_5 as f25
from experiments.live_instrument import kiwi_gate_f2_5_20 as f2520
from experiments.live_instrument import kiwi_probe as kiwi


NOW = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)
PLAN_HASH = "9" * 64


class _Frame:
    def __init__(self, data: bytes):
        self.data = data


class _Socket:
    def __init__(self, role: str, *, reject: bool = False) -> None:
        channel = 7 if role == "reference" else 8
        sequence = 17 if role == "reference" else 29
        self.frames = (
            [b"MSG badp=5"]
            if reject
            else [_msg(channel), _snd(sequence=sequence)]
        )
        self.sent: list[str] = []
        self.closed = False

    def connect(self, *args: object, **kwargs: object) -> "_Socket":
        del args, kwargs
        return self

    def send(self, command: str) -> None:
        self.sent.append(command)

    def recv_data_frame(self, control_frame: bool = False) -> tuple[int, _Frame]:
        assert control_frame
        if not self.frames:
            raise ConnectionError("synthetic stream exhausted")
        return websocket.ABNF.OPCODE_BINARY, _Frame(self.frames.pop(0))

    def close(self) -> None:
        self.closed = True


class _Provider:
    def __init__(self, *, reject_perturbed: bool = False) -> None:
        self.reject_perturbed = reject_perturbed
        self.sockets: list[_Socket] = []
        self.calls: list[str] = []
        self._lock = Lock()

    def __call__(self, endpoint: object, role: str):  # type: ignore[no-untyped-def]
        del endpoint
        socket = _Socket(
            role,
            reject=self.reject_perturbed and role == "perturbed",
        )
        with self._lock:
            self.calls.append(role)
            self.sockets.append(socket)
        return socket.connect


def _msg(channel: int) -> bytes:
    return (
        f"MSG is_local={channel},0,0 badp=0 audio_rate=12000 sample_rate=12000"
    ).encode("ascii")


def _snd(*, sequence: int) -> bytes:
    return b"SND" + (
        struct.pack("<BI", 0x08, sequence)
        + struct.pack(">H", 1_000)
        + struct.pack("<BBII", 0, 0, 100_000, 250_000_000)
        + struct.pack(">hhhh", 100, -100, 200, -200)
    )


def _artifact(
    role: str,
    phase: str,
    *,
    sequence: int,
    channel_id: str,
) -> f24._MemoryArtifact:
    samples = np.ones(12_000, dtype=np.complex64)
    start = datetime.now(timezone.utc) - timedelta(seconds=1.2)
    end = start + timedelta(seconds=1.0)
    block = kiwi.IQBlock(
        start,
        end,
        samples,
        -70.0,
        0,
        True,
        False,
        sequence,
        end + timedelta(seconds=0.1),
    )
    capture = kiwi.KiwiCapture(
        f2520.selected_endpoint(),
        f2520.SELECTED_BOOTSTRAP_CENTER_HZ,
        12_000.0,
        {},
        (block,),
        block.arrived_at,  # type: ignore[arg-type]
        block.arrived_at,  # type: ignore[arg-type]
    )
    prefix = "a" if role == "reference" else "b"
    return f24._MemoryArtifact(
        capture,
        (prefix + f"{sequence:x}").ljust(64, "0"),
        int(samples.nbytes),
        channel_id,
        role,
        phase,
        f2520.SELECTED_BOOTSTRAP_CENTER_HZ,
    )


def _artifacts(phase: str = "DISCOVERY_A") -> f24._DualArtifacts:
    reference = _artifact(
        "reference", phase, sequence=101, channel_id="rx:7"
    )
    perturbed = _artifact(
        "perturbed", phase, sequence=211, channel_id="rx:8"
    )
    return f24._DualArtifacts(
        {phase: reference},
        {phase: perturbed},
        reference.capture.blocks,
        perturbed.capture.blocks,
    )


def _qualified(provider: _Provider | None = None) -> f2520.F2520Qualification:
    return f2520.qualify_selected_capability_injected(
        connector_provider=provider or _Provider(),
        websocket_module=websocket,
        capture_dual=lambda *_args, **_kwargs: _artifacts(),
    )


def _geometry() -> f24._PlanGeometry:
    target = f2._FeatureGeometry(
        1_000.0,
        20.0,
        (-0.2, -0.1, 0.2, 0.8, 0.2, -0.1, -0.2),
        (7.0, 7.2, 0.2),
        (7.0, 9.0),
        20.0,
        0.9,
    )
    witness = f2._FeatureGeometry(
        -1_200.0,
        20.0,
        (-0.1, 0.0, 0.3, 0.9, 0.3, 0.0, -0.1),
        (8.0, 8.1, 0.1),
        (8.0, 10.0),
        20.0,
        0.92,
    )
    return f24._PlanGeometry(
        target,
        witness,
        750.0,
        20.0,
        10.0,
        1_750.0,
        625.0,
        -875.0,
        (1.0,),
    )


def _phase(
    phase: f25.F25Phase,
    state: f25.F25PhaseState,
    hashes: tuple[str, ...] = (),
) -> f25.PhaseReceipt:
    return f25.PhaseReceipt(
        f2520.SELECTED_ENDPOINT_IDENTITY,
        phase,
        state,
        NOW,
        NOW,
        "synthetic offline phase",
        hashes,
        (),
    )


@dataclass(frozen=True, slots=True)
class _FakePlan:
    discovery_artifact_hashes: tuple[str, str]
    plan_hash: str
    center_a_hz: float
    delta_f_hz: float
    a1_duration_s: float
    settling_duration_s: float
    frozen_at: datetime


@dataclass(frozen=True, slots=True)
class _FakeSegmentReceipt:
    artifact_hash: str


@dataclass(frozen=True, slots=True)
class _FakeConfirmation:
    receipts: tuple[_FakeSegmentReceipt, ...]


def _walk_keys(value: object) -> tuple[str, ...]:
    if isinstance(value, dict):
        return tuple(str(key) for key in value) + tuple(
            key for item in value.values() for key in _walk_keys(item)
        )
    if isinstance(value, list):
        return tuple(key for item in value for key in _walk_keys(item))
    return ()


def test_parent_outcome_is_hash_bound_and_selects_only_its_live_winner() -> None:
    assert f2520.verify_parent_outcome()
    assert f2520.PARENT_OUTCOME_ARTIFACT.stat().st_size == 186_920
    endpoint = f2520.selected_endpoint()
    assert f"{endpoint.host.lower()}:{endpoint.port}" == (
        f2520.SELECTED_ENDPOINT_IDENTITY
    )


def test_envelope_freezes_question_controls_thresholds_and_zero_retry() -> None:
    envelope = f2520.build_envelope(created_at=NOW)

    assert envelope.selected_endpoint_source == (
        "FROZEN_GATE_F2_5_19_FIRST_AND_ONLY_READY_PAIR"
    )
    assert envelope.bootstrap_center_role == "QUALIFICATION_BOOTSTRAP_NOT_FEATURE"
    assert envelope.phase_order == f25.PHASE_ORDER
    assert envelope.qualification_freshness == (
        "REQUALIFY_IN_SAME_SESSION_BEFORE_DISCOVERY"
    )
    assert envelope.prefreeze_retry_budget == 0
    assert envelope.postfreeze_retry_budget == 0
    assert envelope.waterfall_role == "ABSENT_FROM_CAUSAL_PATH"
    assert envelope.ext_api_role == "DESCRIPTIVE_HINT_UNUSED"
    assert envelope.predefined_controls == (
        "wrong_sign_position",
        "wrong_magnitude_position",
        "off_feature_position",
        "A2_return",
        "reference_command_ledger_empty",
    )
    assert not envelope.live_execution_authorised
    assert envelope.raw_rf_persistence == "ZERO"
    with pytest.raises(FrozenInstanceError):
        envelope.prefreeze_retry_budget = 1  # type: ignore[misc]


def test_corrected_pair_is_requalified_before_any_discovery() -> None:
    provider = _Provider()
    qualification = _qualified(provider)

    assert isinstance(qualification.result, f25._TopologyContext)
    receipt = qualification.result.phase_receipt
    assert provider.calls.count("reference") == 1
    assert provider.calls.count("perturbed") == 1
    assert receipt.state is f25.F25PhaseState.SATISFIED
    assert receipt.ext_api_hint is None
    assert receipt.direct_reference_opened
    assert receipt.direct_perturbed_opened
    assert len(receipt.atomic_branch_receipts) == 2
    assert ("status_precondition", "NONE") in receipt.properties
    assert ("waterfall_requested", "FALSE") in receipt.properties
    assert ("both_streams_continuous", "TRUE") in receipt.properties
    assert all("SET keepalive" not in socket.sent for socket in provider.sockets)
    qualification.result.close()
    assert all(socket.closed for socket in provider.sockets)


def test_explicit_second_branch_rejection_never_enters_discovery() -> None:
    provider = _Provider(reject_perturbed=True)
    qualification = _qualified(provider)

    assert isinstance(qualification.result, f25.PhaseReceipt)
    assert qualification.result.state is f25.F25PhaseState.CAPABILITY_REJECTED
    assert qualification.result.direct_reference_attempted
    assert qualification.result.direct_perturbed_attempted
    assert not qualification.result.direct_perturbed_opened


def test_discovery_failure_blocks_every_downstream_phase_and_closes_receipt(
    tmp_path: Path,
) -> None:
    provider = _Provider()
    receipt_path = tmp_path / "f2520-discovery-stop.jsonl"

    result = f2520.execute_prospective_injected(
        qualifier=lambda: _qualified(provider),
        receipt_path=receipt_path,
        discover=lambda *_args: _phase(
            f25.F25Phase.LOCAL_IQ_FEATURE_DISCOVERY,
            f25.F25PhaseState.UNSATISFIED,
        ),
    )

    assert result.physical_result.outcome is (
        f25.F25Outcome.NO_FALSIFIABLE_INTERVENTION
    )
    states = {
        receipt.phase: receipt.state
        for receipt in result.physical_result.phase_receipts
    }
    assert states[f25.F25Phase.LOCAL_IQ_FEATURE_DISCOVERY] is (
        f25.F25PhaseState.UNSATISFIED
    )
    assert states[f25.F25Phase.PER_CHANNEL_RETUNE_QUALIFICATION] is (
        f25.F25PhaseState.NOT_EVALUATED
    )
    assert states[f25.F25Phase.PLAN_FREEZE] is f25.F25PhaseState.NOT_EVALUATED
    assert states[f25.F25Phase.ONE_CONFIRMATION] is (
        f25.F25PhaseState.NOT_EVALUATED
    )
    assert result.receipt_artifact.state.value == "COMPLETE"
    assert result.receipt_artifact.raw_rf_persistence == "ZERO"
    assert all(socket.closed for socket in provider.sockets)


def test_complete_vertical_orders_new_discovery_retune_freeze_and_one_confirmation(
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    provider = _Provider()
    hashes = ("c" * 64, "d" * 64)
    discovery = f25._DiscoveryContext(
        _artifacts(),
        f25._DiscoverySelection(_geometry(), hashes),
        _phase(
            f25.F25Phase.LOCAL_IQ_FEATURE_DISCOVERY,
            f25.F25PhaseState.SATISFIED,
            hashes,
        ),
    )
    retune = f25._RetuneQualification(
        1,
        f2.FeatureMatch(True, -1_950.0, -1_950.0, 8.0, 0.9, "synthetic"),
        _phase(
            f25.F25Phase.PER_CHANNEL_RETUNE_QUALIFICATION,
            f25.F25PhaseState.SATISFIED,
            ("e" * 64,),
        ),
        None,  # type: ignore[arg-type]
    )
    plan = _FakePlan(
        hashes,
        PLAN_HASH,
        f2520.SELECTED_BOOTSTRAP_CENTER_HZ,
        750.0,
        3.0,
        0.8,
        NOW,
    )
    confirmation = _FakeConfirmation(
        (_FakeSegmentReceipt("f" * 64), _FakeSegmentReceipt("1" * 64))
    )
    physical = replace(
        f24._terminal_before_plan(
            f23.F23Outcome.AMBIGUOUS,
            "EXPERIMENT",
            "synthetic evaluated outcome",
            (),
        ),
        plan_hash=PLAN_HASH,
    )

    result = f2520.execute_prospective_injected(
        qualifier=lambda: calls.append("dual-SND") or _qualified(provider),
        receipt_path=tmp_path / "f2520-complete.jsonl",
        discover=lambda *_args: calls.append("discovery") or discovery,
        qualify_retune=lambda *_args: calls.append("retune") or retune,
        freeze_plan=lambda *_args, **_kwargs: calls.append("freeze") or plan,
        capture_dual=lambda *_args, **_kwargs: calls.append("confirmation")
        or confirmation,
        evaluate_confirmation=lambda *_args: calls.append("evaluate") or physical,
    )

    assert calls == [
        "dual-SND",
        "discovery",
        "retune",
        "freeze",
        "confirmation",
        "evaluate",
    ]
    assert result.physical_result.outcome is f25.F25Outcome.AMBIGUOUS
    assert result.physical_result.plan_hash == PLAN_HASH
    assert tuple(item.phase for item in result.physical_result.phase_receipts) == (
        f25.F25Phase.DIRECT_DUAL_SND_QUALIFICATION,
        f25.F25Phase.LOCAL_IQ_FEATURE_DISCOVERY,
        f25.F25Phase.PER_CHANNEL_RETUNE_QUALIFICATION,
        f25.F25Phase.PLAN_FREEZE,
        f25.F25Phase.ONE_CONFIRMATION,
    )
    assert result.physical_result.phase_receipts[-1].properties == (
        ("postfreeze_retry_count", "0"),
    )
    assert all(socket.closed for socket in provider.sockets)


def test_terminal_json_contains_no_rf_payload_or_non_finite_number(
    tmp_path: Path,
) -> None:
    result = f2520.execute_prospective_injected(
        qualifier=lambda: _qualified(),
        receipt_path=tmp_path / "f2520-strict.jsonl",
        discover=lambda *_args: _phase(
            f25.F25Phase.LOCAL_IQ_FEATURE_DISCOVERY,
            f25.F25PhaseState.UNSATISFIED,
        ),
    )
    documents = tuple(
        json.loads(
            line,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )
        for line in Path(result.receipt_artifact.path).read_text().splitlines()
    )
    keys = set(_walk_keys(list(documents)))

    assert not keys & {
        "frames",
        "iq",
        "iq_samples",
        "raw_body",
        "raw_frame",
        "samples",
        "stft",
        "waterfall",
    }
    assert documents[-1]["event"] == "gate_f2_5_3_1_receipt_artifact_terminal"
    assert documents[-1]["payload"]["physical_decision_affected"] is False


def test_separate_authority_can_be_bound_as_the_first_receipt_event(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "f2520-authority-first.jsonl"
    result = f2520.execute_prospective_injected(
        qualifier=lambda: _qualified(),
        receipt_path=receipt_path,
        discover=lambda *_args: _phase(
            f25.F25Phase.LOCAL_IQ_FEATURE_DISCOVERY,
            f25.F25PhaseState.UNSATISFIED,
        ),
        authority_event=(
            "gate_f2_5_21_authority_envelope_frozen",
            {"authority_envelope_hash": "a" * 64},
        ),
    )
    documents = tuple(
        json.loads(line)
        for line in Path(result.receipt_artifact.path).read_text().splitlines()
    )

    assert documents[0]["event"] == "gate_f2_5_21_authority_envelope_frozen"
    assert documents[0]["payload"]["authority_envelope_hash"] == "a" * 64
    assert documents[1]["event"] == "gate_f2_5_20_prospective_envelope"


def test_gate_remains_offline_and_requires_a_postcommit_seal() -> None:
    source = inspect.getsource(f2520)
    qualifier = inspect.signature(f2520.qualify_selected_capability_injected)
    execution = inspect.signature(f2520.execute_prospective_injected)
    assessment = f2520.assess_gate_f2_5_20()

    assert qualifier.parameters["connector_provider"].default is inspect.Parameter.empty
    assert qualifier.parameters["websocket_module"].default is inspect.Parameter.empty
    assert execution.parameters["qualifier"].default is inspect.Parameter.empty
    assert "create_connection" not in source
    assert "import websocket" not in source
    assert not hasattr(f2520, "run")
    assert not hasattr(f2520, "main")
    assert assessment.exit is (
        f2520.F2520Exit.PROSPECTIVE_VERTICAL_MATERIALIZED_OFFLINE
    )
    assert assessment.parent_outcome_hash_matches
    assert assessment.corrected_dual_snd_reused
    assert assessment.discovery_is_new_and_ephemeral
    assert assessment.retune_uses_witness_before_target
    assert assessment.confirmation_is_postfreeze_and_single
    assert assessment.zero_retry
    assert assessment.post_commit_review_required
    assert not assessment.live_execution_authorised
    assert assessment.raw_rf_persistence == "ZERO"
