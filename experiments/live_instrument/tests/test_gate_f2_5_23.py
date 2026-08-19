"""Offline integration tests for the Gate F2.5.23 one-target successor."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import inspect
import json
import struct
from threading import Lock

import numpy as np
import websocket

from experiments.live_instrument import kiwi_gate_f2 as f2
from experiments.live_instrument import kiwi_gate_f2_4 as f24
from experiments.live_instrument import kiwi_gate_f2_5 as f25
from experiments.live_instrument import kiwi_gate_f2_5_20 as f2520
from experiments.live_instrument import kiwi_gate_f2_5_23 as f2523
from experiments.live_instrument import kiwi_probe as kiwi
from experiments.live_instrument.models import strict_json_value


NOW = datetime(2026, 8, 18, 15, 0, tzinfo=timezone.utc)


class _Frame:
    def __init__(self, data: bytes):
        self.data = data


class _Socket:
    def __init__(self, role: str) -> None:
        channel = 7 if role == "reference" else 8
        sequence = 17 if role == "reference" else 29
        self.frames = [_msg(channel), _snd(sequence)]
        self.sent: list[str] = []
        self.closed = False

    def connect(self, *args: object, **kwargs: object) -> "_Socket":
        del args, kwargs
        return self

    def send(self, command: str) -> None:
        self.sent.append(command)

    def recv_data_frame(self, control_frame: bool = False) -> tuple[int, _Frame]:
        assert control_frame
        if not self.frames:
            raise ConnectionError("synthetic stream exhausted")
        return websocket.ABNF.OPCODE_BINARY, _Frame(self.frames.pop(0))

    def close(self) -> None:
        self.closed = True


class _Provider:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.sockets: list[_Socket] = []
        self._lock = Lock()

    def __call__(self, endpoint: object, role: str):  # type: ignore[no-untyped-def]
        del endpoint
        socket = _Socket(role)
        with self._lock:
            self.calls.append(role)
            self.sockets.append(socket)
        return socket.connect


def _msg(channel: int) -> bytes:
    return (
        f"MSG is_local={channel},0,0 badp=0 audio_rate=12000 sample_rate=12000"
    ).encode("ascii")


def _snd(sequence: int) -> bytes:
    return b"SND" + (
        struct.pack("<BI", 0x08, sequence)
        + struct.pack(">H", 1_000)
        + struct.pack("<BBII", 0, 0, 100_000, 250_000_000)
        + struct.pack(">hhhh", 100, -100, 200, -200)
    )


def _profile(residual: np.ndarray) -> f2._SpectralProfile:
    frequencies = np.arange(-4_000.0, 4_000.1, 10.0)
    return f2._SpectralProfile(
        frequencies,
        residual.copy(),
        residual.copy(),
        residual.copy(),
        residual.copy(),
        10.0,
    )


def _shift(values: np.ndarray, lag: int) -> np.ndarray:
    result = np.zeros_like(values)
    if lag > 0:
        result[lag:] = values[:-lag]
    elif lag < 0:
        result[:lag] = values[-lag:]
    else:
        result[:] = values
    return result


def _artifact(
    role: str,
    phase: str,
    sequence: int,
    profile_key: str,
) -> f24._MemoryArtifact:
    samples = np.zeros(1_024, dtype=np.complex64)
    # Distinct stream sequence roots share one synthetic event-time interval.
    start = NOW + timedelta(seconds=sequence % 100)
    end = start + timedelta(seconds=1.0)
    block = kiwi.IQBlock(
        start,
        end,
        samples,
        -70.0,
        0,
        True,
        False,
        sequence,
        end + timedelta(milliseconds=100),
    )
    capture = kiwi.KiwiCapture(
        f2520.selected_endpoint(),
        f2520.SELECTED_BOOTSTRAP_CENTER_HZ,
        12_000.0,
        {"profile_key": profile_key},
        (block,),
        block.arrived_at,  # type: ignore[arg-type]
        block.arrived_at,  # type: ignore[arg-type]
    )
    artifact_hash = f2._hash(
        {"role": role, "phase": phase, "sequence": sequence, "profile": profile_key}
    )
    return f24._MemoryArtifact(
        capture,
        artifact_hash,
        int(samples.nbytes),
        "rx:7" if role == "reference" else "rx:8",
        role,
        phase,
        f2520.SELECTED_BOOTSTRAP_CENTER_HZ,
    )


def _artifacts(
    phases: tuple[str, ...],
    prefix: str,
) -> f24._DualArtifacts:
    reference = {
        phase: _artifact("reference", phase, 100 + index, f"{prefix}:reference:{phase}")
        for index, phase in enumerate(phases)
    }
    perturbed = {
        phase: _artifact("perturbed", phase, 200 + index, f"{prefix}:perturbed:{phase}")
        for index, phase in enumerate(phases)
    }
    return f24._DualArtifacts(
        reference,
        perturbed,
        tuple(item.capture.blocks[0] for item in reference.values()),
        tuple(item.capture.blocks[0] for item in perturbed.values()),
    )


def _topology_artifacts() -> f24._DualArtifacts:
    raw = _artifacts(("DISCOVERY_A",), "topology")
    return raw


class _SyntheticExperiment:
    def __init__(self, *, target: bool = True, translated_witness: bool = True) -> None:
        self.profiles: dict[str, f2._SpectralProfile] = {}
        self.target = target
        self.translated_witness = translated_witness
        self.diagnostic_called = False
        self.discovery = _artifacts(("DISCOVERY_A",), "discovery")
        rng = np.random.default_rng(2523)
        self.background = rng.normal(0.0, 0.6, 801)
        frequencies = np.arange(-4_000.0, 4_000.1, 10.0)
        target_shape = 9.0 * np.exp(-0.5 * ((frequencies + 1_000.0) / 20.0) ** 2)
        discovery_profile = self.background + (target_shape if target else 0.0)
        for role in ("reference", "perturbed"):
            self.profiles[f"discovery:{role}:DISCOVERY_A"] = _profile(discovery_profile)

    def profile_provider(
        self,
        capture: object,
        mother: f2.MotherPlan,
    ) -> f2._SpectralProfile:
        del mother
        return self.profiles[capture.status["profile_key"]]  # type: ignore[attr-defined]

    def capture_discovery(self, context: f25._TopologyContext) -> f24._DualArtifacts:
        assert context.phase_receipt.state is f25.F25PhaseState.SATISFIED
        return self.discovery

    def capture_diagnostic(
        self,
        context: f25._TopologyContext,
        delta_hz: float,
    ) -> f24._DualArtifacts:
        assert context.phase_receipt.state is f25.F25PhaseState.SATISFIED
        self.diagnostic_called = True
        artifacts = _artifacts(("A1", "B", "A2"), "diagnostic")
        delta_bins = int(round(delta_hz / 10.0))
        frequencies = np.arange(-4_000.0, 4_000.1, 10.0)
        target_shape = 9.0 * np.exp(-0.5 * ((frequencies + 1_000.0) / 20.0) ** 2)
        a_state = self.background + target_shape
        b_background = (
            _shift(self.background, delta_bins)
            if self.translated_witness
            else self.background.copy()
        )
        # The target is deliberately channel-fixed in diagnostic B. It is not
        # allowed to participate in retune qualification.
        b_perturbed = b_background + target_shape
        for phase in ("A1", "B", "A2"):
            self.profiles[f"diagnostic:reference:{phase}"] = _profile(a_state)
        self.profiles["diagnostic:perturbed:A1"] = _profile(a_state)
        self.profiles["diagnostic:perturbed:B"] = _profile(b_perturbed)
        self.profiles["diagnostic:perturbed:A2"] = _profile(a_state)
        return artifacts


def _qualification(provider: _Provider | None = None) -> f2520.F2520Qualification:
    return f2520.qualify_selected_capability_injected(
        connector_provider=provider or _Provider(),
        websocket_module=websocket,
        capture_dual=lambda *_args, **_kwargs: _topology_artifacts(),
    )


def test_envelope_is_offline_one_target_and_keeps_the_frozen_thresholds() -> None:
    envelope = f2523.build_envelope()
    assessment = f2523.assess_gate_f2_5_23()

    assert envelope.parent_outcome_sha256 == f2523.PARENT_OUTCOME_SHA256
    assert envelope.phase_order == f2523.PHASE_ORDER
    assert envelope.prefreeze_retry_budget == 0
    assert envelope.postfreeze_retry_budget == 0
    assert not envelope.live_execution_authorised
    assert envelope.capture_functions_required_injected
    assert envelope.raw_rf_persistence == "ZERO"
    assert assessment.one_target_allowed
    assert assessment.orthogonal_witness_still_required
    assert assessment.target_bins_excluded_from_all_witness_controls
    assert assessment.thresholds_unchanged
    assert assessment.confirmation_integration_required
    assert not assessment.live_execution_authorised


def test_synthetic_sockets_then_one_target_witness_and_plan_freeze() -> None:
    provider = _Provider()
    qualification = _qualification(provider)
    experiment = _SyntheticExperiment()

    result = f2523.materialize_prefreeze_injected(
        qualification,
        capture_discovery=experiment.capture_discovery,
        capture_diagnostic=experiment.capture_diagnostic,
        profile_provider=experiment.profile_provider,
        frozen_at=NOW,
    )

    # Both connectors are intentionally opened concurrently. Their scheduling
    # order is not part of the causal contract and differs across platforms.
    assert len(provider.calls) == 2
    assert set(provider.calls) == {"reference", "perturbed"}
    assert all(socket.closed for socket in provider.sockets)
    assert experiment.diagnostic_called
    assert result.outcome == "PREFREEZE_PLAN_MATERIALIZED_OFFLINE"
    assert result.plan is not None
    assert len(result.plan.plan_hash) == 64
    assert result.plan.target_excluded_from_witness
    assert result.plan.confirmation_windows == 1
    assert result.plan.postfreeze_retry_budget == 0
    assert result.plan.allowed_outcomes == f2523.ALLOWED_FUTURE_OUTCOMES
    assert [item.state for item in result.phase_receipts] == [
        "SATISFIED",
        "SATISFIED",
        "SATISFIED",
        "SATISFIED",
        "NOT_EVALUATED",
    ]
    discovery = result.phase_receipts[1]
    witness = result.phase_receipts[2]
    assert discovery.discovery_audit is not None
    assert discovery.discovery_audit.admitted_feature_count == 1
    assert dict(discovery.properties)["second_narrowband_peak_required"] == "FALSE"
    assert witness.distributed_witness is not None
    assert witness.distributed_witness.state == "QUALIFIED_AS_FUTURE_WITNESS"
    assert dict(witness.properties)["target_evaluated"] == "FALSE"


def test_frozen_predictions_are_distinct_and_confirmation_remains_future() -> None:
    experiment = _SyntheticExperiment()
    result = f2523.materialize_prefreeze_injected(
        _qualification(),
        capture_discovery=experiment.capture_discovery,
        capture_diagnostic=experiment.capture_diagnostic,
        profile_provider=experiment.profile_provider,
        frozen_at=NOW,
    )
    assert result.plan is not None
    intervals = {
        name: (low, high) for name, low, high in result.plan.prediction_intervals
    }

    assert intervals["TARGET_UPSTREAM_B"] != intervals["TARGET_CHANNEL_FIXED_B"]
    assert set(name for name, _ in result.plan.controls) == {
        "WRONG_SIGN_B",
        "HALF_MAGNITUDE_B",
        "OFF_FEATURE_B",
    }
    assert result.plan.confirmation_event_not_before == NOW
    assert result.phase_receipts[-1].phase == "ONE_CONFIRMATION"
    assert result.phase_receipts[-1].state == "NOT_EVALUATED"
    assert "future confirmation authorised" in result.unauthorised_claims


def test_no_target_stops_before_diagnostic_and_marks_downstream_not_evaluated() -> None:
    experiment = _SyntheticExperiment(target=False)
    result = f2523.materialize_prefreeze_injected(
        _qualification(),
        capture_discovery=experiment.capture_discovery,
        capture_diagnostic=experiment.capture_diagnostic,
        profile_provider=experiment.profile_provider,
        frozen_at=NOW,
    )

    assert result.outcome == "NO_FALSIFIABLE_INTERVENTION"
    assert result.plan is None
    assert not experiment.diagnostic_called
    assert [item.state for item in result.phase_receipts] == [
        "SATISFIED",
        "UNSATISFIED",
        "NOT_EVALUATED",
        "NOT_EVALUATED",
        "NOT_EVALUATED",
    ]
    assert "no signal existed" in result.unauthorised_claims


def test_channel_fixed_fingerprint_does_not_qualify_the_intervention() -> None:
    experiment = _SyntheticExperiment(translated_witness=False)
    result = f2523.materialize_prefreeze_injected(
        _qualification(),
        capture_discovery=experiment.capture_discovery,
        capture_diagnostic=experiment.capture_diagnostic,
        profile_provider=experiment.profile_provider,
        frozen_at=NOW,
    )

    assert result.outcome == "INTERVENTION_NOT_QUALIFIED"
    assert result.plan is None
    assert result.phase_receipts[2].state == "UNSATISFIED"
    assert result.phase_receipts[2].distributed_witness is not None
    assert result.phase_receipts[2].distributed_witness.state == (
        "INTERVENTION_UNRESOLVED"
    )
    assert result.phase_receipts[3].state == "NOT_EVALUATED"
    assert result.phase_receipts[4].state == "NOT_EVALUATED"


def test_diagnostic_target_mutation_cannot_change_witness_qualification() -> None:
    experiment = _SyntheticExperiment()
    qualification = _qualification()
    assert isinstance(qualification.result, f25._TopologyContext)
    discovery = f2523.discover_one_target(
        experiment.capture_discovery(qualification.result),
        qualification.result.center_hz,
        f2.MotherPlan(),
        profile_provider=experiment.profile_provider,
    )
    assert isinstance(discovery, f2523._DiscoveryContext)
    diagnostic = experiment.capture_diagnostic(
        qualification.result,
        discovery.geometry.delta_hz,
    )
    baseline = f2523.qualify_distributed_witness(
        discovery,
        diagnostic,
        f2.MotherPlan(),
        profile_provider=experiment.profile_provider,
    )
    assert isinstance(baseline, f2523.WitnessQualification)

    delta_bins = int(round(discovery.geometry.delta_hz / 10.0))
    target_index = int(round((discovery.geometry.target.baseband_position_a_hz + 4_000.0) / 10.0))
    target_radius = int(
        np.ceil(
            max(
                discovery.geometry.target.bandwidth_hz,
                discovery.geometry.target.uncertainty_hz,
            )
            / 10.0
        )
    )
    for key, profile in tuple(experiment.profiles.items()):
        if not key.startswith("diagnostic:"):
            continue
        altered = profile.residual_db.copy()
        for offset in (0, delta_bins, -delta_bins, delta_bins // 2, -(delta_bins // 2)):
            centre = target_index + offset
            altered[
                max(0, centre - target_radius) : min(
                    len(altered), centre + target_radius + 1
                )
            ] = 10_000.0
        experiment.profiles[key] = _profile(altered)
    changed = f2523.qualify_distributed_witness(
        discovery,
        diagnostic,
        f2.MotherPlan(),
        profile_provider=experiment.profile_provider,
    )
    qualification.result.close()

    assert isinstance(changed, f2523.WitnessQualification)
    assert changed.orientation == baseline.orientation
    assert changed.observed_translation_hz == baseline.observed_translation_hz
    assert changed.receipt.state == baseline.receipt.state
    assert changed.receipt.correlations == baseline.receipt.correlations
    assert changed.receipt.clauses == baseline.receipt.clauses


def test_result_is_strict_metadata_and_contains_no_rf_arrays() -> None:
    experiment = _SyntheticExperiment()
    result = f2523.materialize_prefreeze_injected(
        _qualification(),
        capture_discovery=experiment.capture_discovery,
        capture_diagnostic=experiment.capture_diagnostic,
        profile_provider=experiment.profile_provider,
        frozen_at=NOW,
    )
    encoded = f2523.strict_json(result)

    assert "samples" not in encoded.lower()
    assert "stft" not in encoded.lower()
    assert '"waterfall":' not in encoded.lower()
    assert json.loads(encoded)["plan"]["raw_rf_persistence"] == "ZERO"
    strict_json_value(asdict(result))


def test_module_has_no_connector_or_live_execution_surface() -> None:
    source = inspect.getsource(f2523)
    signature = inspect.signature(f2523.materialize_prefreeze_injected)

    assert signature.parameters["capture_discovery"].default is inspect.Parameter.empty
    assert signature.parameters["capture_diagnostic"].default is inspect.Parameter.empty
    assert "fetch_kiwi_status" not in source
    assert "_capture_dual(" not in source
    assert "websocket" not in source
    assert "run_live" not in source
    assert f2523.assess_gate_f2_5_23().post_commit_seal_required
