"""Offline physical-response integration tests for Gate F2.5.32."""

from __future__ import annotations

from dataclasses import asdict
from functools import lru_cache
import inspect
import json
import math
import struct
import time

import numpy as np

from experiments.live_instrument import kiwi_gate_f2 as f2
from experiments.live_instrument import kiwi_gate_f2_5_17 as f2517
from experiments.live_instrument import kiwi_gate_f2_5_20 as f2520
from experiments.live_instrument import kiwi_gate_f2_5_22 as f2522
from experiments.live_instrument import kiwi_gate_f2_5_24 as f2524
from experiments.live_instrument import kiwi_gate_f2_5_27 as f2527
from experiments.live_instrument import kiwi_gate_f2_5_29 as f2529
from experiments.live_instrument import kiwi_gate_f2_5_31 as f2531
from experiments.live_instrument import kiwi_gate_f2_5_32 as f2532


SAMPLE_RATE_HZ = 12_000.0
SAMPLE_COUNT = 512
FRAME_DURATION_NS = round(SAMPLE_COUNT * 1_000_000_000 / SAMPLE_RATE_HZ)
TARGET_HZ = 492.1875
DELTA_HZ = 750.0
BIN_HZ = SAMPLE_RATE_HZ / 1024
TARGET_TONES = (
    (TARGET_HZ, 9_000.0),
    (TARGET_HZ + 4 * BIN_HZ, 4_500.0),
)
WITNESS = tuple(
    (sign * index * BIN_HZ, float(55 + (index * 37) % 70))
    for sign in (-1, 1)
    for index in range(260, 381, 6)
)


@lru_cache(maxsize=None)
def _periodic_waveform(
    tones: tuple[tuple[float, float], ...],
) -> np.ndarray:
    sample_index = np.arange(1024)
    samples = np.zeros(1024, dtype=np.complex128)
    for frequency, amplitude in tones:
        samples += amplitude * np.exp(
            2j * np.pi * frequency * sample_index / SAMPLE_RATE_HZ
        )
    return samples


def _snd(
    sequence: int,
    start_ns: int,
    tones: tuple[tuple[float, float], ...],
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
    waveform = _periodic_waveform(tones)
    # Every transport block starts at the same phase in this synthetic
    # transcript. This makes phase-window selection irrelevant to the PSD;
    # sequence/timestamp continuity is still exercised independently.
    samples = waveform[:SAMPLE_COUNT]
    words = np.empty(SAMPLE_COUNT * 2, dtype=">i2")
    words[0::2] = np.rint(samples.real).astype(np.int16)
    words[1::2] = np.rint(samples.imag).astype(np.int16)
    return b"SND" + header + words.tobytes()


class _PhaseSocket:
    def __init__(
        self,
        channel: int,
        *,
        role: str,
        hypothesis: str = "upstream",
        sequence_gap_at: int | None = None,
        arrival_offset_ns: int = 0,
    ) -> None:
        self.channel = channel
        self.role = role
        self.hypothesis = hypothesis
        self.sequence_gap_at = sequence_gap_at
        self.phase = "A1"
        self.sequence_index = 0
        self.arrival_origin = (
            time.monotonic_ns()
            - 7 * FRAME_DURATION_NS
            - 20_000_000
            + arrival_offset_ns
        )
        self.sent: list[str] = []
        self.leases: list[f2529._InjectedFrameLease] = []
        self.timeout: float | None = None
        self.closed = False
        self.metadata_sent = False

    def settimeout(self, value: float) -> None:
        self.timeout = value

    def send(self, command: str) -> None:
        if self.closed:
            raise RuntimeError("send after close")
        self.sent.append(command)
        if self.role != "perturbed":
            return
        if command == f2._tune_command(f2520.SELECTED_BOOTSTRAP_CENTER_HZ + DELTA_HZ):
            self.phase = "B"
        elif self.phase == "B" and command == f2._tune_command(
            f2520.SELECTED_BOOTSTRAP_CENTER_HZ
        ):
            self.phase = "A2"

    def _tones(self) -> tuple[tuple[float, float], ...]:
        target = TARGET_TONES
        witness = WITNESS
        if self.role == "reference" or self.phase != "B":
            if self.role == "perturbed" and self.phase == "A2" and self.hypothesis == "not_detectable":
                return witness
            return target + witness
        if self.hypothesis == "intervention_invalid":
            return tuple(
                (frequency - DELTA_HZ, amplitude)
                for frequency, amplitude in target
            ) + witness
        shifted_witness = tuple((frequency - DELTA_HZ, amplitude) for frequency, amplitude in witness)
        if self.hypothesis == "upstream" or self.hypothesis == "not_detectable":
            target_b = tuple(
                (frequency - DELTA_HZ, amplitude)
                for frequency, amplitude in target
            )
        elif self.hypothesis == "downstream":
            target_b = target
        elif self.hypothesis == "ambiguous":
            target_b = target + tuple(
                (frequency - DELTA_HZ, amplitude)
                for frequency, amplitude in target
            )
        else:
            raise AssertionError(self.hypothesis)
        return target_b + shifted_witness

    def recv_data_frame(self, *, control_frame: bool):
        assert control_frame is True
        if self.closed:
            raise RuntimeError("receive after close")
        if not self.metadata_sent:
            self.metadata_sent = True
            payload = (
                f"MSG badp=0 is_local={self.channel},0,0 "
                "audio_rate=12000 sample_rate=12000"
            ).encode()
            arrival = self.arrival_origin - FRAME_DURATION_NS
        else:
            self.sequence_index += 1
            sequence = self.sequence_index
            if self.sequence_gap_at is not None and sequence >= self.sequence_gap_at:
                sequence += 1
            payload = _snd(
                sequence,
                100_000_000_000 + self.sequence_index * FRAME_DURATION_NS,
                self._tones(),
            )
            arrival = self.arrival_origin + (self.sequence_index - 1) * FRAME_DURATION_NS
        lease = f2529._InjectedFrameLease(2, arrival, bytearray(payload))
        self.leases.append(lease)
        return 2, lease

    def close(self) -> None:
        self.closed = True


def _run(hypothesis: str = "upstream", *, gap: int | None = None):
    reference = _PhaseSocket(0, role="reference")
    perturbed = _PhaseSocket(
        1,
        role="perturbed",
        hypothesis=hypothesis,
        sequence_gap_at=gap,
        arrival_offset_ns=1_000_000,
    )
    result = f2532._run_open_handle_rf_injected(
        reference_socket=reference,
        perturbed_socket=perturbed,
    )
    return result, reference, perturbed


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


def test_plan_binds_parent_and_reuses_reviewed_thresholds() -> None:
    assessment = f2532.assess()
    mother = f2.MotherPlan()

    assert assessment.exit is f2532.F2532Exit.RF_RESPONSE_INTEGRATED_OFFLINE
    assert assessment.blockers == ()
    assert assessment.distributed_witness_reused is True
    assert assessment.target_reveal_order_enforced is True
    assert assessment.no_public_execution_surface is True
    assert assessment.live_execution_authorised is False
    assert assessment.plan is not None
    assert dict(assessment.plan.thresholds) == {
        "minimum_contrast_db": mother.minimum_contrast_db,
        "minimum_half_contrast_db": mother.minimum_half_contrast_db,
        "minimum_fingerprint_correlation": mother.minimum_fingerprint_correlation,
        "prediction_tolerance_bins": mother.prediction_tolerance_bins,
    }


def test_target_excluded_witness_admits_upstream_result() -> None:
    result, reference, perturbed = _run("upstream")

    assert result.outcome == "UPSTREAM_OF_CHANNEL_DDC_SUPPORTED"
    assert result.physical_hypothesis_state == result.outcome
    assert result.distributed_witness is not None
    assert result.distributed_witness.state == "QUALIFIED_AS_FUTURE_WITNESS"
    assert result.distributed_witness.target_bins_excluded is True
    assert result.distributed_witness.learned_orientation == -1
    assert result.frozen_target_plan is not None
    assert result.frozen_target_plan.target_B_A2_revealed_after_plan_hash is True
    matched = {item.label: item.matched for item in result.target_matches}
    assert matched["perturbed_B_upstream"] is True
    assert matched["perturbed_B_channel_fixed"] is False
    assert reference.closed is True and perturbed.closed is True


def test_valid_witness_can_support_channel_fixed_result() -> None:
    result, _reference, _perturbed = _run("downstream")
    matched = {item.label: item.matched for item in result.target_matches}

    assert result.outcome == "DOWNSTREAM_CHANNEL_FIXED_SUPPORTED"
    assert result.distributed_witness is not None
    assert result.distributed_witness.state == "QUALIFIED_AS_FUTURE_WITNESS"
    assert matched["perturbed_B_upstream"] is False
    assert matched["perturbed_B_channel_fixed"] is True


def test_both_predictions_present_is_ambiguous_not_a_vote() -> None:
    result, _reference, _perturbed = _run("ambiguous")
    matched = {item.label: item.matched for item in result.target_matches}

    assert result.outcome == "AMBIGUOUS"
    assert matched["perturbed_B_upstream"] is True
    assert matched["perturbed_B_channel_fixed"] is True
    assert result.physical_hypothesis_state == "AMBIGUOUS"


def test_witness_failure_blocks_target_reveal_as_intervention_invalid() -> None:
    result, _reference, _perturbed = _run("intervention_invalid")

    assert result.outcome == "INTERVENTION_INVALID"
    assert result.distributed_witness is not None
    assert result.distributed_witness.state == "INTERVENTION_UNRESOLVED"
    assert result.frozen_target_plan is None
    assert result.target_matches == ()
    assert result.physical_hypothesis_state == "NOT_EVALUATED"
    assert result.phases[5].state == "NOT_EVALUATED"
    assert result.phases[6].state == "NOT_EVALUATED"
    states = {item.clause: item.state for item in result.clause_receipts}
    assert states["target_matches_upstream_prediction_B"] == "NOT_EVALUATED"


def test_valid_intervention_with_failed_return_is_not_detectable() -> None:
    result, _reference, _perturbed = _run("not_detectable")

    assert result.outcome == "NOT_DETECTABLE"
    assert result.distributed_witness is not None
    assert result.distributed_witness.state == "QUALIFIED_AS_FUTURE_WITNESS"
    assert result.frozen_target_plan is not None
    assert result.physical_hypothesis_state == "NOT_EVALUATED"
    states = {item.clause: item.state for item in result.clause_receipts}
    assert states["target_returns_A2"] == "UNSATISFIED"


def test_target_match_is_never_called_before_witness_admission(monkeypatch) -> None:
    observed: list[str] = []
    original_hash = f2532._phase_hash
    original_profile = f2532._profile
    original_witness = f2522.assess_distributed_witness
    original_match = f2524._target_match

    def phase_hash(*args, **kwargs):
        observed.append("hash")
        return original_hash(*args, **kwargs)

    def profile(*args, **kwargs):
        assert observed[:6] == ["hash"] * 6
        observed.append("profile")
        return original_profile(*args, **kwargs)

    def witness(*args, **kwargs):
        assert observed[:12] == ["hash"] * 6 + ["profile"] * 6
        receipt = original_witness(*args, **kwargs)
        observed.append(f"witness:{receipt.state}")
        return receipt

    def match(*args, **kwargs):
        assert observed
        assert observed[12] == "witness:QUALIFIED_AS_FUTURE_WITNESS"
        observed.append("target")
        return original_match(*args, **kwargs)

    monkeypatch.setattr(f2532, "_phase_hash", phase_hash)
    monkeypatch.setattr(f2532, "_profile", profile)
    monkeypatch.setattr(f2522, "assess_distributed_witness", witness)
    monkeypatch.setattr(f2524, "_target_match", match)
    result, _reference, _perturbed = _run("upstream")

    assert result.outcome == "UPSTREAM_OF_CHANNEL_DDC_SUPPORTED"
    assert observed[12] == "witness:QUALIFIED_AS_FUTURE_WITNESS"
    assert observed.count("target") == 10


def test_sequence_failure_prevents_all_rf_analysis(monkeypatch) -> None:
    calls = 0

    def forbidden(**kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("RF response must not run")

    monkeypatch.setattr(f2532, "_evaluate_rf_response", forbidden)
    result, _reference, _perturbed = _run("upstream", gap=45)

    assert result.outcome == "INTERVENTION_INVALID"
    assert calls == 0
    assert result.distributed_witness is None
    assert result.target_matches == ()
    assert result.physical_hypothesis_state == "NOT_EVALUATED"


def test_cleanup_strict_json_and_private_surface() -> None:
    result, reference, perturbed = _run("upstream")
    value = asdict(result)
    signature = inspect.signature(f2532._run_open_handle_rf_injected)
    source = inspect.getsource(f2532)

    assert result.cleanup.frame_lease_count == result.cleanup.frame_release_count
    assert result.cleanup.all_iq_zeroized is True
    assert result.cleanup.transient_raw_references_after_return == 0
    assert all(item.released and item.payload is None for item in reference.leases)
    assert all(item.released and item.payload is None for item in perturbed.leases)
    _assert_finite(value)
    assert json.loads(f2532.strict_json(value))["raw_rf_persistence"] == "ZERO"
    assert not set(_walk_keys(value)) & f2531._FORBIDDEN_RECEIPT_KEYS
    assert set(signature.parameters) == {"reference_socket", "perturbed_socket"}
    assert "import websocket" not in source
    assert "urlopen" not in source
    assert "run_reviewed_once" not in source
    assert "_run_open_handle_rf_injected" not in f2532.__all__
    setup = f2517.setup_commands(f2520.SELECTED_BOOTSTRAP_CENTER_HZ, 12_000.0)
    assert reference.sent == [f2529.AUTH_COMMAND, *setup]
    assert perturbed.sent[-2:] == [
        f2._tune_command(f2520.SELECTED_BOOTSTRAP_CENTER_HZ + DELTA_HZ),
        f2._tune_command(f2520.SELECTED_BOOTSTRAP_CENTER_HZ),
    ]
