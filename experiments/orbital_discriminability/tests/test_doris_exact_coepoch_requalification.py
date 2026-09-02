"""Synthetic tests for the value-blind DORIS exact-coepoch scanner."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import inspect
import json
from pathlib import Path

import ncompress
import pytest

from experiments.orbital_discriminability import doris_development_header as header
from experiments.orbital_discriminability import (
    doris_exact_coepoch_requalification as coepoch,
)


SECRET_OBSERVATION_TEXT = "1234567890.12"  # noqa: S105 - synthetic magnitude
ROOT = Path(__file__).resolve().parents[3]
RECEIPT = (
    ROOT
    / "experiments"
    / "orbital_discriminability"
    / "DORIS_EXACT_COEPOCH_REQUALIFICATION_RECEIPT.json"
)
PLAN = (
    ROOT
    / "experiments"
    / "orbital_discriminability"
    / "DORIS_EXACT_COEPOCH_REQUALIFICATION_PLAN.md"
)


def _header_line(data: str, label: str) -> bytes:
    return f"{data:<60}{label:<20}\n".encode("ascii")


def _field(*, present: bool = True, flag1: str = "", flag2: str = "") -> bytes:
    value = SECRET_OBSERVATION_TEXT if present else ""
    return f"{value:>14}{flag1:1}{flag2:1}".encode("ascii")


def _station_record(
    station_id: str,
    *,
    l1_present: bool = True,
    l2_present: bool = True,
    phase_flag2: str = "",
) -> bytes:
    fields = [
        _field(present=l1_present, flag2=phase_flag2),
        _field(present=l2_present, flag2=phase_flag2),
        *[_field() for _ in range(8)],
    ]
    return (
        station_id.encode("ascii")
        + b"".join(fields[:5])
        + b"\n   "
        + b"".join(fields[5:])
        + b"\n"
    )


def _epoch_line(epoch: datetime, record_count: int) -> bytes:
    second = epoch.second + epoch.microsecond / 1_000_000
    return (
        f"> {epoch.year:04d} {epoch.month:02d} {epoch.day:02d} "
        f"{epoch.hour:02d} {epoch.minute:02d} {second:11.7f}  0{record_count:3d}\n"
    ).encode("ascii")


def _synthetic_product(
    path: Path,
    station_sets: list[tuple[str, ...]],
    *,
    step_s: float = 10.0,
    break_index: int | None = None,
    absent_index: int | None = None,
) -> tuple[header.ProductAuthority, dict[str, object]]:
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
    station_record_count = 0
    for index, station_ids in enumerate(station_sets):
        epoch = start + timedelta(seconds=index * step_s)
        body.extend(_epoch_line(epoch, len(station_ids)))
        for station_id in station_ids:
            body.extend(
                _station_record(
                    station_id,
                    l2_present=not (
                        index == absent_index and station_id == coepoch.PAIR.left_id
                    ),
                    phase_flag2=(
                        "1"
                        if index == break_index
                        and station_id == coepoch.PAIR.left_id
                        else ""
                    ),
                )
            )
            station_record_count += 1
    raw = header_bytes + bytes(body)
    compressed = ncompress.compress(raw)
    path.write_bytes(compressed)
    authority = header.ProductAuthority(
        name=path.name,
        url="https://example.invalid/exact-coepoch-development",
        bytes=len(compressed),
        sha256=sha256(compressed).hexdigest(),
        remote_last_modified_utc="2026-08-31T22:20:14Z",
        role="SYNTHETIC_EXACT_COEPOCH_DEVELOPMENT",
    )
    frozen = {
        "expected_header_sha256": sha256(header_bytes).hexdigest(),
        "expected_decompressed_sha256": sha256(raw).hexdigest(),
        "expected_decompressed_bytes": len(raw),
        "expected_stream_lines": len(raw.splitlines()),
        "expected_epochs": len(station_sets),
        "expected_station_records": station_record_count,
    }
    return authority, frozen


def _scan(
    path: Path,
    authority: header.ProductAuthority,
    frozen: dict[str, object],
) -> dict[str, object]:
    return coepoch.scan_exact_coepoch_topology(
        path,
        authority=authority,
        expected_header_sha256=str(frozen["expected_header_sha256"]),
        expected_decompressed_sha256=str(
            frozen["expected_decompressed_sha256"]
        ),
        expected_decompressed_bytes=int(frozen["expected_decompressed_bytes"]),
        expected_stream_lines=int(frozen["expected_stream_lines"]),
        expected_epochs=int(frozen["expected_epochs"]),
        expected_station_records=int(frozen["expected_station_records"]),
    )


def test_exact_coepoch_chain_qualifies_at_frozen_duration(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.Z"
    station_sets = [("D46", "D40") for _ in range(49)]
    authority, frozen = _synthetic_product(path, station_sets)

    receipt = _scan(path, authority, frozen)

    assert receipt["outcome"] == "DORIS_EXACT_COEPOCH_TOPOLOGY_QUALIFIED"
    assert receipt["pair"]["maximum_exact_coepoch_segment_s"] == 480.0
    assert receipt["pair"]["coepoch_pair_count"] == 49
    assert receipt["pair"]["valid_coepoch_pair_count"] == 49
    assert receipt["pair"]["target_epoch_presence_counts"] == {"BOTH": 49}
    assert receipt["records"]["numeric_observation_values_decoded"] == 0
    assert receipt["records"]["numeric_observation_values_persisted"] == 0
    assert SECRET_OBSERVATION_TEXT not in coepoch.strict_json(receipt)


def test_asynchronous_station_streams_do_not_form_a_pair(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.Z"
    station_sets = [
        (("D46",) if index % 2 == 0 else ("D40",)) for index in range(98)
    ]
    authority, frozen = _synthetic_product(path, station_sets, step_s=5)

    receipt = _scan(path, authority, frozen)

    assert receipt["outcome"] == "DORIS_EXACT_COEPOCH_TOPOLOGY_INSUFFICIENT"
    assert receipt["pair"]["maximum_exact_coepoch_segment_s"] == 0.0
    assert receipt["pair"]["coepoch_pair_count"] == 0
    assert receipt["pair"]["target_epoch_presence_counts"] == {
        "LEFT_ONLY": 49,
        "RIGHT_ONLY": 49,
    }


def test_gap_one_microsecond_above_limit_breaks_every_segment(
    tmp_path: Path,
) -> None:
    path = tmp_path / "synthetic.Z"
    station_sets = [("D46", "D40") for _ in range(49)]
    authority, frozen = _synthetic_product(
        path,
        station_sets,
        step_s=10.000001,
    )

    receipt = _scan(path, authority, frozen)

    assert receipt["outcome"] == "DORIS_EXACT_COEPOCH_TOPOLOGY_INSUFFICIENT"
    assert receipt["pair"]["maximum_exact_coepoch_segment_s"] == 0.0
    assert receipt["pair"]["break_reasons"] == {
        "EXACT_COEPOCH_SAMPLE_GAP_EXCEEDED": 48
    }


@pytest.mark.parametrize("failure", ["missing_pair", "phase_break"])
def test_missing_or_discontinuous_phase_breaks_the_chain(
    tmp_path: Path,
    failure: str,
) -> None:
    path = tmp_path / "synthetic.Z"
    station_sets = [("D46", "D40") for _ in range(49)]
    if failure == "missing_pair":
        station_sets[24] = ("D46",)
    authority, frozen = _synthetic_product(
        path,
        station_sets,
        break_index=24 if failure == "phase_break" else None,
    )

    receipt = _scan(path, authority, frozen)

    assert receipt["outcome"] == "DORIS_EXACT_COEPOCH_TOPOLOGY_INSUFFICIENT"
    assert receipt["pair"]["maximum_exact_coepoch_segment_s"] == 230.0
    if failure == "missing_pair":
        assert receipt["pair"]["break_reasons"] == {
            "EXACT_COEPOCH_SAMPLE_GAP_EXCEEDED": 1
        }
    else:
        assert receipt["pair"]["break_reasons"] == {
            "LEFT_PHASE_DISCONTINUITY": 1
        }


def test_absent_l2_is_a_typed_phase_break(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.Z"
    station_sets = [("D46", "D40") for _ in range(49)]
    authority, frozen = _synthetic_product(
        path,
        station_sets,
        absent_index=24,
    )

    receipt = _scan(path, authority, frozen)

    assert receipt["pair"]["maximum_exact_coepoch_segment_s"] == 230.0
    assert receipt["pair"]["break_reasons"] == {"LEFT_CORE_PHASE_ABSENT": 1}


def test_hash_is_checked_before_decompressor_resolution(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.Z"
    authority, frozen = _synthetic_product(path, [("D46", "D40")])
    wrong = replace(authority, sha256="0" * 64)

    with pytest.raises(header.DorisHeaderError, match="SHA256_CHANGED"):
        coepoch.scan_exact_coepoch_topology(
            path,
            authority=wrong,
            gzip_executable=str(tmp_path / "does-not-exist"),
            **frozen,
        )


def test_scanner_surface_is_value_blind_and_candidate_blind() -> None:
    source = inspect.getsource(coepoch)

    assert "s3arx26245" not in source
    assert "requests" not in source
    assert "ftplib" not in source
    assert "_code_witness_valid" not in source
    assert "float(slot" not in source
    assert "numeric_observation_values_decoded" in source
    assert "candidate_day_product_access" in source


def test_frozen_receipt_records_exact_coepoch_result_and_zero_retention() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))

    assert receipt["outcome"] == "DORIS_EXACT_COEPOCH_TOPOLOGY_QUALIFIED"
    assert receipt["authority"]["sha256"] == header.DEVELOPMENT_SHA256
    assert receipt["execution"]["materialization_attempts"] == 1
    assert receipt["execution"]["scanner_invocations"] == 1
    assert receipt["execution"]["retry_count"] == 0
    assert receipt["pair"]["maximum_exact_coepoch_segment_s"] == 633.0
    assert receipt["pair"]["longest_exact_coepoch_segments"][0][
        "epoch_count"
    ] == 128
    assert receipt["stream"]["compressed_retention_after_receipt"] == (
        "ZERO_CONFIRMED"
    )
    assert receipt["records"]["numeric_observation_values_decoded"] == 0
    assert receipt["records"]["numeric_observation_values_persisted"] == 0
    assert receipt["scope"]["candidate_day_product_access"] == "ZERO"
    assert receipt["scope"]["measurement_admission"] == "NOT_EVALUATED"
    assert receipt["scope"]["orbital_prediction"] == "NOT_EVALUATED"


def test_frozen_receipt_binds_canonical_source_and_plan() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    plan = PLAN.read_bytes().replace(b"\r\n", b"\n")

    assert receipt["execution"]["source_commit"] == (
        "7d954f576f000bd84d5a6b3bdc23f744bba7cb4c"
    )
    assert receipt["execution"]["source_sha256"] == (
        "4cc40fcc2fed2521fc69c4b5654a35fd8803501d91b930d29d7c1d300b182ee8"
    )
    assert receipt["execution"]["plan_sha256"] == sha256(plan).hexdigest()
