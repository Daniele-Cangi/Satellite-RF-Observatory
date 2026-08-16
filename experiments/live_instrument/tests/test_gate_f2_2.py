"""Offline Gate F2.2 tests: frozen multipath bootstrap and one-shot boundary."""

from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
import json

import pytest

from experiments.live_instrument import kiwi_gate_f2 as f2
from experiments.live_instrument import kiwi_gate_f2_2 as f22
from experiments.live_instrument import kiwi_probe as kiwi
from experiments.live_instrument.models import strict_json_value


NOW = datetime(2026, 8, 16, 16, 0, tzinfo=timezone.utc)
COMMIT = "a" * 40


def _receipt(
    path: f22.BootstrapPathPlan,
    candidates: int,
    *,
    status: f2.DiscoveryResponseStatus | None = None,
) -> f2.DiscoveryReceipt:
    status = status or (
        f2.DiscoveryResponseStatus.VALID_CANDIDATE_RESULT
        if candidates
        else f2.DiscoveryResponseStatus.VALID_EMPTY_RESULT
    )
    valid = status in (
        f2.DiscoveryResponseStatus.VALID_CANDIDATE_RESULT,
        f2.DiscoveryResponseStatus.VALID_EMPTY_RESULT,
    )
    return f2.DiscoveryReceipt(
        path.provider,
        path.inventory_root,
        path.transport_route,
        path.access_mode,
        NOW,
        NOW + timedelta(seconds=1),
        status,
        candidates,
        "1" * 64 if valid else None,
        None if valid else "FixtureError",
        None if valid else "fixture error",
        0,
        NOW + timedelta(seconds=601),
    )


def test_bootstrap_plan_freezes_exactly_three_paths_before_network() -> None:
    mother = f2.MotherPlan()
    plan = f22.build_bootstrap_plan(mother, started_at=NOW, gate_f2_runtime_commit=COMMIT)
    assert plan.budget_s == 90.0
    assert plan.retry_budget == 1
    assert plan.path_order_or_concurrency == "CONCURRENT_FROZEN_SET"
    assert plan.frequency_policy_version == f22.FREQUENCY_POLICY_VERSION
    assert len(plan.discovery_paths) == 3
    assert plan.discovery_paths[0].inventory_root == plan.discovery_paths[1].inventory_root
    assert plan.discovery_paths[0].transport_route != plan.discovery_paths[1].transport_route
    assert plan.discovery_paths[2].bootstrap_origin is f22.BootstrapOrigin.SESSION_AFFORDANCE
    assert plan.session_affordance_hash == f22.session_affordance_hash()
    assert len(plan.plan_hash) == 64
    strict_json_value(plan)


def test_bootstrap_plan_hash_changes_if_a_postfreeze_path_is_added() -> None:
    mother = f2.MotherPlan()
    plan = f22.build_bootstrap_plan(mother, started_at=NOW, gate_f2_runtime_commit=COMMIT)
    added = f22.BootstrapPathPlan(
        "illegal-fourth",
        f22.BootstrapOrigin.PROVIDER_LISTING,
        "other",
        "other-root",
        "https://other.invalid/list",
        "GET",
    )
    with pytest.raises(ValueError, match="one to three"):
        replace(plan, discovery_paths=plan.discovery_paths + (added,))


def test_session_affordances_are_finite_tracked_candidates_not_capabilities() -> None:
    plan = f22.build_bootstrap_plan(f2.MotherPlan(), started_at=NOW, gate_f2_runtime_commit=COMMIT)
    session_path = plan.discovery_paths[2]
    attempt = f22._session_attempt(session_path, f2.MotherPlan(), retry_index=0, now=lambda: NOW)
    identities = {f22.endpoint_identity(endpoint) for endpoint in attempt.candidates}
    assert identities == {
        "dl1bajkiwisdr.ddns.net:8074",
        "g0ghk.uk:8050",
        "hill.n8ga.org:8073",
        "kiwisdr2blair.ddns.net:8073",
        "kiwisdr.kfsdr.com:8074",
        "va6ok.ddns.net:8073",
    }
    assert attempt.receipt.inventory_root == "session-affordance:tracked-receipts"
    assert attempt.receipt.response_hash == plan.session_affordance_hash
    assert not hasattr(attempt.receipt, "measurement_root")


def test_deduplication_preserves_every_origin_without_increasing_capability_trust(monkeypatch) -> None:
    mother = f2.MotherPlan()
    plan = f22.build_bootstrap_plan(mother, started_at=NOW, gate_f2_runtime_commit=COMMIT)
    shared = kiwi.KiwiEndpoint("shared", "shared.invalid", 8073)
    session_only = kiwi.KiwiEndpoint("session", "session.invalid", 8074)

    def execute(path: f22.BootstrapPathPlan, _mother: f2.MotherPlan, _deadline: float):
        candidates = (shared, session_only) if path.bootstrap_origin is f22.BootstrapOrigin.SESSION_AFFORDANCE else (shared,)
        return f22.PathExecution(path, (_receipt(path, len(candidates)),), candidates)

    monkeypatch.setattr(f22, "_execute_path", execute)
    receipts, candidate_receipts, candidates = f22.execute_bootstrap(plan, mother, sink=lambda _line: None)
    assert len(receipts) == 3
    assert len(candidate_receipts) == 4
    by_id = {candidate.endpoint_identity: candidate for candidate in candidates}
    merged = by_id["shared.invalid:8073"]
    assert set(merged.all_bootstrap_origins) == set(f22.BootstrapOrigin)
    assert set(merged.inventory_roots) == {
        "kiwisdr-public-registry",
        "session-affordance:tracked-receipts",
    }
    assert len(merged.listing_transports) == 3
    assert len(merged.candidate_receipt_hashes) == 3


def test_run_emits_bootstrap_plan_before_any_discovery_result(monkeypatch) -> None:
    mother = f2.MotherPlan()
    plan = f22.build_bootstrap_plan(mother, started_at=NOW, gate_f2_runtime_commit=COMMIT)
    empty = _receipt(plan.discovery_paths[0], 0)

    def bootstrap(_plan, _mother, *, sink):
        return (empty,), (), ()

    monkeypatch.setattr(f22, "execute_bootstrap", bootstrap)
    lines: list[str] = []
    result = f22.run_once(mother=mother, gate_f2_runtime_commit=COMMIT, sink=lines.append)
    events = [json.loads(line)["event"] for line in lines]
    assert events[0] == "gate_f2_2_bootstrap_plan_frozen"
    assert events.index("gate_f2_2_bootstrap_plan_frozen") < events.index("gate_f2_2_discovery_outcome")
    assert result.outcome is f2.OutcomeKind.NO_CAPABILITY_DISCOVERED


def _fingerprint(position: float) -> f2.FeatureFingerprint:
    return f2.FeatureFingerprint(
        position,
        5_000_000.0 + position,
        50.0,
        (-0.2, -0.1, 0.0, 0.4, 0.8, 0.4, 0.0, -0.1, -0.2),
        -700.0,
        (8.0, 7.0, 1.0),
        (7.0, 9.0),
        20.0,
    )


def test_plan_freeze_contains_hardware_duration_prediction_threshold_and_artifact_ledgers() -> None:
    mother = f2.MotherPlan()
    reference = kiwi.KiwiEndpoint("reference", "reference.invalid", 8073)
    perturbed = kiwi.KiwiEndpoint("perturbed", "perturbed.invalid", 8074)
    plan = f2.freeze_plan(
        mother,
        reference,
        perturbed,
        5_000_000.0,
        400.0,
        1,
        _fingerprint(100.0),
        _fingerprint(800.0),
        frozen_at=NOW,
        prediction_tolerance_hz=40.0,
    )
    assert plan.reference_hardware_root == "kiwi:reference.invalid:8073"
    assert plan.perturbed_hardware_root == "kiwi:perturbed.invalid:8074"
    assert (plan.a1_duration_s, plan.b_duration_s, plan.a2_duration_s) == (3.0, 3.0, 3.0)
    assert {name for name, _low, _high in plan.prediction_intervals_hz} == {
        "RF_FRAME_B",
        "BASEBAND_FRAME_B",
        "A_RETURN",
    }
    assert dict(plan.thresholds)["minimum_contrast_db"] == mother.minimum_contrast_db
    assert plan.ttl_s == mother.offer_ttl_s
    assert plan.transform_versions == (f2.TRANSFORM_VERSION,)
    assert "RAM" in plan.artifact_policy
    strict_json_value(asdict(plan))


def test_f2_2_module_is_vertical_not_a_scanner_catalog_or_planner() -> None:
    names = set(vars(f22))
    assert not {"Scanner", "Catalog", "Planner", "InternetSource", "Database"} & names
