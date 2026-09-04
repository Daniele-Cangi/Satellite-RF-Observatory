"""Offline tests for the frozen DRAO physical-envelope audit."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from experiments.orbital_discriminability import (
    gnss_drao_physical_envelope_audit as audit,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def frozen() -> dict[str, object]:
    return audit.build_audit(ROOT)


def test_common_mode_transfer_is_topology_aware() -> None:
    assert audit.centered_peak_to_peak_bounds([10.0] * 6) == (20.0,) * 6
    assert audit.centered_peak_to_peak_bounds([6.0, 0.0, 0.0, 0.0, 0.0, 0.0]) == (
        7.0,
        1.0,
        1.0,
        1.0,
        1.0,
        1.0,
    )
    with pytest.raises(audit.DraoPhysicalEnvelopeError):
        audit.centered_peak_to_peak_bounds([1.0] * 5)


def test_common_receiver_clock_is_not_confused_with_implementation(
    frozen: dict[str, object],
) -> None:
    topology = frozen["common_mode_topology"]
    terms = {row["term"]: row for row in frozen["terms"]}
    receiver = terms["RECEIVER_CLOCK_AND_IMPLEMENTATION"]

    assert topology["epoch_common_additive_receiver_clock_cancels_exactly"] is True
    assert receiver["epoch_common_receiver_clock_contribution_m"] == 0.0
    assert receiver["state"] == "PARTIAL_EXACT_CANCELLATION_REMAINDER_UNRESOLVED"
    assert receiver["common_mode_heldout_peak_to_peak_bound_m"] is None


def test_partial_code_witness_cannot_bound_the_full_phase_window(
    frozen: dict[str, object],
) -> None:
    terms = {row["term"]: row for row in frozen["terms"]}
    hardware = terms["MULTIPATH_AND_SIGNAL_SPECIFIC_HARDWARE"]

    assert audit.maximum_missing_witness_epochs() == 6
    assert hardware["maximum_unwitnessed_epochs_per_track"] == 6
    assert hardware["state"] == "UNRESOLVED"
    assert hardware["common_mode_heldout_peak_to_peak_bound_m"] is None
    assert hardware["conditional_bound_if_every_epoch_witnessed_m"] == 2_500.0


def test_direct_timing_bound_is_refused_without_retained_curves(
    frozen: dict[str, object],
) -> None:
    terms = {row["term"]: row for row in frozen["terms"]}
    timing = terms["EVENT_TIME_DIRECT_TRAJECTORY_ENVELOPE"]

    assert timing["state"] == "UNRESOLVED"
    assert timing["common_mode_heldout_peak_to_peak_bound_m"] is None
    assert timing["forbidden_substitute"] == "LOCAL_SLOPE_TIMES_CLOCK_ERROR"


def test_audit_closes_before_artifact_and_does_not_score(
    frozen: dict[str, object],
) -> None:
    aggregate = frozen["aggregate"]

    assert frozen["outcome"] == audit.OUTCOME
    assert aggregate["numeric_state"] == "UNAVAILABLE"
    assert aggregate["common_mode_heldout_peak_to_peak_bound_m"] is None
    assert aggregate["unresolved_terms_defaulted_to_zero"] is False
    assert aggregate["admitted"] is False
    assert len(aggregate["unresolved_terms"]) == 7
    assert set(frozen["artifact_access"].values()) == {0}
    assert frozen["orbital_scores_produced"] == 0
    assert frozen["route_state"] == "CLOSED_BEFORE_DRAO_ARTIFACT_SELECTION"


def test_only_finite_active_term_is_strictly_below_guard(
    frozen: dict[str, object],
) -> None:
    aggregate = frozen["aggregate"]

    assert aggregate["finite_partial_bound_m"] == pytest.approx(18.125149614907023)
    assert aggregate["finite_partial_bound_m"] < aggregate["guard_m"]
    assert aggregate["comparison_to_guard"] == (
        "NOT_EVALUABLE_WITH_UNRESOLVED_TERMS"
    )


def test_source_has_no_network_or_observation_decoder_surface() -> None:
    source = inspect.getsource(audit).lower()
    for forbidden in (
        "import requests",
        "import urllib",
        "import socket",
        "rinexfile",
        "observation decoder",
        "product_url",
    ):
        assert forbidden not in source


def test_persisted_artifacts_match_builder(frozen: dict[str, object]) -> None:
    persisted = json.loads((ROOT / audit.AUDIT_NAME).read_text(encoding="utf-8"))
    report = (ROOT / audit.REPORT_NAME).read_text(encoding="utf-8")

    assert persisted == frozen
    assert report == audit.render_report(frozen)
    assert "DRAO_PHYSICAL_ENVELOPE_NOT_ADMITTED" in report
    assert "UNAVAILABLE" in report


def test_changed_plan_hash_is_refused(tmp_path: Path) -> None:
    for name in (audit.PLAN_NAME, audit.HISTORICAL_ENVELOPE_NAME):
        (tmp_path / name).write_bytes((ROOT / name).read_bytes())
    plan_path = tmp_path / audit.PLAN_NAME
    plan_path.write_bytes(plan_path.read_bytes() + b"\n")

    with pytest.raises(
        audit.DraoPhysicalEnvelopeError,
        match="FROZEN_ARTIFACT_HASH_CHANGED",
    ):
        audit.build_audit(tmp_path)
