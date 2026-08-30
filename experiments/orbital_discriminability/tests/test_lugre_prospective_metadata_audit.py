"""Offline tests for the sample-blind LuGRE prospective metadata audit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.orbital_discriminability import lugre_prospective_metadata_audit as audit


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / audit.RECEIPT_NAME
RECEIPT_SHA256 = "f44c6c92858b87adec65e86794403cdd70f834b6101567aa725526afb79a7730"


def _sdrx(*, band: str = "L1", forbidden: str = "") -> bytes:
    center = "1575.420" if band == "L1" else "1176.450"
    rate = "8" if band == "L1" else "24"
    return f"""<?xml version="1.0" encoding="utf-8"?>
<metadata xmlns="{audit.ION_NAMESPACE}">
  <lane id="Lane"><system id="System"/><bandsrc idband="{band}" idsrc="Source"/>
    <block id="Block00"><chunk id="Chunk00"><sizeword>1</sizeword><countwords>1</countwords>
      <lump id="Lump00"><stream id="Stream00"><ratefactor>1</ratefactor>
        <quantization>4</quantization><packedbits>8</packedbits><format>IQ</format>
        <encoding>TC</encoding><band id="{band}"/></stream></lump></chunk>
      <sizeheader>62</sizeheader><sizefooter>3</sizefooter></block></lane>
  <session id="Session"><toa>2025-03-15T13:07:27.163Z</toa></session>
  <system id="System"><freqbase format="MHz">{rate}</freqbase></system>
  <band id="{band}"><centerfreq format="MHz">{center}</centerfreq>
    <translatedfreq format="MHz">0</translatedfreq><inverted>false</inverted>
    <delaybias format="sec">0.000e+000</delaybias></band>
  <file id="File"><url>fixture.bin</url><timestamp>2025-03-15T13:07:27.163Z</timestamp></file>
  {forbidden}
</metadata>""".encode()


def test_sdrx_whitelist_exposes_only_frequency_and_time_description() -> None:
    value = audit.parse_lugre_sdrx_metadata(_sdrx())

    assert value == {
        "toa": "2025-03-15T13:07:27.163Z",
        "file_timestamp": "2025-03-15T13:07:27.163Z",
        "data_file": "fixture.bin",
        "band": "L1",
        "sample_rate_hz": 8_000_000.0,
        "quantization_bits": 4,
        "packed_bits": 8,
        "sample_format": "IQ",
        "encoding": "TC",
        "header_bytes": 62,
        "footer_bytes": 3,
        "center_frequency_hz": 1_575_420_000.0,
        "translated_frequency_hz": 0.0,
        "spectrum_inverted": False,
        "delay_bias_s": 0.0,
    }


def test_sdrx_whitelist_rejects_signal_derived_fields() -> None:
    with pytest.raises(audit.LuGreMetadataAuditError, match="FORBIDDEN"):
        audit.parse_lugre_sdrx_metadata(_sdrx(forbidden="<adc_rms>1</adc_rms>"))


def test_deflated_iqs_header_cannot_be_mislabeled_as_header_only_access() -> None:
    for row in audit.SDRX_RECEIPTS:
        assert row.data_member.compression_method == audit.ZIP_DEFLATE
        assert audit.data_header_access_state(row.data_member) == (
            "NOT_SEPARABLE_FROM_COMPRESSED_SAMPLE_PAYLOAD"
        )


def test_candidate_metadata_is_dual_band_and_internally_simultaneous() -> None:
    for operation in ("OP73", "OP74", "OP76"):
        rows = [row for row in audit.SDRX_RECEIPTS if row.operation == operation]
        assert {row.band for row in rows} == {"L1", "L5"}
        assert len({row.timestamp_utc for row in rows}) == 1
        assert {row.quantization_bits for row in rows} == {4}
        assert {row.spectrum_inverted for row in rows} == {False}
        assert {row.translated_frequency_hz for row in rows} == {0.0}


def test_timestamp_resolution_is_not_promoted_to_accuracy() -> None:
    value = audit.build_receipt(ROOT, "0" * 40)
    timing = value["time_semantics"]

    assert timing["sdrx_and_optable_resolution_s"] == 0.001
    assert timing["repeated_sdrx_minus_optable_s"] == pytest.approx(-0.001)
    assert timing["resolution_is_accuracy"] is False
    assert timing["generic_qn400_bound_product_applicable"] is False
    assert timing["adc_to_true_gpst_error_bound_s"] is None
    assert timing["state"] == "UNRESOLVED_FINITE_ABSOLUTE_TIME_BOUND"


def test_native_fft_spacing_is_not_promoted_to_detector_error() -> None:
    value = audit.build_receipt(ROOT, "0" * 40)
    rows = {row["operation"]: row for row in value["candidate_split"]}

    assert rows["OP73"]["native_whole_window_fft_spacing_hz"] == 0.5
    assert rows["OP76"]["native_whole_window_fft_spacing_hz"] == 0.5
    assert rows["OP74"]["native_whole_window_fft_spacing_hz"] == 2.0
    assert value["detectability"]["native_spacing_is_detector_error_bound"] is False
    assert value["detectability"]["detector"] == "NOT_IMPLEMENTED"


def test_blocking_clause_prevents_role_or_plan_freeze() -> None:
    value = audit.build_receipt(ROOT, "0" * 40)
    clauses = {row["clause"]: row["state"] for row in value["clauses"]}

    assert value["outcome"] == audit.OUTCOME
    assert clauses["FINITE_ADC_TO_TRUE_GPST_BOUND"] == "UNRESOLVED"
    assert clauses["PHYSICAL_CORRECTION_ENVELOPE"] == (
        "NOT_EVALUATED_AFTER_BLOCKING_CLAUSE"
    )
    assert value["roles_frozen"] is False
    assert value["prospective_plan_frozen"] is False


def test_access_receipt_preserves_zero_iq_and_telemetry() -> None:
    value = audit.build_receipt(ROOT, "0" * 40)
    access = value["access_boundary"]

    assert access["sdrx_companions"] == 6
    assert access["iqs_compressed_payload_bytes"] == 0
    assert access["iqs_uncompressed_bytes"] == 0
    assert access["iq_sample_values"] == 0
    assert access["telemetry_bytes"] == 0
    assert access["primary_opened"] is False
    assert access["reserve_opened"] is False


def test_strict_json_refuses_nonfinite_values() -> None:
    assert json.loads(audit.strict_json({"finite": 1.25})) == {"finite": 1.25}
    with pytest.raises(ValueError):
        audit.strict_json({"bad": float("nan")})
    with pytest.raises(ValueError):
        audit.strict_json({"bad": float("inf")})


def test_source_has_no_network_sample_decoder_or_orbital_scorer() -> None:
    source = Path(audit.__file__).read_text(encoding="utf-8").lower()

    for forbidden in (
        "import requests",
        "import urllib",
        "import socket",
        "def decode_iq",
        "frombuffer",
        "spiceypy",
        "tle",
        "tlm_nav",
    ):
        assert forbidden not in source


def test_committed_receipt_binds_source_and_terminal_boundary() -> None:
    canonical = RECEIPT.read_bytes().replace(b"\r\n", b"\n")
    value = json.loads(canonical)

    assert len(canonical) == 16_089
    assert audit.canonical_sha256(RECEIPT) == RECEIPT_SHA256
    assert value["source_commit"] == "40dccba136e84a609a3abd3b98307b489a19565d"
    assert value["source_sha256"] == (
        "9a7846d73ad1674201f08c5f9d572664090953dca61f56b3d232ddcc4edb38c1"
    )
    assert value["outcome"] == audit.OUTCOME
    assert value["time_semantics"]["adc_to_true_gpst_error_bound_s"] is None
    assert value["access_boundary"]["iq_sample_values"] == 0
    assert value["roles_frozen"] is False
    assert value["prospective_plan_frozen"] is False
