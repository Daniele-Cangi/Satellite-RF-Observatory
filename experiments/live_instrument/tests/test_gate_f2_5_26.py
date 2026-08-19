"""Offline tests for Gate F2.5.26 temporal failure attribution."""

from __future__ import annotations

from dataclasses import asdict
import inspect
import json
import math

from experiments.live_instrument import kiwi_gate_f2_5_26 as f2526


def _assessment() -> f2526.F2526Assessment:
    return f2526.assess()


def _assert_finite(value: object) -> None:
    if isinstance(value, dict):
        for item in value.values():
            _assert_finite(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _assert_finite(item)
    elif isinstance(value, float):
        assert math.isfinite(value)


def test_attribution_binds_the_frozen_receipt_and_pinned_server_source() -> None:
    result = _assessment()

    assert result.receipt_sha256 == f2526.FROZEN_RECEIPT_SHA256
    assert result.receipt_prefix_sha256 == f2526.FROZEN_RECEIPT_PREFIX_SHA256
    assert result.source.archive_sha256 == f2526.PINNED_SERVER_ARCHIVE_SHA256
    assert result.source.member_sha256 == f2526.PINNED_SERVER_MEMBER_SHA256
    assert result.source.server_commit == f2526.PINNED_SERVER_COMMIT
    assert result.source.source_anchors_satisfied is True
    assert result.source.local_decoder_sha256 == f2526.LOCAL_DECODER_SHA256
    assert result.source.local_semantic_receipt_sha256 == (
        f2526.LOCAL_SEMANTIC_RECEIPT_SHA256
    )
    assert result.source.local_decoder_anchors_satisfied is True
    assert result.source.saturation_value_s == 252
    assert result.source.field_semantics == (
        "seconds since the server's latest GPS position solution"
    )


def test_both_branches_delivered_contiguous_decodable_iq() -> None:
    branches = {item.role: item for item in _assessment().branches}

    reference = branches["reference"]
    perturbed = branches["perturbed"]
    assert (reference.channel_id, perturbed.channel_id) == (0, 1)
    assert (reference.incoming_frame_count, perturbed.incoming_frame_count) == (
        295,
        293,
    )
    assert (reference.snd_frame_count, perturbed.snd_frame_count) == (275, 274)
    assert (reference.first_sequence, reference.last_sequence) == (1, 275)
    assert (perturbed.first_sequence, perturbed.last_sequence) == (1, 274)
    assert all(item.unique_sequence_count == item.snd_frame_count for item in branches.values())
    assert all(item.sequence_gap_count == 0 for item in branches.values())
    assert all(item.transport_state == "ACTIVE_CONTIGUOUS_SND_DELIVERY" for item in branches.values())
    assert all(item.snd_header_state == "SATISFIED" for item in branches.values())
    assert all(item.sample_decode_state == "SATISFIED" for item in branches.values())
    assert all(item.iq_mode_state == "SATISFIED" for item in branches.values())


def test_temporal_clause_failed_identically_upstream_of_both_channels() -> None:
    branches = _assessment().branches

    assert all(item.missing_gps_seconds_count == 1 for item in branches)
    assert {item.stale_gps_solution_count for item in branches} == {273, 274}
    assert all(item.minimum_stale_gps_solution_age_s == 92 for item in branches)
    assert all(item.maximum_stale_gps_solution_age_s == 103 for item in branches)
    assert all(item.readiness_admitted_count == 0 for item in branches)
    assert all(item.terminal_error_type == "TimeoutError" for item in branches)
    assert all(
        item.terminal_error_relation == "DOWNSTREAM_DEADLINE_CONSEQUENCE"
        for item in branches
    )
    assert _assessment().requirement.shared_causal_location == (
        "SHARED_UPSTREAM_SERVER_GPS_CLOCK_STATE"
    )


def test_frozen_outcome_and_physical_non_evaluation_cannot_change() -> None:
    result = _assessment()

    assert result.frozen_outcome == "QUALIFICATION_INCOMPLETE"
    assert result.requirement.frozen_limit_s == 30
    assert result.requirement.frozen_clause_result == "UNSATISFIED"
    assert result.requirement.frozen_outcome_preserved is True
    assert result.data_available is True
    assert result.measurement_admissible is False
    assert result.physical_hypothesis_state == "NOT_EVALUATED"
    assert result.physical_decision_affected is False
    assert result.raw_rf_persistence == "ZERO"


def test_remote_staleness_cause_is_not_inferred() -> None:
    requirement = _assessment().requirement

    assert requirement.proximal_observed_failure == (
        "REMOTE_GPS_SOLUTION_FRESHNESS_CLAUSE_UNSATISFIED"
    )
    assert requirement.remote_staleness_cause == "UNKNOWN_NOT_RECORDED"
    assert "the receiver GPS subsystem failed for a known cause" in (
        _assessment().unauthorised_claims
    )


def test_relative_clock_alternative_is_new_trial_only_and_not_receipt_evaluable() -> None:
    requirement = _assessment().requirement

    assert requirement.absolute_gnss_freshness_necessity == "NOT_DERIVED"
    assert requirement.relative_time_alternative == (
        "CONCEPTUALLY_PLAUSIBLE_NEW_TRIAL_ONLY"
    )
    assert requirement.alternative_receipt_status == (
        "NOT_FALSIFIABLE_WITH_THIS_RECEIPT"
    )
    assert requirement.missing_relative_time_statistics == (
        "per_frame_monotonic_arrival_time",
        "gps_seconds_value",
        "gps_nanoseconds_value",
        "server_sample_tick_or_equivalent",
        "decoded_sample_count_per_frame",
        "retune_command_issue_time",
    )
    assert requirement.future_change_scope.startswith(
        "derive a new temporal clause from the intervention topology"
    )


def test_attribution_surface_has_no_live_connector_or_threshold_override() -> None:
    source = inspect.getsource(f2526)
    signature = inspect.signature(f2526.audit_frozen_outcome)

    assert "websocket" not in source.lower()
    assert "run_live" not in source
    assert "capture(" not in source
    assert "maximum_gps_solution_age_s" not in signature.parameters
    assert "frozen_limit_s=FROZEN_MAXIMUM_GPS_SOLUTION_AGE_S" in source


def test_attribution_is_strict_finite_metadata_with_zero_rf_persistence() -> None:
    value = asdict(_assessment())

    _assert_finite(value)
    encoded = json.dumps(value, allow_nan=False, default=str)
    assert encoded
    keys = set(f2526._walk_keys(value))
    assert not keys & f2526._FORBIDDEN_RF_KEYS
    assert "raw_rf_persistence" in keys
    assert value["raw_rf_persistence"] == "ZERO"
