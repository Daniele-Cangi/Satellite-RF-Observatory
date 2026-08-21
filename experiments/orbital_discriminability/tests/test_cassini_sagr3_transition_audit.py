from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from experiments.orbital_discriminability import cassini_dss26_one_way as one_way
from experiments.orbital_discriminability import (
    cassini_sagr3_distributed_geometry as geometry,
)
from experiments.orbital_discriminability import (
    cassini_sagr3_transition_audit as audit,
)


def _fixed_state(position, velocity=(0.0, 0.0, 0.0)):
    state = one_way.StateVector(tuple(position), tuple(velocity))
    return lambda _epoch: state


def _u32(value: int) -> bytes:
    return int(value).to_bytes(4, "big", signed=False)


def _i32(value: int) -> bytes:
    return int(value).to_bytes(4, "big", signed=True)


def _seconds_since_1950(instant: datetime) -> int:
    epoch = datetime(1950, 1, 1, tzinfo=timezone.utc)
    return int((instant - epoch).total_seconds())


def _synthetic_ramp_range() -> bytes:
    data = bytearray(audit.RAMP_RANGE_BYTES)
    base = datetime(2006, 9, 8, 12, 0, tzinfo=timezone.utc)
    for group_index, group in enumerate(audit.RAMP_GROUPS):
        header = (
            group.header_record_one_based
            - audit.RAMP_RANGE_FIRST_RECORD_ONE_BASED
        ) * audit.ODF_RECORD_BYTES
        data[header : header + 16] = (
            _i32(2030)
            + _u32(group.station_id)
            + _u32(1)
            + _u32(group.header_record_one_based - 1)
        )
        for row in range(group.rows):
            offset = header + audit.ODF_RECORD_BYTES * (row + 1)
            start = base + timedelta(hours=group_index, seconds=row)
            end = start + timedelta(seconds=1)
            packed = (7 << 10) | group.station_id
            data[offset : offset + audit.ODF_RECORD_BYTES] = (
                _u32(_seconds_since_1950(start))
                + _u32(0)
                + _i32(-1)
                + _i32(-500_000_000)
                + _u32(packed)
                + _u32(174_526_800)
                + _u32(0)
                + _u32(_seconds_since_1950(end))
                + _u32(0)
            )
    return bytes(data)


def test_synthetic_ramp_groups_are_structurally_parsed_without_observables():
    entries = audit._parse_ramp_range(_synthetic_ramp_range())

    assert len(entries) == 56
    assert {entry.station_id for entry in entries} == {14, 25, 43, 65}
    assert entries[0].rate_hz_s == pytest.approx(-1.5, abs=1e-15)
    assert entries[0].start_frequency_hz == pytest.approx(7_174_526_800.0)
    assert audit.ramp_at(entries, 14, entries[0].start_utc) == entries[0]
    assert audit.ramp_at(entries, 14, entries[0].end_utc) == entries[1]


def test_frozen_parser_rejects_wrong_hash_and_length():
    with pytest.raises(audit.CassiniSagr3TransitionAuditError, match="exactly"):
        audit.parse_frozen_ramp_range(b"")
    with pytest.raises(audit.CassiniSagr3TransitionAuditError, match="SHA-256"):
        audit.parse_frozen_ramp_range(_synthetic_ramp_range())


def test_ramp_structure_rejects_station_and_packet_corruption():
    station_corrupt = bytearray(_synthetic_ramp_range())
    first_row_packed_offset = audit.ODF_RECORD_BYTES + 16
    station_corrupt[first_row_packed_offset : first_row_packed_offset + 4] = _u32((7 << 10) | 99)
    with pytest.raises(audit.CassiniSagr3TransitionAuditError, match="station"):
        audit._parse_ramp_range(station_corrupt)

    packet_corrupt = bytearray(_synthetic_ramp_range())
    packet_corrupt[12:16] = _u32(0)
    with pytest.raises(audit.CassiniSagr3TransitionAuditError, match="packet"):
        audit._parse_ramp_range(packet_corrupt)


def test_two_way_epoch_solver_uses_two_relative_light_times():
    c = one_way.SPEED_OF_LIGHT_M_S
    epochs = geometry.solve_two_way_epochs(
        100_000_002.0,
        _fixed_state((-c, 0.0, 0.0)),
        _fixed_state((c, 0.0, 0.0)),
        _fixed_state((0.0, 0.0, 0.0)),
        tolerance_s=1e-12,
    )

    assert epochs.turnaround_et_tdb_s == pytest.approx(100_000_001.0, abs=0.0)
    assert epochs.uplink_transmit_et_tdb_s == pytest.approx(100_000_000.0, abs=0.0)
    assert epochs.downlink_light_time_s == pytest.approx(1.0, abs=1e-15)
    assert epochs.uplink_light_time_s == pytest.approx(1.0, abs=1e-15)


def test_pretransition_manifest_preserves_original_prefix_and_nulls():
    manifest_hash = geometry.pretransition_screen_manifest_sha256()

    assert len(manifest_hash) == 64
    assert geometry.PRETRANSITION_RECORDS == 10_651
    assert geometry.PRETRANSITION_CALIBRATION_RECORDS == 3_360
    assert geometry.PRETRANSITION_HOLDOUT_RECORDS == 7_291
    assert geometry.PRETRANSITION_LAST_RECEIVE_UTC == "2006-09-08T14:57:31Z"


def test_audit_manifest_excludes_observables_iq_and_detector():
    manifest = audit.parser_manifest()
    encoded = audit.strict_json(manifest)

    assert len(audit.parser_manifest_sha256()) == 64
    assert manifest["scope"] == "FOUR_ODF_RAMP_GROUPS_ONLY"
    assert manifest["authorized_byte_range"]["bytes"] == 2_160
    assert "ODF orbit-observable group" in manifest["forbidden"]
    assert "IQ or amplitude" in manifest["forbidden"]
    assert "detector input" in manifest["forbidden"]
    assert "NaN" not in encoded


def test_frozen_transition_receipt_keeps_full_heldout_blocked():
    path = Path(audit.__file__).with_name(
        "CASSINI_SAGR3_TRANSITION_AUDIT_RECEIPT.json"
    )
    receipt = json.loads(path.read_text(encoding="utf-8"))

    assert receipt["full_heldout_status"] == (
        "BLOCKED_BY_UNMODELED_COORDINATE_TRANSITION_INSIDE_HELDOUT"
    )
    assert receipt["transition_cause"] == "UNRESOLVED"
    assert receipt["odf_ramp_audit"]["parser_manifest_sha256"] == (
        audit.parser_manifest_sha256()
    )
    screen = receipt["pretransition_screen"]
    assert screen["manifest_sha256"] == (
        geometry.pretransition_screen_manifest_sha256()
    )
    assert screen["controlling_heldout_separation_hz_peak_to_peak"] == (
        0.07231370056321107
    )
    assert screen["best_case_detector_resolution_ceiling_hz_for_three_bins"] == (
        0.024102072553341698
    )
    assert screen["physical_admission"] is False
    assert receipt["iq_accessed"] is False
    assert receipt["detector_implemented"] is False
