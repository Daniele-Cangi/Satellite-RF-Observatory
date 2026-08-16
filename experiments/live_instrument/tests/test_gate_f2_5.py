"""Offline causal-boundary tests for Gate F2.5."""

from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from experiments.live_instrument import kiwi_gate_f2 as f2
from experiments.live_instrument import kiwi_gate_f2_4 as f24
from experiments.live_instrument import kiwi_gate_f2_5 as f25
from experiments.live_instrument import kiwi_probe as kiwi
from experiments.live_instrument.models import strict_json_value


NOW = datetime(2026, 8, 16, 20, 0, tzinfo=timezone.utc)
ENDPOINT = kiwi.KiwiEndpoint("fixture", "fixture.invalid", 8073)
STATUS = {"bandwidth": "30000000", "ext_api": "0", "version_maj": "1", "version_min": "800"}


class _Socket:
    def close(self) -> None:
        return None


def _connection(role: str, channel_id: str) -> f24._ChannelConnection:
    return f24._ChannelConnection(
        ENDPOINT,
        role,
        1 if role == "reference" else 2,
        channel_id,
        "fixture allocation",
        _Socket(),
        1000.0,
        STATUS,
        {"rx_chan": channel_id},
        ("1" if role == "reference" else "2") * 64,
        [],
    )


def _dual() -> f24._DualConnections:
    return f24._DualConnections(_connection("reference", "rx:1"), _connection("perturbed", "rx:2"))


def _artifact(role: str, phase: str, sequence: int, center: float = 10_000_000.0) -> f24._MemoryArtifact:
    start = NOW + timedelta(seconds=sequence)
    samples = np.zeros(1200, dtype=np.complex64)
    block = kiwi.IQBlock(
        start,
        start + timedelta(seconds=1.2),
        samples,
        -80.0,
        0,
        True,
        False,
        sequence,
        start + timedelta(seconds=1.21),
    )
    capture = kiwi.KiwiCapture(
        ENDPOINT,
        center,
        1000.0,
        STATUS,
        (block,),
        block.arrived_at,
        block.arrived_at,
    )
    digest = ("a" if role == "reference" else "b") + f"{sequence:x}"
    return f24._MemoryArtifact(
        capture,
        digest.ljust(64, "0"),
        int(samples.nbytes),
        "rx:1" if role == "reference" else "rx:2",
        role,
        phase,
        center,
    )


def _baseline() -> f24._DualArtifacts:
    reference = _artifact("reference", "DISCOVERY_A", 1)
    perturbed = _artifact("perturbed", "DISCOVERY_A", 1)
    return f24._DualArtifacts(
        {"DISCOVERY_A": reference},
        {"DISCOVERY_A": perturbed},
        reference.capture.blocks,
        perturbed.capture.blocks,
    )


def _diagnostic() -> f24._DualArtifacts:
    reference = {name: _artifact("reference", name, index) for index, name in enumerate(("A1", "B", "A2"), 1)}
    perturbed = {
        name: _artifact(
            "perturbed",
            name,
            index + 10,
            10_000_750.0 if name == "B" else 10_000_000.0,
        )
        for index, name in enumerate(("A1", "B", "A2"), 1)
    }
    return f24._DualArtifacts(
        reference,
        perturbed,
        tuple(block for artifact in reference.values() for block in artifact.capture.blocks),
        tuple(block for artifact in perturbed.values() for block in artifact.capture.blocks),
        (),
        (("SET B", NOW), ("SET A2", NOW + timedelta(seconds=1))),
    )


def _geometry(*, target_position: float = 1000.0) -> f24._PlanGeometry:
    target = f2._FeatureGeometry(
        target_position,
        20.0,
        (-0.2, -0.1, 0.2, 0.8, 0.2, -0.1, -0.2),
        (7.0, 7.2, 0.2),
        (7.0, 9.0),
        20.0,
        0.9,
    )
    witness = f2._FeatureGeometry(
        -1200.0,
        20.0,
        (-0.1, 0.0, 0.3, 0.9, 0.3, 0.0, -0.1),
        (8.0, 8.1, 0.1),
        (8.0, 10.0),
        20.0,
        0.92,
    )
    return f24._PlanGeometry(target, witness, 750.0, 20.0, 10.0, 1750.0, 625.0, -875.0, (1.0,))


def _phase(
    state: f25.F25PhaseState,
    *,
    attempted: bool,
    opened: bool = False,
    endpoint: str = "fixture.invalid:8073",
) -> f25.PhaseReceipt:
    return f25.PhaseReceipt(
        endpoint,
        f25.F25Phase.DIRECT_DUAL_SND_QUALIFICATION,
        state,
        NOW,
        NOW,
        "fixture",
        (),
        (),
        None,
        attempted,
        attempted,
        opened,
        opened,
    )


def test_bootstrap_freezes_direct_snd_path_and_is_strict_json() -> None:
    receipt = f25.build_bootstrap_receipt(runtime_commit="e" * 40, created_at=NOW)
    value = strict_json_value(receipt)
    json.dumps(value, allow_nan=False)
    assert receipt.candidate_order == f24.ordered_candidate_identities()
    assert receipt.phase_order == f25.PHASE_ORDER
    assert receipt.ext_api_semantics == "DESCRIPTIVE_HINT_ONLY"
    assert receipt.waterfall_semantics == "OPTIONAL_AND_OUTSIDE_CAUSAL_PATH"


@pytest.mark.parametrize("raw, expected", [(None, None), ("-1", -1), ("0", 0), ("2", 2), ("broken", None)])
def test_ext_api_is_always_a_non_gating_hint(raw: str | None, expected: int | None) -> None:
    status = {} if raw is None else {"ext_api": raw}
    hint = f25.ext_api_hint(status)
    assert hint.parsed_value == expected
    assert hint.used_as_gate is False


def test_center_policy_is_data_independent_and_inside_advertised_band() -> None:
    left = f25.center_from_status(ENDPOINT, STATUS)
    right = f25.center_from_status(ENDPOINT, {**STATUS, "ext_api": "99"})
    assert left == right
    assert 25_000.0 <= left <= 30_000_000.0 - 25_000.0


def test_ext_api_zero_does_not_prevent_actual_second_channel_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(f25.kiwi, "fetch_kiwi_status", lambda *_args, **_kwargs: STATUS)
    calls = []

    def refuse(*_args: object, **_kwargs: object) -> object:
        calls.append("dual")
        raise RuntimeError("fixture is busy")

    monkeypatch.setattr(f25.f24, "_open_dual", refuse)
    receipt = f25.direct_dual_snd_qualification(ENDPOINT, f2.MotherPlan())
    assert isinstance(receipt, f25.PhaseReceipt)
    assert calls == ["dual"]
    assert receipt.ext_api_hint is not None and receipt.ext_api_hint.parsed_value == 0
    assert receipt.direct_reference_attempted and receipt.direct_perturbed_attempted
    assert receipt.state is f25.F25PhaseState.UNSATISFIED


def test_transport_error_after_real_attempt_is_not_physical_rejection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(f25.kiwi, "fetch_kiwi_status", lambda *_args, **_kwargs: STATUS)
    monkeypatch.setattr(f25.f24, "_open_dual", lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("socket timed out")))
    receipt = f25.direct_dual_snd_qualification(ENDPOINT, f2.MotherPlan())
    assert isinstance(receipt, f25.PhaseReceipt)
    assert receipt.state is f25.F25PhaseState.QUALIFICATION_ERROR
    assert f25.no_topology_outcome((receipt,)) is f25.F25Outcome.QUALIFICATION_INCOMPLETE


def test_two_open_allocations_with_same_identity_are_topology_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(f25.kiwi, "fetch_kiwi_status", lambda *_args, **_kwargs: STATUS)
    monkeypatch.setattr(
        f25.f24,
        "_open_dual",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("server did not expose distinct channel allocations")),
    )
    receipt = f25.direct_dual_snd_qualification(ENDPOINT, f2.MotherPlan())
    assert isinstance(receipt, f25.PhaseReceipt)
    assert receipt.direct_reference_opened and receipt.direct_perturbed_opened
    assert f25.no_topology_outcome((receipt,)) is f25.F25Outcome.NO_ADMISSIBLE_CAUSAL_TOPOLOGY


def test_no_multi_channel_requires_actual_attempt_and_uses_latest_retry() -> None:
    not_attempted = _phase(f25.F25PhaseState.QUALIFICATION_ERROR, attempted=False)
    attempted = _phase(f25.F25PhaseState.UNSATISFIED, attempted=True)
    assert f25.no_topology_outcome((not_attempted,)) is f25.F25Outcome.QUALIFICATION_INCOMPLETE
    assert f25.no_topology_outcome((attempted,)) is f25.F25Outcome.NO_MULTI_CHANNEL_CAPABILITY
    assert f25.no_topology_outcome((not_attempted, attempted)) is f25.F25Outcome.NO_MULTI_CHANNEL_CAPABILITY


def test_open_pair_with_invalid_timing_is_topology_failure_not_no_multi() -> None:
    opened = _phase(f25.F25PhaseState.UNSATISFIED, attempted=True, opened=True)
    assert f25.no_topology_outcome((opened,)) is f25.F25Outcome.NO_ADMISSIBLE_CAUSAL_TOPOLOGY


def test_module_contains_no_server_waterfall_call() -> None:
    source = Path(f25.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "_capture_waterfall" not in calls
    assert "_automatic_center" not in calls


def test_local_discovery_consumes_dual_iq_and_never_waterfall(monkeypatch: pytest.MonkeyPatch) -> None:
    dual = _dual()
    topology = _baseline()
    direct = _phase(f25.F25PhaseState.SATISFIED, attempted=True, opened=True)
    context = f25._TopologyContext(ENDPOINT, STATUS, 10_000_000.0, dual, topology, direct)
    captured = _baseline()
    monkeypatch.setattr(f25.f24, "_capture_dual", lambda *_args, **_kwargs: captured)
    selection = f25._DiscoverySelection(_geometry(), ("c" * 64, "d" * 64))
    monkeypatch.setattr(f25, "_orientation_neutral_selection", lambda *_args, **_kwargs: selection)
    result = f25.discover_features_locally(context, f2.MotherPlan())
    assert isinstance(result, f25._DiscoveryContext)
    assert ("input_surface", "SND_IQ_ONLY") in result.phase_receipt.properties
    assert ("waterfall_requested", "FALSE") in result.phase_receipt.properties


def test_discovery_cannot_choose_a_feature_that_depends_on_unrevealed_axis(monkeypatch: pytest.MonkeyPatch) -> None:
    artifacts = _baseline()

    def select(_artifacts: object, _mother: object, orientation: int) -> f24._PlanGeometry:
        return _geometry(target_position=1000.0 + orientation)

    monkeypatch.setattr(f25.f24, "_select_plan_geometry", select)
    with pytest.raises(ValueError, match="orientation"):
        f25._orientation_neutral_selection(artifacts, f2.MotherPlan())


def test_retune_qualification_uses_witness_only_and_clears_prefreeze_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    dual = _dual()
    dual.perturbed.command_ledger.extend((("SET B", NOW), ("SET A2", NOW)))
    direct = _phase(f25.F25PhaseState.SATISFIED, attempted=True, opened=True)
    context = f25._TopologyContext(ENDPOINT, STATUS, 10_000_000.0, dual, _baseline(), direct)
    discovery = f25._DiscoveryContext(
        _baseline(),
        f25._DiscoverySelection(_geometry(), ("c" * 64, "d" * 64)),
        f25.PhaseReceipt(
            "fixture.invalid:8073",
            f25.F25Phase.LOCAL_IQ_FEATURE_DISCOVERY,
            f25.F25PhaseState.SATISFIED,
            NOW,
            NOW,
            "fixture",
            ("c" * 64, "d" * 64),
            (),
        ),
    )
    diagnostic = _diagnostic()
    monkeypatch.setattr(f25.f24, "_capture_dual", lambda *_args, **_kwargs: diagnostic)
    monkeypatch.setattr(f25.f24, "_integrity", lambda *_args, **_kwargs: (True, True, True))
    match = f2.FeatureMatch(True, -1950.0, -1950.0, 8.0, 0.9, "fixture")
    monkeypatch.setattr(f25, "_selected_witness_qualification", lambda *_args, **_kwargs: (1, match, None))
    result = f25.qualify_retune(context, discovery, f2.MotherPlan())
    assert isinstance(result, f25._RetuneQualification)
    assert ("target_evaluated", "FALSE") in result.phase_receipt.properties
    assert dual.reference.command_ledger == []
    assert dual.perturbed.command_ledger == []


def test_plan_freeze_binds_exact_local_iq_hashes_without_reselection(monkeypatch: pytest.MonkeyPatch) -> None:
    dual = _dual()
    direct = _phase(f25.F25PhaseState.SATISFIED, attempted=True, opened=True)
    context = f25._TopologyContext(ENDPOINT, STATUS, 10_000_000.0, dual, _baseline(), direct)
    hashes = ("c" * 64, "d" * 64)
    discovery = f25._DiscoveryContext(
        _baseline(),
        f25._DiscoverySelection(_geometry(), hashes),
        f25.PhaseReceipt(
            "fixture.invalid:8073",
            f25.F25Phase.LOCAL_IQ_FEATURE_DISCOVERY,
            f25.F25PhaseState.SATISFIED,
            NOW,
            NOW,
            "fixture",
            hashes,
            (),
        ),
    )
    match = f2.FeatureMatch(True, -1950.0, -1950.0, 8.0, 0.9, "fixture")
    retune = f25._RetuneQualification(1, match, discovery.phase_receipt, None)  # type: ignore[arg-type]
    monkeypatch.setattr(f25.f24, "_select_plan_geometry", lambda *_args, **_kwargs: pytest.fail("reselection"))
    plan = f25.freeze_preselected_plan(context, discovery, retune, f2.MotherPlan(), frozen_at=NOW)
    assert plan.discovery_artifact_hashes == hashes
    assert plan.reference_channel_id == "rx:1"
    assert plan.perturbed_channel_id == "rx:2"
    assert plan.expected_translation_hz == -750.0


def test_one_shot_runner_preserves_the_three_phase_order_before_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    dual = _dual()
    direct = _phase(f25.F25PhaseState.SATISFIED, attempted=True, opened=True)
    context = f25._TopologyContext(ENDPOINT, STATUS, 10_000_000.0, dual, _baseline(), direct)
    hashes = ("c" * 64, "d" * 64)
    discovery_receipt = f25.PhaseReceipt(
        "fixture.invalid:8073",
        f25.F25Phase.LOCAL_IQ_FEATURE_DISCOVERY,
        f25.F25PhaseState.SATISFIED,
        NOW,
        NOW,
        "fixture",
        hashes,
        (),
    )
    discovery = f25._DiscoveryContext(
        _baseline(),
        f25._DiscoverySelection(_geometry(), hashes),
        discovery_receipt,
    )
    match = f2.FeatureMatch(True, -1950.0, -1950.0, 8.0, 0.9, "fixture")
    retune_receipt = f25.PhaseReceipt(
        "fixture.invalid:8073",
        f25.F25Phase.PER_CHANNEL_RETUNE_QUALIFICATION,
        f25.F25PhaseState.SATISFIED,
        NOW,
        NOW,
        "fixture",
        ("e" * 64,),
        (("target_evaluated", "FALSE"),),
    )
    retune = f25._RetuneQualification(1, match, retune_receipt, None)  # type: ignore[arg-type]

    monkeypatch.setattr(
        f25,
        "direct_dual_snd_qualification",
        lambda *_args, **_kwargs: calls.append("dual-SND") or context,
    )
    monkeypatch.setattr(
        f25,
        "discover_features_locally",
        lambda *_args, **_kwargs: calls.append("local-STFT") or discovery,
    )
    monkeypatch.setattr(
        f25,
        "qualify_retune",
        lambda *_args, **_kwargs: calls.append("retune") or retune,
    )
    original_freeze = f25.freeze_preselected_plan
    monkeypatch.setattr(
        f25,
        "freeze_preselected_plan",
        lambda *args, **kwargs: calls.append("freeze") or original_freeze(*args, **kwargs),
    )
    monkeypatch.setattr(
        f25.f24,
        "_capture_dual",
        lambda *_args, **_kwargs: calls.append("confirmation") or _baseline(),
    )
    monkeypatch.setattr(
        f25.f24,
        "evaluate_confirmation",
        lambda *_args, **_kwargs: calls.append("evaluate") or SimpleNamespace(outcome=SimpleNamespace(value="AMBIGUOUS")),
    )
    monkeypatch.setattr(
        f25,
        "_f25_from_physical",
        lambda _physical, receipts: f25._terminal_result(f25.F25Outcome.AMBIGUOUS, receipts, "fixture"),
    )
    result = f25.run_once(runtime_commit="f" * 40, sink=lambda _line: None)
    assert result.outcome is f25.F25Outcome.AMBIGUOUS
    assert calls == ["dual-SND", "local-STFT", "retune", "freeze", "confirmation", "evaluate"]


def test_blocked_downstream_phases_are_explicitly_not_evaluated() -> None:
    blocked = f25.downstream_not_evaluated(
        "fixture.invalid:8073",
        (f25.F25Phase.DIRECT_DUAL_SND_QUALIFICATION,),
    )
    assert tuple(item.phase for item in blocked) == (
        f25.F25Phase.LOCAL_IQ_FEATURE_DISCOVERY,
        f25.F25Phase.PER_CHANNEL_RETUNE_QUALIFICATION,
        f25.F25Phase.PLAN_FREEZE,
        f25.F25Phase.ONE_CONFIRMATION,
    )
    assert all(item.state is f25.F25PhaseState.NOT_EVALUATED for item in blocked)


def test_ephemeral_rf_cannot_cross_the_receipt_boundary() -> None:
    with pytest.raises(Exception):
        strict_json_value({"raw_iq": np.zeros(8, dtype=np.complex64)})
