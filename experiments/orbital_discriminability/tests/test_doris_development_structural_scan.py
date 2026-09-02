"""Specification-shaped tests for the value-blind DORIS body scan."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import inspect
from pathlib import Path

import ncompress
import pytest

from experiments.orbital_discriminability import doris_development_header as header
from experiments.orbital_discriminability import (
    doris_development_structural_scan as scanner,
)


SECRET_OBSERVATION_TEXT = "9876543210.12"


def _header_line(data: str, label: str) -> bytes:
    return f"{data:<60}{label:<20}\n".encode("ascii")


def _field(*, present: bool = True, flag1: str = "", flag2: str = "") -> bytes:
    value = SECRET_OBSERVATION_TEXT if present else ""
    return f"{value:>14}{flag1:1}{flag2:1}".encode("ascii")


def _station_record(
    station_id: str,
    *,
    phase_flag1: str = "",
    phase_flag2: str = "",
) -> bytes:
    fields = [
        _field(flag1=phase_flag1, flag2=phase_flag2),
        _field(flag1=phase_flag1, flag2=phase_flag2),
        _field(),
        _field(),
        _field(),
        _field(),
        _field(),
        _field(),
        _field(),
        _field(),
    ]
    return (
        station_id.encode("ascii")
        + b"".join(fields[:5])
        + b"\n   "
        + b"".join(fields[5:])
        + b"\n"
    )


def _epoch_line(epoch: datetime, *, flag: int, count: int) -> bytes:
    second = epoch.second + epoch.microsecond / 1_000_000
    return (
        f"> {epoch.year:04d} {epoch.month:02d} {epoch.day:02d} "
        f"{epoch.hour:02d} {epoch.minute:02d} {second:11.7f}  {flag:1d}{count:3d}\n"
    ).encode("ascii")


def _synthetic_product(
    path: Path,
    *,
    epoch_count: int = 49,
    power_failure_index: int | None = None,
    phase_break_index: int | None = None,
    central_frequency_index: int | None = None,
    cadence_pattern_s: tuple[int, ...] | None = None,
) -> tuple[header.ProductAuthority, str]:
    header_bytes = b"".join(
        [
            _header_line(
                "     3.00           OBSERVATION DATA    D",
                "RINEX VERSION / TYPE",
            ),
            _header_line("", "END OF HEADER"),
        ]
    )
    body = bytearray()
    start = datetime(2026, 8, 30, tzinfo=timezone.utc)
    elapsed_s = 0
    for index in range(epoch_count):
        if index and cadence_pattern_s:
            elapsed_s += cadence_pattern_s[(index - 1) % len(cadence_pattern_s)]
        elif index:
            elapsed_s += 10
        epoch = start + timedelta(seconds=elapsed_s)
        flag = 1 if index == power_failure_index else 0
        body.extend(_epoch_line(epoch, flag=flag, count=4))
        for station_id in ("D49", "D47", "D46", "D40"):
            phase_flag1 = (
                "1"
                if index == central_frequency_index and station_id == "D49"
                else ""
            )
            phase_flag2 = "1" if index == phase_break_index and station_id == "D49" else ""
            body.extend(
                _station_record(
                    station_id,
                    phase_flag1=phase_flag1,
                    phase_flag2=phase_flag2,
                )
            )
    raw = header_bytes + bytes(body)
    compressed = ncompress.compress(raw)
    path.write_bytes(compressed)
    authority = header.ProductAuthority(
        name=path.name,
        url="https://example.invalid/value-blind-development",
        bytes=len(compressed),
        sha256=sha256(compressed).hexdigest(),
        remote_last_modified_utc="2026-08-31T22:20:14Z",
        role="SYNTHETIC_VALUE_BLIND_DEVELOPMENT",
    )
    return authority, sha256(header_bytes).hexdigest()


def _scan(path: Path, authority: header.ProductAuthority, header_hash: str) -> dict:
    return scanner.scan_exact_development_structure(
        path,
        authority=authority,
        expected_header_sha256=header_hash,
    )


def test_complete_structural_scan_qualifies_long_witnessed_segments(
    tmp_path: Path,
) -> None:
    path = tmp_path / "synthetic.Z"
    authority, header_hash = _synthetic_product(path)

    receipt = _scan(path, authority, header_hash)

    assert receipt["outcome"] == (
        "DORIS_DEVELOPMENT_STRUCTURE_QUALIFIED_MEASUREMENT_UNADMITTED"
    )
    assert receipt["stream"]["complete_stream_scanned"] is True
    assert receipt["epochs"]["count"] == 49
    assert receipt["records"]["station_record_count"] == 196
    assert receipt["records"]["continuation_line_count"] == 196
    assert receipt["records"]["numeric_observation_values_decoded"] == 0
    assert receipt["records"]["numeric_observation_values_persisted"] == 0
    assert [pair["maximum_same_path_witnessed_segment_s"] for pair in receipt["pairs"]] == [
        480.0,
        480.0,
    ]
    assert SECRET_OBSERVATION_TEXT not in scanner.strict_json(receipt)
    assert receipt["measurement_admission"] == "NOT_EVALUATED"
    assert receipt["orbital_score"] == "NOT_EVALUATED"
    assert receipt["candidate_day_product_access"] == "ZERO"


def test_power_failure_epoch_is_a_hard_continuity_cut(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.Z"
    authority, header_hash = _synthetic_product(path, power_failure_index=24)

    receipt = _scan(path, authority, header_hash)

    assert receipt["outcome"] == "DORIS_DEVELOPMENT_STRUCTURE_INSUFFICIENT"
    assert receipt["epochs"]["power_failure_epoch_count"] == 1
    assert [pair["maximum_same_path_witnessed_segment_s"] for pair in receipt["pairs"]] == [
        240.0,
        240.0,
    ]
    for station in receipt["stations"].values():
        assert station["core_break_reasons"]["EPOCH_FLAG_1_POWER_FAILURE"] == 1
        assert station["same_path_witness_break_reasons"][
            "EPOCH_FLAG_1_POWER_FAILURE"
        ] == 1


def test_nonzero_phase_flag_breaks_only_the_affected_pair(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.Z"
    authority, header_hash = _synthetic_product(path, phase_break_index=24)

    receipt = _scan(path, authority, header_hash)

    tlsb_weuc, paub_rimc = receipt["pairs"]
    assert tlsb_weuc["maximum_core_phase_segment_s"] == 230.0
    assert receipt["stations"]["D49"]["core_break_reasons"][
        "PHASE_DISCONTINUITY"
    ] == 1
    assert receipt["stations"]["D49"]["same_path_witness_break_reasons"][
        "PHASE_DISCONTINUITY"
    ] == 1
    assert paub_rimc["maximum_core_phase_segment_s"] == 480.0
    assert paub_rimc["structurally_admitted"] is True


def test_central_frequency_phase_flag_is_descriptive_not_a_break(
    tmp_path: Path,
) -> None:
    path = tmp_path / "synthetic.Z"
    authority, header_hash = _synthetic_product(
        path,
        central_frequency_index=24,
    )

    receipt = _scan(path, authority, header_hash)

    assert receipt["pairs"][0]["maximum_core_phase_segment_s"] == 480.0
    assert receipt["stations"]["D49"]["flag_counts"]["L1_FLAG1_1"] == 1
    assert receipt["stations"]["D49"]["flag_counts"]["L2_FLAG1_1"] == 1


def test_interleaved_three_seven_second_station_cadence_is_continuous(
    tmp_path: Path,
) -> None:
    path = tmp_path / "synthetic.Z"
    authority, header_hash = _synthetic_product(
        path,
        epoch_count=97,
        cadence_pattern_s=(3, 7),
    )

    receipt = _scan(path, authority, header_hash)

    assert receipt["pairs"][0]["maximum_core_phase_segment_s"] == 480.0
    assert receipt["stations"]["D49"]["nonconforming_delta_count"] == 0
    assert receipt["stations"]["D49"]["cadence_delta_counts"] == {
        "3.000000": 48,
        "7.000000": 48,
    }


@pytest.mark.parametrize(
    ("seconds_token", "suffix"),
    [
        ("56.2500000", b"      999999.999\n"),
        ("56.250000000", b"        9.999999999 9\n"),
    ],
)
def test_epoch_prefix_keeps_count_and_ignores_receiver_clock_value(
    seconds_token: str,
    suffix: bytes,
) -> None:
    epoch = datetime(2026, 8, 30, 12, 34, 56, 250_000, tzinfo=timezone.utc)
    raw = (
        f"> 2026 08 30 12 34 {seconds_token}  0 56".encode("ascii") + suffix
    )

    parsed_epoch, flag, count = scanner._parse_epoch_prefix(raw)

    assert parsed_epoch == epoch
    assert flag == 0
    assert count == 56


def test_hash_is_verified_before_decompressor_resolution(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.Z"
    authority, header_hash = _synthetic_product(path)
    wrong = replace(authority, sha256="0" * 64)

    with pytest.raises(header.DorisHeaderError, match="SHA256_CHANGED"):
        scanner.scan_exact_development_structure(
            path,
            authority=wrong,
            expected_header_sha256=header_hash,
            gzip_executable=str(tmp_path / "does-not-exist"),
        )


def test_scanner_scope_excludes_candidate_and_observation_decoding() -> None:
    source = inspect.getsource(scanner)

    assert "s3arx26245" not in source
    assert "requests" not in source
    assert "ftplib" not in source
    assert "float(slot" not in source
    assert "numeric_observation_values_decoded" in source
    assert "candidate_day_product_access" in source
