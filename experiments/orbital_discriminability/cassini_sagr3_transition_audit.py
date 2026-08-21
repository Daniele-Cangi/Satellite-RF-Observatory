"""Ramp-only metadata audit for the Cassini SAGR3 coordinate transition.

The authorized slice contains only the four ODF ramp groups.  The ODF
observable group, RSR payloads, IQ, amplitude and detector inputs are outside
this module's scope.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from math import isfinite
from typing import Final, Sequence


AUDIT_VERSION: Final = "cassini-sagr3-coordinate-transition-audit-v1"
ODF_LIDVID: Final = (
    "urn:nasa:pds:cassini.rss.raw.sagr:data.odf:"
    "s23sags2006_251_1151x14v1::1.0"
)
ODF_LABEL_URL: Final = (
    "https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-sagr/"
    "data-odf/2006/s23sags2006_251_1151x14v1.xml"
)
ODF_DATA_URL: Final = (
    "https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-sagr/"
    "data-odf/2006/s23sags2006_251_1151x14v1.dat"
)
ODF_LABEL_BYTES: Final = 136_144
ODF_LABEL_SHA256: Final = (
    "4341e8c5a9f9fc5d261d261af8d287bcd62ec2170b4b9cf9c76afce159f7579a"
)
ODF_DATA_BYTES: Final = 7_257_600
ODF_PUBLISHED_MD5: Final = "9f15d6824b2a90241521eec5982438bf"
ODF_RECORD_BYTES: Final = 36
RAMP_RANGE_FIRST_RECORD_ONE_BASED: Final = 201_366
RAMP_RANGE_LAST_RECORD_ONE_BASED: Final = 201_425
RAMP_RANGE_START_BYTE: Final = 7_249_140
RAMP_RANGE_END_BYTE_INCLUSIVE: Final = 7_251_299
RAMP_RANGE_BYTES: Final = 2_160
RAMP_RANGE_SHA256: Final = (
    "136774e5b55002c2f5c78b614048b9177d14b3fb1215e4c59e39909745de485a"
)
COORDINATE_TRANSITION_UTC: Final = "2006-09-08T14:57:32.000000Z"


class CassiniSagr3TransitionAuditError(ValueError):
    """The frozen ODF ramp slice is malformed or outside scope."""


@dataclass(frozen=True, slots=True)
class RampGroupSpec:
    station_id: int
    header_record_one_based: int
    rows: int


RAMP_GROUPS: Final = (
    RampGroupSpec(14, 201_366, 37),
    RampGroupSpec(25, 201_404, 17),
    RampGroupSpec(43, 201_422, 1),
    RampGroupSpec(65, 201_424, 1),
)


@dataclass(frozen=True, slots=True)
class RampEntry:
    station_id: int
    start_utc: str
    end_utc: str
    rate_hz_s: float
    start_frequency_hz: float

    def contains_utc(self, value: str) -> bool:
        instant = _parse_utc(value)
        return _parse_utc(self.start_utc) <= instant < _parse_utc(self.end_utc)


def parse_frozen_ramp_range(
    data: bytes | bytearray | memoryview,
) -> tuple[RampEntry, ...]:
    """Parse the exact 2,160-byte ramp range after verifying its SHA-256."""

    view = memoryview(data)
    if view.nbytes != RAMP_RANGE_BYTES:
        raise CassiniSagr3TransitionAuditError(
            f"expected exactly {RAMP_RANGE_BYTES} ramp bytes"
        )
    if sha256(view).hexdigest() != RAMP_RANGE_SHA256:
        raise CassiniSagr3TransitionAuditError("ramp range SHA-256 mismatch")
    return _parse_ramp_range(view)


def _parse_ramp_range(
    data: bytes | bytearray | memoryview,
) -> tuple[RampEntry, ...]:
    """Structural parser kept separate for deterministic synthetic tests."""

    view = memoryview(data)
    if view.nbytes != RAMP_RANGE_BYTES:
        raise CassiniSagr3TransitionAuditError(
            f"expected exactly {RAMP_RANGE_BYTES} ramp bytes"
        )
    entries: list[RampEntry] = []
    for group in RAMP_GROUPS:
        header = _record_offset(group.header_record_one_based)
        if (
            _i32(view, header),
            _u32(view, header + 4),
            _u32(view, header + 8),
        ) != (2030, group.station_id, 1):
            raise CassiniSagr3TransitionAuditError("invalid ODF ramp-group header")
        if _u32(view, header + 12) != group.header_record_one_based - 1:
            raise CassiniSagr3TransitionAuditError("ramp group-start packet mismatch")
        for index in range(group.rows):
            offset = header + ODF_RECORD_BYTES * (index + 1)
            packed = _u32(view, offset + 16)
            station_id = packed & 0x3FF
            if station_id != group.station_id:
                raise CassiniSagr3TransitionAuditError("ramp-row station mismatch")
            rate = _i32(view, offset + 8) + _i32(view, offset + 12) * 1e-9
            frequency = (
                (packed >> 10) * 1e9
                + _u32(view, offset + 20)
                + _u32(view, offset + 24) * 1e-9
            )
            start = _odf_utc(_u32(view, offset), _u32(view, offset + 4))
            end = _odf_utc(_u32(view, offset + 28), _u32(view, offset + 32))
            if (
                not isfinite(rate)
                or not isfinite(frequency)
                or _parse_utc(end) <= _parse_utc(start)
            ):
                raise CassiniSagr3TransitionAuditError("invalid ramp-row value")
            entries.append(RampEntry(station_id, start, end, rate, frequency))
    if len(entries) != sum(group.rows for group in RAMP_GROUPS):
        raise CassiniSagr3TransitionAuditError("ramp-row count mismatch")
    strict_json([asdict(entry) for entry in entries])
    return tuple(entries)


def ramp_at(
    entries: Sequence[RampEntry], station_id: int, utc: str
) -> RampEntry | None:
    matches = [
        entry
        for entry in entries
        if entry.station_id == station_id and entry.contains_utc(utc)
    ]
    if len(matches) > 1:
        raise CassiniSagr3TransitionAuditError("overlapping ramp intervals")
    return matches[0] if matches else None


def parser_manifest() -> dict[str, object]:
    return {
        "audit_version": AUDIT_VERSION,
        "scope": "FOUR_ODF_RAMP_GROUPS_ONLY",
        "odf_lidvid": ODF_LIDVID,
        "odf_label": {
            "url": ODF_LABEL_URL,
            "bytes": ODF_LABEL_BYTES,
            "sha256": ODF_LABEL_SHA256,
        },
        "odf_data": {
            "url": ODF_DATA_URL,
            "bytes": ODF_DATA_BYTES,
            "published_md5": ODF_PUBLISHED_MD5,
        },
        "authorized_byte_range": {
            "start": RAMP_RANGE_START_BYTE,
            "end_inclusive": RAMP_RANGE_END_BYTE_INCLUSIVE,
            "bytes": RAMP_RANGE_BYTES,
            "sha256": RAMP_RANGE_SHA256,
            "first_record_one_based": RAMP_RANGE_FIRST_RECORD_ONE_BASED,
            "last_record_one_based": RAMP_RANGE_LAST_RECORD_ONE_BASED,
        },
        "groups": [asdict(group) for group in RAMP_GROUPS],
        "forbidden": [
            "ODF orbit-observable group",
            "TNF tracking observables",
            "RSR Data CHDO",
            "IQ or amplitude",
            "detector input",
            "post-outcome link-mode inference",
        ],
    }


def parser_manifest_sha256() -> str:
    return sha256(strict_json(parser_manifest()).encode("ascii")).hexdigest()


def strict_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _record_offset(record_one_based: int) -> int:
    offset = (
        record_one_based - RAMP_RANGE_FIRST_RECORD_ONE_BASED
    ) * ODF_RECORD_BYTES
    if offset < 0 or offset + ODF_RECORD_BYTES > RAMP_RANGE_BYTES:
        raise CassiniSagr3TransitionAuditError(
            "record lies outside ramp-only range"
        )
    return offset


def _u32(view: memoryview, offset: int) -> int:
    return int.from_bytes(view[offset : offset + 4], "big", signed=False)


def _i32(view: memoryview, offset: int) -> int:
    return int.from_bytes(view[offset : offset + 4], "big", signed=True)


def _odf_utc(seconds_since_1950: int, nanoseconds: int) -> str:
    if not 0 <= nanoseconds < 1_000_000_000:
        raise CassiniSagr3TransitionAuditError("invalid ODF nanosecond field")
    instant = datetime(1950, 1, 1, tzinfo=timezone.utc) + timedelta(
        seconds=seconds_since_1950, microseconds=nanoseconds / 1000
    )
    return instant.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _parse_utc(value: str) -> datetime:
    if not value.endswith("Z"):
        raise CassiniSagr3TransitionAuditError("UTC value must end in Z")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise CassiniSagr3TransitionAuditError("invalid UTC value") from error
