"""Synthetic-only tests for the bounded DSS-14 header whitelist."""

from dataclasses import FrozenInstanceError, fields
import json
import struct

import pytest

from experiments.orbital_discriminability.cassini_dss14_header_candidates import (
    CANDIDATES,
    CassiniDss14HeaderError,
    CassiniDss14HeaderReceipt,
    parse_candidate_header,
    parser_manifest,
    parser_manifest_sha256,
    strict_json,
)
from experiments.orbital_discriminability.cassini_dss26_rsr_header import (
    RSR_HEADER_BYTES,
    RSR_RECORD_BYTES,
)


def _synthetic_header(*, station: int = 14, rsr: int = 5) -> bytearray:
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
    struct.pack_into(">H", value, 40, 7)
    value[42:46] = bytes((10, station, rsr, 1))
    value[56] = 0
    value[68] = 16
    struct.pack_into(">H", value, 70, 1)
    struct.pack_into(">H", value, 72, 327)
    struct.pack_into(">H", value, 74, 8_100)
    struct.pack_into(">H", value, 76, 2006)
    struct.pack_into(">H", value, 78, 251)
    struct.pack_into(">d", value, 80, 43_201.0)
    for offset, number in {
        88: 0.0,
        96: 0.0,
        104: 0.0,
        112: 40.0,
        120: 0.0,
        176: 11_000.0,
        184: -4.0,
        192: 0.25,
        200: 80.0,
        208: 0.0,
        216: 11.0,
        224: -2.0,
        232: 0.25,
    }.items():
        struct.pack_into(">d", value, offset, number)
    struct.pack_into(">H", value, 256, 10)
    struct.pack_into(">H", value, 258, RSR_RECORD_BYTES - 260)
    return value


def test_two_roles_are_exactly_bound_to_the_pds_label_identities() -> None:
    left = parse_candidate_header(_synthetic_header(rsr=5), "HEADER_CANDIDATE_A")
    right = parse_candidate_header(_synthetic_header(rsr=3), "HEADER_CANDIDATE_B")
    assert (left.station_id, left.rsr_id, left.source_product_id) == (
        "DSS-14",
        5,
        CANDIDATES["HEADER_CANDIDATE_A"].source_product_id,
    )
    assert right.rsr_id == 3
    assert right.lidvid == CANDIDATES["HEADER_CANDIDATE_B"].lidvid


def test_cross_product_rsr_and_wrong_station_are_refused() -> None:
    with pytest.raises(CassiniDss14HeaderError, match="product-specific"):
        parse_candidate_header(_synthetic_header(rsr=3), "HEADER_CANDIDATE_A")
    with pytest.raises(CassiniDss14HeaderError, match="DSS-14"):
        parse_candidate_header(
            _synthetic_header(station=26, rsr=5), "HEADER_CANDIDATE_A"
        )


def test_receiver_transform_is_exactly_header_driven() -> None:
    receipt = parse_candidate_header(_synthetic_header(), "HEADER_CANDIDATE_A")
    u = 0.5005
    nco = 11_000.0 - 4.0 * u + 0.25 * u * u
    assert receipt.nco_frequency_hz(0.5) == pytest.approx(nco, abs=1e-12)
    assert receipt.recorded_baseband_frequency_hz(8_427_000_000.0, 0.5) == pytest.approx(
        8_427_000_000.0 - 8_100_000_000.0 - 327_000_000.0 + nco,
        abs=1e-9,
    )


def test_complete_record_and_unknown_role_are_refused() -> None:
    with pytest.raises(CassiniDss14HeaderError, match="260"):
        parse_candidate_header(bytes(RSR_RECORD_BYTES), "HEADER_CANDIDATE_A")
    with pytest.raises(CassiniDss14HeaderError, match="candidate set"):
        parse_candidate_header(_synthetic_header(), "UNKNOWN")  # type: ignore[arg-type]


def test_signal_and_sample_diagnostics_are_not_representable() -> None:
    receipt = parse_candidate_header(_synthetic_header(), "HEADER_CANDIDATE_A")
    representation = (
        " ".join(field.name for field in fields(CassiniDss14HeaderReceipt))
        + strict_json(receipt.as_json_object())
        + strict_json(parser_manifest())
    ).lower()
    for forbidden in (
        "adc_rms",
        "adc_peak",
        "signal_strength",
        "fgain",
        "sample_values",
        "signal_diagnostic",
    ):
        assert forbidden not in representation


def test_manifest_is_strict_limited_and_immutable() -> None:
    manifest = parser_manifest()
    assert manifest["scope"] == "CASSINI_SAGR_TWO_DSS14_HEADER_CANDIDATES_ONLY"
    assert manifest["data_chdo_access"] == "PROHIBITED"
    assert manifest["raw_header_retention"] == "PROHIBITED"
    assert len(manifest["candidate_specs"]) == 2
    assert len(parser_manifest_sha256()) == 64
    json.loads(strict_json(manifest))

    receipt = parse_candidate_header(_synthetic_header(), "HEADER_CANDIDATE_A")
    with pytest.raises(FrozenInstanceError):
        receipt.sample_rate_hz = 2_000  # type: ignore[misc]
