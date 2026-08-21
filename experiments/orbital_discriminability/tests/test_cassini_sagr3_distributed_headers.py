"""Synthetic-only tests for the frozen three-product SFDU header spike."""

from dataclasses import fields, replace
import struct

import pytest

from experiments.orbital_discriminability.cassini_dss26_rsr_header import (
    RSR_HEADER_BYTES,
    RSR_RECORD_BYTES,
)
from experiments.orbital_discriminability.cassini_sagr3_distributed_headers import (
    PRODUCTS,
    CassiniDistributedHeaderError,
    DistributedHeaderReceipt,
    _HeaderAccumulator,
    parse_distributed_header,
    parser_manifest,
    parser_manifest_sha256,
    qualify_topology,
    locate_ddc_transition,
    strict_json,
)


def _header(
    *, station: int, rsr: int = 2, sequence: int = 0,
    second: float = 43_201.0, ddc_lo_mhz: int = 327,
    nco_f1_hz: float = 11_000.0,
):
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
    struct.pack_into(">H", value, 76, 2006)
    struct.pack_into(">H", value, 78, 251)
    struct.pack_into(">d", value, 80, second)
    for offset, number in {
        88: 0.0, 96: 0.0, 104: 0.0, 112: 40.0, 120: 0.0,
        176: nco_f1_hz, 184: -4.0, 192: 0.25,
        200: 80.0, 208: 0.0, 216: 11.0, 224: -2.0, 232: 0.25,
    }.items():
        struct.pack_into(">d", value, offset, number)
    struct.pack_into(">H", value, 256, 10)
    struct.pack_into(">H", value, 258, RSR_RECORD_BYTES - RSR_HEADER_BYTES)
    return value


def test_three_products_bind_station_and_label_channel_but_learn_rsr_from_sfdu() -> None:
    left = parse_distributed_header(_header(station=25, rsr=5), "MEASUREMENT_X_DSS25")
    witness = parse_distributed_header(_header(station=25, rsr=6), "WITNESS_KA_DSS25")
    right = parse_distributed_header(_header(station=65, rsr=3), "MEASUREMENT_X_DSS65")
    assert (left.station_id, left.rsr_id, left.channel_id, left.subchannel_id) == (
        "DSS-25", 5, "A", 1,
    )
    assert (witness.downlink_band, witness.rsr_id, witness.channel_id) == (
        "KA", 6, "B",
    )
    assert (right.station_id, right.rsr_id, right.downlink_band) == (
        "DSS-65", 3, "X",
    )


def test_cross_product_station_zero_rsr_and_unknown_role_are_refused() -> None:
    with pytest.raises(CassiniDistributedHeaderError, match="station/subchannel"):
        parse_distributed_header(_header(station=65), "MEASUREMENT_X_DSS25")
    with pytest.raises(CassiniDistributedHeaderError, match="RSR identity is zero"):
        parse_distributed_header(_header(station=25, rsr=0), "WITNESS_KA_DSS25")
    with pytest.raises(CassiniDistributedHeaderError, match="three-product"):
        parse_distributed_header(_header(station=25), "OTHER")  # type: ignore[arg-type]


def test_incremental_summary_commits_controls_and_detects_a_gap() -> None:
    spec = replace(
        PRODUCTS["MEASUREMENT_X_DSS25"],
        records=3,
        first_sample_utc="2006-09-08T12:00:01.000000Z",
        last_first_sample_utc="2006-09-08T12:00:03.000000Z",
    )
    accumulator = _HeaderAccumulator(spec)
    for index in range(3):
        accumulator.add(parse_distributed_header(
            _header(station=25, sequence=index, second=43_201.0 + index),
            "MEASUREMENT_X_DSS25",
        ))
    summary = accumulator.finish()
    assert summary["record_count"] == 3
    assert summary["data_chdo_bytes_read"] == 0
    assert len(summary["ordered_whitelist_receipts_sha256"]) == 64

    broken = _HeaderAccumulator(spec)
    broken.add(parse_distributed_header(
        _header(station=25, sequence=0, second=43_201.0), "MEASUREMENT_X_DSS25"
    ))
    broken.add(parse_distributed_header(
        _header(station=25, sequence=2, second=43_203.0), "MEASUREMENT_X_DSS25"
    ))
    broken.add(parse_distributed_header(
        _header(station=25, sequence=3, second=43_204.0), "MEASUREMENT_X_DSS25"
    ))
    with pytest.raises(CassiniDistributedHeaderError, match="discontinuous"):
        broken.finish()


def _summary(*, station: int, rsr: int, channel: str, end: str) -> dict[str, object]:
    return {
        "event_time": {
            "first_sample_utc": "2006-09-08T12:00:01.000000Z",
            "last_first_sample_utc": end,
            "non_one_second_steps": 0,
        },
        "record_sequence": {"non_unit_steps_modulo_65536": 0},
        "identity_and_sample_mode": {
            "signal_processing_center_id": [10],
            "deep_space_station_id": [station],
            "rsr_id": [rsr],
            "channel_id": [channel],
            "subchannel_id": [1],
        },
        "receiver_frequency_transform": {
            "finite_and_explicit_on_every_record": True,
        },
    }


def test_topology_requires_distinct_dss25_channels_and_receive_roots() -> None:
    summaries = {
        "MEASUREMENT_X_DSS25": _summary(
            station=25, rsr=5, channel="A", end="2006-09-08T22:30:00.000000Z"
        ),
        "WITNESS_KA_DSS25": _summary(
            station=25, rsr=6, channel="B", end="2006-09-08T22:30:00.000000Z"
        ),
        "MEASUREMENT_X_DSS65": _summary(
            station=65, rsr=3, channel="A", end="2006-09-08T16:40:00.000000Z"
        ),
    }
    result = qualify_topology(summaries)  # type: ignore[arg-type]
    assert result["outcome"] == "CASSINI_SAGR3_HEADER_TOPOLOGY_QUALIFIED"
    assert result["physical_margin_admitted"] is False
    assert result["iq_access_authorized"] is False

    invalid = dict(summaries)
    invalid["WITNESS_KA_DSS25"] = _summary(
        station=25, rsr=6, channel="A", end="2006-09-08T22:30:00.000000Z"
    )
    assert qualify_topology(invalid)["outcome"] == (
        "NO_ADMISSIBLE_DISTRIBUTED_HEADER_TOPOLOGY"
    )


def test_frequency_transform_boundary_includes_ddc_lo_not_only_nco() -> None:
    spec = replace(
        PRODUCTS["MEASUREMENT_X_DSS25"],
        records=2,
        first_sample_utc="2006-09-08T12:00:01.000000Z",
        last_first_sample_utc="2006-09-08T12:00:02.000000Z",
    )
    accumulator = _HeaderAccumulator(spec)
    accumulator.add(parse_distributed_header(
        _header(station=25, sequence=0, second=43_201.0),
        "MEASUREMENT_X_DSS25",
    ))
    accumulator.add(parse_distributed_header(
        _header(
            station=25, sequence=1, second=43_202.0,
            ddc_lo_mhz=330, nco_f1_hz=3_010_996.25,
        ),
        "MEASUREMENT_X_DSS25",
    ))
    summary = accumulator.finish()
    assert summary["frequency_polynomial_maximum_absolute_boundary_residual_hz"] > 2e6
    assert summary["receiver_frequency_transform"]["ddc_lo_change_count"] == 1
    assert summary["receiver_frequency_transform"][
        "maximum_absolute_adjacent_boundary_residual_hz"
    ] == pytest.approx(0.0, abs=1e-3)


def test_transition_locator_uses_header_metadata_and_returns_exact_boundary() -> None:
    role = "MEASUREMENT_X_DSS65"
    spec = PRODUCTS[role]
    transition = spec.records // 2

    def header_at_index(_role, index):
        assert _role == role
        return parse_distributed_header(
            _header(
                station=65,
                sequence=index % 65_536,
                second=43_201.0 + index,
                ddc_lo_mhz=327 if index < transition else 330,
                nco_f1_hz=11_000.0 if index < transition else 3_011_000.0,
            ),
            role,
        )

    result = locate_ddc_transition(role, header_at_index)
    assert result is not None
    assert result["transition_record_index_zero_based"] == transition
    assert result["before"]["ddc_lo_hz"] == 327_000_000
    assert result["after"]["ddc_lo_hz"] == 330_000_000
    assert result["access_boundary"]["data_chdo_bytes_read"] == 0


def test_manifest_and_receipt_cannot_represent_signal_or_samples() -> None:
    receipt = parse_distributed_header(_header(station=25), "MEASUREMENT_X_DSS25")
    representation = (
        " ".join(field.name for field in fields(DistributedHeaderReceipt))
        + strict_json(receipt.as_json_object())
        + strict_json(parser_manifest())
    ).lower()
    for forbidden in (
        "adc_rms", "adc_peak", "signal_strength", "fgain", "sample_values",
        "signal_diagnostic",
    ):
        assert forbidden not in representation
    assert parser_manifest()["data_chdo_access"] == "PROHIBITED"
    assert len(parser_manifest_sha256()) == 64
