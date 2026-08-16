"""Deterministic CP3 tests for the targetless live Kiwi scout."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

import experiments.live_instrument.kiwi_probe as kiwi_probe
from experiments.live_instrument.kiwi_probe import (
    IQBlock,
    KiwiCapture,
    KiwiEndpoint,
    ScoutPlan,
    audit_capture,
    compare_rf_structure,
    scout_targetless_region,
)
from experiments.live_instrument.models import (
    ClauseStatus,
    DecisionClause,
    DecisionContract,
    Intent,
)


NOW = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
SAMPLE_RATE = 12_000.0
CENTER = 10_000_000.0


def test_scout_plan_hash_freezes_center_grid_and_thresholds() -> None:
    plan = ScoutPlan(center_frequencies_hz=(5_000_000.0, 10_000_000.0))

    assert plan.plan_hash == replace(plan).plan_hash
    assert plan.plan_hash != replace(plan, significance_alpha=0.02).plan_hash
    assert plan.plan_hash != replace(plan, center_frequencies_hz=(10_000_000.0,)).plan_hash


def test_capture_audit_splits_sequence_gap_instead_of_concatenating() -> None:
    plan = replace(ScoutPlan(center_frequencies_hz=(CENTER,)), min_overlap_s=0.75)
    blocks = (
        _block(NOW, np.ones(50, dtype=np.complex64), 1, 100.0),
        _block(NOW + timedelta(seconds=0.5), np.ones(50, dtype=np.complex64), 2, 100.0),
        _block(NOW + timedelta(seconds=1.0), np.ones(50, dtype=np.complex64), 4, 100.0),
    )

    audit = audit_capture(_capture_from_blocks("left", blocks, 100.0), plan)

    assert audit.usable
    assert audit.sequence_gap_count == 1
    assert [block.sequence for block in audit.blocks] == [1, 2]
    assert audit.dropped_block_count == 1


def test_common_transient_beats_frozen_time_and_frequency_nulls() -> None:
    left_samples, right_samples = _shared_transient_pair(seed=14)
    plan = ScoutPlan(center_frequencies_hz=(CENTER,))

    result = scout_targetless_region(
        _single_block_capture("left", left_samples),
        _single_block_capture("right", right_samples),
        plan,
    )

    assert result.region is not None
    assert result.time_null_count == plan.null_shift_count
    assert result.frequency_null_count == plan.null_shift_count
    assert result.time_null_p is not None and result.time_null_p <= plan.significance_alpha
    assert result.frequency_null_p is not None and result.frequency_null_p <= plan.significance_alpha
    assert result.self_consistent
    assert result.alignable
    assert result.similarity_exceeds_null
    assert result.plan_hash == plan.plan_hash


def test_wrong_gnss_alignment_cannot_be_rescued_by_lag_search() -> None:
    left_samples, right_samples = _shared_transient_pair(seed=15)
    plan = ScoutPlan(center_frequencies_hz=(CENTER,))
    left = _single_block_capture("left", left_samples)
    right = _single_block_capture(
        "right",
        right_samples,
        start=NOW + timedelta(seconds=0.45),
    )

    result = scout_targetless_region(left, right, plan)

    assert not result.similarity_exceeds_null
    assert result.time_null_p is None or result.time_null_p > plan.significance_alpha


def test_measurement_availability_is_separate_from_unresolved_common_cause() -> None:
    left_samples, _right_samples = _shared_transient_pair(seed=16)
    invalid = _single_block_capture("left", left_samples, gps_available=False)
    valid = _single_block_capture("right", left_samples)

    _event, belief, _graph = compare_rf_structure(
        _contract(),
        invalid,
        valid,
        NOW + timedelta(seconds=4.0),
        plan=ScoutPlan(center_frequencies_hz=(CENTER,)),
    )

    assert belief.assessment("measurement_availability").status is ClauseStatus.UNOBSERVABLE
    assert belief.assessment("shared_structure_beyond_null").status is ClauseStatus.UNOBSERVABLE
    assert belief.assessment("common_physical_cause").status is ClauseStatus.UNOBSERVABLE


def test_runner_scouts_frozen_grid_then_stops_at_first_calibrated_comparison(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = replace(
        ScoutPlan(center_frequencies_hz=(5_000_000.0, 10_000_000.0)),
        scout_duration_s=2.5,
    )
    capture_calls: list[tuple[float, float]] = []
    compare_calls: list[float] = []

    def fake_capture(
        _endpoints: tuple[KiwiEndpoint, KiwiEndpoint],
        *,
        center_frequency_hz: float,
        duration_s: float,
        **_kwargs: object,
    ) -> tuple[KiwiCapture, KiwiCapture]:
        capture_calls.append((center_frequency_hz, duration_s))
        if center_frequency_hz == 10_000_000.0:
            samples = _shared_transient_pair(seed=17)
        else:
            rng = np.random.default_rng(17)
            count = int(SAMPLE_RATE * 3.0)
            samples = (
                (rng.normal(size=count) + 1j * rng.normal(size=count)).astype(np.complex64),
                (rng.normal(size=count) + 1j * rng.normal(size=count)).astype(np.complex64),
            )
        return (
            _single_block_capture("left", samples[0], center=center_frequency_hz),
            _single_block_capture("right", samples[1], center=center_frequency_hz),
        )

    class StopAfterComparison(RuntimeError):
        pass

    def fake_compare(
        _contract: DecisionContract,
        left: KiwiCapture,
        _right: KiwiCapture,
        _now: datetime,
        **_kwargs: object,
    ) -> tuple[object, object, object]:
        compare_calls.append(left.center_frequency_hz)
        raise StopAfterComparison

    monkeypatch.setattr(kiwi_probe, "capture_dual_kiwi", fake_capture)
    monkeypatch.setattr(kiwi_probe, "compare_rf_structure", fake_compare)

    with pytest.raises(StopAfterComparison):
        kiwi_probe.run_probe_b(_contract(), duration_s=4.0, plan=plan)

    assert [frequency for frequency, duration in capture_calls if duration == plan.scout_duration_s] == list(plan.center_frequencies_hz)
    assert len(compare_calls) == 1
    assert capture_calls[-1][0] == compare_calls[0]


def _contract() -> DecisionContract:
    return DecisionContract(
        Intent("Did one live RF change appear at two stations?"),
        (
            DecisionClause("measurement_availability", "two timed IQ roots", ("iq",), 2),
            DecisionClause("shared_structure_beyond_null", "beats frozen nulls", ("region",), 2),
            DecisionClause("common_physical_cause", "causal account", ("cause",), 2),
        ),
        30.0,
    )


def _shared_transient_pair(seed: int) -> tuple[np.ndarray, np.ndarray]:
    count = int(SAMPLE_RATE * 3.0)
    time_s = np.arange(count) / SAMPLE_RATE
    envelope = np.exp(-0.5 * ((time_s - 1.55) / 0.045) ** 2)
    instantaneous_frequency = 780.0 + 3_200.0 * (time_s - 1.55)
    phase = 2.0 * np.pi * np.cumsum(instantaneous_frequency) / SAMPLE_RATE
    shared = 2.5 * envelope * np.exp(1j * phase)
    rng = np.random.default_rng(seed)
    left_noise = 0.035 * (rng.normal(size=count) + 1j * rng.normal(size=count))
    right_noise = 0.04 * (rng.normal(size=count) + 1j * rng.normal(size=count))
    return (
        (shared + left_noise).astype(np.complex64),
        (shared * np.exp(0.7j) + right_noise).astype(np.complex64),
    )


def _block(
    start: datetime,
    samples: np.ndarray,
    sequence: int,
    sample_rate: float,
    *,
    gps_available: bool = True,
) -> IQBlock:
    event_end = start + timedelta(seconds=len(samples) / sample_rate)
    return IQBlock(
        event_start=start,
        event_end=event_end,
        samples=samples,
        rssi_db=-80.0,
        gps_solution_age_s=2,
        gps_timestamp_available=gps_available,
        adc_overflow=False,
        sequence=sequence,
        arrived_at=event_end + timedelta(milliseconds=80),
    )


def _single_block_capture(
    name: str,
    samples: np.ndarray,
    *,
    start: datetime = NOW,
    center: float = CENTER,
    gps_available: bool = True,
) -> KiwiCapture:
    block = _block(
        start,
        samples,
        1,
        SAMPLE_RATE,
        gps_available=gps_available,
    )
    return _capture_from_blocks(name, (block,), SAMPLE_RATE, center=center)


def _capture_from_blocks(
    name: str,
    blocks: tuple[IQBlock, ...],
    sample_rate: float,
    *,
    center: float = CENTER,
) -> KiwiCapture:
    return KiwiCapture(
        endpoint=KiwiEndpoint(name, "127.0.0.1"),
        center_frequency_hz=center,
        sample_rate_hz=sample_rate,
        status={"ext_api": "4"},
        blocks=blocks,
        arrived_start=blocks[0].event_start,
        arrived_end=blocks[-1].arrived_at or blocks[-1].event_end,
    )
