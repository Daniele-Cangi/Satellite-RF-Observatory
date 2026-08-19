"""Offline sibling discovery-audit integration tests for Gate F2.5.35."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, replace
from hashlib import sha256
import inspect
import json
import struct
import time

import numpy as np
import pytest

from experiments.live_instrument import kiwi_gate_f2_5_22 as f2522
from experiments.live_instrument import kiwi_gate_f2_5_27 as f2527
from experiments.live_instrument import kiwi_gate_f2_5_28 as f2528
from experiments.live_instrument import kiwi_gate_f2_5_29 as f2529
from experiments.live_instrument import kiwi_gate_f2_5_31 as f2531
from experiments.live_instrument import kiwi_gate_f2_5_32 as f2532
from experiments.live_instrument import kiwi_gate_f2_5_35 as f2535
from experiments.live_instrument.models import strict_json_value
from experiments.live_instrument.tests import test_gate_f2_5_32 as f2532_fixtures


SAMPLE_RATE_HZ = 12_000.0
SAMPLE_COUNT = 512
FRAME_COUNT = f2531.PHASE_FRAME_COUNT
FRAME_DURATION_NS = round(SAMPLE_COUNT * 1_000_000_000 / SAMPLE_RATE_HZ)


def _frames(
    role: str,
    *,
    tone_hz: float | None,
) -> tuple[f2528._EphemeralDecodedFrame, ...]:
    result: list[f2528._EphemeralDecodedFrame] = []
    for index in range(FRAME_COUNT):
        offset = index * SAMPLE_COUNT
        if tone_hz is None:
            samples = np.zeros(SAMPLE_COUNT, dtype=np.complex64)
        else:
            sample_index = offset + np.arange(SAMPLE_COUNT)
            samples = (
                12_000.0
                * np.exp(2j * np.pi * tone_hz * sample_index / SAMPLE_RATE_HZ)
            ).astype(np.complex64)
        digest = sha256(
            role.encode() + index.to_bytes(2, "big") + samples.tobytes()
        ).hexdigest()
        receipt = f2527.ScalarFrameReceipt(
            digest,
            17 + 4 * SAMPLE_COUNT,
            "synthetic.invalid:8073",
            role,
            0 if role == "reference" else 1,
            index + 1,
            100 + index,
            0,
            0,
            SAMPLE_COUNT,
            SAMPLE_RATE_HZ,
            1_000_000_000 + index * FRAME_DURATION_NS,
        )
        result.append(f2528._EphemeralDecodedFrame(receipt, samples))
    return tuple(result)


def _snd(sequence: int, *, tone_hz: float | None) -> bytes:
    start_ns = 100_000_000_000 + (sequence - 1) * FRAME_DURATION_NS
    header = (
        struct.pack("<BI", 0x08, sequence)
        + b"\x00\x00"
        + struct.pack(
            "<BBII",
            103,
            0,
            start_ns // 1_000_000_000,
            start_ns % 1_000_000_000,
        )
    )
    if tone_hz is None:
        samples = np.zeros(SAMPLE_COUNT, dtype=np.complex64)
    else:
        indices = (sequence - 1) * SAMPLE_COUNT + np.arange(SAMPLE_COUNT)
        samples = 12_000.0 * np.exp(
            2j * np.pi * tone_hz * indices / SAMPLE_RATE_HZ
        )
    words = np.empty(2 * SAMPLE_COUNT, dtype=">i2")
    words[0::2] = np.rint(samples.real).astype(np.int16)
    words[1::2] = np.rint(samples.imag).astype(np.int16)
    return b"SND" + header + words.tobytes()


class _NegativeSocket:
    def __init__(self, channel: int, arrival_offset_ns: int = 0) -> None:
        first = time.monotonic_ns() - 8 * FRAME_DURATION_NS + arrival_offset_ns
        payloads: list[tuple[int, bytes]] = [
            (
                first - FRAME_DURATION_NS,
                (
                    f"MSG badp=0 is_local={channel},0,0 "
                    "audio_rate=12000 sample_rate=12000"
                ).encode(),
            )
        ]
        payloads.extend(
            (first + index * FRAME_DURATION_NS, _snd(index + 1, tone_hz=None))
            for index in range(FRAME_COUNT)
        )
        self.leases = [
            f2529._InjectedFrameLease(2, arrival, bytearray(payload))
            for arrival, payload in payloads
        ]
        self.remaining = deque(self.leases)
        self.sent: list[str] = []
        self.closed = False

    def settimeout(self, value: float) -> None:
        assert value > 0

    def send(self, command: str) -> None:
        self.sent.append(command)

    def recv_data_frame(self, *, control_frame: bool):
        assert control_frame is True
        lease = self.remaining.popleft()
        return lease.opcode, lease

    def close(self) -> None:
        self.closed = True
        for lease in self.remaining:
            if isinstance(lease.payload, bytearray):
                lease.payload[:] = b"\x00" * len(lease.payload)
            lease.payload = None
            lease.released = True


def _failing_audit(*args: object, **kwargs: object) -> f2535.ScalarDiscoveryAuditReceipt:
    del args, kwargs
    raise RuntimeError("synthetic scalar description failure")


def test_assessment_binds_frozen_sources_and_has_no_authority() -> None:
    assessment = f2535.assess()

    assert assessment.exit is f2535.F2535Exit.SCALAR_AUDIT_INTEGRATED_OFFLINE
    assert assessment.reviewed_f2534_commit == f2535.REVIEWED_F2534_COMMIT
    assert assessment.f2534_source_hash_matches is True
    assert assessment.f2532_source_hash_matches is True
    assert assessment.frozen_outcome_still_attributable is True
    assert assessment.sibling_receipt_boundary is True
    assert assessment.audit_failure_decision_independent is True
    assert assessment.thresholds_unchanged is True
    assert assessment.connector_surface_present is False
    assert assessment.live_execution_authorised is False
    assert assessment.blockers == ()


@pytest.mark.parametrize("tone_hz", [None, 1_500.0])
def test_new_selector_decision_is_byte_equivalent_to_frozen_selector(
    tone_hz: float | None,
) -> None:
    reference = _frames("reference", tone_hz=tone_hz)
    perturbed = _frames("perturbed", tone_hz=tone_hz)

    frozen = f2531._discover_one_feature(reference, perturbed)
    decision, envelope = f2535.discover_with_scalar_audit(reference, perturbed)

    assert asdict(decision) == asdict(frozen)
    assert decision.receipt_hash == frozen.receipt_hash
    assert envelope.state is f2535.AuditState.COMPLETE
    assert envelope.receipt is not None
    assert envelope.receipt.decision_receipt_hash == decision.receipt_hash
    assert envelope.receipt.decision_state == decision.state
    assert envelope.receipt.input_artifact_hashes == decision.input_artifact_hashes
    assert envelope.physical_decision_affected is False
    if tone_hz is None:
        assert decision.state == "NO_FEATURE_ADMITTED"
        assert envelope.receipt.raw_peak_count == 0
        assert envelope.receipt.admitted_feature_count == 0
    else:
        assert decision.state == "ONE_FEATURE_ADMITTED"
        assert envelope.receipt.raw_peak_count >= 1
        assert envelope.receipt.admitted_feature_count >= 1


def test_stage_counts_close_and_numeric_states_are_explicit() -> None:
    reference = _frames("reference", tone_hz=None)
    perturbed = _frames("perturbed", tone_hz=None)
    _decision, envelope = f2535.discover_with_scalar_audit(reference, perturbed)
    receipt = envelope.receipt
    assert receipt is not None

    assert receipt.raw_peak_count == (
        receipt.patch_incomplete_count + receipt.patch_valid_count
    )
    assert receipt.patch_valid_count == (
        receipt.correlation_below_threshold_count + receipt.correlation_pass_count
    )
    assert receipt.correlation_pass_count == (
        receipt.half_stability_below_threshold_count
        + receipt.half_stability_pass_count
    )
    assert receipt.half_stability_pass_count == receipt.admitted_feature_count
    assert receipt.best_valid_joint_contrast_db.state == "FINITE"
    assert receipt.best_patch_correlation.state == "NOT_EVALUATED"
    assert receipt.best_patch_correlation.value is None
    assert receipt.best_correlation_pass_half_contrast_db.state == "NOT_EVALUATED"


def test_description_failure_cannot_change_discovery_decision() -> None:
    reference = _frames("reference", tone_hz=1_500.0)
    perturbed = _frames("perturbed", tone_hz=1_500.0)
    expected = f2531._discover_one_feature(reference, perturbed)

    decision, envelope = f2535.discover_with_scalar_audit(
        reference,
        perturbed,
        _audit_builder=_failing_audit,
    )

    assert asdict(decision) == asdict(expected)
    assert envelope.state is f2535.AuditState.DESCRIPTION_ERROR
    assert envelope.receipt is None
    assert envelope.description_error_type == "RuntimeError"
    assert envelope.description_error_hash is not None
    assert envelope.physical_decision_affected is False


def test_description_failure_cannot_change_integrated_physical_control_flow() -> None:
    baseline = f2535._run_audited_open_handle_rf_injected(
        reference_socket=_NegativeSocket(0),
        perturbed_socket=_NegativeSocket(1, 1_000_000),
    )
    failed = f2535._run_audited_open_handle_rf_injected(
        reference_socket=_NegativeSocket(0),
        perturbed_socket=_NegativeSocket(1, 1_000_000),
        _audit_builder=_failing_audit,
    )

    assert baseline.physical_result.outcome == "NO_FALSIFIABLE_INTERVENTION"
    assert failed.physical_result.outcome == baseline.physical_result.outcome
    assert asdict(failed.physical_result.discovery) == asdict(
        baseline.physical_result.discovery
    )
    assert tuple(item.state for item in failed.physical_result.phases) == tuple(
        item.state for item in baseline.physical_result.phases
    )
    assert failed.discovery_audit is not None
    assert failed.discovery_audit.state is f2535.AuditState.DESCRIPTION_ERROR
    assert failed.physical_result.command_receipts == ()
    assert failed.physical_result.physical_hypothesis_state == "NOT_EVALUATED"
    assert failed.physical_decision_affected_by_description is False


def test_positive_full_vertical_preserves_the_frozen_physical_evaluator() -> None:
    baseline = f2532._run_open_handle_rf_injected(
        reference_socket=f2532_fixtures._PhaseSocket(0, role="reference"),
        perturbed_socket=f2532_fixtures._PhaseSocket(
            1,
            role="perturbed",
            hypothesis="upstream",
            arrival_offset_ns=1_000_000,
        ),
    )
    audited = f2535._run_audited_open_handle_rf_injected(
        reference_socket=f2532_fixtures._PhaseSocket(0, role="reference"),
        perturbed_socket=f2532_fixtures._PhaseSocket(
            1,
            role="perturbed",
            hypothesis="upstream",
            arrival_offset_ns=1_000_000,
        ),
    )
    physical = audited.physical_result

    assert physical.outcome == baseline.outcome == "UPSTREAM_OF_CHANNEL_DDC_SUPPORTED"
    assert physical.physical_hypothesis_state == baseline.physical_hypothesis_state
    assert asdict(physical.discovery) == asdict(baseline.discovery)
    assert tuple(item.state for item in physical.phases) == tuple(
        item.state for item in baseline.phases
    )
    assert tuple(item.state for item in physical.clause_receipts) == tuple(
        item.state for item in baseline.clause_receipts
    )
    assert len(physical.command_receipts) == len(baseline.command_receipts) == 2
    assert len(physical.boundary_receipts) == len(baseline.boundary_receipts) == 2
    assert audited.discovery_audit is not None
    assert audited.discovery_audit.state is f2535.AuditState.COMPLETE
    assert audited.discovery_audit.receipt is not None
    assert audited.discovery_audit.receipt.admitted_feature_count >= 1
    assert physical.cleanup.all_iq_zeroized is True


def test_scalar_receipt_rejects_stage_count_or_decision_conflicts() -> None:
    reference = _frames("reference", tone_hz=1_500.0)
    perturbed = _frames("perturbed", tone_hz=1_500.0)
    _decision, envelope = f2535.discover_with_scalar_audit(reference, perturbed)
    receipt = envelope.receipt
    assert receipt is not None

    with pytest.raises(ValueError, match="patch-stage counts"):
        replace(receipt, patch_incomplete_count=receipt.patch_incomplete_count + 1)
    with pytest.raises(ValueError, match="conflict with the authoritative decision"):
        replace(
            receipt,
            decision_state="NO_FEATURE_ADMITTED",
        )
    with pytest.raises(ValueError, match="finite"):
        f2522.NumericObservation("FINITE", float("inf"), "dB", "invalid")


def test_persisted_shape_is_strict_scalar_json_with_no_rf_arrays() -> None:
    reference = _frames("reference", tone_hz=1_500.0)
    perturbed = _frames("perturbed", tone_hz=1_500.0)
    _decision, envelope = f2535.discover_with_scalar_audit(reference, perturbed)
    encoded = json.dumps(
        strict_json_value(asdict(envelope)),
        sort_keys=True,
        allow_nan=False,
        separators=(",", ":"),
    )
    decoded = json.loads(encoded)

    assert decoded["raw_rf_persistence"] == "ZERO"
    assert decoded["physical_decision_affected"] is False
    assert decoded["receipt"]["candidate_arrays_persisted"] is False
    assert len(decoded["input_artifact_hashes"]) == 16
    assert "NaN" not in encoded and "Infinity" not in encoded
    forbidden = ("samples", "iq", "stft", "spectrum", "waterfall", "patch_values")
    assert all(key not in decoded for key in forbidden)


def test_integration_is_offline_and_frozen_gate_sources_remain_untouched() -> None:
    source = inspect.getsource(f2535)

    assert f2535.current_f2534_source_sha256() == f2535.REVIEWED_F2534_SOURCE_SHA256
    assert f2535.current_f2532_source_sha256() == f2535.REVIEWED_F2532_SOURCE_SHA256
    assert "websocket" not in source
    assert "create_connection" not in source
    assert "requests." not in source
    assert "urlopen" not in source
    assert "live_authorised" not in inspect.signature(
        f2535._run_audited_open_handle_rf_injected
    ).parameters
    assert f2535.RAW_RF_PERSISTENCE == "ZERO"
