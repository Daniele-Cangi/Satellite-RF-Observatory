"""Offline tests for the frozen DSS-45 SFDU-header whitelist."""

from dataclasses import FrozenInstanceError
import json
import math
import struct

import pytest

from experiments.orbital_discriminability.maven_rsr_header import (
    NOT_CALCULABLE_SENTINEL,
    RSR_HEADER_BYTES,
    RsrHeaderError,
    parse_dss45_header,
    parser_manifest,
    parser_manifest_sha256,
    strict_json,
)


def _header() -> bytearray:
    value = bytearray(RSR_HEADER_BYTES)
    value[0:4] = b"NJPL"
    value[4:6] = b"2I"
    value[8:12] = b"C997"
    struct.pack_into(">I", value, 12, 0)
    struct.pack_into(">I", value, 16, 4240)
    struct.pack_into(">H", value, 20, 1)
    struct.pack_into(">H", value, 22, 232)
    struct.pack_into(">H", value, 24, 2)
    struct.pack_into(">H", value, 26, 4)
    struct.pack_into(">H", value, 32, 104)
    struct.pack_into(">H", value, 34, 220)
    struct.pack_into(">H", value, 40, 7)
    value[42:46] = bytes((40, 45, 2, 1))
    value[56] = 0
    value[68] = 16
    struct.pack_into(">H", value, 70, 1)
    struct.pack_into(">H", value, 72, 320)
    struct.pack_into(">H", value, 74, 8100)
    struct.pack_into(">H", value, 76, 2016)
    struct.pack_into(">H", value, 78, 194)
    struct.pack_into(">d", value, 80, 45_121.25)
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
    struct.pack_into(">H", value, 258, 4000)
    return value


def test_header_parser_extracts_only_frozen_metadata() -> None:
    receipt = parse_dss45_header(_header())
    assert receipt.first_sample_utc == "2016-07-12T12:32:01.250000Z"
    assert receipt.sample_rate_hz == 1_000
    assert receipt.filter_decimation.decimation == 16_000
    assert receipt.filter_decimation.output_bandwidth_hz == 1_000
    assert receipt.frequency_polynomial.coefficients[0].value == 12_000.0
    assert receipt.phase_polynomial.coefficients[-1].value == 0.5
    rendered = strict_json(receipt.as_json_object())
    assert "ADC" not in rendered
    assert "FGAIN" not in rendered
    assert "sample_values" not in rendered


def test_signal_diagnostics_cannot_affect_receipt_or_allowed_hash() -> None:
    left = _header()
    right = _header()
    # FGAIN, expected IF bandwidth, attenuation, ADC RMS/peak, and data error.
    for offset, value in ((54, 255), (55, 127), (57, 63), (58, 250), (59, 249)):
        right[offset] = value
    right[69] = 254
    assert parse_dss45_header(left) == parse_dss45_header(right)


def test_documented_not_calculable_sentinel_is_explicit_json_state() -> None:
    header = _header()
    header[184:192] = NOT_CALCULABLE_SENTINEL
    receipt = parse_dss45_header(header)
    state = receipt.frequency_polynomial.coefficients[1]
    assert state.state == "NOT_CALCULABLE"
    assert state.value is None
    assert '"state":"NOT_CALCULABLE"' in strict_json(receipt.as_json_object())


@pytest.mark.parametrize("number", [math.nan, math.inf, -math.inf])
def test_nonstandard_non_finite_values_are_refused(number: float) -> None:
    header = _header()
    struct.pack_into(">d", header, 176, number)
    with pytest.raises(RsrHeaderError, match="non-standard non-finite"):
        parse_dss45_header(header)


def test_parser_is_role_bound_and_never_accepts_another_station() -> None:
    header = _header()
    header[43] = 35
    with pytest.raises(RsrHeaderError, match="DSS-45 development"):
        parse_dss45_header(header)


def test_manifest_is_canonical_and_forbids_samples_and_diagnostics() -> None:
    manifest = parser_manifest()
    assert manifest["scope"] == "DSS45_DEVELOPMENT_HEADER_ONLY"
    forbidden = set(manifest["forbidden_semantics"])
    assert {"DIG ADC RMS", "DIG ADC peak", "sample values"} <= forbidden
    assert len(parser_manifest_sha256()) == 64
    json.loads(strict_json(manifest))


def test_receipt_is_immutable_and_wrong_length_is_refused() -> None:
    receipt = parse_dss45_header(_header())
    with pytest.raises(FrozenInstanceError):
        receipt.sample_rate_hz = 2_000  # type: ignore[misc]
    with pytest.raises(RsrHeaderError, match="260"):
        parse_dss45_header(bytes(259))
