"""Gate G1 pass-specific capability admission tests."""

from dataclasses import asdict, replace
from datetime import timedelta
import inspect
import json

import numpy as np
import pytest

from experiments.orbital_discriminability import g1_admission as g1
from experiments.orbital_discriminability.g1_synthetic import (
    EVALUATED_AT,
    coarse_local_offers,
    reference_offers,
    reference_pass_plan,
    run_reference_admission,
)


def _clause(assessment, clause_id: str):  # type: ignore[no-untyped-def]
    return next(item for item in assessment.clauses if item.clause_id == clause_id)


def test_reference_pair_is_admitted_for_pass_specific_margin() -> None:
    result = run_reference_admission()

    assert result.outcome == g1.G1Outcome.CAPABILITY_SET_ADMITTED.value
    assert result.selected_pair is not None
    selected = next(
        pair for pair in result.pair_assessments if pair.capability_ids == result.selected_pair
    )
    assert selected.admitted
    assert selected.detectability_margin_hz > 0.0
    assert selected.joint_visible_holdout_samples >= 12
    assert selected.hardware_roots[0] != selected.hardware_roots[1]
    assert result.raw_rf_activity == "ZERO"
    assert result.calibrated_probability_used is False


def test_available_coarse_local_pair_is_not_detectable() -> None:
    result = g1.evaluate_capability_admission(
        reference_pass_plan(),
        coarse_local_offers(),
        evaluated_at=EVALUATED_AT,
    )

    assert all(item.qualified for item in result.capability_assessments)
    assert result.outcome == g1.G1Outcome.NO_CAPABILITY_ADMITTED.value
    assert result.terminal_reason == "NO_PAIR_CLEARS_DETECTABILITY"
    assert result.pair_assessments[0].detectability_margin_hz < 0.0


def test_same_hardware_root_blocks_even_detectable_geometry() -> None:
    offers = reference_offers()[:2]
    shared = (
        replace(offers[0], hardware_root="receiver:shared"),
        replace(offers[1], hardware_root="receiver:shared"),
    )
    result = g1.evaluate_capability_admission(
        reference_pass_plan(),
        shared,
        evaluated_at=EVALUATED_AT,
    )

    assert result.outcome == g1.G1Outcome.NO_CAPABILITY_ADMITTED.value
    assert result.terminal_reason == "NO_INDEPENDENT_HARDWARE_ROOT_PAIR"
    pair = result.pair_assessments[0]
    assert pair.detectability_margin_hz > 0.0
    assert _clause(pair, "independent_hardware_roots").state == "UNSATISFIED"


@pytest.mark.parametrize(
    ("mutation", "clause_id"),
    (
        ({"same_path_witnesses": ("sample_sequence",)}, "same_path_witnesses"),
        ({"frequency_axis_preserved": False}, "frequency_axis_preserved"),
        ({"ridge_shape_preserved": False}, "ridge_shape_preserved"),
        ({"event_time_source": None}, "event_time_bound"),
        ({"sequence_continuity_exposed": False}, "sequence_continuity"),
        ({"availability_end": reference_pass_plan().end_time - timedelta(seconds=1)}, "full_pass_window"),
        ({"band_high_hz": 145_700_000.0}, "carrier_band"),
    ),
)
def test_missing_observability_property_fails_individual_qualification(
    mutation: dict[str, object],
    clause_id: str,
) -> None:
    offers = list(reference_offers()[:2])
    offers[0] = replace(offers[0], **mutation)
    result = g1.evaluate_capability_admission(
        reference_pass_plan(),
        offers,
        evaluated_at=EVALUATED_AT,
    )

    assessment = next(
        item for item in result.capability_assessments if item.capability_id == offers[0].capability_id
    )
    assert not assessment.qualified
    assert _clause(assessment, clause_id).state == "UNSATISFIED"
    assert result.terminal_reason == "INDIVIDUAL_QUALIFICATION_FAILED"


def test_expired_description_cannot_be_rescued_by_future_availability() -> None:
    offers = list(reference_offers()[:2])
    offers[0] = replace(
        offers[0],
        described_at=EVALUATED_AT - timedelta(seconds=601),
        ttl_s=600.0,
    )
    result = g1.evaluate_capability_admission(
        reference_pass_plan(),
        offers,
        evaluated_at=EVALUATED_AT,
    )

    assessment = next(
        item for item in result.capability_assessments if item.capability_id == offers[0].capability_id
    )
    assert _clause(assessment, "description_ttl").state == "UNSATISFIED"
    assert _clause(assessment, "full_pass_window").state == "SATISFIED"


def test_offer_fresh_now_but_expiring_before_pass_end_is_not_qualified() -> None:
    offers = list(reference_offers()[:2])
    offers[0] = replace(offers[0], ttl_s=30.0)
    result = g1.evaluate_capability_admission(
        reference_pass_plan(),
        offers,
        evaluated_at=EVALUATED_AT,
    )
    assessment = next(
        item for item in result.capability_assessments if item.capability_id == offers[0].capability_id
    )

    assert offers[0].described_at <= EVALUATED_AT
    assert _clause(assessment, "description_ttl").state == "UNSATISFIED"
    assert not assessment.qualified


def test_offer_order_cannot_change_selection_or_receipts() -> None:
    plan = reference_pass_plan()
    offers = reference_offers()
    forward = g1.evaluate_capability_admission(plan, offers, evaluated_at=EVALUATED_AT)
    reverse = g1.evaluate_capability_admission(
        plan,
        tuple(reversed(offers)),
        evaluated_at=EVALUATED_AT,
    )

    assert forward == reverse
    assert forward.selected_pair == ("BERLIN", "EINDHOVEN")


def test_plan_hash_binds_orbit_carrier_window_and_thresholds() -> None:
    plan = reference_pass_plan()
    hashes = {
        plan.plan_hash,
        replace(plan, carrier_hz=145_900_000.0).plan_hash,
        replace(plan, end_time=plan.end_time + timedelta(seconds=5)).plan_hash,
        replace(plan, minimum_signature_bins=4.0).plan_hash,
    }

    assert len(hashes) == 4
    assert len(plan.plan_hash) == 64


def test_result_and_rejected_offer_are_strict_hash_bound_json() -> None:
    offers = list(reference_offers()[:2])
    offers[0] = replace(offers[0], frequency_resolution_hz=None)
    result = g1.evaluate_capability_admission(
        reference_pass_plan(),
        offers,
        evaluated_at=EVALUATED_AT,
    )
    encoded = result.strict_json()
    payload = json.loads(encoded)

    assert len(payload["capability_assessments"][0]["offer_hash"]) == 64
    assert "NaN" not in encoded and "Infinity" not in encoded
    assert json.dumps(asdict(result), allow_nan=False)


def test_nonfinite_and_numpy_offer_scalars_remain_descriptive() -> None:
    offers = list(reference_offers()[:2])
    offers[0] = replace(
        offers[0],
        frequency_resolution_hz=np.float64("nan"),
        sequence_continuity_exposed=np.bool_(True),
    )
    result = g1.evaluate_capability_admission(
        reference_pass_plan(),
        offers,
        evaluated_at=EVALUATED_AT,
    )
    assessment = next(
        item for item in result.capability_assessments if item.capability_id == offers[0].capability_id
    )

    assert not assessment.qualified
    assert len(assessment.offer_hash) == 64
    assert _clause(assessment, "frequency_resolution").state == "UNSATISFIED"
    assert "NaN" not in result.strict_json()


def test_g1_has_no_discovery_connector_or_rf_payload_path() -> None:
    source = inspect.getsource(g1)

    assert "requests" not in source
    assert "urllib" not in source
    assert "websocket" not in source
    assert "satnogs_probe" not in source
    assert "kiwi_probe" not in source
    assert "socket" not in source
    assert "connect(" not in source
    assert "np.complex" not in source
    assert "raw_rf_activity: str = \"ZERO\"" in source


@pytest.mark.parametrize(
    "mutation",
    (
        {"start_time": reference_pass_plan().start_time.replace(tzinfo=None)},
        {"carrier_hz": 0.0},
        {"minimum_joint_holdout_samples": 2},
        {"required_transforms": ()},
    ),
)
def test_invalid_frozen_plan_is_refused(mutation: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        replace(reference_pass_plan(), **mutation).validate()
