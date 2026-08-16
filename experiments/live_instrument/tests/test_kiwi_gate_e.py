"""Offline tests for the single immutable WWV/WWVH Gate E experiment."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import numpy as np

from experiments.live_instrument import kiwi_probe as kiwi
from experiments.live_instrument.kiwi_gate_e import (
    GateECapabilityOffer,
    GateEMotherPlan,
    GateEOutcomeKind,
    GateESchedule,
    SegmentMetrics,
    WWV,
    WWVH,
    evaluate_frozen_window,
    freeze_plan_after_positive_control,
    measure_segment,
    select_capability_offer,
)


HOUR = datetime(2026, 8, 16, 14, 0, tzinfo=timezone.utc)


def test_mother_and_frozen_hash_bind_apparatus_identity_and_thresholds() -> None:
    mother, schedule, offer, pre, capture = _protocol()
    frozen = freeze_plan_after_positive_control(
        mother, offer, schedule, pre, schedule.pre_end + timedelta(seconds=1)
    )

    assert mother.plan_hash != replace(mother, minimum_tick_contrast_db=5.0).plan_hash
    assert frozen.plan_hash != replace(frozen, center_frequency_hz=15_000_000.0).plan_hash
    assert frozen.frozen_at < schedule.target_start
    assert frozen.stations_supported == (WWV,)


def test_station_specific_marker_cannot_borrow_other_station_tone() -> None:
    mother, schedule, offer, pre, _capture = _protocol()
    wrong_source_control = replace(
        pre,
        tone_500_contrast_db=1.0,
        tone_600_contrast_db=14.0,
        wwv_tick_contrast_db=13.0,
        wwvh_tick_contrast_db=0.0,
    )

    try:
        freeze_plan_after_positive_control(
            mother,
            offer,
            schedule,
            wrong_source_control,
            schedule.pre_end + timedelta(seconds=1),
        )
    except ValueError as error:
        assert "WWV at 500 Hz" in str(error)
    else:
        raise AssertionError("WWV path incorrectly borrowed the WWVH positive tone")


def test_absence_with_same_path_witnesses_and_recovery_is_not_detected() -> None:
    mother, schedule, offer, pre, capture = _protocol()
    frozen = freeze_plan_after_positive_control(
        mother, offer, schedule, pre, schedule.pre_end + timedelta(seconds=1)
    )
    target = _metrics(schedule.target_start, schedule.target_end, tone500=0.0, tone600=1.0)
    post = _metrics(schedule.post_start, schedule.post_end, tone500=0.0, tone600=13.0)

    outcome = evaluate_frozen_window(
        mother, offer, frozen, capture, pre, target, post, now=schedule.post_end + timedelta(milliseconds=100)
    )

    assert outcome.kind is GateEOutcomeKind.NOT_DETECTED
    assert outcome.belief.assessment("standard_tone_absent").status.value == "SATISFIED"
    assert outcome.belief.assessment("negative_interpretable").status.value == "SATISFIED"
    assert outcome.evidence.receipt.measurement_roots == ("kiwi:primary",)


def test_absence_without_same_station_ticks_is_not_detectable() -> None:
    mother, schedule, offer, pre, capture = _protocol()
    frozen = freeze_plan_after_positive_control(
        mother, offer, schedule, pre, schedule.pre_end + timedelta(seconds=1)
    )
    target = replace(
        _metrics(schedule.target_start, schedule.target_end, tone500=0.0, tone600=1.0),
        wwv_tick_contrast_db=0.0,
    )
    post = _metrics(schedule.post_start, schedule.post_end, tone500=0.0, tone600=13.0)

    outcome = evaluate_frozen_window(
        mother, offer, frozen, capture, pre, target, post, now=schedule.post_end + timedelta(milliseconds=100)
    )

    assert outcome.kind is GateEOutcomeKind.NOT_DETECTABLE
    assert outcome.belief.assessment("path_alive_during_target_window").status.value == "UNSATISFIED"
    assert outcome.belief.assessment("standard_tone_absent").status.value == "SATISFIED"
    assert outcome.belief.assessment("negative_interpretable").status.value == "UNSATISFIED"


def test_tone_during_scheduled_silence_falsifies_observational_prediction() -> None:
    mother, schedule, offer, pre, capture = _protocol()
    frozen = freeze_plan_after_positive_control(
        mother, offer, schedule, pre, schedule.pre_end + timedelta(seconds=1)
    )
    target = _metrics(schedule.target_start, schedule.target_end, tone500=12.0, tone600=1.0)
    post = _metrics(schedule.post_start, schedule.post_end, tone500=0.0, tone600=13.0)

    outcome = evaluate_frozen_window(
        mother, offer, frozen, capture, pre, target, post, now=schedule.post_end + timedelta(milliseconds=100)
    )

    assert outcome.kind is GateEOutcomeKind.OBSERVATIONAL_PREDICTION_FALSIFIED
    assert outcome.belief.assessment("standard_tone_absent").status.value == "UNSATISFIED"


def test_receiver_change_invalidates_receipt() -> None:
    mother, schedule, offer, pre, capture = _protocol()
    frozen = freeze_plan_after_positive_control(
        mother, offer, schedule, pre, schedule.pre_end + timedelta(seconds=1)
    )
    changed = replace(capture, endpoint=kiwi.KiwiEndpoint("replacement", "127.0.0.2"))
    target = _metrics(schedule.target_start, schedule.target_end, tone500=0.0, tone600=1.0)
    post = _metrics(schedule.post_start, schedule.post_end, tone500=0.0, tone600=13.0)

    outcome = evaluate_frozen_window(
        mother, offer, frozen, changed, pre, target, post, now=schedule.post_end + timedelta(milliseconds=100)
    )

    assert outcome.kind is GateEOutcomeKind.RECEIPT_INVALIDATED
    assert outcome.belief.assessment("receiver_health_continuous").status.value == "UNSATISFIED"


def test_offer_ranking_prefers_causal_witness_over_information_gain() -> None:
    mother, schedule, offer, _pre, _capture = _protocol()
    generic = replace(
        offer,
        offer_id="high-snr-no-witness",
        stations_supported=(),
        same_path_witness=False,
        causal_cuts_closed=("carrier_path",),
        robust_margin_db=40.0,
        information_gain_proxy=80.0,
    )

    selected = select_capability_offer(
        (generic, offer),
        now=offer.verified_at,
        required_until=schedule.post_end,
    )

    assert selected is offer


def test_feature_extraction_resolves_wwv_tick_and_500_hz_tone() -> None:
    sample_rate = 12_000.0
    start = HOUR + timedelta(minutes=28, seconds=3)
    duration = 8.0
    count = int(sample_rate * duration)
    times = np.arange(count) / sample_rate
    modulation = 0.30 * np.sin(2 * np.pi * 500.0 * times)
    for second in range(1, 8):
        begin = int((second + 0.012) * sample_rate)
        finish = begin + int(0.005 * sample_rate)
        local = np.arange(finish - begin) / sample_rate
        modulation[begin:finish] += 0.55 * np.sin(2 * np.pi * 1000.0 * local)
    rng = np.random.default_rng(91)
    samples = ((1.0 + modulation) * np.exp(0.2j) + 0.01 * (rng.normal(size=count) + 1j * rng.normal(size=count))).astype(np.complex64)
    capture = _capture(start, samples, sample_rate, center=10_000_000.0)
    audit = kiwi.audit_capture(
        capture,
        kiwi.ScoutPlan(
            center_frequencies_hz=(10_000_000.0,),
            scout_duration_s=duration,
            nperseg=1024,
            noverlap=768,
            min_overlap_s=7.0,
        ),
    )

    metrics = measure_segment(capture, audit, start, start + timedelta(seconds=duration))

    assert metrics.tone_500_contrast_db > 15.0
    assert metrics.wwv_tick_contrast_db > 4.0
    assert metrics.wwv_tick_contrast_db > metrics.wwvh_tick_contrast_db


def _protocol():
    mother = GateEMotherPlan()
    schedule = GateESchedule.for_hour(HOUR, mother)
    capture = _capture(
        schedule.stream_start,
        np.ones(int(10.0 * (schedule.post_end - schedule.stream_start).total_seconds()), dtype=np.complex64),
        10.0,
        center=10_000_000.0,
        endpoint=kiwi.KiwiEndpoint("primary", "127.0.0.1"),
    )
    audit = kiwi.CaptureAudit(
        True, (), capture.blocks, 0, 0, 0,
        (capture.event_end - capture.event_start).total_seconds(),
        capture.sample_rate_hz, 0.0, 0.0, 0.05, 0.08, 1,
    )
    pre = _metrics(schedule.pre_start, schedule.pre_end, tone500=14.0, tone600=0.0)
    offer = GateECapabilityOffer(
        "offer-primary",
        capture.endpoint,
        capture.center_frequency_hz,
        schedule.stream_start - timedelta(minutes=1),
        schedule.post_end + timedelta(minutes=1),
        (WWV,),
        pre,
        audit,
        True,
        ("station_specific_marker", "carrier_path", "timecode_path"),
        8.0,
        14.0,
        "a" * 64,
    )
    return mother, schedule, offer, pre, capture


def _metrics(start, end, *, tone500, tone600):
    return SegmentMetrics(start, end, tone500, tone600, 13.0, 0.0, 16.0, 12.0)


def _capture(start, samples, sample_rate, *, center, endpoint=None):
    endpoint = endpoint or kiwi.KiwiEndpoint("synthetic", "127.0.0.1")
    end = start + timedelta(seconds=len(samples) / sample_rate)
    block = kiwi.IQBlock(
        start, end, samples, -70.0, 1, True, False, 1,
        arrived_at=end + timedelta(milliseconds=50),
    )
    return kiwi.KiwiCapture(
        endpoint, center, sample_rate, {"ext_api": "4"}, (block,), start,
        block.arrived_at,
    )
