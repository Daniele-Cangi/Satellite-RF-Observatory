"""Synthetic-only tests for Gate F2.5.27 relative-time admission."""

from __future__ import annotations

from dataclasses import asdict, replace
from hashlib import sha256
import inspect
import json
import math

from experiments.live_instrument import kiwi_gate_f2_5_26 as f2526
from experiments.live_instrument import kiwi_gate_f2_5_27 as f2527


SAMPLE_RATE_HZ = 12_000.0
SAMPLE_COUNT = 512
FRAME_DURATION_NS = round(SAMPLE_COUNT * 1_000_000_000 / SAMPLE_RATE_HZ)


def _hash(label: str) -> str:
    return sha256(label.encode()).hexdigest()


def _frame(
    role: str,
    index: int,
    *,
    start_ns: int,
    sequence: int | None = None,
    channel_id: int | None = None,
    arrival_offset_ns: int = 0,
    sample_rate_hz: float = SAMPLE_RATE_HZ,
    age_s: int = 103,
) -> f2527.ScalarFrameReceipt:
    raw = start_ns % f2527.GPS_WEEK_NS
    return f2527.ScalarFrameReceipt(
        artifact_hash_before_analysis=_hash(f"{role}-{index}-{start_ns}"),
        artifact_byte_count=2_069,
        endpoint_identity="one-kiwi.example:8073",
        branch_role=role,
        channel_id=(0 if role == "reference" else 1) if channel_id is None else channel_id,
        sequence=index + 1 if sequence is None else sequence,
        server_gps_seconds=raw // 1_000_000_000,
        server_gps_nanoseconds=raw % 1_000_000_000,
        gps_solution_age_s=age_s,
        decoded_sample_count=SAMPLE_COUNT,
        sample_rate_hz=sample_rate_hz,
        monotonic_arrival_ns=(
            1_000_000_000 + index * 50_000_000 + arrival_offset_ns
        ),
    )


def _stream(
    role: str,
    *,
    start_ns: int = 100_000_000_000,
    count: int = 8,
    arrival_offset_ns: int = 0,
) -> tuple[f2527.ScalarFrameReceipt, ...]:
    return tuple(
        _frame(
            role,
            index,
            start_ns=start_ns + index * FRAME_DURATION_NS,
            arrival_offset_ns=arrival_offset_ns,
        )
        for index in range(count)
    )


def _admitted() -> f2527.RelativeTimingAdmissionReceipt:
    return f2527.evaluate_relative_timing(
        _stream("reference"),
        _stream("perturbed", arrival_offset_ns=1_000_000),
    )


def _clause(
    receipt: f2527.RelativeTimingAdmissionReceipt, name: str
) -> f2527.ClauseReceipt:
    return next(item for item in receipt.clauses if item.clause == name)


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


def test_plan_is_specific_immutable_and_preserves_the_frozen_outcome() -> None:
    assessment = f2527.assess()
    plan = assessment.plan

    assert assessment.exit is f2527.F2527Exit.RELATIVE_TIME_ADMISSION_MATERIALIZED_OFFLINE
    assert plan.reviewed_f2526_commit == f2527.REVIEWED_F2526_COMMIT
    assert plan.parent_outcome == "QUALIFICATION_INCOMPLETE"
    assert plan.parent_receipt_sha256 == f2526.FROZEN_RECEIPT_SHA256
    assert plan.intervention_boundary == "SAME_KIWI_PER_CHANNEL_DDC"
    assert plan.absolute_utc_role == "DESCRIPTIVE_NOT_REQUIRED_FOR_THIS_CAUSAL_CUT"
    assert plan.nperseg == 1_024
    assert plan.noverlap == 512
    assert plan.minimum_common_samples == 2_048
    assert plan.maximum_timestamp_step_residual_samples == 1.0
    assert plan.prefreeze_retry_budget == 0
    assert plan.postfreeze_retry_budget == 0
    assert plan.live_execution_authorised is False
    assert plan.plan_hash == f2527.build_plan().plan_hash


def test_stale_absolute_gps_can_pass_only_by_proving_relative_sample_time() -> None:
    receipt = _admitted()

    assert receipt.state == "ADMISSIBLE_FOR_RELATIVE_TIME_EXPERIMENT"
    assert receipt.physical_hypothesis_state == "NOT_EVALUATED"
    assert receipt.common_sample_count_floor is not None
    assert receipt.common_sample_count_floor >= 2_048
    assert all(item.maximum_timestamp_step_residual_samples == 0.0 for item in receipt.branches)
    assert _clause(receipt, "absolute_gnss_freshness").state == "NOT_REQUIRED"
    assert _clause(receipt, "reference_sample_clock_continuity").state == "SATISFIED"
    assert _clause(receipt, "perturbed_sample_clock_continuity").state == "SATISFIED"
    assert receipt.gps_solution_age_role == "DESCRIPTIVE_ONLY_NOT_AN_ADMISSION_SUBSTITUTE"
    assert "absolute UTC is accurate" in receipt.unauthorised_claims
    assert "the frozen Gate F2.5.25 session would have passed" in receipt.unauthorised_claims


def test_sequence_gap_refuses_before_feature_analysis() -> None:
    perturbed = list(_stream("perturbed", arrival_offset_ns=1_000_000))
    perturbed[4] = replace(perturbed[4], sequence=99)

    receipt = f2527.evaluate_relative_timing(_stream("reference"), perturbed)

    assert receipt.state == "NOT_ADMISSIBLE"
    assert receipt.branches[1].sequence_gap_count == 2
    assert _clause(receipt, "perturbed_sequence_continuity").state == "UNSATISFIED"
    assert receipt.physical_hypothesis_state == "NOT_EVALUATED"


def test_timestamp_jump_refuses_even_with_contiguous_sequences() -> None:
    perturbed = list(_stream("perturbed", arrival_offset_ns=1_000_000))
    perturbed[4] = replace(
        perturbed[4],
        server_gps_nanoseconds=perturbed[4].server_gps_nanoseconds + 10_000_000,
    )

    receipt = f2527.evaluate_relative_timing(_stream("reference"), perturbed)

    assert receipt.state == "NOT_ADMISSIBLE"
    assert receipt.branches[1].sequence_gap_count == 0
    assert receipt.branches[1].timestamp_step_violation_count == 2
    assert _clause(receipt, "perturbed_sample_clock_continuity").state == "UNSATISFIED"


def test_reserved_server_clock_state_is_not_mistaken_for_stale_but_valid_time() -> None:
    perturbed = tuple(
        replace(item, gps_solution_age_s=255)
        for item in _stream("perturbed", arrival_offset_ns=1_000_000)
    )

    receipt = f2527.evaluate_relative_timing(_stream("reference"), perturbed)

    assert receipt.state == "NOT_ADMISSIBLE"
    assert receipt.branches[1].server_clock_error_code_count == len(perturbed)
    assert _clause(receipt, "server_clock_error_codes_absent").state == "UNSATISFIED"
    assert _clause(receipt, "absolute_gnss_freshness").state == "NOT_REQUIRED"


def test_nonoverlap_and_rate_mismatch_are_separate_refusals() -> None:
    nonoverlap = f2527.evaluate_relative_timing(
        _stream("reference", start_ns=100_000_000_000),
        _stream("perturbed", start_ns=200_000_000_000, arrival_offset_ns=1_000_000),
    )
    rate_frames = tuple(
        replace(item, sample_rate_hz=11_999.0)
        for item in _stream("perturbed", arrival_offset_ns=1_000_000)
    )
    rate_mismatch = f2527.evaluate_relative_timing(_stream("reference"), rate_frames)

    assert nonoverlap.state == "NOT_ADMISSIBLE"
    assert _clause(nonoverlap, "common_server_time_overlap").state == "UNSATISFIED"
    assert rate_mismatch.state == "NOT_ADMISSIBLE"
    assert _clause(rate_mismatch, "same_sample_rate").state == "UNSATISFIED"


def test_leading_zero_is_counted_and_week_rollover_is_unwrapped() -> None:
    reference = (_frame("reference", 0, start_ns=0),) + tuple(
        _frame(
            "reference",
            index + 1,
            sequence=index + 2,
            start_ns=100_000_000_000 + index * FRAME_DURATION_NS,
        )
        for index in range(8)
    )
    perturbed = (_frame("perturbed", 0, start_ns=0, arrival_offset_ns=1_000_000),) + tuple(
        _frame(
            "perturbed",
            index + 1,
            sequence=index + 2,
            start_ns=100_000_000_000 + index * FRAME_DURATION_NS,
            arrival_offset_ns=1_000_000,
        )
        for index in range(8)
    )
    zero_receipt = f2527.evaluate_relative_timing(reference, perturbed)

    rollover_start = f2527.GPS_WEEK_NS - 3 * FRAME_DURATION_NS
    rollover_receipt = f2527.evaluate_relative_timing(
        _stream("reference", start_ns=rollover_start),
        _stream("perturbed", start_ns=rollover_start, arrival_offset_ns=1_000_000),
    )

    assert zero_receipt.state == "ADMISSIBLE_FOR_RELATIVE_TIME_EXPERIMENT"
    assert all(item.leading_zero_timestamp_count == 1 for item in zero_receipt.branches)
    assert rollover_receipt.state == "ADMISSIBLE_FOR_RELATIVE_TIME_EXPERIMENT"
    assert all(
        item.unwrapped_end_ns is not None and item.unwrapped_end_ns > f2527.GPS_WEEK_NS
        for item in rollover_receipt.branches
    )


def test_command_boundary_requires_both_streams_and_settled_server_time() -> None:
    perturbed_before = _frame("perturbed", 0, start_ns=100_000_000_000)
    perturbed_after = _frame(
        "perturbed",
        1,
        start_ns=101_000_000_000,
        arrival_offset_ns=950_000_000,
    )
    reference_before = _frame(
        "reference", 0, start_ns=100_000_000_000, arrival_offset_ns=100_000_000
    )
    reference_after = _frame(
        "reference", 1, start_ns=101_000_000_000, arrival_offset_ns=1_050_000_000
    )
    anchor = f2527.CommandBoundaryAnchor(
        transition="A1_TO_B",
        command_hash=_hash("SET mod=iq retune B"),
        command_issued_monotonic_ns=1_200_000_000,
        settling_complete_monotonic_ns=1_800_000_000,
        last_precommand_perturbed_frame_hash=perturbed_before.artifact_hash_before_analysis,
        first_postsettling_perturbed_frame_hash=perturbed_after.artifact_hash_before_analysis,
        reference_before_frame_hash=reference_before.artifact_hash_before_analysis,
        reference_after_frame_hash=reference_after.artifact_hash_before_analysis,
    )

    witnessed = f2527.evaluate_command_boundary(
        anchor,
        last_precommand_perturbed=perturbed_before,
        first_postsettling_perturbed=perturbed_after,
        reference_before=reference_before,
        reference_after=reference_after,
    )
    too_late = replace(anchor, settling_complete_monotonic_ns=2_100_000_000)
    not_witnessed = f2527.evaluate_command_boundary(
        too_late,
        last_precommand_perturbed=perturbed_before,
        first_postsettling_perturbed=perturbed_after,
        reference_before=reference_before,
        reference_after=reference_after,
    )

    assert witnessed.state == "BOUNDARY_WITNESSED"
    assert witnessed.local_order_satisfied is True
    assert witnessed.perturbed_server_time_advanced is True
    assert witnessed.reference_spanned_boundary is True
    assert witnessed.physical_hypothesis_state == "NOT_EVALUATED"
    assert not_witnessed.state == "BOUNDARY_NOT_WITNESSED"
    assert not_witnessed.local_order_satisfied is False


def test_receipts_are_strict_finite_scalars_and_persist_no_rf() -> None:
    value = asdict(_admitted())

    _assert_finite(value)
    assert json.dumps(value, allow_nan=False, default=str)
    assert not set(_walk_keys(value)) & f2527._FORBIDDEN_RF_KEYS
    assert value["raw_rf_persistence"] == "ZERO"
    assert all(item["artifact_hashes"] for item in value["branches"])


def test_module_has_no_live_or_capture_surface() -> None:
    source = inspect.getsource(f2527)

    assert "websocket" not in source.lower()
    assert "urlopen" not in source
    assert "run_live" not in source
    assert "capture(" not in source
    assert set(inspect.signature(f2527.evaluate_relative_timing).parameters) == {
        "reference_frames",
        "perturbed_frames",
        "plan",
    }
