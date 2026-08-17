"""Offline tests for the phase-aware Gate F2.5.17 SND control path."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import inspect
import json
import struct

import pytest
import websocket

from experiments.live_instrument import kiwi_gate_f2 as f2
from experiments.live_instrument import kiwi_gate_f2_5_8 as f258
from experiments.live_instrument import kiwi_gate_f2_5_12 as f2512
from experiments.live_instrument import kiwi_gate_f2_5_17 as f2517
from experiments.live_instrument import kiwi_probe as kiwi
from experiments.live_instrument.models import strict_json_value


ENDPOINT = kiwi.KiwiEndpoint("fixture", "fixture.invalid", 8073)
STATUS = {"name": "fixture"}


class _Frame:
    def __init__(self, data: bytes):
        self.data = data


class _Socket:
    def __init__(self, frames: list[bytes | tuple[int, bytes] | Exception]) -> None:
        self.frames = list(frames)
        self.sent: list[str] = []
        self.closed = False

    def send(self, command: str) -> None:
        self.sent.append(command)

    def recv_data_frame(self, control_frame: bool = False) -> tuple[int, _Frame]:
        assert control_frame
        if not self.frames:
            raise ConnectionError("synthetic stream exhausted")
        item = self.frames.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, tuple):
            opcode, payload = item
        else:
            opcode, payload = websocket.ABNF.OPCODE_BINARY, item
        return opcode, _Frame(payload)

    def close(self) -> None:
        self.closed = True


class _Connector:
    def __init__(self, socket: _Socket):
        self.socket = socket
        self.calls = 0

    def __call__(self, *args: object, **kwargs: object) -> _Socket:
        del args, kwargs
        self.calls += 1
        return self.socket


class _Clock:
    def __init__(self, step_s: float):
        self.value = 0.0
        self.step_s = step_s

    def __call__(self) -> float:
        current = self.value
        self.value += self.step_s
        return current


def _full_msg(channel: int = 7) -> bytes:
    return (
        f"MSG is_local={channel},0,0 badp=0 audio_rate=12000 sample_rate=12000"
    ).encode("ascii")


def _snd(*, sequence: int = 23, gps_age_s: int = 5) -> bytes:
    return b"SND" + (
        struct.pack("<BI", 0x08, sequence)
        + struct.pack(">H", 1_000)
        + struct.pack("<BBII", gps_age_s, 0, 100_000, 250_000_000)
        + struct.pack(">hhhh", 100, -100, 200, -200)
    )


def _open(socket: _Socket) -> tuple[f2517.PhaseAwareOpenResult, _Connector]:
    connector = _Connector(socket)
    result = f2517.open_channel_phase_aware_injected(
        ENDPOINT,
        "reference",
        10_000_000.0,
        STATUS,
        f2.MotherPlan(),
        connector=connector,
        websocket_module=websocket,
    )
    return result, connector


def test_pinned_header_is_exact_hash_bound_and_license_retained() -> None:
    manifest = json.loads(f2517.PINNED_MANIFEST_PATH.read_text(encoding="utf-8"))
    header = f2517.PINNED_HEADER_PATH.read_text(encoding="utf-8")

    assert sha256(f2517.PINNED_HEADER_PATH.read_bytes()).hexdigest() == (
        f2517.PINNED_HEADER_SHA256
    )
    assert manifest["commit"] == f2517.PINNED_SERVER_COMMIT
    assert manifest["git_blob"] == "3a4bc5b8674f40fa205a1f8f7a12ff7ea09e2027"
    assert manifest["size_bytes"] == 2004
    assert "GNU Library General Public" in header
    assert f2517._header_is_exact()
    assert f2517.CMD_SND_ALL == 0x1F


def test_frozen_failed_schedule_exposes_guard_but_corrected_order_does_not() -> None:
    old = (
        *f2517.f24._initial_channel_commands(10_000_000.0),
        *("SET keepalive",) * 14,
        "SET AR OK in=12000 out=44100",
    )
    corrected = (
        *f2517.setup_commands(10_000_000.0, 12_000.0),
        *("SET keepalive",) * 12,
    )

    old_simulation = f2517.simulate_pinned_guard(old)
    corrected_simulation = f2517.simulate_pinned_guard(corrected)
    assert old_simulation.guard_exposed
    assert old_simulation.setup_complete
    assert old_simulation.first_guard_exposure_command_index is not None
    assert old_simulation.first_guard_exposure_command_index < (
        old_simulation.setup_complete_command_index
    )
    assert corrected_simulation.setup_complete
    assert not corrected_simulation.guard_exposed


def test_setup_sequence_is_unique_keepalive_free_and_immutable() -> None:
    commands = f2517.setup_commands(10_000_000.0, 12_000.0)

    assert commands[0] == "SET AR OK in=12000 out=44100"
    assert "SET keepalive" not in commands
    assert len(commands) == len(set(commands))
    assert sum(command.startswith("SET mod=iq ") for command in commands) == 1
    assert sum(command.startswith("SET agc=") for command in commands) == 1
    f2517.validate_setup_commands(commands, 10_000_000.0, 12_000.0)
    with pytest.raises(ValueError, match="reordered"):
        f2517.validate_setup_commands(
            (commands[1], commands[0], *commands[2:]),
            10_000_000.0,
            12_000.0,
        )
    with pytest.raises(ValueError, match="reordered"):
        f2517.validate_setup_commands(
            (*commands, commands[-1]), 10_000_000.0, 12_000.0
        )


def test_ready_branch_emits_complete_setup_once_and_no_preset_keepalive() -> None:
    socket = _Socket([_full_msg(), _snd()])
    result, connector = _open(socket)
    receipt = result.receipt

    assert connector.calls == 1
    assert result.connection is not None
    assert receipt.integrated_receipt.state is f258.F258BranchState.READY
    assert tuple(item.phase for item in receipt.transitions) == (
        f2517.ControlPhase.AUTH_EMITTED_LOCAL,
        f2517.ControlPhase.REQUIRED_METADATA_OBSERVED,
        f2517.ControlPhase.REQUIRED_SETUP_EMITTED_LOCAL,
        f2517.ControlPhase.FIRST_SND_READY_OBSERVED,
    )
    assert socket.sent.count("SET AR OK in=12000 out=44100") == 1
    assert not any(command == "SET keepalive" for command in socket.sent)
    assert socket.sent.index("SET AR OK in=12000 out=44100") < next(
        index for index, command in enumerate(socket.sent) if command.startswith("SET mod=iq ")
    )
    assert receipt.pre_setup_keepalive_count == 0
    assert receipt.post_setup_keepalive_count == 0
    assert receipt.local_setup_emission_clause is f2512.ClauseEvaluation.SATISFIED
    assert receipt.remote_setup_acknowledgement_clause is (
        f2512.ClauseEvaluation.NOT_EVALUATED
    )
    result.connection.close()


def test_piecemeal_metadata_cannot_trigger_partial_setup_or_keepalive() -> None:
    socket = _Socket(
        [
            b"MSG badp=0",
            b"MSG is_local=7,0,0",
            b"MSG sample_rate=12000",
            b"MSG audio_rate=12000",
            _snd(),
        ]
    )
    result, _ = _open(socket)

    assert result.connection is not None
    assert socket.sent.count("SET AR OK in=12000 out=44100") == 1
    assert sum(command.startswith("SET mod=iq ") for command in socket.sent) == 1
    assert "SET keepalive" not in socket.sent
    setup = tuple(
        item
        for item in result.receipt.transitions
        if item.phase is f2517.ControlPhase.REQUIRED_SETUP_EMITTED_LOCAL
    )
    assert len(setup) == 1
    result.connection.close()


def test_repeated_metadata_does_not_repeat_setup_and_liveness_is_time_paced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(f2517.time, "monotonic", _Clock(0.3))
    socket = _Socket(
        [
            _full_msg(),
            b"MSG audio_rate=12000",
            b"MSG audio_rate=12000",
            b"MSG audio_rate=12000",
            b"MSG audio_rate=12000",
            _snd(),
        ]
    )
    result, _ = _open(socket)
    receipt = result.receipt

    assert result.connection is not None
    assert socket.sent.count("SET AR OK in=12000 out=44100") == 1
    assert sum(command.startswith("SET mod=iq ") for command in socket.sent) == 1
    assert receipt.pre_setup_keepalive_count == 0
    assert receipt.post_setup_keepalive_count == 2
    assert receipt.minimum_observed_keepalive_spacing_s is not None
    assert receipt.minimum_observed_keepalive_spacing_s >= (
        f2517.KEEPALIVE_INTERVAL_S
    )
    result.connection.close()


def test_explicit_rejection_never_promotes_setup_or_physical_absence() -> None:
    result, _ = _open(_Socket([b"MSG badp=5"]))
    receipt = result.receipt

    assert result.connection is None
    assert receipt.integrated_receipt.state is f258.F258BranchState.CAPABILITY_REJECTED
    assert receipt.local_setup_emission_clause is f2512.ClauseEvaluation.NOT_EVALUATED
    assert receipt.remote_setup_acknowledgement_clause is (
        f2512.ClauseEvaluation.NOT_EVALUATED
    )
    assert receipt.pre_setup_keepalive_count == 0
    assert tuple(item.phase for item in receipt.transitions) == (
        f2517.ControlPhase.AUTH_EMITTED_LOCAL,
        f2517.ControlPhase.TERMINATED_BEFORE_READINESS,
    )


def test_receipt_cannot_be_relabelled_as_having_a_pre_setup_keepalive() -> None:
    result, _ = _open(_Socket([b"MSG badp=5"]))

    with pytest.raises(ValueError, match="before local setup"):
        replace(result.receipt, pre_setup_keepalive_count=1)


def test_strict_receipt_has_no_rf_payload_and_no_remote_ack_inference() -> None:
    result, _ = _open(_Socket([_full_msg(), _snd()]))
    encoded = json.dumps(
        strict_json_value(result.receipt), allow_nan=False, sort_keys=True
    )

    assert '"raw_rf_persistence": "ZERO"' in encoded
    assert '"remote_setup_acknowledgement_clause": "NOT_EVALUATED"' in encoded
    for forbidden in ('"samples"', '"iq"', '"raw_frame"', '"waterfall"'):
        assert forbidden not in encoded
    assert result.connection is not None
    result.connection.close()


def test_connector_is_mandatory_and_assessment_stops_before_live_authority() -> None:
    signature = inspect.signature(f2517.open_channel_phase_aware_injected)
    source = inspect.getsource(f2517)
    assessment = f2517.assess_gate_f2_5_17()

    assert signature.parameters["connector"].default is inspect.Parameter.empty
    assert signature.parameters["websocket_module"].default is inspect.Parameter.empty
    assert "create_connection" not in source
    assert "import websocket" not in source
    assert not hasattr(f2517, "run")
    assert not hasattr(f2517, "main")
    assert assessment.exit is (
        f2517.F2517Exit.PHASE_AWARE_SND_CONTROL_MATERIALIZED_OFFLINE
    )
    assert assessment.pinned_header_hash_matches
    assert assessment.cmd_snd_all_exactly_defined
    assert assessment.frozen_failed_schedule_exceeded_guard
    assert assessment.corrected_schedule_avoids_guard
    assert assessment.keepalive_is_phase_and_time_gated
    assert assessment.local_send_is_separate_from_remote_acknowledgement
    assert assessment.connector_injection_required
    assert not assessment.live_execution_authorised
    assert assessment.raw_rf_persistence == "ZERO"
