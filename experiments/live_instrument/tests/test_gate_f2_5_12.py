"""Offline tests for Gate F2.5.12 semantic frame receipts."""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timezone
from hashlib import sha256
import inspect
import json
import math
import struct

import pytest

from experiments.live_instrument import kiwi_gate_f2_5_11 as f2511
from experiments.live_instrument import kiwi_gate_f2_5_12 as f2512
from experiments.live_instrument.models import strict_json_value


ARRIVAL = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)


def _snd_message(
    *,
    flags: int = 0x08,
    sequence: int = 17,
    gps_age_s: int = 5,
    gps_seconds: int = 100_000,
    sample_bytes: bytes | None = None,
) -> bytes:
    if sample_bytes is None:
        sample_bytes = struct.pack(">hhhh", 100, -100, 200, -200)
    body = (
        struct.pack("<BI", flags, sequence)
        + struct.pack(">H", 1_000)
        + struct.pack("<BBII", gps_age_s, 0, gps_seconds, 250_000_000)
        + sample_bytes
    )
    return b"SND" + body


def _walk_keys(value: object) -> tuple[str, ...]:
    if isinstance(value, dict):
        return tuple(str(key) for key in value) + tuple(
            key for item in value.values() for key in _walk_keys(item)
        )
    if isinstance(value, list):
        return tuple(key for item in value for key in _walk_keys(item))
    return ()


def test_ready_snd_materialises_every_clause_and_event_time() -> None:
    raw = _snd_message()
    receipt = f2512.observe_data_frame(raw, sample_rate_hz=12_000.0, arrival=ARRIVAL)

    assert receipt.artifact_hash == sha256(raw).hexdigest()
    assert receipt.frame_class is f2512.FrameClass.SND
    assert receipt.disposition is f2512.FrameDisposition.READINESS_ADMITTED
    assert receipt.snd_header_clause is f2512.ClauseEvaluation.SATISFIED
    assert receipt.iq_mode_clause is f2512.ClauseEvaluation.SATISFIED
    assert receipt.sample_decode_clause is f2512.ClauseEvaluation.SATISFIED
    assert receipt.gps_seconds_present_clause is f2512.ClauseEvaluation.SATISFIED
    assert receipt.gps_age_within_limit_clause is f2512.ClauseEvaluation.SATISFIED
    assert receipt.readiness_clause is f2512.ClauseEvaluation.SATISFIED
    assert receipt.sequence == 17
    assert receipt.gps_solution_age_s == 5
    assert receipt.readiness_event_start is not None
    assert receipt.readiness_event_end > receipt.readiness_event_start
    assert receipt.raw_rf_persistence == "ZERO"


def test_no_snd_and_nonqualifying_snd_are_now_distinguishable() -> None:
    no_snd = (
        f2512.observe_data_frame(
            b"MSG sample_rate=12000", sample_rate_hz=12_000.0, arrival=ARRIVAL
        ),
        f2512.observe_close_frame(b""),
    )
    stale_snd = (
        f2512.observe_data_frame(
            b"MSG sample_rate=12000", sample_rate_hz=12_000.0, arrival=ARRIVAL
        ),
        f2512.observe_data_frame(
            _snd_message(gps_age_s=31), sample_rate_hz=12_000.0, arrival=ARRIVAL
        ),
        f2512.observe_close_frame(b""),
    )

    assert not any(item.frame_class is f2512.FrameClass.SND for item in no_snd)
    snd = next(item for item in stale_snd if item.frame_class is f2512.FrameClass.SND)
    assert snd.disposition is f2512.FrameDisposition.SND_NOT_ADMITTED
    assert snd.gps_seconds_present_clause is f2512.ClauseEvaluation.SATISFIED
    assert snd.gps_age_within_limit_clause is f2512.ClauseEvaluation.UNSATISFIED
    assert snd.readiness_clause is f2512.ClauseEvaluation.UNSATISFIED


def test_missing_gps_seconds_is_a_separate_unsatisfied_clause() -> None:
    receipt = f2512.observe_data_frame(
        _snd_message(gps_seconds=0), sample_rate_hz=12_000.0, arrival=ARRIVAL
    )

    assert receipt.disposition is f2512.FrameDisposition.SND_NOT_ADMITTED
    assert receipt.sample_decode_clause is f2512.ClauseEvaluation.SATISFIED
    assert receipt.gps_seconds_present_clause is f2512.ClauseEvaluation.UNSATISFIED
    assert receipt.gps_age_within_limit_clause is f2512.ClauseEvaluation.SATISFIED
    assert receipt.readiness_clause is f2512.ClauseEvaluation.UNSATISFIED
    assert receipt.readiness_event_start is None
    assert receipt.readiness_event_end is None


def test_non_iq_snd_is_not_misreported_as_a_decode_error() -> None:
    receipt = f2512.observe_data_frame(
        _snd_message(flags=0), sample_rate_hz=12_000.0, arrival=ARRIVAL
    )

    assert receipt.snd_header_clause is f2512.ClauseEvaluation.SATISFIED
    assert receipt.iq_mode_clause is f2512.ClauseEvaluation.UNSATISFIED
    assert receipt.sample_decode_clause is f2512.ClauseEvaluation.NOT_EVALUATED
    assert receipt.readiness_clause is f2512.ClauseEvaluation.UNSATISFIED
    assert receipt.disposition is f2512.FrameDisposition.SND_NOT_ADMITTED
    assert receipt.descriptive_error_type is None


def test_short_header_is_descriptive_and_blocks_downstream_clauses() -> None:
    raw = b"SNDshort"
    receipt = f2512.observe_data_frame(raw, sample_rate_hz=12_000.0, arrival=ARRIVAL)

    assert receipt.artifact_hash == sha256(raw).hexdigest()
    assert receipt.disposition is f2512.FrameDisposition.QUALIFICATION_ERROR
    assert receipt.snd_header_clause is f2512.ClauseEvaluation.QUALIFICATION_ERROR
    assert receipt.iq_mode_clause is f2512.ClauseEvaluation.NOT_EVALUATED
    assert receipt.sample_decode_clause is f2512.ClauseEvaluation.NOT_EVALUATED
    assert receipt.gps_seconds_present_clause is f2512.ClauseEvaluation.NOT_EVALUATED
    assert receipt.gps_age_within_limit_clause is f2512.ClauseEvaluation.NOT_EVALUATED
    assert receipt.readiness_clause is f2512.ClauseEvaluation.NOT_EVALUATED
    assert receipt.descriptive_error_type == "ShortSNDHeader"
    assert receipt.descriptive_error_hash is not None


def test_sample_decode_error_cannot_become_physical_rejection() -> None:
    raw = _snd_message(sample_bytes=b"\x01")
    receipt = f2512.observe_data_frame(raw, sample_rate_hz=12_000.0, arrival=ARRIVAL)

    assert receipt.artifact_hash == sha256(raw).hexdigest()
    assert receipt.snd_header_clause is f2512.ClauseEvaluation.SATISFIED
    assert receipt.iq_mode_clause is f2512.ClauseEvaluation.SATISFIED
    assert receipt.sample_decode_clause is f2512.ClauseEvaluation.QUALIFICATION_ERROR
    assert receipt.readiness_clause is f2512.ClauseEvaluation.NOT_EVALUATED
    assert receipt.disposition is f2512.FrameDisposition.QUALIFICATION_ERROR
    assert receipt.descriptive_error_type == "ValueError"
    assert "CAPABILITY_REJECTED" not in {item.value for item in f2512.FrameDisposition}


def test_nonfinite_sample_rate_is_descriptive_and_never_reaches_json() -> None:
    raw = _snd_message()
    receipt = f2512.observe_data_frame(raw, sample_rate_hz=math.nan, arrival=ARRIVAL)
    encoded = json.dumps(strict_json_value(receipt), allow_nan=False)

    assert receipt.disposition is f2512.FrameDisposition.QUALIFICATION_ERROR
    assert receipt.sample_decode_clause is f2512.ClauseEvaluation.QUALIFICATION_ERROR
    assert receipt.readiness_clause is f2512.ClauseEvaluation.NOT_EVALUATED
    assert receipt.descriptive_error_type == "ValueError"
    assert "NaN" not in encoded
    assert "Infinity" not in encoded


def test_msg_content_is_hashed_but_not_retained() -> None:
    raw = b"MSG unknown=do-not-retain"
    receipt = f2512.observe_data_frame(raw, sample_rate_hz=12_000.0, arrival=ARRIVAL)
    encoded = json.dumps(strict_json_value(receipt), allow_nan=False)

    assert receipt.frame_class is f2512.FrameClass.MSG
    assert receipt.disposition is f2512.FrameDisposition.DESCRIPTIVE_CONTROL
    assert receipt.artifact_hash == sha256(raw).hexdigest()
    assert "do-not-retain" not in encoded
    assert receipt.readiness_clause is f2512.ClauseEvaluation.NOT_EVALUATED


def test_empty_close_has_no_invented_1005_status() -> None:
    receipt = f2512.observe_close_frame(b"")

    assert receipt.artifact_hash == f2511.EMPTY_CLOSE_ARTIFACT_SHA256
    assert receipt.frame_class is f2512.FrameClass.CLOSE
    assert receipt.close_payload_state is f2512.ClosePayloadState.EMPTY_NO_STATUS
    assert receipt.peer_close_status_code is None
    assert receipt.disposition is f2512.FrameDisposition.DESCRIPTIVE_CONTROL


def test_explicit_close_status_remains_distinct_from_empty_payload() -> None:
    payload = struct.pack(">H", 1000) + b"normal"
    receipt = f2512.observe_close_frame(payload)

    assert receipt.close_payload_state is f2512.ClosePayloadState.STATUS_PRESENT
    assert receipt.peer_close_status_code == 1000
    assert receipt.artifact_hash == sha256(b"CLOSE" + payload).hexdigest()


def test_one_byte_close_is_qualification_error_not_peer_status() -> None:
    receipt = f2512.observe_close_frame(b"\x03")

    assert receipt.close_payload_state is f2512.ClosePayloadState.MALFORMED_ONE_BYTE
    assert receipt.peer_close_status_code is None
    assert receipt.disposition is f2512.FrameDisposition.QUALIFICATION_ERROR
    assert receipt.descriptive_error_type == "MalformedClosePayload"


def test_empty_close_receipt_refuses_an_invented_peer_status() -> None:
    receipt = f2512.observe_close_frame(b"")

    with pytest.raises(ValueError, match="cannot invent"):
        replace(receipt, peer_close_status_code=1005)


def test_descriptive_error_cannot_be_relabelled_physical_non_admission() -> None:
    receipt = f2512.observe_data_frame(
        _snd_message(sample_bytes=b"\x01"),
        sample_rate_hz=12_000.0,
        arrival=ARRIVAL,
    )

    with pytest.raises(ValueError, match="descriptive errors cannot alter"):
        replace(receipt, disposition=f2512.FrameDisposition.SND_NOT_ADMITTED)


def test_receipts_are_strict_json_and_have_no_rf_surface() -> None:
    receipts = (
        f2512.observe_data_frame(
            _snd_message(), sample_rate_hz=12_000.0, arrival=ARRIVAL
        ),
        f2512.observe_data_frame(
            _snd_message(gps_age_s=31), sample_rate_hz=12_000.0, arrival=ARRIVAL
        ),
        f2512.observe_close_frame(b""),
    )
    encoded_value = strict_json_value(receipts)
    encoded = json.dumps(encoded_value, allow_nan=False, sort_keys=True)
    keys = set(_walk_keys(encoded_value))

    assert not keys & {
        "body",
        "frames",
        "iq",
        "iq_array",
        "iq_samples",
        "payload",
        "raw_frame",
        "raw_message",
        "samples",
        "stft",
        "waterfall",
    }
    assert "complex" not in encoded
    assert all(item.raw_rf_persistence == "ZERO" for item in receipts)
    assert all(len(item.receipt_hash) == 64 for item in receipts)


def test_frozen_threshold_and_offline_surface_have_no_runtime_override() -> None:
    signature = inspect.signature(f2512.observe_data_frame)
    source = inspect.getsource(f2512)

    assert f2512.FROZEN_MAX_GPS_SOLUTION_AGE_S == 30
    assert "max_gps_solution_age_s" not in signature.parameters
    assert f2512.F2512Exit.HASH_BOUND_SEMANTIC_RECEIPT_IMPLEMENTED.value == (
        "HASH_BOUND_SEMANTIC_RECEIPT_IMPLEMENTED"
    )
    assert not any(
        token in source
        for token in (
            "import websocket",
            "import requests",
            "urlopen",
            "create_connection",
            "run_live",
            "run_reviewed_once",
        )
    )
    assert not hasattr(f2512, "run")
    assert not hasattr(f2512, "main")


def test_dataclass_itself_contains_no_byte_or_array_field() -> None:
    receipt = f2512.observe_data_frame(
        _snd_message(), sample_rate_hz=12_000.0, arrival=ARRIVAL
    )
    materialised = asdict(receipt)

    assert not any(isinstance(value, (bytes, bytearray, memoryview)) for value in materialised.values())
    assert all(not value.__class__.__module__.startswith("numpy") for value in materialised.values())
