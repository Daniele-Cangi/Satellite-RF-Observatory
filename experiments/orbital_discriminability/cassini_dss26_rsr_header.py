"""Synthetic-fixture-only SFDU whitelist for Cassini SAGR DSS-26 development.

The parser is product-bound to the PDS3/PDS4 identity ending in ``2A1``.  It
accepts exactly the 260-byte RSR header and never accepts or indexes the data
CHDO.  Unlisted header bytes are structurally discarded; there is no generic
field registry and no escape hatch that can expose them later.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from math import floor, isfinite
import struct
from typing import Final, Literal


PARSER_VERSION: Final = "cassini-sagr-dss26-rsr-header-whitelist-v1"
DEVELOPMENT_LIDVID: Final = (
    "urn:nasa:pds:cassini.rss.raw.sagr:data.rsr01:"
    "s11sags2005_157_1750nnnx26rd::1.0"
)
DEVELOPMENT_PRODUCT_NAME: Final = "s11sags2005_157_1750nnnx26rd.dat"
DEVELOPMENT_SOURCE_PRODUCT_ID: Final = (
    "CO-S-RSS-1-SAGR1-V1.0:S11SAGS2005157_1750NNNX26RD.2A1"
)
RSR_HEADER_BYTES: Final = 260
RSR_RECORD_BYTES: Final = 4_260
RSR_DDC_OUTPUT_RATE_HZ: Final = 16_000_000
EXPECTED_STATION_ID: Final = 26
EXPECTED_RSR_ID: Final = 2
EXPECTED_CHANNEL_ID: Final = "A"
EXPECTED_SUBCHANNEL_ID: Final = 1
EXPECTED_SAMPLE_RATE_HZ: Final = 1_000
NOT_CALCULABLE_SENTINEL: Final = bytes.fromhex("7fffffffffffffff")


class CassiniRsrHeaderError(ValueError):
    """The whitelisted control metadata are malformed or inconsistent."""


@dataclass(frozen=True, slots=True)
class NumericState:
    state: Literal["FINITE", "NOT_CALCULABLE"]
    value: float | None

    @classmethod
    def finite(cls, value: float) -> "NumericState":
        if not isfinite(value):
            raise CassiniRsrHeaderError("a finite SFDU value was required")
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
class CassiniDss26HeaderReceipt:
    parser_version: str
    development_lidvid: str
    record_sequence_number: int
    first_sample_utc: str
    first_sample_year: int
    first_sample_day_of_year: int
    first_sample_second_of_day: float
    signal_processing_center_id: int
    station_id: str
    deep_space_station_id: int
    rsr_id: int
    channel_id: str
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

    def nco_frequency_hz(self, sample_offset_s: float) -> float:
        """Evaluate the concrete per-SFDU NCO at the documented ms midpoint."""

        if not isfinite(sample_offset_s) or not 0.0 <= sample_offset_s < 1.0:
            raise CassiniRsrHeaderError("sample offset is outside the one-second SFDU")
        coefficients = tuple(
            _required_number(value, f"frequency polynomial F{index}")
            for index, value in enumerate(self.frequency_polynomial.coefficients, start=1)
        )
        millisecond = min(999, floor(sample_offset_s * 1_000.0))
        u = (millisecond + 0.5) / 1_000.0
        return coefficients[0] + coefficients[1] * u + coefficients[2] * u * u

    def phase_cycles(self, sample_offset_s: float) -> float:
        if not isfinite(sample_offset_s) or not 0.0 <= sample_offset_s < 1.0:
            raise CassiniRsrHeaderError("sample offset is outside the one-second SFDU")
        coefficients = tuple(
            _required_number(value, f"phase polynomial P{index}")
            for index, value in enumerate(self.phase_polynomial.coefficients, start=1)
        )
        millisecond = min(999, floor(sample_offset_s * 1_000.0))
        u = (millisecond + 0.5) / 1_000.0
        return (
            coefficients[0]
            + coefficients[1] * u
            + coefficients[2] * u * u
            + coefficients[3] * u * u * u
        )

    def recorded_baseband_frequency_hz(
        self,
        received_sky_frequency_hz: float,
        sample_offset_s: float,
    ) -> float:
        """Apply the documented inverse RSR sky-to-recorded transform."""

        if not isfinite(received_sky_frequency_hz):
            raise CassiniRsrHeaderError("received sky frequency must be finite")
        return (
            received_sky_frequency_hz
            - self.rf_to_if_lo_hz
            - self.ddc_lo_hz
            + self.nco_frequency_hz(sample_offset_s)
        )


# Zero-based inclusive/exclusive ranges.  The table is intentionally complete
# for the receipt: every other header byte is discarded without interpretation.
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


def parse_dss26_header(
    header: bytes | bytearray | memoryview,
) -> CassiniDss26HeaderReceipt:
    """Parse one synthetic or future authorized header, never its data CHDO."""

    view = memoryview(header)
    if view.nbytes != RSR_HEADER_BYTES:
        raise CassiniRsrHeaderError(f"expected {RSR_HEADER_BYTES} header bytes")
    _validate_sfdu_structure(view)

    year = _u16(view, 76)
    day_of_year = _u16(view, 78)
    second_of_day = _finite_double(view, 80, "first-sample second")
    sample_rate_hz = _u16(view, 70) * 1_000
    sample_resolution_bits = view[68]
    if sample_resolution_bits not in {1, 2, 4, 8, 16}:
        raise CassiniRsrHeaderError("unsupported RSR sample resolution")

    receipt = CassiniDss26HeaderReceipt(
        parser_version=PARSER_VERSION,
        development_lidvid=DEVELOPMENT_LIDVID,
        record_sequence_number=_u16(view, 40),
        first_sample_utc=_utc_tag(year, day_of_year, second_of_day),
        first_sample_year=year,
        first_sample_day_of_year=day_of_year,
        first_sample_second_of_day=second_of_day,
        signal_processing_center_id=view[42],
        station_id=DEVELOPMENT_STATION_ID,
        deep_space_station_id=view[43],
        rsr_id=view[44],
        channel_id=EXPECTED_CHANNEL_ID,
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
            tuple(_number(view, offset) for offset in (176, 184, 192)),
            "hertz",
            "F1 + F2*u + F3*u^2; u=(millisecond+0.5)/1000",
        ),
        accumulated_phase_cycles=_number(view, 200),
        phase_polynomial=PolynomialState(
            tuple(_number(view, offset) for offset in (208, 216, 224, 232)),
            "cycle",
            "P1 + P2*u + P3*u^2 + P4*u^3; u=(millisecond+0.5)/1000",
        ),
        filter_decimation=_filter_decimation(sample_rate_hz),
        allowed_bytes_sha256=_allowed_bytes_hash(view),
    )
    if receipt.deep_space_station_id != EXPECTED_STATION_ID:
        raise CassiniRsrHeaderError("header is not from frozen DSS-26 development")
    if (receipt.rsr_id, receipt.channel_id, receipt.subchannel_id) != (
        EXPECTED_RSR_ID,
        EXPECTED_CHANNEL_ID,
        EXPECTED_SUBCHANNEL_ID,
    ):
        raise CassiniRsrHeaderError("header differs from frozen RSR/channel/subchannel 2A1")
    if receipt.sample_rate_hz != EXPECTED_SAMPLE_RATE_HZ:
        raise CassiniRsrHeaderError("header differs from frozen 1 ksps product")
    if receipt.frequency_override_active:
        _required_number(
            receipt.predicts_frequency_override_hz,
            "active predicts-frequency override",
        )
    strict_json(receipt.as_json_object())
    return receipt


DEVELOPMENT_STATION_ID: Final = f"DSS-{EXPECTED_STATION_ID}"


def parser_manifest() -> dict[str, object]:
    """Return the product-specific contract, never a registry of other fields."""

    return {
        "parser_version": PARSER_VERSION,
        "scope": "CASSINI_SAGR_DSS26_DEVELOPMENT_HEADER_ONLY",
        "development_lidvid": DEVELOPMENT_LIDVID,
        "development_product_name": DEVELOPMENT_PRODUCT_NAME,
        "development_source_product_id": DEVELOPMENT_SOURCE_PRODUCT_ID,
        "identity": {
            "station": DEVELOPMENT_STATION_ID,
            "rsr": EXPECTED_RSR_ID,
            "channel": EXPECTED_CHANNEL_ID,
            "subchannel": EXPECTED_SUBCHANNEL_ID,
            "channel_source": "frozen PDS source-product suffix 2A1",
        },
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
        "unlisted_header_semantics": "STRUCTURALLY_DISCARDED_WITHOUT_REPRESENTATION",
        "raw_header_retention": "PROHIBITED",
        "data_chdo_access": "PROHIBITED",
        "fixture_policy": "SPECIFICATION_DERIVED_SYNTHETIC_ONLY_BEFORE_AUTHORITY",
        "non_finite_policy": (
            "7fffffffffffffff becomes NOT_CALCULABLE with null value; "
            "all other non-finite encodings are rejected"
        ),
        "sources": [
            "DSN 820-013 0159-Science RSR SIS",
            "Cassini SAGR PDS4 development label v1.0",
        ],
    }


def parser_manifest_sha256() -> str:
    return sha256(strict_json(parser_manifest()).encode("utf-8")).hexdigest()


def strict_json(value: object) -> str:
    return json.dumps(value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _validate_sfdu_structure(view: memoryview) -> None:
    if bytes(view[0:4]) != b"NJPL" or bytes(view[8:12]) != b"C997":
        raise CassiniRsrHeaderError("unexpected SFDU authority or data-description ID")
    if bytes(view[4:6]) != b"2I":
        raise CassiniRsrHeaderError("unexpected SFDU version/class")
    if _u32(view, 12) != 0 or _u32(view, 16) != RSR_RECORD_BYTES - 20:
        raise CassiniRsrHeaderError("unexpected SFDU record length")
    if _u16(view, 20) != 1 or _u16(view, 22) != 232:
        raise CassiniRsrHeaderError("unexpected header aggregation CHDO")
    if _u16(view, 24) != 2 or _u16(view, 26) != 4:
        raise CassiniRsrHeaderError("unexpected primary header CHDO")
    if _u16(view, 32) != 104 or _u16(view, 34) != 220:
        raise CassiniRsrHeaderError("unexpected secondary header CHDO")
    if _u16(view, 256) != 10 or _u16(view, 258) != RSR_RECORD_BYTES - 260:
        raise CassiniRsrHeaderError("unexpected data CHDO framing")


def _allowed_bytes_hash(view: memoryview) -> str:
    digest = sha256()
    for name, start, end in _ALLOWED_RANGES:
        encoded = name.encode("ascii")
        digest.update(len(encoded).to_bytes(1, "big"))
        digest.update(encoded)
        digest.update(bytes(view[start:end]))
    return digest.hexdigest()


def _number(view: memoryview, offset: int) -> NumericState:
    encoded = bytes(view[offset : offset + 8])
    if encoded == NOT_CALCULABLE_SENTINEL:
        return NumericState("NOT_CALCULABLE", None)
    value = struct.unpack(">d", encoded)[0]
    if not isfinite(value):
        raise CassiniRsrHeaderError("non-standard non-finite SFDU number")
    return NumericState.finite(value)


def _required_number(value: NumericState, name: str) -> float:
    if value.state != "FINITE" or value.value is None:
        raise CassiniRsrHeaderError(f"required SFDU field is not calculable: {name}")
    return float(value.value)


def _finite_double(view: memoryview, offset: int, name: str) -> float:
    return _required_number(_number(view, offset), name)


def _filter_decimation(sample_rate_hz: int) -> FilterDecimationState:
    if sample_rate_hz <= 0 or RSR_DDC_OUTPUT_RATE_HZ % sample_rate_hz:
        raise CassiniRsrHeaderError("sample rate is not an exact supported RSR decimation")
    return FilterDecimationState(
        input_rate_hz=RSR_DDC_OUTPUT_RATE_HZ,
        output_rate_hz=sample_rate_hz,
        output_bandwidth_hz=sample_rate_hz,
        decimation=RSR_DDC_OUTPUT_RATE_HZ // sample_rate_hz,
        coefficient_state="NOT_ENCODED_IN_SFDU",
        derivation=(
            "DSN 0159-Science: VDP FIR input 16 Msps; configured header mode "
            "provides the output bandwidth/sample rate"
        ),
    )


def _utc_tag(year: int, day_of_year: int, second_of_day: float) -> str:
    if not 1900 <= year <= 3000 or not 1 <= day_of_year <= 366:
        raise CassiniRsrHeaderError("first-sample date is outside the RSR domain")
    if not 0.0 <= second_of_day <= 86_400.0:
        raise CassiniRsrHeaderError("first-sample second is outside the RSR domain")
    instant = datetime(year, 1, 1, tzinfo=timezone.utc) + timedelta(
        days=day_of_year - 1,
        seconds=second_of_day,
    )
    return instant.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _u16(view: memoryview, offset: int) -> int:
    return struct.unpack_from(">H", view, offset)[0]


def _u32(view: memoryview, offset: int) -> int:
    return struct.unpack_from(">I", view, offset)[0]
