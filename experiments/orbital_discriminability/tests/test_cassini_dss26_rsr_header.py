"""Specification-derived synthetic tests for the DSS-26 Cassini SFDU parser."""

from dataclasses import FrozenInstanceError, fields
import json
import math
import struct

import pytest

from experiments.orbital_discriminability.cassini_dss26_rsr_header import (
    CassiniDss26HeaderReceipt,
    CassiniRsrHeaderError,
    NOT_CALCULABLE_SENTINEL,
    RSR_HEADER_BYTES,
    RSR_RECORD_BYTES,
    parse_dss26_header,
    parser_manifest,
    parser_manifest_sha256,
    strict_json,
)


def _synthetic_header() -> bytearray:
    value = bytearray(RSR_HEADER_BYTES)
    value[0:4] = b"NJPL"
    value[4:6] = b"2I"
    value[8:12] = b"C997"
    struct.pack_into(">I", value, 12, 0)
    struct.pack_into(">I", value, 16, RSR_RECORD_BYTES - 20)
    struct.pack_into(">H", value, 20, 1)
    struct.pack_into(">H", value, 22, 232)
    struct.pack_into(">H", value, 24, 2)
    struct.pack_into(">H", value, 26, 4)
    struct.pack_into(">H", value, 32, 104)
    struct.pack_into(">H", value, 34, 220)
    struct.pack_into(">H", value, 40, 17)
    value[42:46] = bytes((40, 26, 1, 1))
    value[56] = 0
    value[68] = 8
    struct.pack_into(">H", value, 70, 1)
    struct.pack_into(">H", value, 72, 320)
    struct.pack_into(">H", value, 74, 8_100)
    struct.pack_into(">H", value, 76, 2005)
    struct.pack_into(">H", value, 78, 157)
    struct.pack_into(">d", value, 80, 64_201.0)
    for offset, number in {
        88: 0.0,
        96: 0.0,
        104: 1.5,
        112: -2.0,
        120: 125.0,
        176: 12_000.0,
        184: -40.0,
        192: 2.0,
        200: 100.0,
        208: 0.0,
        216: 12.0,
        224: -20.0,
        232: 0.5,
    }.items():
        struct.pack_into(">d", value, offset, number)
    struct.pack_into(">H", value, 256, 10)
    struct.pack_into(">H", value, 258, RSR_RECORD_BYTES - 260)
    return value


def test_parser_exposes_only_dss26_1a1_control_metadata() -> None:
    receipt = parse_dss26_header(_synthetic_header())
    assert receipt.first_sample_utc == "2005-06-06T17:50:01.000000Z"
    assert (receipt.station_id, receipt.rsr_id, receipt.channel_id, receipt.subchannel_id) == (
        "DSS-26",
        1,
        "A",
        1,
    )
    assert receipt.sample_rate_hz == 1_000
    assert receipt.sample_resolution_bits == 8
    assert receipt.filter_decimation.decimation == 16_000
    assert receipt.frequency_polynomial.coefficients[0].value == 12_000.0
    assert receipt.phase_polynomial.coefficients[-1].value == 0.5


def test_receiver_transform_reaches_recorded_baseband_coordinates() -> None:
    receipt = parse_dss26_header(_synthetic_header())
    u = 0.2505
    nco = 12_000.0 - 40.0 * u + 2.0 * u * u
    assert receipt.nco_frequency_hz(0.25) == pytest.approx(nco, abs=1e-12)
    sky = 8_420_005_000.0
    assert receipt.recorded_baseband_frequency_hz(sky, 0.25) == pytest.approx(
        sky - 8_100_000_000.0 - 320_000_000.0 + nco,
        abs=1e-9,
    )


def test_unlisted_header_bytes_cannot_affect_receipt_or_hash() -> None:
    left = _synthetic_header()
    right = _synthetic_header()
    for offset in (*range(46, 54), 54, 55, *range(57, 68), 69, *range(128, 176), *range(240, 256)):
        right[offset] = (right[offset] + offset + 1) % 256
    assert parse_dss26_header(left) == parse_dss26_header(right)


def test_receipt_model_has_no_signal_or_sample_diagnostic_representation() -> None:
    receipt = parse_dss26_header(_synthetic_header())
    field_names = " ".join(field.name for field in fields(CassiniDss26HeaderReceipt)).lower()
    rendered = strict_json(receipt.as_json_object()).lower()
    for token in (
        "adc_rms",
        "adc_peak",
        "signal_strength",
        "fgain",
        "sample_values",
        "signal_diagnostic",
    ):
        assert token not in field_names
        assert token not in rendered


def test_not_calculable_state_is_explicit_and_active_override_requires_value() -> None:
    header = _synthetic_header()
    header[184:192] = NOT_CALCULABLE_SENTINEL
    receipt = parse_dss26_header(header)
    assert receipt.frequency_polynomial.coefficients[1].state == "NOT_CALCULABLE"
    assert receipt.frequency_polynomial.coefficients[1].value is None
    with pytest.raises(CassiniRsrHeaderError, match="not calculable"):
        receipt.nco_frequency_hz(0.5)

    header = _synthetic_header()
    header[56] = 1
    header[96:104] = NOT_CALCULABLE_SENTINEL
    with pytest.raises(CassiniRsrHeaderError, match="active predicts-frequency override"):
        parse_dss26_header(header)


@pytest.mark.parametrize("number", [math.nan, math.inf, -math.inf])
def test_nonstandard_non_finite_numbers_are_refused(number: float) -> None:
    header = _synthetic_header()
    struct.pack_into(">d", header, 176, number)
    with pytest.raises(CassiniRsrHeaderError, match="non-standard non-finite"):
        parse_dss26_header(header)


def test_product_binding_and_zero_data_chdo_access() -> None:
    wrong_station = _synthetic_header()
    wrong_station[43] = 14
    with pytest.raises(CassiniRsrHeaderError, match="DSS-26"):
        parse_dss26_header(wrong_station)

    wrong_subchannel = _synthetic_header()
    wrong_subchannel[45] = 2
    with pytest.raises(CassiniRsrHeaderError, match="1A1"):
        parse_dss26_header(wrong_subchannel)

    with pytest.raises(CassiniRsrHeaderError, match="260"):
        parse_dss26_header(bytes(RSR_RECORD_BYTES))


def test_manifest_is_product_bound_strict_and_synthetic_only() -> None:
    manifest = parser_manifest()
    assert manifest["scope"] == "CASSINI_SAGR_DSS26_DEVELOPMENT_HEADER_ONLY"
    assert manifest["identity"] == {
        "station": "DSS-26",
        "rsr": 1,
        "channel": "A",
        "subchannel": 1,
        "channel_source": "frozen PDS source-product suffix 1A1",
    }
    assert manifest["data_chdo_access"] == "PROHIBITED"
    assert manifest["fixture_policy"] == "SPECIFICATION_DERIVED_SYNTHETIC_ONLY_BEFORE_AUTHORITY"
    assert manifest["utc_policy"] == {
        "calendar": "PROLEPTIC_GREGORIAN",
        "scale": "UTC",
        "ordinary_second_of_day_interval": "0 <= second < 86400",
        "day_rollover": (
            "requires the next encoded year/day-of-year; second 86400 is never "
            "silently normalized"
        ),
        "positive_leap_second": (
            "REJECTED_UNTIL_THE_PRODUCT_SPECIFIC_SFDU_ENCODING_IS_EXPLICITLY IMPLEMENTED"
        ),
        "negative_leap_second": "REJECTED_UNTIL_EXPLICITLY IMPLEMENTED",
    }
    assert len(parser_manifest_sha256()) == 64
    json.loads(strict_json(manifest))


def test_receipt_is_immutable() -> None:
    receipt = parse_dss26_header(_synthetic_header())
    with pytest.raises(FrozenInstanceError):
        receipt.sample_rate_hz = 2_000  # type: ignore[misc]


def test_utc_boundary_and_leap_second_are_never_silently_normalized() -> None:
    leap_boundary = _synthetic_header()
    struct.pack_into(">d", leap_boundary, 80, 86_400.0)
    with pytest.raises(CassiniRsrHeaderError, match="leap-second|normalization"):
        parse_dss26_header(leap_boundary)

    invalid_doy = _synthetic_header()
    struct.pack_into(">H", invalid_doy, 76, 2005)
    struct.pack_into(">H", invalid_doy, 78, 366)
    with pytest.raises(CassiniRsrHeaderError, match="day-of-year"):
        parse_dss26_header(invalid_doy)

    last_ordinary_instant = _synthetic_header()
    struct.pack_into(">d", last_ordinary_instant, 80, 86_399.999999)
    assert parse_dss26_header(last_ordinary_instant).first_sample_utc.endswith(
        "23:59:59.999999Z"
    )
