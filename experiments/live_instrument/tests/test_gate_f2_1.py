"""Offline Gate F2.1 tests: phase semantics and atomic discovery receipts."""

from dataclasses import fields
from datetime import datetime, timedelta, timezone
from urllib.error import URLError

import pytest

from experiments.live_instrument import kiwi_gate_f2 as f2
from experiments.live_instrument import kiwi_probe as kiwi
from experiments.live_instrument.models import ClauseStatus, strict_json_value


NOW = datetime(2026, 8, 16, 15, 0, tzinfo=timezone.utc)


def _receipt(
    status: f2.DiscoveryResponseStatus,
    *,
    candidate_count: int = 0,
    retry_index: int = 0,
    route: str = "https://inventory.invalid/list",
) -> f2.DiscoveryReceipt:
    valid = status in (
        f2.DiscoveryResponseStatus.VALID_EMPTY_RESULT,
        f2.DiscoveryResponseStatus.VALID_CANDIDATE_RESULT,
    )
    return f2.DiscoveryReceipt(
        "fixture-provider",
        "fixture-inventory-root",
        route,
        "fixture access",
        NOW,
        NOW + timedelta(seconds=1),
        status,
        candidate_count,
        "0" * 64 if valid else None,
        None if valid else "FixtureError",
        None if valid else "fixture failure",
        retry_index,
        NOW + timedelta(seconds=601),
    )


def _result(outcome: f2.OutcomeKind, progress: f2.GateProgress):
    candidate_count = progress.candidates_discovered
    receipt = _receipt(
        f2.DiscoveryResponseStatus.VALID_CANDIDATE_RESULT
        if candidate_count
        else f2.DiscoveryResponseStatus.VALID_EMPTY_RESULT,
        candidate_count=candidate_count,
    )
    return f2.no_experiment_result(
        outcome,
        "fixture stop",
        progress=progress,
        discovery_receipts=(receipt,),
        evaluated_at=NOW,
    )


def test_discovery_receipt_has_no_payload_and_transport_failure_has_no_hash() -> None:
    receipt = _receipt(f2.DiscoveryResponseStatus.TRANSPORT_ERROR)
    assert receipt.response_hash is None
    assert receipt.candidate_count == 0
    assert "response_body" not in {field.name for field in fields(receipt)}
    strict_json_value(receipt)

    with pytest.raises(ValueError, match="cannot invent"):
        f2.DiscoveryReceipt(
            receipt.provider,
            receipt.inventory_root,
            receipt.transport_route,
            receipt.access_mode,
            receipt.started_at,
            receipt.completed_at,
            receipt.response_status,
            0,
            "a" * 64,
            receipt.error_class,
            receipt.error_detail,
            0,
            receipt.expires_at,
        )


def test_valid_discovery_statuses_enforce_candidate_cardinality() -> None:
    _receipt(f2.DiscoveryResponseStatus.VALID_EMPTY_RESULT)
    _receipt(f2.DiscoveryResponseStatus.VALID_CANDIDATE_RESULT, candidate_count=2)
    with pytest.raises(ValueError, match="zero candidates"):
        _receipt(f2.DiscoveryResponseStatus.VALID_EMPTY_RESULT, candidate_count=1)
    with pytest.raises(ValueError, match="at least one"):
        _receipt(f2.DiscoveryResponseStatus.VALID_CANDIDATE_RESULT)


def test_discovery_outcome_is_separate_from_capability_admission() -> None:
    failed = _receipt(f2.DiscoveryResponseStatus.TRANSPORT_ERROR)
    empty = _receipt(f2.DiscoveryResponseStatus.VALID_EMPTY_RESULT)
    candidates = _receipt(f2.DiscoveryResponseStatus.VALID_CANDIDATE_RESULT, candidate_count=3)
    assert f2.discovery_outcome((failed,), unique_candidate_count=0) is f2.DiscoveryOutcomeKind.DISCOVERY_PATH_FAILED
    assert f2.discovery_outcome((failed, empty), unique_candidate_count=0) is f2.DiscoveryOutcomeKind.NO_CAPABILITY_DISCOVERED
    assert f2.discovery_outcome((candidates,), unique_candidate_count=3) is f2.DiscoveryOutcomeKind.CANDIDATES_DISCOVERED


@pytest.mark.parametrize(
    ("outcome", "progress"),
    [
        (f2.OutcomeKind.DISCOVERY_PATH_FAILED, f2.GateProgress(f2.GatePhase.DISCOVERY, 0, 0, 0, 0)),
        (f2.OutcomeKind.NO_CAPABILITY_DISCOVERED, f2.GateProgress(f2.GatePhase.DISCOVERY, 1, 0, 0, 0)),
        (f2.OutcomeKind.NO_CAPABILITY_QUALIFIED, f2.GateProgress(f2.GatePhase.QUALIFICATION, 1, 3, 0, 0)),
        (f2.OutcomeKind.NO_CAPABILITY_ADMITTED, f2.GateProgress(f2.GatePhase.ADMISSION, 1, 3, 2, 0)),
        (f2.OutcomeKind.NO_FALSIFIABLE_EXPERIMENT_AVAILABLE, f2.GateProgress(f2.GatePhase.ADMISSION, 1, 3, 2, 1)),
    ],
)
def test_prefreeze_outcome_invariants_accept_only_reached_phases(
    outcome: f2.OutcomeKind,
    progress: f2.GateProgress,
) -> None:
    f2.validate_prefreeze_outcome(outcome, progress)


@pytest.mark.parametrize(
    ("outcome", "progress"),
    [
        (f2.OutcomeKind.DISCOVERY_PATH_FAILED, f2.GateProgress(f2.GatePhase.DISCOVERY, 1, 0, 0, 0)),
        (f2.OutcomeKind.NO_CAPABILITY_DISCOVERED, f2.GateProgress(f2.GatePhase.DISCOVERY, 0, 0, 0, 0)),
        (f2.OutcomeKind.NO_CAPABILITY_QUALIFIED, f2.GateProgress(f2.GatePhase.QUALIFICATION, 1, 0, 0, 0)),
        (f2.OutcomeKind.NO_CAPABILITY_ADMITTED, f2.GateProgress(f2.GatePhase.ADMISSION, 1, 2, 0, 0)),
        (f2.OutcomeKind.NO_FALSIFIABLE_EXPERIMENT_AVAILABLE, f2.GateProgress(f2.GatePhase.ADMISSION, 1, 2, 2, 0)),
    ],
)
def test_prefreeze_outcome_invariants_reject_phase_leakage(
    outcome: f2.OutcomeKind,
    progress: f2.GateProgress,
) -> None:
    with pytest.raises(ValueError, match="inconsistent"):
        f2.validate_prefreeze_outcome(outcome, progress)


def test_downstream_phase_clauses_are_not_evaluated_until_predecessor_completes() -> None:
    discovery_stop = f2.no_experiment_result(
        f2.OutcomeKind.DISCOVERY_PATH_FAILED,
        "transport failed",
        progress=f2.GateProgress(f2.GatePhase.DISCOVERY, 0, 0, 0, 0),
        discovery_receipts=(_receipt(f2.DiscoveryResponseStatus.TRANSPORT_ERROR),),
        evaluated_at=NOW,
    )
    assert all(item.status is ClauseStatus.NOT_EVALUATED for item in discovery_stop.phase_clause_assessments)
    assert all(item.status is ClauseStatus.NOT_EVALUATED for item in discovery_stop.clause_assessments)

    qualification_stop = _result(
        f2.OutcomeKind.NO_CAPABILITY_QUALIFIED,
        f2.GateProgress(f2.GatePhase.QUALIFICATION, 1, 2, 0, 0),
    )
    phase = {item.clause: item.status for item in qualification_stop.phase_clause_assessments}
    assert phase == {
        "qualification_completed": ClauseStatus.UNSATISFIED,
        "capability_admitted": ClauseStatus.NOT_EVALUATED,
        "falsifiable_intervention_available": ClauseStatus.NOT_EVALUATED,
    }

    admission_stop = _result(
        f2.OutcomeKind.NO_CAPABILITY_ADMITTED,
        f2.GateProgress(f2.GatePhase.ADMISSION, 1, 2, 1, 0),
    )
    phase = {item.clause: item.status for item in admission_stop.phase_clause_assessments}
    assert phase["qualification_completed"] is ClauseStatus.SATISFIED
    assert phase["capability_admitted"] is ClauseStatus.UNSATISFIED
    assert phase["falsifiable_intervention_available"] is ClauseStatus.NOT_EVALUATED


def test_listing_transport_is_not_inventory_or_measurement_root() -> None:
    mirror_a = f2.CapabilityLineage("registry-1", "https-route-a")
    mirror_b = f2.CapabilityLineage("registry-1", "https-route-b")
    registry_b = f2.CapabilityLineage("registry-2", "api-route")
    assert f2.inventory_root_count((mirror_a, mirror_b)) == 1
    assert f2.inventory_root_count((mirror_a, mirror_b, registry_b)) == 2

    with pytest.raises(ValueError, match="measurement root"):
        f2.CapabilityLineage("registry-1", "route", "endpoint", None, False, "measurement")
    direct = f2.CapabilityLineage("registry-1", "route", "endpoint", "hardware", True, "measurement")
    assert direct.measurement_root == "measurement"


def test_expired_candidate_receipt_cannot_enter_pair_admission() -> None:
    left = f2.EndpointCapability(
        kiwi.KiwiEndpoint("left", "left.invalid", 8073),
        f2.CapabilityState.CAPABILITY_QUALIFIED,
        NOW - timedelta(seconds=10),
        "left-hash",
        1,
        True,
        (50.0, 7.0),
        "fixture",
        NOW + timedelta(seconds=10),
    )
    expired = f2.EndpointCapability(
        kiwi.KiwiEndpoint("expired", "expired.invalid", 8073),
        f2.CapabilityState.CAPABILITY_QUALIFIED,
        NOW - timedelta(seconds=20),
        "expired-hash",
        1,
        True,
        (51.0, 7.0),
        "fixture",
        NOW - timedelta(seconds=1),
    )
    assert f2.enumerate_hardware_pairs((left, expired), f2.MotherPlan(), at=NOW) == ()


def test_transport_error_in_run_once_is_discovery_path_failed_not_rejection(monkeypatch) -> None:
    def fail(_mother: f2.MotherPlan, *, retry_index: int):
        return f2.DiscoveryAttempt(
            _receipt(f2.DiscoveryResponseStatus.TRANSPORT_ERROR, retry_index=retry_index),
            (),
        )

    monkeypatch.setattr(f2, "discover_directory_attempt", fail)
    lines: list[str] = []
    result = f2.run_once(sink=lines.append)
    assert result.outcome is f2.OutcomeKind.DISCOVERY_PATH_FAILED
    assert result.phase_reached is f2.GatePhase.DISCOVERY
    assert result.progress == f2.GateProgress(f2.GatePhase.DISCOVERY, 0, 0, 0, 0)
    assert len(result.discovery_receipts) == 2
    assert result.evidence_receipt.model_roots == ("inventory:fixture-inventory-root",)
    assert not any("CAPABILITY_REJECTED" in line or "capability_rejected" in line for line in lines)


def test_direct_discovery_transport_failure_is_atomic_and_does_not_touch_network_again(monkeypatch) -> None:
    calls = 0

    def refuse(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise URLError("offline fixture")

    monkeypatch.setattr(f2, "urlopen", refuse)
    attempt = f2.discover_directory_attempt(f2.MotherPlan(), retry_index=0, now=lambda: NOW)
    assert calls == 1
    assert attempt.candidates == ()
    assert attempt.receipt.response_status is f2.DiscoveryResponseStatus.TRANSPORT_ERROR
    assert attempt.receipt.response_hash is None


@pytest.mark.parametrize(
    ("payload", "http_status", "expected", "candidate_count"),
    [
        (b"<html>no receivers</html>", 200, f2.DiscoveryResponseStatus.VALID_EMPTY_RESULT, 0),
        (b"http://receiver.invalid:8073", 200, f2.DiscoveryResponseStatus.VALID_CANDIDATE_RESULT, 1),
        (b"\xff", 200, f2.DiscoveryResponseStatus.DESCRIPTION_ERROR, 0),
        (b"service unavailable", 503, f2.DiscoveryResponseStatus.PROTOCOL_ERROR, 0),
    ],
)
def test_response_statuses_are_derived_before_capability_semantics(
    monkeypatch,
    payload: bytes,
    http_status: int,
    expected: f2.DiscoveryResponseStatus,
    candidate_count: int,
) -> None:
    class Response:
        status = http_status

        def read(self) -> bytes:
            return payload

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

    monkeypatch.setattr(f2, "urlopen", lambda *_args, **_kwargs: Response())
    attempt = f2.discover_directory_attempt(f2.MotherPlan(), retry_index=0, now=lambda: NOW)
    assert attempt.receipt.response_status is expected
    assert attempt.receipt.candidate_count == candidate_count
    assert attempt.receipt.response_hash is not None
