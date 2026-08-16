"""Offline tests for the single prospective targetless Kiwi experiment."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import numpy as np

from experiments.live_instrument.kiwi_probe import IQBlock, KiwiCapture, KiwiEndpoint
from experiments.live_instrument.kiwi_prospective import (
    audit_checkpoint_3_band_selection,
    checkpoint_3_discovery,
    default_prospective_plan,
    evaluate_confirmation,
    register_prediction,
    reveal_model,
)
from experiments.live_instrument.models import ClauseStatus


NOW = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
SAMPLE_RATE = 12_000.0


def test_band_audit_exposes_center_selection_outside_cp3_null() -> None:
    discovery = checkpoint_3_discovery()

    audit = audit_checkpoint_3_band_selection(discovery)

    assert not audit.center_search_repeated_inside_checkpoint_3_null
    assert audit.within_band_search_repeated_inside_checkpoint_3_null
    assert audit.center_scout_and_checkpoint_3_comparison_used_distinct_windows
    assert audit.prospective_confirmation_band_fixed_before_samples


def test_prospective_plan_hash_binds_discovery_thresholds_and_controls() -> None:
    discovery = checkpoint_3_discovery()
    plan = default_prospective_plan(discovery)

    assert plan.discovery_record_hash == discovery.record_hash
    assert plan.plan_hash == replace(plan).plan_hash
    assert plan.plan_hash != replace(plan, positive_threshold=2.1).plan_hash
    assert plan.plan_hash != replace(
        plan, frequency_control_offsets_hz=(-1_000.0, 1_000.0)
    ).plan_hash


def test_independent_window_confirms_positive_then_negative_against_controls() -> None:
    discovery, audit, plan, model, prediction = _protocol()
    left_samples, right_samples = _transition_pair(plan, seed=71)
    left = _capture("left", left_samples, plan, start=NOW)
    right = _capture("right", right_samples, plan, start=NOW)

    result = evaluate_confirmation(
        discovery,
        audit,
        plan,
        model,
        prediction,
        left,
        right,
        NOW + timedelta(seconds=4.1),
    )

    assert result.target_pair.positive is not None
    assert result.target_pair.negative is not None
    assert result.controls_passed
    assert result.belief.assessment("measurement_availability").status is ClauseStatus.SATISFIED
    assert result.belief.assessment("positive_transition").status is ClauseStatus.SATISFIED
    assert result.belief.assessment("negative_transition").status is ClauseStatus.SATISFIED
    assert result.belief.assessment("prospective_confirmation").status is ClauseStatus.SATISFIED
    assert result.belief.assessment("common_physical_cause").status is ClauseStatus.UNRESOLVED


def test_new_window_without_ordered_pair_is_a_negative_prospective_outcome() -> None:
    discovery, audit, plan, model, prediction = _protocol()
    rng = np.random.default_rng(72)
    count = int(SAMPLE_RATE * 4.0)
    left_samples = (0.04 * (rng.normal(size=count) + 1j * rng.normal(size=count))).astype(np.complex64)
    right_samples = (0.04 * (rng.normal(size=count) + 1j * rng.normal(size=count))).astype(np.complex64)

    result = evaluate_confirmation(
        discovery,
        audit,
        plan,
        model,
        prediction,
        _capture("left", left_samples, plan, start=NOW),
        _capture("right", right_samples, plan, start=NOW),
        NOW + timedelta(seconds=4.1),
    )

    assert not result.controls_passed
    assert result.belief.assessment("measurement_availability").status is ClauseStatus.SATISFIED
    assert result.belief.assessment("positive_transition").status is ClauseStatus.UNSATISFIED
    assert result.belief.assessment("negative_transition").status is ClauseStatus.UNSATISFIED
    assert result.belief.assessment("prospective_confirmation").status is ClauseStatus.UNSATISFIED
    assert result.belief.assessment("common_physical_cause").status is ClauseStatus.UNRESOLVED


def test_pre_registration_samples_are_unobservable_not_confirmation() -> None:
    discovery, audit, plan, model, prediction = _protocol()
    samples = np.ones(int(SAMPLE_RATE * 4.0), dtype=np.complex64)
    before_registration = prediction.registered_at - timedelta(seconds=5)

    result = evaluate_confirmation(
        discovery,
        audit,
        plan,
        model,
        prediction,
        _capture("left", samples, plan, start=before_registration),
        _capture("right", samples, plan, start=before_registration),
        prediction.registered_at + timedelta(seconds=0.1),
    )

    assert result.belief.assessment("measurement_availability").status is ClauseStatus.UNOBSERVABLE
    assert result.belief.assessment("prospective_confirmation").status is ClauseStatus.UNOBSERVABLE


def _protocol():
    discovery = checkpoint_3_discovery()
    audit = audit_checkpoint_3_band_selection(discovery)
    plan = replace(
        default_prospective_plan(discovery),
        confirmation_duration_s=4.0,
        minimum_overlap_s=3.0,
        time_control_shifts_frames=(-96, -64, 64, 96),
    )
    model = reveal_model(plan, NOW - timedelta(seconds=2))
    prediction = register_prediction(plan, NOW - timedelta(seconds=1))
    return discovery, audit, plan, model, prediction


def _transition_pair(plan, seed: int) -> tuple[np.ndarray, np.ndarray]:
    count = int(SAMPLE_RATE * 4.0)
    time_s = np.arange(count) / SAMPLE_RATE
    envelope = ((time_s >= 1.5) & (time_s < 1.82)).astype(float) * 2.5
    frequency_offset_hz = (
        (plan.target_frequency_low_hz + plan.target_frequency_high_hz) / 2.0
        - plan.center_frequency_hz
    )
    tone = envelope * np.exp(2j * np.pi * frequency_offset_hz * time_s)
    rng = np.random.default_rng(seed)
    left_noise = 0.035 * (rng.normal(size=count) + 1j * rng.normal(size=count))
    right_noise = 0.04 * (rng.normal(size=count) + 1j * rng.normal(size=count))
    return (
        (tone + left_noise).astype(np.complex64),
        (tone * np.exp(0.6j) + right_noise).astype(np.complex64),
    )


def _capture(
    name: str,
    samples: np.ndarray,
    plan,
    *,
    start: datetime,
) -> KiwiCapture:
    event_end = start + timedelta(seconds=len(samples) / SAMPLE_RATE)
    block = IQBlock(
        event_start=start,
        event_end=event_end,
        samples=samples,
        rssi_db=-80.0,
        gps_solution_age_s=1,
        gps_timestamp_available=True,
        adc_overflow=False,
        sequence=1,
        arrived_at=event_end + timedelta(milliseconds=80),
    )
    return KiwiCapture(
        endpoint=KiwiEndpoint(name, "127.0.0.1"),
        center_frequency_hz=plan.center_frequency_hz,
        sample_rate_hz=SAMPLE_RATE,
        status={"ext_api": "4"},
        blocks=(block,),
        arrived_start=start,
        arrived_end=block.arrived_at,
    )
