"""Synthetic integration tests for Gate F2.5.28."""

from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import inspect
import json
import math
import struct

import numpy as np

from experiments.live_instrument import kiwi_gate_f2_5_27 as f2527
from experiments.live_instrument import kiwi_gate_f2_5_28 as f2528


SAMPLE_RATE_HZ = 12_000.0
SAMPLE_COUNT = 512
FRAME_DURATION_NS = round(SAMPLE_COUNT * 1_000_000_000 / SAMPLE_RATE_HZ)


def _hash(label: str) -> str:
    return sha256(label.encode()).hexdigest()


def _snd(
    sequence: int,
    start_ns: int,
    *,
    age_s: int = 103,
    iq: bool = True,
) -> bytes:
    raw_time = start_ns % f2527.GPS_WEEK_NS
    flags = 0x08 if iq else 0x00
    header = (
        struct.pack("<BI", flags, sequence)
        + b"\x00\x00"
        + struct.pack(
            "<BBII",
            age_s,
            0,
            raw_time // 1_000_000_000,
            raw_time % 1_000_000_000,
        )
    )
    values = np.empty(SAMPLE_COUNT * 2, dtype=">i2")
    values[0::2] = np.arange(SAMPLE_COUNT, dtype=np.int16) % 127
    values[1::2] = -(np.arange(SAMPLE_COUNT, dtype=np.int16) % 97)
    return b"SND" + header + values.tobytes()


def _inputs(
    *,
    start_ns: int = 100_000_000_000,
    age_s: int = 103,
    arrival_offset_ns: int = 0,
) -> tuple[f2528.TransientSNDInput, ...]:
    return tuple(
        f2528.TransientSNDInput(
            monotonic_arrival_ns=(
                1_000_000_000 + index * 50_000_000 + arrival_offset_ns
            ),
            raw_message=_snd(
                index + 1,
                start_ns + index * FRAME_DURATION_NS,
                age_s=age_s,
            ),
        )
        for index in range(8)
    )


def _discovery(eligible: bool = True, retained: list[np.ndarray] | None = None):
    def probe(view: object) -> f2528.DiscoveryProbeResult:
        if retained is not None:
            retained.append(view.reference_iq[0])
        assert all(not item.flags.writeable for item in view.reference_iq)
        assert all(not item.flags.writeable for item in view.perturbed_iq)
        return f2528.DiscoveryProbeResult(
            eligible=eligible,
            artifact_hashes=(_hash("discovery"),),
            statement=(
                "one synthetic target is eligible"
                if eligible
                else "no synthetic target is eligible"
            ),
        )

    return probe


def _boundary(
    view: object,
    transition: str,
    before_index: int,
    after_index: int,
    command_ns: int,
    settling_complete_ns: int,
) -> f2527.BoundaryWitnessReceipt:
    before_perturbed = view.perturbed_receipts[before_index]
    after_perturbed = view.perturbed_receipts[after_index]
    before_reference = view.reference_receipts[before_index]
    after_reference = view.reference_receipts[after_index]
    anchor = f2527.CommandBoundaryAnchor(
        transition=transition,
        command_hash=_hash(f"command-{transition}"),
        command_issued_monotonic_ns=command_ns,
        settling_complete_monotonic_ns=settling_complete_ns,
        last_precommand_perturbed_frame_hash=(
            before_perturbed.artifact_hash_before_analysis
        ),
        first_postsettling_perturbed_frame_hash=(
            after_perturbed.artifact_hash_before_analysis
        ),
        reference_before_frame_hash=before_reference.artifact_hash_before_analysis,
        reference_after_frame_hash=after_reference.artifact_hash_before_analysis,
    )
    return f2527.evaluate_command_boundary(
        anchor,
        last_precommand_perturbed=before_perturbed,
        first_postsettling_perturbed=after_perturbed,
        reference_before=before_reference,
        reference_after=after_reference,
    )


def _retune(qualified: bool = True, retain_one_boundary: bool = False):
    def probe(view: object) -> f2528.RetuneProbeResult:
        boundaries = (
            _boundary(view, "A1_TO_B", 2, 4, 1_110_000_000, 1_130_000_000),
            _boundary(view, "B_TO_A2", 4, 6, 1_210_000_000, 1_230_000_000),
        )
        if retain_one_boundary:
            boundaries = boundaries[:1]
        return f2528.RetuneProbeResult(
            claimed_qualified=qualified,
            boundary_receipts=boundaries,
            witness_artifact_hashes=(_hash("distributed-witness"),),
            statement="synthetic distributed witness result",
        )

    return probe


def _run(
    *,
    reference: tuple[f2528.TransientSNDInput, ...] | None = None,
    perturbed: tuple[f2528.TransientSNDInput, ...] | None = None,
    discovery_probe=None,
    retune_probe=None,
) -> f2528.F2528RunResult:
    return f2528.run_one_shot_injected(
        reference_inputs=reference or _inputs(),
        perturbed_inputs=perturbed or _inputs(arrival_offset_ns=1_000_000),
        endpoint_identity="one-kiwi.example:8073",
        reference_channel_id=0,
        perturbed_channel_id=1,
        sample_rate_hz=SAMPLE_RATE_HZ,
        discovery_probe=discovery_probe or _discovery(),
        retune_probe=retune_probe or _retune(),
    )


def _phase(result: f2528.F2528RunResult, name: str) -> f2528.PhaseReceipt:
    return next(item for item in result.phases if item.phase == name)


def _walk_keys(value: object) -> tuple[str, ...]:
    if isinstance(value, dict):
        return tuple(str(key) for key in value) + tuple(
            key for item in value.values() for key in _walk_keys(item)
        )
    if isinstance(value, (list, tuple)):
        return tuple(key for item in value for key in _walk_keys(item))
    return ()


def _assert_finite(value: object) -> None:
    if isinstance(value, dict):
        for item in value.values():
            _assert_finite(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _assert_finite(item)
    elif isinstance(value, float):
        assert math.isfinite(value)


def test_parent_environment_and_integration_surfaces_are_sealed() -> None:
    assessment = f2528.assess()

    assert assessment.exit is f2528.F2528Exit.INJECTED_ONE_SHOT_INTEGRATED_OFFLINE
    assert assessment.envelope is not None
    assert assessment.envelope.reviewed_f2527_commit == f2528.REVIEWED_F2527_COMMIT
    assert assessment.causal_source_hashes_match is True
    assert assessment.numerical_environment_matches is True
    assert assessment.integration_surfaces_match is True
    assert assessment.envelope.input_mode == "INJECTED_TRANSIENT_SND_AND_CALLBACKS_ONLY"
    assert assessment.envelope.live_execution_authorised is False


def test_frame_is_hashed_before_decode_and_returns_only_scalars_plus_ephemeral_ram() -> None:
    transient = _inputs()[0]
    observed = f2528.observe_relative_snd(
        transient,
        endpoint_identity="one-kiwi.example:8073",
        branch_role="reference",
        channel_id=0,
        sample_rate_hz=SAMPLE_RATE_HZ,
    )

    assert isinstance(observed, f2528._EphemeralDecodedFrame)
    assert observed.receipt.artifact_hash_before_analysis == sha256(
        transient.raw_message
    ).hexdigest()
    assert observed.receipt.decoded_sample_count == SAMPLE_COUNT
    assert observed.receipt.gps_solution_age_s == 103
    assert observed.samples.dtype == np.complex64
    assert observed.samples.size == SAMPLE_COUNT
    assert "raw_message" not in asdict(observed.receipt)
    observed.zeroize()
    assert np.all(observed.samples == 0)


def test_malformed_frame_keeps_hash_but_never_becomes_physical_rejection() -> None:
    transient = f2528.TransientSNDInput(1_000_000_000, b"SNDbad")
    observed = f2528.observe_relative_snd(
        transient,
        endpoint_identity="one-kiwi.example:8073",
        branch_role="reference",
        channel_id=0,
        sample_rate_hz=SAMPLE_RATE_HZ,
    )

    assert isinstance(observed, f2528.FrameQualificationErrorReceipt)
    assert observed.artifact_hash_before_analysis == sha256(b"SNDbad").hexdigest()
    assert observed.error_type == "MalformedSNDFrame"
    assert observed.physical_decision_affected is False
    assert observed.raw_rf_persistence == "ZERO"


def test_temporal_failure_calls_neither_discovery_nor_retune() -> None:
    calls = {"discovery": 0, "retune": 0}

    def discovery(_view: object) -> f2528.DiscoveryProbeResult:
        calls["discovery"] += 1
        return _discovery()(_view)

    def retune(_view: object) -> f2528.RetuneProbeResult:
        calls["retune"] += 1
        return _retune()(_view)

    result = _run(
        perturbed=_inputs(age_s=255, arrival_offset_ns=1_000_000),
        discovery_probe=discovery,
        retune_probe=retune,
    )

    assert result.outcome == "TEMPORAL_NOT_ADMITTED"
    assert result.temporal_admission is not None
    assert result.temporal_admission.state == "NOT_ADMISSIBLE"
    assert calls == {"discovery": 0, "retune": 0}
    assert result.discovery_call_count == 0
    assert result.retune_call_count == 0
    assert _phase(result, "RELATIVE_DUAL_SND_QUALIFICATION").state == "UNSATISFIED"
    assert all(item.state == "NOT_EVALUATED" for item in result.phases[1:])
    assert result.zeroization.all_arrays_zeroized is True


def test_frame_qualification_error_blocks_every_downstream_phase() -> None:
    reference = list(_inputs())
    reference[3] = f2528.TransientSNDInput(
        reference[3].monotonic_arrival_ns, b"SNDbad"
    )

    result = _run(reference=tuple(reference))

    assert result.outcome == "QUALIFICATION_ERROR"
    assert result.temporal_admission is None
    assert len(result.frame_errors) == 1
    assert result.discovery_call_count == 0
    assert result.retune_call_count == 0
    assert result.phases[0].state == "QUALIFICATION_ERROR"
    assert all(item.state == "NOT_EVALUATED" for item in result.phases[1:])
    assert result.zeroization.ephemeral_frame_count == 15


def test_discovery_failure_blocks_retune_and_zeroizes_leaked_readonly_views() -> None:
    retained: list[np.ndarray] = []

    result = _run(discovery_probe=_discovery(False, retained))

    assert result.outcome == "NO_FALSIFIABLE_INTERVENTION"
    assert result.discovery_call_count == 1
    assert result.retune_call_count == 0
    assert result.phases[0].state == "SATISFIED"
    assert result.phases[1].state == "UNSATISFIED"
    assert all(item.state == "NOT_EVALUATED" for item in result.phases[2:])
    assert retained and np.all(retained[0] == 0)
    assert result.zeroization.zeroized_before_result_return is True


def test_retune_requires_both_predeclared_boundary_witnesses() -> None:
    valid = _run()
    missing_boundary = _run(retune_probe=_retune(retain_one_boundary=True))

    assert valid.outcome == "RETUNE_QUALIFIED_OFFLINE"
    assert valid.discovery_call_count == 1
    assert valid.retune_call_count == 1
    assert [item.state for item in valid.phases] == [
        "SATISFIED",
        "SATISFIED",
        "SATISFIED",
        "NOT_EVALUATED",
        "NOT_EVALUATED",
    ]
    assert {item.transition for item in valid.boundary_receipts} == {
        "A1_TO_B",
        "B_TO_A2",
    }
    assert missing_boundary.outcome == "INTERVENTION_NOT_QUALIFIED"
    assert missing_boundary.phases[2].state == "UNSATISFIED"
    assert len(missing_boundary.boundary_receipts) == 1


def test_description_error_cannot_call_later_phase_or_change_physical_state() -> None:
    def broken_discovery(_view: object) -> f2528.DiscoveryProbeResult:
        raise RuntimeError("synthetic description failure")

    result = _run(discovery_probe=broken_discovery)

    assert result.outcome == "QUALIFICATION_ERROR"
    assert result.discovery_call_count == 1
    assert result.retune_call_count == 0
    assert len(result.downstream_errors) == 1
    assert result.downstream_errors[0].physical_decision_affected is False
    assert result.physical_hypothesis_state == "NOT_EVALUATED"
    assert result.physical_decision_affected_by_description is False


def test_result_is_strict_finite_receipt_json_without_rf_payload() -> None:
    value = asdict(_run())

    _assert_finite(value)
    assert json.dumps(value, allow_nan=False, default=str)
    assert not set(_walk_keys(value)) & f2528._FORBIDDEN_RECEIPT_KEYS
    assert value["raw_rf_persistence"] == "ZERO"
    assert value["zeroization"]["raw_rf_persistence"] == "ZERO"


def test_public_surface_is_injected_only_and_source_orders_hash_before_decode() -> None:
    module_source = inspect.getsource(f2528)
    frame_source = inspect.getsource(f2528.observe_relative_snd)
    signature = inspect.signature(f2528.run_one_shot_injected)

    assert frame_source.index("artifact_hash = sha256(raw_message).hexdigest()") < (
        frame_source.index("struct.unpack")
    )
    assert "websocket" not in module_source.lower()
    assert "urlopen" not in module_source
    assert "run_live" not in module_source
    assert "live_authorised" not in signature.parameters
    assert "connector" not in signature.parameters
    assert set(signature.parameters) == {
        "reference_inputs",
        "perturbed_inputs",
        "endpoint_identity",
        "reference_channel_id",
        "perturbed_channel_id",
        "sample_rate_hz",
        "discovery_probe",
        "retune_probe",
        "temporal_plan",
    }
