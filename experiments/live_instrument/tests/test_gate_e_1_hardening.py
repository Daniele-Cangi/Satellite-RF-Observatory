"""Gate E.1: strict receipts, immutable qualification and zero RF persistence."""

from datetime import datetime, timedelta, timezone
import json
import math

import numpy as np
import pytest

from experiments.live_instrument import kiwi_gate_e as gate_e
from experiments.live_instrument import kiwi_probe as kiwi
from experiments.live_instrument.models import (
    ClauseStatus,
    DescriptiveSerializationError,
    emit_jsonl,
)


NOW = datetime(2026, 8, 16, 16, 0, tzinfo=timezone.utc)


def test_strict_json_represents_nonfinite_and_numpy_scalars_explicitly() -> None:
    lines: list[str] = []

    emit_jsonl(
        "numeric_boundary",
        {
            "negative": -math.inf,
            "positive": math.inf,
            "nan": math.nan,
            "numpy_bool": np.bool_(True),
            "numpy_int": np.int64(17),
            "numpy_float": np.float32(1.25),
        },
        sink=lines.append,
    )

    assert len(lines) == 1
    assert "NaN" not in lines[0]
    assert "Infinity" not in lines[0]
    value = json.loads(lines[0])["payload"]
    assert value["negative"] == {"numeric_state": "NEGATIVE_INFINITY"}
    assert value["positive"] == {"numeric_state": "POSITIVE_INFINITY"}
    assert value["nan"] == {"numeric_state": "NOT_A_NUMBER"}
    assert value["numpy_bool"] is True
    assert value["numpy_int"] == 17
    assert value["numpy_float"] == 1.25


def test_strict_json_refuses_numpy_arrays_instead_of_leaking_rf() -> None:
    with pytest.raises(DescriptiveSerializationError, match="hash the ephemeral artifact"):
        emit_jsonl("forbidden_rf", {"samples": np.ones(8, dtype=np.complex64)})


def test_qualification_error_is_not_capability_rejected(monkeypatch) -> None:
    mother = gate_e.GateEMotherPlan()
    capture = _capture()

    def broken_transform(*_args, **_kwargs):
        raise RuntimeError("feature extraction defect")

    monkeypatch.setattr(gate_e, "offer_from_capture", broken_transform)

    qualification = gate_e.qualify_ephemeral_capture(mother, capture, NOW)

    assert qualification.decision is gate_e.QualificationDecision.QUALIFICATION_ERROR
    assert qualification.decision is not gate_e.QualificationDecision.CAPABILITY_REJECTED
    assert qualification.artifact_hash == kiwi._capture_hash(capture)


def test_physically_evaluated_continuity_failure_is_capability_rejected(monkeypatch) -> None:
    mother = gate_e.GateEMotherPlan()
    capture = _capture()
    offer = _offer(capture, usable=False)
    monkeypatch.setattr(gate_e, "offer_from_capture", lambda *_args, **_kwargs: offer)

    qualification = gate_e.qualify_ephemeral_capture(mother, capture, NOW)

    assert qualification.decision is gate_e.QualificationDecision.CAPABILITY_REJECTED
    assert "continuous" in qualification.reason
    assert qualification.artifact_hash == offer.artifact_hash


def test_rejected_candidate_description_retains_artifact_hash(monkeypatch) -> None:
    mother = gate_e.GateEMotherPlan()
    capture = _capture()
    offer = _offer(capture, usable=False)
    monkeypatch.setattr(gate_e, "offer_from_capture", lambda *_args, **_kwargs: offer)
    qualification = gate_e.qualify_ephemeral_capture(mother, capture, NOW)
    lines: list[str] = []

    description = gate_e.emit_qualification_description(qualification, sink=lines.append)

    assert description.description_state is gate_e.DescriptionState.DESCRIBED
    payload = json.loads(lines[0])["payload"]
    assert payload["decision"] == "CAPABILITY_REJECTED"
    assert payload["artifact_hash"] == kiwi._capture_hash(capture)


def test_receipt_failure_cannot_rewrite_physical_decision(monkeypatch) -> None:
    mother = gate_e.GateEMotherPlan()
    capture = _capture()
    offer = _offer(capture, usable=False)
    monkeypatch.setattr(gate_e, "offer_from_capture", lambda *_args, **_kwargs: offer)
    qualification = gate_e.qualify_ephemeral_capture(mother, capture, NOW)

    def broken_sink(_line: str) -> None:
        raise OSError("receipt sink unavailable")

    description = gate_e.emit_qualification_description(
        qualification,
        sink=broken_sink,
    )

    assert qualification.decision is gate_e.QualificationDecision.CAPABILITY_REJECTED
    assert description.physical_decision is qualification.decision
    assert description.description_state is gate_e.DescriptionState.DESCRIPTION_ERROR
    assert "receipt sink unavailable" in (description.error or "")


def test_downstream_clauses_are_not_evaluated_when_admission_fails() -> None:
    artifact_hash = "b" * 64
    outcome = gate_e.falsifiability_not_entered(
        gate_e.GateEMotherPlan(),
        None,
        NOW - timedelta(seconds=1),
        NOW,
        "no candidate admitted",
        now=NOW,
        candidate_artifact_hashes=(artifact_hash,),
        candidate_measurement_roots=("kiwi:rejected",),
    )

    assert all(
        assessment.status is ClauseStatus.NOT_EVALUATED
        for assessment in outcome.belief.clause_assessments
    )
    assert outcome.evidence.receipt.artifact_hashes == (artifact_hash,)
    assert outcome.evidence.receipt.measurement_roots == ("kiwi:rejected",)


def test_ephemeral_hashing_creates_no_rf_files(monkeypatch) -> None:
    mother = gate_e.GateEMotherPlan()
    capture = _capture()
    offer = _offer(capture, usable=False)
    observed: dict[str, str] = {}

    def inspected_offer(*_args, artifact_hash=None, **_kwargs):
        observed["hash"] = artifact_hash
        return offer

    monkeypatch.setattr(gate_e, "offer_from_capture", inspected_offer)
    def forbidden_file_open(*_args, **_kwargs):
        raise AssertionError("qualification attempted filesystem persistence")

    monkeypatch.setattr("builtins.open", forbidden_file_open)

    qualification = gate_e.qualify_ephemeral_capture(mother, capture, NOW)

    assert observed["hash"] == kiwi._capture_hash(capture)
    assert qualification.artifact_hash == observed["hash"]
    assert qualification.offer is not None
    assert qualification.offer.audit.blocks == ()


def _capture() -> kiwi.KiwiCapture:
    sample_rate = 100.0
    samples = np.ones(500, dtype=np.complex64)
    end = NOW + timedelta(seconds=len(samples) / sample_rate)
    block = kiwi.IQBlock(
        NOW,
        end,
        samples,
        -70.0,
        1,
        True,
        False,
        1,
        arrived_at=end + timedelta(milliseconds=50),
    )
    return kiwi.KiwiCapture(
        kiwi.KiwiEndpoint("candidate", "127.0.0.1"),
        10_000_000.0,
        sample_rate,
        {"ext_api": "4"},
        (block,),
        NOW,
        block.arrived_at,
    )


def _offer(capture: kiwi.KiwiCapture, *, usable: bool) -> gate_e.GateECapabilityOffer:
    artifact_hash = kiwi._capture_hash(capture)
    audit = kiwi.CaptureAudit(
        usable,
        () if usable else ("longest continuous segment is shorter than the frozen minimum",),
        capture.blocks,
        0,
        0,
        0,
        1.25,
        capture.sample_rate_hz,
        0.0,
        0.0,
        0.05,
        0.08,
        1,
    )
    metrics = gate_e.SegmentMetrics(NOW, NOW + timedelta(seconds=1), 8.0, 7.0, 9.0, 2.0, 12.0, 8.0)
    return gate_e.GateECapabilityOffer(
        f"candidate:{artifact_hash[:12]}",
        capture.endpoint,
        capture.center_frequency_hz,
        NOW,
        NOW + timedelta(minutes=10),
        (gate_e.WWV,),
        metrics,
        audit,
        usable,
        ("station_specific_marker", "carrier_path", "timecode_path"),
        4.0,
        12.0,
        artifact_hash,
    )
