"""Offline tests for the one-shot Gate F2.4 vertical runner."""

import ast
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.live_instrument import kiwi_gate_f2 as f2
from experiments.live_instrument import kiwi_gate_f2_3 as f23
from experiments.live_instrument import kiwi_gate_f2_4 as f24
from experiments.live_instrument import kiwi_probe as kiwi
from experiments.live_instrument.models import ClauseStatus, strict_json_value


NOW = datetime(2026, 8, 16, 18, 0, tzinfo=timezone.utc)
ENDPOINT = kiwi.KiwiEndpoint("fixture", "fixture.invalid", 8073)


def _server() -> f24.ServerInstanceReceipt:
    return f24.ServerInstanceReceipt(
        "fixture.invalid:8073",
        "1" * 64,
        (("version_maj", "1"), ("version_min", "800")),
        "2" * 64,
        "3" * 64,
        "rx:1",
        "rx:2",
        "explicit server handshake channel identifier",
        "4" * 64,
    )


def _fingerprint(position: float, witness_position: float) -> f2.FeatureFingerprint:
    return f2.FeatureFingerprint(
        position,
        10_000_000.0 + position,
        20.0,
        (-0.2, -0.1, 0.1, 0.5, 0.9, 0.5, 0.1, -0.1, -0.2),
        position - witness_position,
        (7.0, 7.2, 0.2),
        (7.0, 9.0),
        20.0,
    )


def _plan() -> f24.F24Plan:
    target = _fingerprint(1000.0, -1200.0)
    witness = _fingerprint(-1200.0, 1000.0)
    delta = 750.0
    translation = -delta
    tolerance = 20.0
    return f24.F24Plan(
        ENDPOINT,
        _server(),
        "rx:1",
        "rx:2",
        10_000_000.0,
        10_000_750.0,
        delta,
        1,
        translation,
        target,
        witness,
        ("a" * 64, "b" * 64),
        3.0,
        0.8,
        3.0,
        3.0,
        (
            ("TARGET_UPSTREAM_B", 250.0 - tolerance, 250.0 + tolerance),
            ("TARGET_DOWNSTREAM_B", 1000.0 - tolerance, 1000.0 + tolerance),
            ("WITNESS_UPSTREAM_B", -1950.0 - tolerance, -1950.0 + tolerance),
            ("TARGET_A_RETURN", 1000.0 - tolerance, 1000.0 + tolerance),
            ("WITNESS_A_RETURN", -1200.0 - tolerance, -1200.0 + tolerance),
        ),
        1750.0,
        625.0,
        -875.0,
        (
            ("minimum_contrast_db", 5.0),
            ("minimum_witness_contrast_db", 5.0),
            ("minimum_fingerprint_correlation", 0.65),
            ("prediction_tolerance_hz", tolerance),
            ("spectral_resolution_hz", 10.0),
            ("maximum_arrival_latency_s", 5.0),
        ),
        NOW,
        NOW + timedelta(seconds=600),
        600.0,
        (f2.TRANSFORM_VERSION, f24.F24_TRANSFORM_VERSION),
        "SHA-256 before analysis and destruction; zero RF persistence; receipts and hashes only",
    )


def _qualified() -> f24.EndpointQualification:
    states = {
        name: (f24.PropertyState.SATISFIED, "fixture satisfied")
        for name in f24.QUALIFICATION_PROPERTIES
    }
    return f24._qualification_receipt(
        ENDPOINT,
        0,
        states,
        artifact_hashes=("c" * 64,),
        status_hash="d" * 64,
        server=_server(),
        center_a_hz=10_000_000.0,
        axis_orientation=1,
        reason="fixture qualified",
    )


def _block(start: datetime, sequence: int, *, overflow: bool = False) -> kiwi.IQBlock:
    samples = np.zeros(2000, dtype=np.complex64)
    end = start + timedelta(seconds=2)
    return kiwi.IQBlock(
        start,
        end,
        samples,
        -80.0,
        0,
        True,
        overflow,
        sequence,
        end + timedelta(milliseconds=10),
    )


def _artifact(role: str, phase: str, block: kiwi.IQBlock, center: float) -> f24._MemoryArtifact:
    capture = kiwi.KiwiCapture(
        ENDPOINT,
        center,
        1000.0,
        {"role": role, "phase": phase},
        (block,),
        block.arrived_at,
        block.arrived_at,
    )
    return f24._MemoryArtifact(capture, (role[0] + phase[0]).encode().hex().ljust(64, "0"), 8000, f"rx:{1 if role == 'reference' else 2}", role, phase, center)


def _confirmation(*, overflow: bool = False) -> f24._DualArtifacts:
    reference: dict[str, f24._MemoryArtifact] = {}
    perturbed: dict[str, f24._MemoryArtifact] = {}
    reference_blocks = []
    perturbed_blocks = []
    for index, phase in enumerate(("A1", "B", "A2")):
        start = NOW + timedelta(seconds=index * 2)
        ref_block = _block(start, 10 + index, overflow=overflow)
        pert_block = _block(start, 20 + index, overflow=overflow)
        reference[phase] = _artifact("reference", phase, ref_block, 10_000_000.0)
        perturbed[phase] = _artifact(
            "perturbed",
            phase,
            pert_block,
            10_000_750.0 if phase == "B" else 10_000_000.0,
        )
        reference_blocks.append(ref_block)
        perturbed_blocks.append(pert_block)
    return f24._DualArtifacts(
        reference,
        perturbed,
        tuple(reference_blocks),
        tuple(perturbed_blocks),
        (),
        (("SET B", NOW + timedelta(seconds=2)), ("SET A2", NOW + timedelta(seconds=4))),
    )


def test_bootstrap_freezes_exactly_the_six_prior_affordances_before_network() -> None:
    receipt = f24.build_bootstrap_receipt(runtime_commit="e" * 40, created_at=NOW)
    assert len(receipt.candidate_order) == 6
    assert receipt.candidate_order == f24.ordered_candidate_identities()
    assert receipt.candidate_set_hash == f24.candidate_set_hash()
    assert receipt.qualification_budget_s == 420.0
    assert receipt.retry_budget == 2
    assert receipt.maximum_retry_per_endpoint == 1
    assert receipt.selection_policy == f24.SELECTION_POLICY
    assert len(receipt.receipt_hash) == 64
    strict_json_value(receipt)


def test_plan_binds_same_server_channel_ids_and_detectability_envelope() -> None:
    plan = _plan()
    assert plan.reference_channel_id == plan.server_instance_receipt.reference_channel_id
    assert plan.perturbed_channel_id == plan.server_instance_receipt.perturbed_channel_id
    assert plan.expected_translation_hz == plan.axis_orientation * (-plan.delta_f_hz)
    assert 2 * max(
        plan.target_fingerprint.bandwidth_hz,
        plan.witness_fingerprint.bandwidth_hz,
        dict(plan.thresholds)["spectral_resolution_hz"],
        plan.target_fingerprint.uncertainty_hz,
    ) <= abs(plan.delta_f_hz)
    assert "zero RF persistence" in plan.artifact_policy
    strict_json_value(plan)
    with pytest.raises(ValueError, match="ids must differ"):
        replace(plan, perturbed_channel_id="rx:1", server_instance_receipt=replace(_server(), perturbed_channel_id="rx:1"))
    with pytest.raises(ValueError, match="wrong frozen sign"):
        replace(plan, expected_translation_hz=plan.delta_f_hz)


def test_qualification_properties_are_atomic_and_downstream_remains_not_evaluated() -> None:
    receipt = f24._qualification_receipt(
        ENDPOINT,
        0,
        {
            "status_access": (f24.PropertyState.SATISFIED, "status hash exists"),
            "two_simultaneous_channel_slots": (f24.PropertyState.UNSATISFIED, "one slot"),
        },
        artifact_hashes=("f" * 64,),
        status_hash="f" * 64,
        reason="one slot",
    )
    assert receipt.property("status_access").state is f24.PropertyState.SATISFIED
    assert receipt.property("two_simultaneous_channel_slots").state is f24.PropertyState.UNSATISFIED
    assert receipt.property("distinct_channel_ids").state is f24.PropertyState.NOT_EVALUATED
    assert not receipt.multi_channel_demonstrated
    assert not receipt.topology_admissible


def test_retry_policy_never_retries_busy_rejected_or_physical_nonmatch() -> None:
    for reason in ("RuntimeError: endpoint is busy", "PermissionError: rejected", "no qualification witness"):
        receipt = f24._qualification_receipt(
            ENDPOINT,
            0,
            {"status_access": (f24.PropertyState.QUALIFICATION_ERROR, reason)},
            reason=reason,
        )
        assert not f24._retryable(receipt)
    timeout = f24._qualification_receipt(
        ENDPOINT,
        0,
        {"status_access": (f24.PropertyState.QUALIFICATION_ERROR, "TimeoutError: connection timed out")},
        reason="timeout",
    )
    assert f24._retryable(timeout)


def test_waterfall_selector_prioritises_stability_and_guard_before_strength() -> None:
    frames = np.zeros((3, 100), dtype=float)
    frames[:, 25] = 20.0
    frames[:, 24] = 5.0
    frames[:, 26] = 5.0
    frames[:, 70] = (0.0, 40.0, 50.0)
    frames[:, 69] = 5.0
    frames[:, 71] = 5.0
    artifact = f24._WaterfallArtifact(frames, 0.0, 100_000.0, "a" * 64, 300)
    selected = f24._salient_waterfall_frequency(artifact)
    assert 24_000.0 <= selected <= 26_000.0


def test_partial_dual_open_closes_the_successful_sibling(monkeypatch) -> None:
    class Socket:
        closed = False

        def close(self):
            self.closed = True

    socket = Socket()

    def open_one(endpoint, role, center, status, mother):
        if role == "perturbed":
            raise RuntimeError("second public slot is busy")
        return f24._ChannelConnection(
            endpoint,
            role,
            1,
            "rx:1",
            "fixture",
            socket,
            1000.0,
            status,
            {},
            "a" * 64,
            [],
        )

    monkeypatch.setattr(f24, "_open_channel", open_one)
    with pytest.raises(RuntimeError, match="busy"):
        f24._open_dual(ENDPOINT, 10_000_000.0, {"ext_api": "2"}, f2.MotherPlan())
    assert socket.closed


def _install_matches(monkeypatch, *, upstream: bool, downstream: bool, target_reference_b: bool = True, witness_reference_b: bool = True):
    monkeypatch.setattr(f2, "_capture_profile", lambda capture, _mother: (capture.status["role"], capture.status["phase"]))

    def match(profile, fingerprint, expected, _tolerance, _mother, *, witness=False):
        role, phase = profile
        is_witness = fingerprint.baseband_position_a_hz < 0
        matched = True
        if role == "perturbed" and phase == "B":
            if is_witness:
                matched = math.isclose(expected, -1950.0)
            elif math.isclose(expected, 250.0):
                matched = upstream
            elif math.isclose(expected, 1000.0):
                matched = downstream
            else:
                matched = False
        if role == "reference" and phase == "B":
            matched = witness_reference_b if is_witness else target_reference_b
        return f2.FeatureMatch(matched, expected if matched else None, expected, 8.0 if matched else None, 0.9 if matched else None, "fixture")

    import math
    monkeypatch.setattr(f2, "match_feature", match)


def test_upstream_and_downstream_outcomes_are_unique_and_never_claim_external_rf(monkeypatch) -> None:
    mother = f2.MotherPlan()
    _install_matches(monkeypatch, upstream=True, downstream=False)
    upstream = f24.evaluate_confirmation(_plan(), _confirmation(), (_qualified(),), mother)
    assert upstream.outcome is f23.F23Outcome.UPSTREAM_OF_CHANNEL_DDC_SUPPORTED
    assert upstream.authorised_claims == ("feature upstream of the per-channel DDC boundary",)
    assert "external RF proven" in upstream.unauthorised_claims
    assert tuple(item.transition for item in upstream.intervention_receipts) == ("A_TO_B", "B_TO_A")
    assert all(item.reference_command_count == 0 for item in upstream.intervention_receipts)
    assert all(item.acknowledgement_state == "NOT_AVAILABLE_IN_KIWI_PROTOCOL" for item in upstream.intervention_receipts)

    _install_matches(monkeypatch, upstream=False, downstream=True)
    downstream = f24.evaluate_confirmation(_plan(), _confirmation(), (_qualified(),), mother)
    assert downstream.outcome is f23.F23Outcome.DOWNSTREAM_CHANNEL_FIXED_SUPPORTED


def test_target_loss_on_stable_reference_is_not_detectable_not_invalid(monkeypatch) -> None:
    _install_matches(
        monkeypatch,
        upstream=False,
        downstream=False,
        target_reference_b=False,
        witness_reference_b=True,
    )
    result = f24.evaluate_confirmation(_plan(), _confirmation(), (_qualified(),), f2.MotherPlan())
    assert result.outcome is f23.F23Outcome.NOT_DETECTABLE
    statuses = {item.clause: item.status for item in result.clause_assessments}
    assert statuses["reference_unaffected"] is ClauseStatus.SATISFIED
    assert statuses["target_detectable_on_reference_B"] is ClauseStatus.UNSATISFIED


def test_reference_witness_change_invalidates_intervention_and_gates_downstream(monkeypatch) -> None:
    _install_matches(
        monkeypatch,
        upstream=True,
        downstream=False,
        witness_reference_b=False,
    )
    result = f24.evaluate_confirmation(_plan(), _confirmation(), (_qualified(),), f2.MotherPlan())
    assert result.outcome is f23.F23Outcome.INTERVENTION_INVALID
    statuses = {item.clause: item.status for item in result.clause_assessments}
    assert statuses["reference_unaffected"] is ClauseStatus.UNSATISFIED
    assert statuses["witness_translation_valid_B"] is ClauseStatus.NOT_EVALUATED
    assert statuses["upstream_prediction_match_B"] is ClauseStatus.NOT_EVALUATED


def test_overflow_makes_confirmation_not_detectable(monkeypatch) -> None:
    _install_matches(monkeypatch, upstream=True, downstream=False)
    result = f24.evaluate_confirmation(_plan(), _confirmation(overflow=True), (_qualified(),), f2.MotherPlan())
    assert result.outcome is f23.F23Outcome.NOT_DETECTABLE
    statuses = {item.clause: item.status for item in result.clause_assessments}
    assert statuses["no_invalidating_overflow"] is ClauseStatus.UNSATISFIED


def test_run_emits_bootstrap_before_any_mocked_qualification(monkeypatch) -> None:
    calls: list[str] = []

    def rejected(endpoint, _mother, *, attempt):
        calls.append(f"qualification:{endpoint.host}")
        return f24._qualification_receipt(
            endpoint,
            attempt,
            {
                "status_access": (f24.PropertyState.SATISFIED, "fixture"),
                "two_simultaneous_channel_slots": (f24.PropertyState.UNSATISFIED, "fixture one slot"),
            },
            reason="fixture one slot",
        )

    monkeypatch.setattr(f24, "_qualify_endpoint_once", rejected)
    lines: list[str] = []
    result = f24.run_once(runtime_commit="9" * 40, sink=lines.append)
    events = [json.loads(line)["event"] for line in lines]
    assert events[0] == "gate_f2_4_bootstrap_frozen"
    assert calls and events.index("gate_f2_4_bootstrap_frozen") < events.index("gate_f2_4_endpoint_qualification")
    assert calls == [f"qualification:{endpoint.host}" for endpoint in f24.ordered_candidates()]
    assert result.outcome is f23.F23Outcome.NO_MULTI_CHANNEL_CAPABILITY


def test_module_has_no_rf_persistence_database_directory_or_scanner() -> None:
    source = Path(f24.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = {
        node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Attribute, ast.Name))
    }
    assert not {"save", "savez", "tofile", "write_bytes", "write_text"} & calls
    assert "DIRECTORY_URL" not in source
    assert "event_not_before=plan.frozen_at" in source
    assert not {"TDoA", "Database", "Scanner", "Catalog", "InternetSource", "Planner"} & set(vars(f24))
