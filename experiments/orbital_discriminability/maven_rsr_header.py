"""Frozen, development-only whitelist parser for MAVEN DSS-45 RSR headers.

The parser accepts exactly the 260-byte SFDU header of the predeclared DSS-45
development product. It never decodes the data CHDO and deliberately has no
representation for ADC RMS, ADC peak, attenuation, FGAIN, samples, or any
other signal-derived diagnostic.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from math import isfinite
import struct
from typing import Final, Literal


PARSER_VERSION: Final = "maven-dss45-rsr-header-whitelist-v1"
DEVELOPMENT_LIDVID: Final = (
    "urn:nasa:pds:maven.rose.raw:data.rsr:"
    "mvn_rse_l0_rsr_20160712t124201::1.0"
)
DEVELOPMENT_PRODUCT_NAME: Final = "mvn_rse_l0_rsr_20160712T124201_v01_r00.dat"
RSR_HEADER_BYTES: Final = 260
RSR_RECORD_BYTES: Final = 4260
RSR_DDC_OUTPUT_RATE_HZ: Final = 16_000_000
NOT_CALCULABLE_SENTINEL: Final = bytes.fromhex("7fffffffffffffff")


class RsrHeaderError(ValueError):
    """The allowed header metadata are malformed or structurally inconsistent."""


@dataclass(frozen=True, slots=True)
class NumericState:
    state: Literal["FINITE", "NOT_CALCULABLE"]
    value: float | None

    @classmethod
    def finite(cls, value: float) -> "NumericState":
        if not isfinite(value):
            raise RsrHeaderError("a finite SFDU value was required")
        return cls("FINITE", value)


@dataclass(frozen=True, slots=True)
class PolynomialState:
    coefficients: tuple[NumericState, ...]
    unit: str
    evaluation: str


@dataclass(frozen=True, slots=True)
class FilterDecimationState:
    input_rate_hz: int
    output_rate_hz: int
    output_bandwidth_hz: int
    decimation: int
    coefficient_state: Literal["NOT_ENCODED_IN_SFDU"]
    derivation: str


@dataclass(frozen=True, slots=True)
class RsrHeaderReceipt:
    parser_version: str
    development_lidvid: str
    record_sequence_number: int
    first_sample_utc: str
    first_sample_year: int
    first_sample_day_of_year: int
    first_sample_second_of_day: float
    signal_processing_center_id: int
    deep_space_station_id: int
    rsr_id: int
    subchannel_id: int
    sample_rate_hz: int
    sample_resolution_bits: int
    rf_to_if_lo_hz: int
    ddc_lo_hz: int
    frequency_override_active: bool
    predicts_time_shift_s: NumericState
    predicts_frequency_override_hz: NumericState
    predicts_frequency_rate_hz_s: NumericState
    predicts_frequency_offset_hz: NumericState
    subchannel_frequency_offset_hz: NumericState
    frequency_polynomial: PolynomialState
    accumulated_phase_cycles: NumericState
    phase_polynomial: PolynomialState
    filter_decimation: FilterDecimationState
    allowed_bytes_sha256: str

    def as_json_object(self) -> dict[str, object]:
        return asdict(self)


# Zero-based byte ranges, inclusive start and exclusive end. No amplitude,
# signal-strength, sample, or diagnostic field is present in this table.
_ALLOWED_RANGES: Final[tuple[tuple[str, int, int], ...]] = (
    ("record_sequence_number", 40, 42),
    ("signal_processing_center", 42, 43),
    ("deep_space_station", 43, 44),
    ("rsr", 44, 45),
    ("subchannel", 45, 46),
    ("frequency_override_state", 56, 57),
    ("sample_resolution", 68, 69),
    ("sample_rate", 70, 72),
    ("ddc_lo", 72, 74),
    ("rf_to_if_lo", 74, 76),
    ("sfdu_year", 76, 78),
    ("sfdu_day_of_year", 78, 80),
    ("sfdu_second", 80, 88),
    ("predicts_time_shift", 88, 96),
    ("predicts_frequency_override", 96, 104),
    ("predicts_frequency_rate", 104, 112),
    ("predicts_frequency_offset", 112, 120),
    ("subchannel_frequency_offset", 120, 128),
    ("frequency_polynomial_f1", 176, 184),
    ("frequency_polynomial_f2", 184, 192),
    ("frequency_polynomial_f3", 192, 200),
    ("accumulated_phase", 200, 208),
    ("phase_polynomial_p1", 208, 216),
    ("phase_polynomial_p2", 216, 224),
    ("phase_polynomial_p3", 224, 232),
    ("phase_polynomial_p4", 232, 240),
)


def parse_dss45_header(header: bytes | bytearray | memoryview) -> RsrHeaderReceipt:
    """Parse one header without decoding or returning any disallowed field."""

    view = memoryview(header)
    if view.nbytes != RSR_HEADER_BYTES:
        raise RsrHeaderError(f"expected {RSR_HEADER_BYTES} header bytes")
    _validate_sfdu_structure(view)

    year = _u16(view, 76)
    day_of_year = _u16(view, 78)
    second_of_day = _finite_double(view, 80, "first-sample second")
    first_sample_utc = _utc_tag(year, day_of_year, second_of_day)
    sample_rate_hz = _u16(view, 70) * 1_000
    sample_resolution_bits = view[68]
    filter_decimation = _filter_decimation(sample_rate_hz)
    if sample_resolution_bits not in {1, 2, 4, 8, 16}:
        raise RsrHeaderError("unsupported RSR sample resolution")

    receipt = RsrHeaderReceipt(
        parser_version=PARSER_VERSION,
        development_lidvid=DEVELOPMENT_LIDVID,
        record_sequence_number=_u16(view, 40),
        first_sample_utc=first_sample_utc,
        first_sample_year=year,
        first_sample_day_of_year=day_of_year,
        first_sample_second_of_day=second_of_day,
        signal_processing_center_id=view[42],
        deep_space_station_id=view[43],
        rsr_id=view[44],
        subchannel_id=view[45],
        sample_rate_hz=sample_rate_hz,
        sample_resolution_bits=sample_resolution_bits,
        rf_to_if_lo_hz=_u16(view, 74) * 1_000_000,
        ddc_lo_hz=_u16(view, 72) * 1_000_000,
        frequency_override_active=view[56] != 0,
        predicts_time_shift_s=_number(view, 88),
        predicts_frequency_override_hz=_number(view, 96),
        predicts_frequency_rate_hz_s=_number(view, 104),
        predicts_frequency_offset_hz=_number(view, 112),
        subchannel_frequency_offset_hz=_number(view, 120),
        frequency_polynomial=PolynomialState(
            coefficients=tuple(_number(view, offset) for offset in (176, 184, 192)),
            unit="hertz",
            evaluation="F1 + F2*u + F3*u^2; u=(millisecond+0.5)/1000",
        ),
        accumulated_phase_cycles=_number(view, 200),
        phase_polynomial=PolynomialState(
            coefficients=tuple(
                _number(view, offset) for offset in (208, 216, 224, 232)
            ),
            unit="cycle",
            evaluation="P1 + P2*u + P3*u^2 + P4*u^3; u=(millisecond+0.5)/1000",
        ),
        filter_decimation=filter_decimation,
        allowed_bytes_sha256=_allowed_bytes_hash(view),
    )
    if (receipt.signal_processing_center_id, receipt.deep_space_station_id) != (40, 45):
        raise RsrHeaderError("header is not from the frozen DSS-45 development station")
    if receipt.sample_rate_hz != 1_000 or receipt.sample_resolution_bits != 16:
        raise RsrHeaderError("header differs from the frozen 1 ksps/16-bit product")
    if receipt.rsr_id != 2 or receipt.subchannel_id != 1:
        raise RsrHeaderError("header differs from frozen RSR1B/subchannel-1 identity")
    strict_json(receipt.as_json_object())
    return receipt


def parser_manifest() -> dict[str, object]:
    """Return the immutable parser contract without product measurements."""

    return {
        "parser_version": PARSER_VERSION,
        "scope": "DSS45_DEVELOPMENT_HEADER_ONLY",
        "development_lidvid": DEVELOPMENT_LIDVID,
        "development_product_name": DEVELOPMENT_PRODUCT_NAME,
        "header_bytes": RSR_HEADER_BYTES,
        "record_bytes": RSR_RECORD_BYTES,
        "allowed_ranges_zero_based_end_exclusive": [
            {"name": name, "start": start, "end": end}
            for name, start, end in _ALLOWED_RANGES
        ],
        "validation_only_ranges_zero_based_end_exclusive": [
            {"name": "sfdu_framing", "start": 0, "end": 40},
            {"name": "data_chdo_framing", "start": 256, "end": 260},
        ],
        "forbidden_semantics": [
            "FGAIN",
            "DIG attenuation",
            "DIG ADC RMS",
            "DIG ADC peak",
            "data error count",
            "sample values",
            "signal strength",
            "signal-derived diagnostics",
        ],
        "non_finite_policy": (
            "7fffffffffffffff becomes NOT_CALCULABLE with null value; "
            "all other non-finite encodings are rejected"
        ),
        "raw_header_retention": "PROHIBITED",
        "sample_chdo_access": "PROHIBITED",
        "sources": [
            "DSN 820-013 0159-Science RSR SIS",
            "PDS MAVEN ROSE development product label v01_r00",
        ],
    }


def parser_manifest_sha256() -> str:
    return sha256(strict_json(parser_manifest()).encode("utf-8")).hexdigest()


def strict_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _validate_sfdu_structure(view: memoryview) -> None:
    if bytes(view[0:4]) != b"NJPL" or bytes(view[8:12]) != b"C997":
        raise RsrHeaderError("unexpected SFDU authority or data-description ID")
    if bytes(view[4:6]) != b"2I":
        raise RsrHeaderError("unexpected SFDU version/class")
    if _u32(view, 12) != 0 or _u32(view, 16) != RSR_RECORD_BYTES - 20:
        raise RsrHeaderError("unexpected SFDU record length")
    if _u16(view, 20) != 1 or _u16(view, 22) != 232:
        raise RsrHeaderError("unexpected header aggregation CHDO")
    if _u16(view, 24) != 2 or _u16(view, 26) != 4:
        raise RsrHeaderError("unexpected primary header CHDO")
    if _u16(view, 32) != 104 or _u16(view, 34) != 220:
        raise RsrHeaderError("unexpected secondary header CHDO")
    if _u16(view, 256) != 10 or _u16(view, 258) != RSR_RECORD_BYTES - 260:
        raise RsrHeaderError("unexpected data CHDO framing")


def _allowed_bytes_hash(view: memoryview) -> str:
    digest = sha256()
    for name, start, end in _ALLOWED_RANGES:
        encoded = name.encode("ascii")
        digest.update(len(encoded).to_bytes(1, "big"))
        digest.update(encoded)
        digest.update(bytes(view[start:end]))
    return digest.hexdigest()


def _u16(view: memoryview, offset: int) -> int:
    return struct.unpack_from(">H", view, offset)[0]


def _u32(view: memoryview, offset: int) -> int:
    return struct.unpack_from(">I", view, offset)[0]


def _number(view: memoryview, offset: int) -> NumericState:
    encoded = bytes(view[offset : offset + 8])
    if encoded == NOT_CALCULABLE_SENTINEL:
        return NumericState("NOT_CALCULABLE", None)
    value = struct.unpack(">d", encoded)[0]
    if not isfinite(value):
        raise RsrHeaderError("non-standard non-finite SFDU number")
    return NumericState.finite(value)


def _finite_double(view: memoryview, offset: int, name: str) -> float:
    value = _number(view, offset)
    if value.state != "FINITE" or value.value is None:
        raise RsrHeaderError(f"{name} is not calculable")
    return value.value


def _filter_decimation(sample_rate_hz: int) -> FilterDecimationState:
    if sample_rate_hz <= 0 or RSR_DDC_OUTPUT_RATE_HZ % sample_rate_hz:
        raise RsrHeaderError("sample rate is not an exact supported RSR decimation")
    return FilterDecimationState(
        input_rate_hz=RSR_DDC_OUTPUT_RATE_HZ,
        output_rate_hz=sample_rate_hz,
        output_bandwidth_hz=sample_rate_hz,
        decimation=RSR_DDC_OUTPUT_RATE_HZ // sample_rate_hz,
        coefficient_state="NOT_ENCODED_IN_SFDU",
        derivation=(
            "DSN 0159-Science section 2.3 and table 3-1: the VDP FIR input is "
            "16 Msps and configured output bandwidth/sample rate is the header mode"
        ),
    )


def _utc_tag(year: int, day_of_year: int, second_of_day: float) -> str:
    if not 1900 <= year <= 3000 or not 1 <= day_of_year <= 366:
        raise RsrHeaderError("first-sample date is outside the RSR domain")
    if not 0.0 <= second_of_day <= 86400.0:
        raise RsrHeaderError("first-sample second is outside the RSR domain")
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    instant = start + timedelta(days=day_of_year - 1, seconds=second_of_day)
    return instant.isoformat(timespec="microseconds").replace("+00:00", "Z")
