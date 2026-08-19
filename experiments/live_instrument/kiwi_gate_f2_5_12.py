"""Gate F2.5.12: hash-bound semantic frame receipts, offline only.

The frozen F2.5.10 runner and outcome are intentionally untouched.  This
module materialises the minimum metadata that a future direct-SND attempt
would need to distinguish no SND from SND rejected by one readiness clause.
Raw frames and decoded samples remain ephemeral and are never returned.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import math
import struct

from . import kiwi_gate_f2 as f2
from . import kiwi_probe as kiwi


F2512_TRANSFORM_VERSION = "gate-f2.5.12-hash-bound-semantic-frame-receipt-v1"
FROZEN_MAX_GPS_SOLUTION_AGE_S = 30
RAW_RF_PERSISTENCE = "ZERO"


class F2512Exit(str, Enum):
    HASH_BOUND_SEMANTIC_RECEIPT_IMPLEMENTED = (
        "HASH_BOUND_SEMANTIC_RECEIPT_IMPLEMENTED"
    )


class FrameClass(str, Enum):
    MSG = "MSG"
    SND = "SND"
    CLOSE = "CLOSE"
    OTHER = "OTHER"
    MALFORMED = "MALFORMED"


class ClauseEvaluation(str, Enum):
    SATISFIED = "SATISFIED"
    UNSATISFIED = "UNSATISFIED"
    NOT_EVALUATED = "NOT_EVALUATED"
    QUALIFICATION_ERROR = "QUALIFICATION_ERROR"


class FrameDisposition(str, Enum):
    DESCRIPTIVE_CONTROL = "DESCRIPTIVE_CONTROL"
    READINESS_ADMITTED = "READINESS_ADMITTED"
    SND_NOT_ADMITTED = "SND_NOT_ADMITTED"
    QUALIFICATION_ERROR = "QUALIFICATION_ERROR"


class ClosePayloadState(str, Enum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    EMPTY_NO_STATUS = "EMPTY_NO_STATUS"
    STATUS_PRESENT = "STATUS_PRESENT"
    MALFORMED_ONE_BYTE = "MALFORMED_ONE_BYTE"


@dataclass(frozen=True, slots=True)
class SemanticFrameReceipt:
    artifact_hash: str
    frame_class: FrameClass
    frame_byte_count: int
    disposition: FrameDisposition
    snd_header_clause: ClauseEvaluation
    iq_mode_clause: ClauseEvaluation
    sample_decode_clause: ClauseEvaluation
    gps_seconds_present_clause: ClauseEvaluation
    gps_age_within_limit_clause: ClauseEvaluation
    readiness_clause: ClauseEvaluation
    sequence: int | None
    gps_solution_age_s: int | None
    readiness_event_start: datetime | None
    readiness_event_end: datetime | None
    close_payload_state: ClosePayloadState
    peer_close_status_code: int | None
    descriptive_error_type: str | None
    descriptive_error_hash: str | None
    raw_rf_persistence: str = RAW_RF_PERSISTENCE
    transform_version: str = F2512_TRANSFORM_VERSION

    def __post_init__(self) -> None:
        if len(self.artifact_hash) != 64 or any(
            character not in "0123456789abcdef" for character in self.artifact_hash
        ):
            raise ValueError("semantic frame receipt requires a SHA-256 artifact hash")
        if self.frame_byte_count < 0:
            raise ValueError("frame byte count cannot be negative")
        if self.raw_rf_persistence != "ZERO":
            raise ValueError("RF persistence is forbidden")
        if (self.descriptive_error_type is None) != (
            self.descriptive_error_hash is None
        ):
            raise ValueError("descriptive error type and hash must appear together")
        if self.descriptive_error_hash is not None and (
            len(self.descriptive_error_hash) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.descriptive_error_hash
            )
        ):
            raise ValueError("descriptive errors require SHA-256")
        if self.disposition is FrameDisposition.QUALIFICATION_ERROR:
            if self.descriptive_error_type is None:
                raise ValueError("qualification error requires a typed description")
        elif self.descriptive_error_type is not None:
            raise ValueError("descriptive errors cannot alter a physical disposition")

        event_fields = (self.readiness_event_start, self.readiness_event_end)
        if self.readiness_clause is ClauseEvaluation.SATISFIED:
            required = (
                self.snd_header_clause,
                self.iq_mode_clause,
                self.sample_decode_clause,
                self.gps_seconds_present_clause,
                self.gps_age_within_limit_clause,
            )
            if self.frame_class is not FrameClass.SND or any(
                clause is not ClauseEvaluation.SATISFIED for clause in required
            ):
                raise ValueError("readiness requires every upstream SND clause")
            if self.disposition is not FrameDisposition.READINESS_ADMITTED:
                raise ValueError("satisfied readiness must be admitted")
            if any(value is None for value in event_fields):
                raise ValueError("admitted readiness requires event time")
            start = _utc(self.readiness_event_start)  # type: ignore[arg-type]
            end = _utc(self.readiness_event_end)  # type: ignore[arg-type]
            if end < start:
                raise ValueError("readiness event time runs backwards")
        elif any(value is not None for value in event_fields):
            raise ValueError("non-admitted frames cannot claim event time")

        if self.frame_class is FrameClass.SND:
            if self.snd_header_clause is ClauseEvaluation.SATISFIED and (
                self.sequence is None or self.gps_solution_age_s is None
            ):
                raise ValueError("decoded SND header requires sequence and GPS age")
        elif self.sequence is not None or self.gps_solution_age_s is not None:
            raise ValueError("non-SND frame cannot claim SND header metadata")

        if self.disposition is FrameDisposition.SND_NOT_ADMITTED:
            if (
                self.frame_class is not FrameClass.SND
                or self.readiness_clause is not ClauseEvaluation.UNSATISFIED
            ):
                raise ValueError("SND_NOT_ADMITTED requires an unsatisfied SND readiness clause")
        if (
            self.readiness_clause is ClauseEvaluation.UNSATISFIED
            and self.disposition is not FrameDisposition.SND_NOT_ADMITTED
        ):
            raise ValueError("unsatisfied readiness must remain a non-admitted SND")

        if self.frame_class is FrameClass.CLOSE:
            if self.close_payload_state is ClosePayloadState.NOT_APPLICABLE:
                raise ValueError("close frame requires payload semantics")
            if self.close_payload_state is ClosePayloadState.STATUS_PRESENT:
                if self.peer_close_status_code is None:
                    raise ValueError("status-present close requires the peer status")
            elif self.peer_close_status_code is not None:
                raise ValueError("close without status cannot invent a peer status")
        elif (
            self.close_payload_state is not ClosePayloadState.NOT_APPLICABLE
            or self.peer_close_status_code is not None
        ):
            raise ValueError("non-close frame cannot claim close semantics")

    @property
    def receipt_hash(self) -> str:
        return f2._hash(self)


_NOT_EVALUATED = ClauseEvaluation.NOT_EVALUATED


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("arrival and event time must be timezone-aware")
    return value.astimezone(timezone.utc)


def _error_hash(
    artifact_hash: str,
    *,
    stage: str,
    error_type: str,
) -> str:
    return f2._hash(
        {
            "artifact_hash": artifact_hash,
            "stage": stage,
            "error_type": error_type,
        }
    )


def _base_receipt(
    *,
    artifact_hash: str,
    frame_class: FrameClass,
    frame_byte_count: int,
    disposition: FrameDisposition,
    snd_header_clause: ClauseEvaluation = _NOT_EVALUATED,
    iq_mode_clause: ClauseEvaluation = _NOT_EVALUATED,
    sample_decode_clause: ClauseEvaluation = _NOT_EVALUATED,
    gps_seconds_present_clause: ClauseEvaluation = _NOT_EVALUATED,
    gps_age_within_limit_clause: ClauseEvaluation = _NOT_EVALUATED,
    readiness_clause: ClauseEvaluation = _NOT_EVALUATED,
    sequence: int | None = None,
    gps_solution_age_s: int | None = None,
    readiness_event_start: datetime | None = None,
    readiness_event_end: datetime | None = None,
    close_payload_state: ClosePayloadState = ClosePayloadState.NOT_APPLICABLE,
    peer_close_status_code: int | None = None,
    descriptive_error_type: str | None = None,
    descriptive_error_hash: str | None = None,
) -> SemanticFrameReceipt:
    return SemanticFrameReceipt(
        artifact_hash,
        frame_class,
        frame_byte_count,
        disposition,
        snd_header_clause,
        iq_mode_clause,
        sample_decode_clause,
        gps_seconds_present_clause,
        gps_age_within_limit_clause,
        readiness_clause,
        sequence,
        gps_solution_age_s,
        readiness_event_start,
        readiness_event_end,
        close_payload_state,
        peer_close_status_code,
        descriptive_error_type,
        descriptive_error_hash,
    )


def observe_data_frame(
    raw_message: bytes,
    *,
    sample_rate_hz: float,
    arrival: datetime,
) -> SemanticFrameReceipt:
    """Hash and classify one transient text/binary data message.

    The hash is computed before tag, header, decode, or readiness analysis.
    No returned field contains ``raw_message``, its body, or decoded samples.
    """

    artifact_hash = sha256(raw_message).hexdigest()
    frame_byte_count = len(raw_message)
    if len(raw_message) < 3:
        error_type = "ShortFrameTag"
        return _base_receipt(
            artifact_hash=artifact_hash,
            frame_class=FrameClass.MALFORMED,
            frame_byte_count=frame_byte_count,
            disposition=FrameDisposition.QUALIFICATION_ERROR,
            descriptive_error_type=error_type,
            descriptive_error_hash=_error_hash(
                artifact_hash, stage="frame_tag", error_type=error_type
            ),
        )

    tag, body = raw_message[:3], raw_message[3:]
    if tag == b"MSG":
        return _base_receipt(
            artifact_hash=artifact_hash,
            frame_class=FrameClass.MSG,
            frame_byte_count=frame_byte_count,
            disposition=FrameDisposition.DESCRIPTIVE_CONTROL,
        )
    if tag != b"SND":
        return _base_receipt(
            artifact_hash=artifact_hash,
            frame_class=FrameClass.OTHER,
            frame_byte_count=frame_byte_count,
            disposition=FrameDisposition.DESCRIPTIVE_CONTROL,
        )

    if len(body) < 17:
        error_type = "ShortSNDHeader"
        return _base_receipt(
            artifact_hash=artifact_hash,
            frame_class=FrameClass.SND,
            frame_byte_count=frame_byte_count,
            disposition=FrameDisposition.QUALIFICATION_ERROR,
            snd_header_clause=ClauseEvaluation.QUALIFICATION_ERROR,
            descriptive_error_type=error_type,
            descriptive_error_hash=_error_hash(
                artifact_hash, stage="snd_header", error_type=error_type
            ),
        )

    flags, sequence = struct.unpack("<BI", body[:5])
    gps_solution_age_s, _dummy, gps_seconds, _gps_nanoseconds = struct.unpack(
        "<BBII", body[7:17]
    )
    iq_mode = (
        ClauseEvaluation.SATISFIED
        if flags & 0x08
        else ClauseEvaluation.UNSATISFIED
    )
    gps_seconds_present = (
        ClauseEvaluation.SATISFIED
        if gps_seconds > 0
        else ClauseEvaluation.UNSATISFIED
    )
    gps_age_within_limit = (
        ClauseEvaluation.SATISFIED
        if gps_solution_age_s <= FROZEN_MAX_GPS_SOLUTION_AGE_S
        else ClauseEvaluation.UNSATISFIED
    )

    if iq_mode is ClauseEvaluation.UNSATISFIED:
        return _base_receipt(
            artifact_hash=artifact_hash,
            frame_class=FrameClass.SND,
            frame_byte_count=frame_byte_count,
            disposition=FrameDisposition.SND_NOT_ADMITTED,
            snd_header_clause=ClauseEvaluation.SATISFIED,
            iq_mode_clause=iq_mode,
            gps_seconds_present_clause=gps_seconds_present,
            gps_age_within_limit_clause=gps_age_within_limit,
            readiness_clause=ClauseEvaluation.UNSATISFIED,
            sequence=int(sequence),
            gps_solution_age_s=int(gps_solution_age_s),
        )

    try:
        arrival_utc = _utc(arrival)
        if not math.isfinite(sample_rate_hz) or sample_rate_hz <= 0.0:
            raise ValueError("sample rate must be positive and finite")
        block = kiwi._decode_iq_block(body, float(sample_rate_hz), arrival_utc)
    except Exception as error:
        error_type = type(error).__name__
        return _base_receipt(
            artifact_hash=artifact_hash,
            frame_class=FrameClass.SND,
            frame_byte_count=frame_byte_count,
            disposition=FrameDisposition.QUALIFICATION_ERROR,
            snd_header_clause=ClauseEvaluation.SATISFIED,
            iq_mode_clause=iq_mode,
            sample_decode_clause=ClauseEvaluation.QUALIFICATION_ERROR,
            gps_seconds_present_clause=gps_seconds_present,
            gps_age_within_limit_clause=gps_age_within_limit,
            readiness_clause=ClauseEvaluation.NOT_EVALUATED,
            sequence=int(sequence),
            gps_solution_age_s=int(gps_solution_age_s),
            descriptive_error_type=error_type,
            descriptive_error_hash=_error_hash(
                artifact_hash, stage="snd_sample_decode", error_type=error_type
            ),
        )

    ready = (
        gps_seconds_present is ClauseEvaluation.SATISFIED
        and gps_age_within_limit is ClauseEvaluation.SATISFIED
    )
    event_start = block.event_start if ready else None
    event_end = block.event_end if ready else None
    del block
    return _base_receipt(
        artifact_hash=artifact_hash,
        frame_class=FrameClass.SND,
        frame_byte_count=frame_byte_count,
        disposition=(
            FrameDisposition.READINESS_ADMITTED
            if ready
            else FrameDisposition.SND_NOT_ADMITTED
        ),
        snd_header_clause=ClauseEvaluation.SATISFIED,
        iq_mode_clause=iq_mode,
        sample_decode_clause=ClauseEvaluation.SATISFIED,
        gps_seconds_present_clause=gps_seconds_present,
        gps_age_within_limit_clause=gps_age_within_limit,
        readiness_clause=(
            ClauseEvaluation.SATISFIED
            if ready
            else ClauseEvaluation.UNSATISFIED
        ),
        sequence=int(sequence),
        gps_solution_age_s=int(gps_solution_age_s),
        readiness_event_start=event_start,
        readiness_event_end=event_end,
    )


def observe_close_frame(payload: bytes) -> SemanticFrameReceipt:
    """Hash a transient close payload without inventing a status code."""

    raw_artifact = b"CLOSE" + payload
    artifact_hash = sha256(raw_artifact).hexdigest()
    if not payload:
        return _base_receipt(
            artifact_hash=artifact_hash,
            frame_class=FrameClass.CLOSE,
            frame_byte_count=0,
            disposition=FrameDisposition.DESCRIPTIVE_CONTROL,
            close_payload_state=ClosePayloadState.EMPTY_NO_STATUS,
        )
    if len(payload) == 1:
        error_type = "MalformedClosePayload"
        return _base_receipt(
            artifact_hash=artifact_hash,
            frame_class=FrameClass.CLOSE,
            frame_byte_count=1,
            disposition=FrameDisposition.QUALIFICATION_ERROR,
            close_payload_state=ClosePayloadState.MALFORMED_ONE_BYTE,
            descriptive_error_type=error_type,
            descriptive_error_hash=_error_hash(
                artifact_hash, stage="close_payload", error_type=error_type
            ),
        )
    status_code = struct.unpack(">H", payload[:2])[0]
    return _base_receipt(
        artifact_hash=artifact_hash,
        frame_class=FrameClass.CLOSE,
        frame_byte_count=len(payload),
        disposition=FrameDisposition.DESCRIPTIVE_CONTROL,
        close_payload_state=ClosePayloadState.STATUS_PRESENT,
        peer_close_status_code=status_code,
    )
