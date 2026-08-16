"""Offline failure-injection tests for clause-driven SatNOGS failover."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from experiments.live_instrument.models import (
    ClauseStatus,
    ModelAvailability,
    Transform,
)
from experiments.live_instrument.satnogs_failover import (
    EVENT_TIME,
    RF_STRUCTURE,
    ObservationLease,
    atomic_offer_from_artifact,
    continuity_contract,
    corroboration_contract,
    evaluate_contract,
    failover_once,
    model_snapshot,
    select_replacement,
)
from experiments.live_instrument.satnogs_probe import (
    SatnogsObservation,
    WaterfallArtifact,
)


NOW = datetime(2026, 8, 16, 0, 30, tzinfo=timezone.utc)


def test_waterfall_receipt_is_atomic_and_identity_remains_control_only() -> None:
    offer = _offer(11, 101, age_s=40)

    assert offer.receipt.branch == "satnogs-waterfall-atomic"
    assert offer.receipt.measurement_roots == ("station:101",)
    assert offer.receipt.artifact_hashes == (f"{11:064x}",)
    assert set(offer.provided_observables) == {RF_STRUCTURE, EVENT_TIME}
    identity = next(
        constraint for constraint in offer.receipt.constraints if constraint.name == "target_identity"
    )
    assert identity.relation == "not_inferred"
    assert all("station:101" != root for root in offer.receipt.model_roots)


def test_continuity_and_corroboration_are_separate_contracts() -> None:
    continuity = continuity_contract(600)
    corroboration = corroboration_contract(600)

    assert continuity.clauses[0].minimum_measurement_roots == 1
    assert corroboration.clauses[0].minimum_measurement_roots == 2
    assert continuity.clauses[0].name != corroboration.clauses[0].name

    one_offer = (_offer(1, 10, age_s=20),)
    assert (
        evaluate_contract(continuity, one_offer, NOW)
        .belief.assessment("measurement_continuity")
        .status
        is ClauseStatus.SATISFIED
    )
    corroboration_eval = evaluate_contract(corroboration, one_offer, NOW)
    assert (
        corroboration_eval.belief.assessment("measurement_corroboration").status
        is ClauseStatus.UNOBSERVABLE
    )


def test_initial_ranking_is_deterministic_and_prefers_remaining_ttl() -> None:
    contract = continuity_contract(600)
    older = _offer(1, 10, age_s=120)
    fresher = _offer(2, 11, age_s=30)

    forward = select_replacement(contract, (), (older, fresher), NOW)
    reverse = select_replacement(contract, (), (fresher, older), NOW)

    assert forward.selected == fresher
    assert reverse.selected == fresher
    assert forward.selected_score is not None
    assert forward.selected_score.restored_clauses == ("measurement_continuity",)
    assert forward.selected_score.remaining_ttl_s == 570


def test_continuity_revocation_selects_a_non_hardcoded_replacement() -> None:
    contract = continuity_contract(600)
    primary = _offer(1, 10, age_s=80)
    replacement = _offer(27, 99, age_s=20)
    lease = ObservationLease("lease:primary", primary, NOW - timedelta(seconds=2))

    result = failover_once(
        contract,
        (lease,),
        (replacement, primary),
        primary.offer_id,
        NOW,
    )

    assert result.before.belief.assessment("measurement_continuity").status is ClauseStatus.SATISFIED
    assert result.after_revocation.belief.assessment("measurement_continuity").status is ClauseStatus.UNOBSERVABLE
    assert result.lost_clauses == ("measurement_continuity",)
    assert result.replacement_lease is not None
    assert result.replacement_lease.offer == replacement
    assert result.after_replacement.belief.assessment("measurement_continuity").status is ClauseStatus.SATISFIED
    assert result.replacement_requests == replacement.request_count
    assert result.replacement_bytes == replacement.bytes_received
    revoked_rejection = next(
        rejection
        for rejection in result.decision.rejections
        if rejection.offer_id == primary.offer_id
    )
    assert "offer was revoked" in revoked_rejection.reasons


def test_corroboration_replaces_revoked_root_with_a_third_root() -> None:
    contract = corroboration_contract(600)
    primary = _offer(1, 10, age_s=80)
    survivor = _offer(2, 11, age_s=60)
    third_root = _offer(3, 12, age_s=40)
    repeated_survivor = _offer(4, 11, age_s=5)
    leases = (
        ObservationLease("lease:a", primary, NOW),
        ObservationLease("lease:b", survivor, NOW),
    )

    result = failover_once(
        contract,
        leases,
        (repeated_survivor, third_root, survivor, primary),
        primary.offer_id,
        NOW,
    )

    assert result.before.belief.assessment("measurement_corroboration").status is ClauseStatus.SATISFIED
    assert result.after_revocation.belief.assessment("measurement_corroboration").status is ClauseStatus.UNOBSERVABLE
    assert result.replacement_lease is not None
    assert result.replacement_lease.offer == third_root
    assert result.after_replacement.belief.assessment("measurement_corroboration").status is ClauseStatus.SATISFIED
    assert set(result.after_replacement.belief.active_measurement_roots) == {
        "station:11",
        "station:12",
    }
    repeated_rejection = next(
        item for item in result.decision.rejections if item.offer_id == repeated_survivor.offer_id
    )
    assert repeated_rejection.reasons == (
        "candidate adds no independent root toward a lost clause",
    )


def test_transform_deficits_precede_cost_and_remain_explicit() -> None:
    contract = corroboration_contract(600)
    survivor = _offer(2, 11, age_s=50)
    complete = _offer(3, 12, age_s=20, bytes_received=2_000_000)
    obscure = _offer(4, 13, age_s=20, bytes_received=100)
    obscure = _replace_transforms(
        obscure,
        (
            Transform("rf_chain", "unknown", "not published"),
            Transform("waterfall", "known_lossy", "raster"),
        ),
    )

    decision = select_replacement(
        contract,
        (survivor,),
        (obscure, complete),
        NOW,
        lost_clauses=("measurement_corroboration",),
    )

    assert decision.selected == complete
    assert decision.ranked_scores[0].transform_deficits.unknown == 0
    assert decision.ranked_scores[1].transform_deficits.unknown == 1
    assert decision.ranked_scores[0].value_per_cost < decision.ranked_scores[1].value_per_cost


def test_value_per_cost_breaks_an_epistemically_equal_tie() -> None:
    contract = continuity_contract(600)
    expensive = _offer(1, 10, age_s=30, bytes_received=2_000_000)
    efficient = _offer(2, 11, age_s=30, bytes_received=100_000)

    decision = select_replacement(contract, (), (expensive, efficient), NOW)

    assert decision.selected == efficient
    assert decision.ranked_scores[0].value_per_cost > decision.ranked_scores[1].value_per_cost


def test_expiry_uses_event_end_and_model_available_is_not_measurement() -> None:
    contract = continuity_contract(5)
    # Arrival is current, but the physical event ended ten seconds ago.
    expired = _offer(1, 10, age_s=10, arrived_at=NOW)

    evaluation = evaluate_contract(contract, (expired,), NOW)
    model = model_snapshot((expired,), NOW)
    decision = select_replacement(contract, (), (expired,), NOW)

    assert evaluation.expired_offer_ids == (expired.offer_id,)
    assert evaluation.belief.active_measurement_roots == ()
    assert evaluation.belief.active_model_roots == ()
    assert (
        evaluation.belief.assessment("measurement_continuity").status
        is ClauseStatus.UNOBSERVABLE
    )
    assert model.status is ModelAvailability.MODEL_AVAILABLE
    assert model.model_roots
    assert decision.selected is None
    assert decision.rejections[0].reasons == ("offer expired by event_end TTL",)


def test_total_expiry_can_be_audited_by_advancing_now() -> None:
    contract = corroboration_contract(600)
    left = _offer(1, 10, age_s=100)
    right = _offer(2, 11, age_s=90)
    before = evaluate_contract(contract, (left, right), NOW)
    after = evaluate_contract(contract, (left, right), NOW + timedelta(seconds=511))

    assert before.belief.assessment("measurement_corroboration").status is ClauseStatus.SATISFIED
    assert after.belief.assessment("measurement_corroboration").status is ClauseStatus.UNOBSERVABLE
    assert after.belief.active_measurement_roots == ()
    assert set(after.expired_offer_ids) == {left.offer_id, right.offer_id}


def test_incompatible_control_context_is_rejected_with_reason() -> None:
    contract = corroboration_contract(600)
    active = _offer(1, 10, age_s=50)
    other_pass = _offer(2, 11, age_s=20, transmitter_uuid="other-transmitter")

    decision = select_replacement(
        contract,
        (active,),
        (other_pass,),
        NOW,
        lost_clauses=("measurement_corroboration",),
    )

    assert decision.selected is None
    assert decision.rejections[0].reasons == (
        "control context or event window is incompatible",
    )


def test_unrelated_control_contexts_cannot_be_pooled_for_corroboration() -> None:
    contract = corroboration_contract(600)
    first_pass = _offer(1, 10, age_s=50)
    other_pass = _offer(2, 11, age_s=20, transmitter_uuid="other-transmitter")

    evaluation = evaluate_contract(contract, (first_pass, other_pass), NOW)

    assert (
        evaluation.belief.assessment("measurement_corroboration").status
        is ClauseStatus.UNOBSERVABLE
    )
    assert len(evaluation.belief.active_measurement_roots) == 1


def _offer(
    observation_id: int,
    station_id: int,
    *,
    age_s: float,
    bytes_received: int = 1_000,
    arrived_at: datetime = NOW,
    transmitter_uuid: str = "shared-transmitter",
):
    event_end = NOW - timedelta(seconds=age_s)
    observation = SatnogsObservation(
        observation_id=observation_id,
        start=NOW - timedelta(minutes=8),
        end=event_end,
        station_id=station_id,
        station_name=f"station-{station_id}",
        station_lat=50.0 + station_id / 100,
        station_lng=8.0 + station_id / 100,
        station_alt_m=100.0,
        norad_id=40014,
        transmitter_uuid=transmitter_uuid,
        carrier_hz=437_445_000.0,
        waterfall_url=f"https://example.invalid/{observation_id}.png",
        status="good",
        tle1="1 25544U 98067A   19343.69339541  .00001764  00000-0  38792-4 0  9991",
        tle2="2 25544  51.6439 211.2001 0007417  17.6667  85.6398 15.50103472202482",
    )
    artifact = WaterfallArtifact(
        observation=observation,
        arrived_at=arrived_at,
        published_at=arrived_at - timedelta(seconds=2),
        content_length=bytes_received,
        sha256_hex=f"{observation_id:064x}",
        constraints={
            "structured_time_fraction": 0.02,
            "structured_time_segments_image_fraction": [[0.2, 0.3]],
            "bright_energy_band_normalized_from_center": [-0.1, 0.1],
            "plot_pixels": [100, 200],
        },
    )
    return atomic_offer_from_artifact(artifact)


def _replace_transforms(offer, transforms):
    receipt = replace(offer.receipt, transforms=transforms)
    evidence = replace(offer.evidence, receipt=receipt)
    return replace(offer, evidence=evidence)
