"""Amplitude-blind SFDU whitelist for exactly two Cassini DSS-14 candidates.

The former primary/reserve payload roles are retired.  This parser admits only
the two bounded header-evaluation identities and exactly one 260-byte SFDU
header at a time.  It never accepts or represents a data CHDO.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from math import floor, isfinite
from typing import Final, Literal

from experiments.orbital_discriminability.cassini_dss26_rsr_header import (
    FilterDecimationState,
    NumericState,
    PolynomialState,
    RSR_HEADER_BYTES,
    RSR_RECORD_BYTES,
    _allowed_bytes_hash,
    _filter_decimation,
    _number,
    _required_number,
    _u16,
    _utc_tag,
    _validate_sfdu_structure,
)


PARSER_VERSION: Final = "cassini-sagr-dss14-two-candidate-header-whitelist-v2"
PLAN_SHA256: Final = "4dd7e60f25a7cb00f955346a7c49c42d11ef0990cb5c4eab9b687d9ac827d818"
EXPECTED_STATION_ID: Final = 14
EXPECTED_CHANNEL_ID: Final = "A"
EXPECTED_SUBCHANNEL_ID: Final = 1
EXPECTED_SAMPLE_RATE_HZ: Final = 1_000


class CassiniDss14HeaderError(ValueError):
    """A whitelisted DSS-14 control header is malformed or out of scope."""


HeaderCandidateRole = Literal["HEADER_CANDIDATE_A", "HEADER_CANDIDATE_B"]


@dataclass(frozen=True, slots=True)
class HeaderCandidateSpec:
    role: HeaderCandidateRole
    lidvid: str
    product_name: str
    source_product_id: str
    label_sha256: str
    file_bytes: int
    published_md5: str
    record_count: int
    expected_rsr_id: int
    first_sample_utc: str
    last_first_sample_utc: str
    predict_spk: str


CANDIDATES: Final = {
    "HEADER_CANDIDATE_A": HeaderCandidateSpec(
        role="HEADER_CANDIDATE_A",
        lidvid=(
            "urn:nasa:pds:cassini.rss.raw.sagr:data.rsr01:"
            "s23sags2006_251_1200nnnx14rd::1.0"
        ),
        product_name="s23sags2006_251_1200nnnx14rd.dat",
        source_product_id="CO-S-RSS-1-SAGR3-V1.0:S23SAGS2006251_1200NNNX14RD.3A1",
        label_sha256="185d43fe474484d1ef29957c603a63feaab9ac5426043d588fe33716e871ca58",
        file_bytes=46_008_000,
        published_md5="378f601ddbc057ebdc822cdb5fac4197",
        record_count=10_800,
        expected_rsr_id=5,
        first_sample_utc="2006-09-08T12:00:01.000000Z",
        last_first_sample_utc="2006-09-08T15:00:00.000000Z",
        predict_spk="060901AP_SCPSE_06244_06255.bsp",
    ),
    "HEADER_CANDIDATE_B": HeaderCandidateSpec(
        role="HEADER_CANDIDATE_B",
        lidvid=(
            "urn:nasa:pds:cassini.rss.raw.sagr:data.rsr01:"
            "s10sags2005_122_1955nnnx14rd::1.0"
        ),
        product_name="s10sags2005_122_1955nnnx14rd.dat",
        source_product_id="CO-S-RSS-1-SAGR1-V1.0:S10SAGS2005122_1955NNNX14RD.2A1",
        label_sha256="b17cf1f4470630894988b9694284fcda7bad115d59018a29a40fe496ede3c6c9",
        file_bytes=18_658_800,
        published_md5="9b8b89c1e3a15ad742c828b51224b85f",
        record_count=4_380,
        expected_rsr_id=3,
        first_sample_utc="2005-05-02T19:55:01.000000Z",
        last_first_sample_utc="2005-05-02T21:08:00.000000Z",
        predict_spk="050426AP_SCPSE_05116_05216.bsp",
    ),
}


@dataclass(frozen=True, slots=True)
class CassiniDss14HeaderReceipt:
    parser_version: str
    candidate_role: HeaderCandidateRole
    lidvid: str
    source_product_id: str
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
        if not isfinite(sample_offset_s) or not 0.0 <= sample_offset_s < 1.0:
            raise CassiniDss14HeaderError("sample offset is outside the one-second SFDU")
        coefficients = tuple(
            _required_number(value, f"frequency polynomial F{index}")
            for index, value in enumerate(self.frequency_polynomial.coefficients, start=1)
        )
        millisecond = min(999, floor(sample_offset_s * 1_000.0))
        u = (millisecond + 0.5) / 1_000.0
        return coefficients[0] + coefficients[1] * u + coefficients[2] * u * u

    def recorded_baseband_frequency_hz(
        self, received_sky_frequency_hz: float, sample_offset_s: float
    ) -> float:
        if not isfinite(received_sky_frequency_hz):
            raise CassiniDss14HeaderError("received sky frequency must be finite")
        return (
            received_sky_frequency_hz
            - self.rf_to_if_lo_hz
            - self.ddc_lo_hz
            + self.nco_frequency_hz(sample_offset_s)
        )


def parse_candidate_header(
    header: bytes | bytearray | memoryview,
    role: HeaderCandidateRole,
) -> CassiniDss14HeaderReceipt:
    """Parse exactly one header under one of the two frozen candidate roles."""

    try:
        spec = CANDIDATES[role]
    except KeyError as error:
        raise CassiniDss14HeaderError("header role is outside the frozen candidate set") from error
    view = memoryview(header)
    if view.nbytes != RSR_HEADER_BYTES:
        raise CassiniDss14HeaderError(f"expected {RSR_HEADER_BYTES} header bytes")
    try:
        _validate_sfdu_structure(view)
        year = _u16(view, 76)
        day_of_year = _u16(view, 78)
        second_of_day = _required_number(_number(view, 80), "first-sample second")
        first_sample_utc = _utc_tag(year, day_of_year, second_of_day)
        sample_rate_hz = _u16(view, 70) * 1_000
        sample_resolution_bits = view[68]
        if sample_resolution_bits not in {1, 2, 4, 8, 16}:
            raise CassiniDss14HeaderError("unsupported RSR sample resolution")
        receipt = CassiniDss14HeaderReceipt(
            parser_version=PARSER_VERSION,
            candidate_role=role,
            lidvid=spec.lidvid,
            source_product_id=spec.source_product_id,
            record_sequence_number=_u16(view, 40),
            first_sample_utc=first_sample_utc,
            first_sample_year=year,
            first_sample_day_of_year=day_of_year,
            first_sample_second_of_day=second_of_day,
            signal_processing_center_id=view[42],
            station_id="DSS-14",
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
    except ValueError as error:
        if isinstance(error, CassiniDss14HeaderError):
            raise
        raise CassiniDss14HeaderError(str(error)) from error

    if receipt.deep_space_station_id != EXPECTED_STATION_ID:
        raise CassiniDss14HeaderError("header is not from frozen DSS-14")
    if (receipt.rsr_id, receipt.channel_id, receipt.subchannel_id) != (
        spec.expected_rsr_id,
        EXPECTED_CHANNEL_ID,
        EXPECTED_SUBCHANNEL_ID,
    ):
        raise CassiniDss14HeaderError(
            "header differs from the frozen product-specific RSR/channel/subchannel"
        )
    if receipt.sample_rate_hz != EXPECTED_SAMPLE_RATE_HZ:
        raise CassiniDss14HeaderError("header differs from the frozen 1 ksps product")
    if receipt.frequency_override_active:
        _required_number(
            receipt.predicts_frequency_override_hz,
            "active predicts-frequency override",
        )
    strict_json(receipt.as_json_object())
    return receipt


def parser_manifest() -> dict[str, object]:
    return {
        "parser_version": PARSER_VERSION,
        "scope": "CASSINI_SAGR_TWO_DSS14_HEADER_CANDIDATES_ONLY",
        "plan_sha256": PLAN_SHA256,
        "candidate_specs": [asdict(CANDIDATES[role]) for role in sorted(CANDIDATES)],
        "identity": {
            "station": "DSS-14",
            "channel": EXPECTED_CHANNEL_ID,
            "subchannel": EXPECTED_SUBCHANNEL_ID,
            "rsr_by_role": {
                role: CANDIDATES[role].expected_rsr_id for role in sorted(CANDIDATES)
            },
            "source": (
                "first authorized amplitude-blind SFDU identity fields, cross-checked "
                "against the frozen PDS product identity; suffix is not treated as RSR ID"
            ),
        },
        "header_bytes": RSR_HEADER_BYTES,
        "record_bytes": RSR_RECORD_BYTES,
        "raw_header_retention": "PROHIBITED",
        "data_chdo_access": "PROHIBITED",
        "signal_or_sample_diagnostics": "NOT_REPRESENTABLE",
        "utc_policy": (
            "inherit explicit ordinary-UTC boundary policy; leap-second tags are rejected"
        ),
        "non_finite_policy": (
            "RSR not-calculable sentinel becomes explicit null; other non-finite values rejected"
        ),
    }


def parser_manifest_sha256() -> str:
    return sha256(strict_json(parser_manifest()).encode("ascii")).hexdigest()


def strict_json(value: object) -> str:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    )
