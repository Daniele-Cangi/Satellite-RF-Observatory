"""Offline full-session timestamp-normalization tests for Gate F2.5.37."""

from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import inspect
import json
import math
from types import SimpleNamespace

import pytest

from experiments.live_instrument import kiwi_gate_f2_5_27 as f2527
from experiments.live_instrument import kiwi_gate_f2_5_31 as f2531
from experiments.live_instrument import kiwi_gate_f2_5_35 as f2535
from experiments.live_instrument import kiwi_gate_f2_5_37 as f2537
from experiments.live_instrument.tests import test_gate_f2_5_32 as f2532_fixtures


SAMPLE_RATE_HZ = 11_998.995409
SAMPLE_COUNT = 512
FRAME_DURATION_NS = round(SAMPLE_COUNT * 1_000_000_000 / SAMPLE_RATE_HZ)


def _frame(
    role: str,
    sequence: int,
    start_ns: int,
    *,
    arrival_ns: int | None = None,
) -> f2527.ScalarFrameReceipt:
    raw = start_ns % f2527.GPS_WEEK_NS
    digest = sha256(f"{role}:{sequence}:{start_ns}".encode()).hexdigest()
    return f2527.ScalarFrameReceipt(
        digest,
        17 + 4 * SAMPLE_COUNT,
        "synthetic.invalid:8073",
        role,
        0 if role == "reference" else 1,
        sequence,
        raw // 1_000_000_000,
        raw % 1_000_000_000,
        0,
        SAMPLE_COUNT,
        SAMPLE_RATE_HZ,
        sequence * FRAME_DURATION_NS if arrival_ns is None else arrival_ns,
    )


def _handle(
    role: str,
    frames: tuple[f2527.ScalarFrameReceipt, ...],
) -> SimpleNamespace:
    return SimpleNamespace(branch_role=role, scalar_receipts=list(frames))


class _LeadingZeroPhaseSocket(f2532_fixtures._PhaseSocket):
    """The live transcript shape: one leading zero, then ordinary SND time."""

    def recv_data_frame(self, *, control_frame: bool):
        opcode, lease = super().recv_data_frame(control_frame=control_frame)
        if self.metadata_sent and self.sequence_index == 1:
            assert isinstance(lease.payload, bytearray)
            # SND prefix is three bytes; seconds/nanoseconds occupy bytes 12:20.
            lease.payload[12:20] = b"\x00" * 8
        return opcode, lease


def _phase_pair():
    return (
        _LeadingZeroPhaseSocket(0, role="reference"),
        _LeadingZeroPhaseSocket(
            1,
            role="perturbed",
            hypothesis="upstream",
            arrival_offset_ns=1_000_000,
        ),
    )


def test_assessment_binds_frozen_outcome_and_exact_failure_attribution() -> None:
    assessment = f2537.assess()

    assert assessment.exit is (
        f2537.F2537Exit.CONTINUITY_NORMALIZATION_INTEGRATED_OFFLINE
    )
    assert assessment.receipt_hash_matches
    assert assessment.prefix_hash_matches
    assert assessment.strict_json_complete
    assert assessment.frozen_outcome_preserved
    assert assessment.frozen_physical_state_preserved
    assert assessment.leading_zero_failure_attribution_exact
    assert assessment.f2531_source_hash_matches
    assert assessment.f2535_source_hash_matches
    assert assessment.one_existing_normalization_rule
    assert assessment.frozen_sources_untouched
    assert assessment.no_public_execution_surface
    assert assessment.live_execution_authorised is False
    assert assessment.blockers == ()
    assert assessment.raw_rf_persistence == "ZERO"


def test_plan_changes_only_full_session_normalization() -> None:
    plan = f2537.build_plan()

    assert plan.reviewed_outcome_commit == f2537.REVIEWED_OUTCOME_COMMIT
    assert plan.reviewed_receipt_sha256 == f2537.REVIEWED_RECEIPT_SHA256
    assert plan.change_scope == "FULL_SESSION_CONTINUITY_NORMALIZATION_ONLY"
    assert plan.normalization_rule == "REUSE_F2527_UNWRAP_START_TIMES_EXACTLY"
    assert plan.retained_receipt_type == "F2531_SESSION_CONTINUITY_RECEIPT"
    assert plan.threshold_policy == "ALL_RF_THRESHOLDS_INHERITED_UNCHANGED"
    assert plan.connector_surface_present is False
    assert plan.prefreeze_retry_budget == plan.postfreeze_retry_budget == 0
    assert plan.live_execution_authorised is False
    assert plan.raw_rf_persistence == "ZERO"
    assert len(plan.plan_hash) == 64


def test_actual_leading_zero_shape_is_excluded_not_counted_as_a_gap() -> None:
    first_valid_ns = 289_745_458_498_570
    frames = (
        _frame("reference", 1, 0),
        _frame("reference", 2, first_valid_ns),
        _frame("reference", 3, first_valid_ns + FRAME_DURATION_NS),
    )
    handle = _handle("reference", frames)

    frozen = f2531._continuity(handle)
    corrected = f2537.evaluate_full_session_continuity(handle)
    reconstructed = abs(first_valid_ns - FRAME_DURATION_NS) / (
        1_000_000_000 / SAMPLE_RATE_HZ
    )

    assert frozen.state == "UNSATISFIED"
    assert frozen.timestamp_step_violation_count == 1
    assert frozen.maximum_timestamp_step_residual_samples == pytest.approx(
        reconstructed,
        abs=1e-6,
    )
    assert corrected.state == "SATISFIED"
    assert corrected.frame_count == 3
    assert corrected.sequence_gap_count == 0
    assert corrected.timestamp_step_violation_count == 0
    assert corrected.maximum_timestamp_step_residual_samples < 1.0
    assert corrected.artifact_hashes == tuple(
        item.artifact_hash_before_analysis for item in frames
    )


def test_multiple_leading_zeros_use_the_same_f2527_rule() -> None:
    first_valid_ns = 200_000_000_000
    frames = (
        _frame("perturbed", 1, 0),
        _frame("perturbed", 2, 0),
        _frame("perturbed", 3, first_valid_ns),
        _frame("perturbed", 4, first_valid_ns + FRAME_DURATION_NS),
    )
    usable, starts, leading = f2527._unwrap_start_times(frames)
    receipt = f2537.evaluate_full_session_continuity(
        _handle("perturbed", frames)
    )

    assert leading == 2
    assert tuple(item.sequence for item in usable) == (3, 4)
    assert starts == (first_valid_ns, first_valid_ns + FRAME_DURATION_NS)
    assert receipt.state == "SATISFIED"
    assert receipt.sequence_gap_count == 0
    assert receipt.timestamp_step_violation_count == 0


def test_interior_zero_is_not_silently_discarded() -> None:
    first_ns = 100_000_000_000
    frames = (
        _frame("reference", 1, first_ns),
        _frame("reference", 2, 0),
        _frame("reference", 3, first_ns + 2 * FRAME_DURATION_NS),
    )
    receipt = f2537.evaluate_full_session_continuity(
        _handle("reference", frames)
    )

    assert receipt.state == "UNSATISFIED"
    assert receipt.sequence_gap_count == 0
    assert receipt.timestamp_step_violation_count == 2


def test_forward_gps_week_rollover_remains_continuous() -> None:
    before_rollover = f2527.GPS_WEEK_NS - FRAME_DURATION_NS
    frames = (
        _frame("reference", 10, before_rollover),
        _frame("reference", 11, f2527.GPS_WEEK_NS),
        _frame("reference", 12, f2527.GPS_WEEK_NS + FRAME_DURATION_NS),
    )
    receipt = f2537.evaluate_full_session_continuity(
        _handle("reference", frames)
    )

    assert receipt.state == "SATISFIED"
    assert receipt.sequence_gap_count == 0
    assert receipt.timestamp_step_violation_count == 0
    assert receipt.maximum_timestamp_step_residual_samples < 1.0


def test_corrected_vertical_changes_only_the_false_continuity_block() -> None:
    frozen_reference, frozen_perturbed = _phase_pair()
    frozen = f2535._run_audited_open_handle_rf_injected(
        reference_socket=frozen_reference,
        perturbed_socket=frozen_perturbed,
    )
    corrected_reference, corrected_perturbed = _phase_pair()
    original_evaluator = f2531._continuity
    corrected = f2537._run_corrected_audited_injected(
        reference_socket=corrected_reference,
        perturbed_socket=corrected_perturbed,
    )

    assert frozen.physical_result.outcome == "INTERVENTION_INVALID"
    assert frozen.physical_result.discovery is not None
    assert frozen.physical_result.discovery.state == "ONE_FEATURE_ADMITTED"
    assert all(
        item.timestamp_step_violation_count == 1
        for item in frozen.physical_result.session_continuity
    )
    assert corrected.physical_result.outcome == "UPSTREAM_OF_CHANNEL_DDC_SUPPORTED"
    assert corrected.physical_result.physical_hypothesis_state == (
        "UPSTREAM_OF_CHANNEL_DDC_SUPPORTED"
    )
    assert asdict(corrected.physical_result.discovery) == asdict(
        frozen.physical_result.discovery
    )
    assert corrected.discovery_audit is not None
    assert corrected.discovery_audit.decision_receipt_hash == (
        corrected.physical_result.discovery.receipt_hash
    )
    assert all(
        item.state == "SATISFIED"
        for item in corrected.physical_result.session_continuity
    )
    assert all(
        item.timestamp_step_violation_count == 0
        for item in corrected.physical_result.session_continuity
    )
    assert corrected.physical_result.cleanup.all_iq_zeroized
    assert corrected.physical_result.cleanup.raw_rf_persistence == "ZERO"
    assert f2531._continuity is original_evaluator


def test_installed_evaluator_is_restored_after_downstream_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_evaluator = f2531._continuity

    def fail(**_kwargs: object) -> f2535.F2535RunResult:
        assert f2531._continuity is f2537.evaluate_full_session_continuity
        raise RuntimeError("synthetic downstream error")

    monkeypatch.setattr(f2535, "_run_audited_open_handle_rf_injected", fail)
    with pytest.raises(RuntimeError, match="synthetic downstream"):
        f2537._run_corrected_audited_injected(
            reference_socket=object(),
            perturbed_socket=object(),
        )
    assert f2531._continuity is original_evaluator


def test_successor_is_offline_strict_and_has_no_new_experiment_controls() -> None:
    source = inspect.getsource(f2537)
    signature = inspect.signature(f2537._run_corrected_audited_injected)
    encoded = json.dumps(asdict(f2537.assess()), allow_nan=False, default=str)

    assert set(signature.parameters) == {"reference_socket", "perturbed_socket"}
    assert "websocket" not in source
    assert "create_connection" not in source
    assert "urlopen" not in source
    assert "requests." not in source
    assert "def run_reviewed_once" not in source
    assert "live_authorised" not in signature.parameters
    assert "threshold" not in signature.parameters
    assert "frequency" not in signature.parameters
    assert "endpoint" not in signature.parameters
    assert "retry" not in signature.parameters
    assert "NaN" not in encoded and "Infinity" not in encoded
    assert f2537.RAW_RF_PERSISTENCE == "ZERO"
