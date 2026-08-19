"""Offline tests for the Gate F2.5.1 pre-SND causal-path correction."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from experiments.live_instrument import kiwi_gate_f2 as f2
from experiments.live_instrument import kiwi_gate_f2_5 as f25
from experiments.live_instrument import kiwi_gate_f2_5_1 as f251
from experiments.live_instrument import kiwi_probe as kiwi
from experiments.live_instrument.models import strict_json_value


NOW = datetime(2026, 8, 16, 21, 0, tzinfo=timezone.utc)
ENDPOINT = kiwi.KiwiEndpoint("fixture", "fixture.invalid", 8073)


def test_bootstrap_invariant_is_narrow_and_not_a_target() -> None:
    invariant = f251.BootstrapTuningInvariant()
    assert invariant.selected_low_hz == 7_500_000.0
    assert invariant.selected_high_hz == 22_500_000.0
    assert invariant.role == "QUALIFICATION_BOOTSTRAP_ONLY"
    assert invariant.status_bandwidth_required is False
    assert invariant.waterfall_required is False
    assert len(invariant.evidence) == 3


@pytest.mark.parametrize(
    "status",
    (
        {},
        {"ext_api": "0"},
        {"bandwidth": ""},
        {"bandwidth": "not-a-number"},
        {"bandwidth": "100"},
        {"bandwidth": "90000000", "ext_api": "99"},
    ),
)
def test_bootstrap_center_never_reads_status_bandwidth_or_ext_api(status: dict[str, str]) -> None:
    center = f251.bootstrap_center(ENDPOINT, status)
    assert center == f251.bootstrap_center(ENDPOINT, {})
    assert 7_500_000.0 <= center <= 22_500_000.0


def test_endpoint_identity_selects_coordinate_without_selecting_a_feature() -> None:
    other = kiwi.KiwiEndpoint("other", "other.invalid", 8073)
    assert f251.bootstrap_center(ENDPOINT, {}) != f251.bootstrap_center(other, {})


def test_corrected_center_preserves_the_prior_30mhz_policy_geometry() -> None:
    expected = f25.center_from_status(ENDPOINT, {"bandwidth": "30000000"})
    assert f251.bootstrap_center(ENDPOINT, {}) == expected


def test_parent_runtime_remains_reproducible_with_its_original_failure() -> None:
    with pytest.raises(ValueError, match="advertised bandwidth"):
        f25.center_from_status(ENDPOINT, {})


@pytest.mark.parametrize("ext_api", (None, "0", "1", "99", "broken"))
def test_missing_bandwidth_and_ext_api_cannot_block_direct_dual_attempt(
    monkeypatch: pytest.MonkeyPatch,
    ext_api: str | None,
) -> None:
    status = {} if ext_api is None else {"ext_api": ext_api}
    monkeypatch.setattr(f251.f25.kiwi, "fetch_kiwi_status", lambda *_args, **_kwargs: status)
    calls: list[float] = []

    def refuse(_endpoint: object, center: float, _status: object, _mother: object) -> object:
        calls.append(center)
        raise RuntimeError("fixture is busy")

    monkeypatch.setattr(f251.f25.f24, "_open_dual", refuse)
    receipt = f251.direct_dual_snd_qualification(ENDPOINT, f2.MotherPlan())
    assert isinstance(receipt, f25.PhaseReceipt)
    assert calls == [f251.bootstrap_center(ENDPOINT, {})]
    assert receipt.direct_reference_attempted and receipt.direct_perturbed_attempted
    assert receipt.state is f25.F25PhaseState.UNSATISFIED
    assert ("status_bandwidth_used_as_gate", "FALSE") in receipt.properties
    assert ("bootstrap_role", "QUALIFICATION_BOOTSTRAP_ONLY") in receipt.properties


def test_transport_failure_after_attempt_remains_qualification_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(f251.f25.kiwi, "fetch_kiwi_status", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        f251.f25.f24,
        "_open_dual",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("socket timed out")),
    )
    receipt = f251.direct_dual_snd_qualification(ENDPOINT, f2.MotherPlan())
    assert isinstance(receipt, f25.PhaseReceipt)
    assert receipt.direct_reference_attempted and receipt.direct_perturbed_attempted
    assert receipt.state is f25.F25PhaseState.QUALIFICATION_ERROR
    assert f25.no_topology_outcome((receipt,)) is f25.F25Outcome.QUALIFICATION_INCOMPLETE


def test_explicit_busy_after_both_attempts_can_support_no_multi_for_that_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(f251.f25.kiwi, "fetch_kiwi_status", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        f251.f25.f24,
        "_open_dual",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("fixture is busy")),
    )
    receipt = f251.direct_dual_snd_qualification(ENDPOINT, f2.MotherPlan())
    assert isinstance(receipt, f25.PhaseReceipt)
    assert f25.no_topology_outcome((receipt,)) is f25.F25Outcome.NO_MULTI_CHANNEL_CAPABILITY


def test_bootstrap_receipt_binds_parent_failure_and_strict_json() -> None:
    receipt = f251.build_bootstrap_receipt(runtime_commit="a" * 40, created_at=NOW)
    value = strict_json_value(receipt)
    json.dumps(value, allow_nan=False)
    assert receipt.parent_runtime_commit == f251.PARENT_RUNTIME_COMMIT
    assert receipt.parent_outcome_commit == f251.PARENT_OUTCOME_COMMIT
    assert receipt.center_policy == f251.CENTER_POLICY
    assert receipt.transform_versions[-1] == f251.F251_TRANSFORM_VERSION


def test_runner_delegates_only_the_corrected_bootstrap_and_direct_qualifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    sentinel = object()

    def delegated(**kwargs: object) -> object:
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(f251.f25, "run_once", delegated)
    result = f251.run_once(runtime_commit="b" * 40, sink=lambda _line: None)
    assert result is sentinel
    assert captured["event_prefix"] == "gate_f2_5_1"
    assert captured["terminal_instrument"] == "gate-f2.5.1-direct-dual-snd"
    assert captured["direct_qualifier"] is f251.direct_dual_snd_qualification
    bootstrap = captured["bootstrap_receipt"]
    assert isinstance(bootstrap, f251.F251BootstrapReceipt)


def test_corrected_runner_accepts_new_receipt_and_emits_strict_gate_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def software_failure(
        endpoint: kiwi.KiwiEndpoint,
        _mother: f2.MotherPlan,
    ) -> f25.PhaseReceipt:
        return f25.PhaseReceipt(
            f"{endpoint.host}:{endpoint.port}",
            f25.F25Phase.DIRECT_DUAL_SND_QUALIFICATION,
            f25.F25PhaseState.QUALIFICATION_ERROR,
            NOW,
            NOW,
            "offline fixture: direct pair transport was indeterminate",
            ("c" * 64,),
            (("fixture", "TRUE"),),
            None,
            True,
            True,
        )

    monkeypatch.setattr(f251, "direct_dual_snd_qualification", software_failure)
    lines: list[str] = []
    result = f251.run_once(runtime_commit="d" * 40, sink=lines.append)
    documents = tuple(json.loads(line) for line in lines)

    assert result.outcome is f25.F25Outcome.QUALIFICATION_INCOMPLETE
    assert documents[0]["event"] == "gate_f2_5_1_bootstrap_frozen"
    assert documents[-1]["event"] == "gate_f2_5_1_first_outcome"
    assert all("NaN" not in line and "Infinity" not in line for line in lines)
    assert result.evidence_receipt.branch == "gate-f2.5.1-direct-dual-snd"


def test_f251_source_has_no_waterfall_call_or_status_bandwidth_lookup() -> None:
    source = Path(f251.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "_capture_waterfall" not in calls
    assert "_automatic_center" not in calls
    assert '["bandwidth"]' not in source
    assert "['bandwidth']" not in source
