"""Synthetic tests for the frozen four-product Cassini header path."""

from dataclasses import fields, replace
import struct

import pytest

from experiments.orbital_discriminability.cassini_dss26_rsr_header import (
    RSR_HEADER_BYTES,
    RSR_RECORD_BYTES,
)
from experiments.orbital_discriminability.cassini_dual_root_headers import (
    PRODUCTS,
    CassiniDualRootHeaderError,
    HeaderReceipt,
    _Accumulator,
    build_qualification,
    canonical_parser_source_sha256,
    parse_header,
    parser_manifest,
    parser_manifest_sha256,
    qualify_header_path,
    strict_json,
)


def _header(
    *,
    station: int,
    rsr: int = 2,
    sequence: int = 0,
    second: float = 69_420.0,
    ddc_lo_mhz: int = 327,
    nco_f1_hz: float = 11_000.0,
) -> bytearray:
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
    struct.pack_into(">H", value, 40, sequence)
    value[42:46] = bytes((10, station, rsr, 1))
    value[56] = 0
    value[68] = 16
    struct.pack_into(">H", value, 70, 1)
    struct.pack_into(">H", value, 72, ddc_lo_mhz)
    struct.pack_into(">H", value, 74, 8_100)
    struct.pack_into(">H", value, 76, 2005)
    struct.pack_into(">H", value, 78, 159)
    struct.pack_into(">d", value, 80, second)
    for offset, number in {
        88: 0.0,
        96: 0.0,
        104: 0.0,
        112: 40.0,
        120: 0.0,
        176: nco_f1_hz,
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
    struct.pack_into(">H", value, 258, RSR_RECORD_BYTES - RSR_HEADER_BYTES)
    return value


def test_product_specs_bind_exact_window_and_label_identity() -> None:
    assert set(PRODUCTS) == {
        "DSS25_X",
        "DSS25_KA",
        "DSS55_X",
        "DSS55_KA",
    }
    assert {spec.window_records for spec in PRODUCTS.values()} == {5_280}
    assert {
        spec.window_first_sample_utc for spec in PRODUCTS.values()
    } == {"2005-06-08T19:17:00.000000Z"}
    assert {
        spec.window_last_first_sample_utc for spec in PRODUCTS.values()
    } == {"2005-06-08T20:44:59.000000Z"}
    assert all(
        spec.file_bytes == spec.full_product_records * RSR_RECORD_BYTES
        for spec in PRODUCTS.values()
    )


def test_parser_binds_station_and_label_channel_but_learns_rsr() -> None:
    x25 = parse_header(_header(station=25, rsr=7), "DSS25_X")
    ka25 = parse_header(_header(station=25, rsr=8), "DSS25_KA")
    x55 = parse_header(_header(station=55, rsr=3), "DSS55_X")
    ka55 = parse_header(_header(station=55, rsr=4), "DSS55_KA")

    assert (x25.station_id, x25.rsr_id, x25.channel_id) == (
        "DSS-25",
        7,
        "A",
    )
    assert (ka25.downlink_band, ka25.channel_id) == ("KA", "B")
    assert (x55.station_id, x55.downlink_band) == ("DSS-55", "X")
    assert (ka55.rsr_id, ka55.channel_id) == (4, "B")


def test_cross_product_station_zero_rsr_and_unknown_role_are_refused() -> None:
    with pytest.raises(CassiniDualRootHeaderError, match="station/subchannel"):
        parse_header(_header(station=55), "DSS25_X")
    with pytest.raises(CassiniDualRootHeaderError, match="RSR identity is zero"):
        parse_header(_header(station=25, rsr=0), "DSS25_KA")
    with pytest.raises(CassiniDualRootHeaderError, match="four-product"):
        parse_header(_header(station=25), "OTHER")  # type: ignore[arg-type]


def test_accumulator_is_incremental_and_detects_control_transition() -> None:
    spec = replace(
        PRODUCTS["DSS25_X"],
        window_records=3,
        window_first_sample_utc="2005-06-08T19:17:00.000000Z",
        window_last_first_sample_utc="2005-06-08T19:17:02.000000Z",
    )
    accumulator = _Accumulator(spec)
    for index in range(3):
        accumulator.add(
            parse_header(
                _header(
                    station=25,
                    sequence=index,
                    second=69_420.0 + index,
                ),
                "DSS25_X",
            )
        )
    summary = accumulator.finish()
    assert summary["window_record_count"] == 3
    assert summary["data_chdo_bytes_read"] == 0
    assert len(summary["ordered_whitelist_receipts_sha256"]) == 64

    changed = _Accumulator(
        replace(
            spec,
            window_records=2,
            window_last_first_sample_utc="2005-06-08T19:17:01.000000Z",
        )
    )
    changed.add(
        parse_header(
            _header(station=25, sequence=0, second=69_420.0),
            "DSS25_X",
        )
    )
    changed.add(
        parse_header(
            _header(
                station=25,
                sequence=1,
                second=69_421.0,
                ddc_lo_mhz=330,
                nco_f1_hz=3_011_000.0,
            ),
            "DSS25_X",
        )
    )
    changed_summary = changed.finish()
    transform = changed_summary["receiver_frequency_transform"]
    assert transform["ddc_lo_change_count"] == 1


def _summary(
    *,
    station: int,
    rsr: int,
    channel: str,
    ddc_changes: int = 0,
) -> dict[str, object]:
    return {
        "event_time": {
            "first_sample_utc": "2005-06-08T19:17:00.000000Z",
            "last_first_sample_utc": "2005-06-08T20:44:59.000000Z",
            "non_one_second_steps": 0,
        },
        "record_sequence": {
            "non_unit_steps_modulo_65536": 0,
        },
        "identity_and_sample_mode": {
            "signal_processing_center_id": [10],
            "deep_space_station_id": [station],
            "rsr_id": [rsr],
            "channel_id": [channel],
            "subchannel_id": [1],
        },
        "receiver_frequency_transform": {
            "finite_and_explicit_on_every_record": True,
            "ddc_lo_change_count": ddc_changes,
            "rf_to_if_lo_change_count": 0,
            "frequency_override_state_change_count": 0,
        },
    }


def _summaries() -> dict[str, dict[str, object]]:
    return {
        "DSS25_X": _summary(station=25, rsr=1, channel="A"),
        "DSS25_KA": _summary(station=25, rsr=2, channel="B"),
        "DSS55_X": _summary(station=55, rsr=3, channel="A"),
        "DSS55_KA": _summary(station=55, rsr=4, channel="B"),
    }


def test_topology_requires_two_roots_two_witnesses_and_no_transition() -> None:
    admitted = qualify_header_path(_summaries())  # type: ignore[arg-type]
    assert admitted["outcome"] == (
        "CASSINI_DUAL_ROOT_HEADER_PATH_QUALIFIED"
    )
    assert admitted["physical_margin_admitted"] is False
    assert admitted["iq_access_authorized"] is False

    transitioned = _summaries()
    transitioned["DSS55_X"] = _summary(
        station=55,
        rsr=3,
        channel="A",
        ddc_changes=1,
    )
    result = qualify_header_path(transitioned)  # type: ignore[arg-type]
    assert result["outcome"] == "NO_ADMISSIBLE_DUAL_ROOT_HEADER_PATH"
    assert result["clauses"][
        "no_discrete_lo_ddc_or_override_transition"
    ] is False


def test_build_qualification_separates_header_and_physical_admission() -> None:
    receipt = build_qualification(
        _summaries(),  # type: ignore[arg-type]
        source_commit="a" * 40,
    )
    assert receipt["outcome"] == (
        "CASSINI_DUAL_ROOT_HEADER_PATH_QUALIFIED"
    )
    assert receipt["access_boundary"] == {
        "sfdu_header_bytes_requested_and_read": 5_491_200,
        "data_chdo_bytes_requested": 0,
        "data_chdo_bytes_read": 0,
        "raw_headers_persisted": False,
        "iq_or_amplitude_fields_represented": False,
    }
    assert receipt["topology_qualification"][
        "physical_margin_admitted"
    ] is False


def test_manifest_and_receipt_cannot_represent_signal_or_samples() -> None:
    receipt = parse_header(_header(station=25), "DSS25_X")
    representation = (
        " ".join(field.name for field in fields(HeaderReceipt))
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
    assert parser_manifest()["data_chdo_access"] == "PROHIBITED"
    assert len(parser_manifest_sha256()) == 64
    assert len(canonical_parser_source_sha256()) == 64


def test_strict_json_refuses_nonfinite_values() -> None:
    with pytest.raises(ValueError):
        strict_json({"value": float("nan")})
