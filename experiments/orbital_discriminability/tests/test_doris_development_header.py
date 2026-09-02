"""Synthetic, specification-derived tests for the DORIS header boundary."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import inspect
import json
from pathlib import Path

import ncompress
import pytest

from experiments.orbital_discriminability import doris_development_header as header


def line(data: str, label: str) -> str:
    return f"{data:<60}{label:<20}\n"


def observation_time(year: int, day: int, label: str) -> str:
    data = f"{year:6d}{9:6d}{day:6d}{0:6d}{0:6d}{0.0:13.7f}{'':5s}{'DOR':3s}"
    return line(data, label)


def station_reference(
    internal_id: str,
    code: str,
    name: str,
    domes: str,
    station_type: int,
    shift_k: int,
) -> str:
    data = (
        f"{internal_id:<3}{'':2s}{code:<4}{'':1s}{name:<30}{domes:<10}"
        f" {station_type:1d} {shift_k:3d}"
    )
    return line(data, "STATION REFERENCE")


def synthetic_product(
    path: Path, *, unknown_label: bool = False
) -> header.ProductAuthority:
    observable_types = ("L1", "L2", "C1", "C2", "W1", "W2", "F", "P", "T", "H")
    observable_record = f"D  {len(observable_types):3d}" + "".join(
        f" {observable:<3}" for observable in observable_types
    )
    scale_record = f"D {100:4d}  {2:2d}" + "".join(
        f" {observable:<3}" for observable in ("C1", "C2")
    )
    records = [
        line("     3.00           OBSERVATION DATA    D", "RINEX VERSION / TYPE"),
        line("DCC                 CNES                20260831 222014 UTC", "PGM / RUN BY / DATE"),
        line("SENTINEL-3A", "SATELLITE NAME"),
        line("2016-011A", "COSPAR NUMBER"),
        line("SPACEBORNE", "MARKER TYPE"),
        line("CHAIN1              DGXX                1.00", "REC # / TYPE / VERS"),
        line("DORIS               STAREC", "ANT # / TYPE"),
        line(f"{0.0:14.4f}{0.0:14.4f}{1.0:14.4f}", "APPROX POSITION XYZ"),
        line(f"{0.0:14.4f}{0.0:14.4f}{0.0:14.4f}", "CENTER OF MASS: XYZ"),
        line(observable_record, "SYS / # / OBS TYPES"),
        line(f"{10.0:10.3f}", "INTERVAL"),
        observation_time(2026, 8, "TIME OF FIRST OBS"),
        observation_time(2026, 8, "TIME OF LAST OBS"),
        line(scale_record, "SYS / SCALE FACTOR"),
        line(f"D  {0.25:14.3f}", "L2 / L1 DATE OFFSET"),
        line(f"{2:6d}", "# OF STATIONS"),
        station_reference("D01", "KRWB", "KOUROU", "97301M2101", 3, -4),
        station_reference("D02", "LAPB", "LE LAMENTIN", "97214M001", 3, 2),
        line(f"{1:6d}", "# TIME REF STATIONS"),
        line(f"{'D01':<3}{'':2s}{1.25:14.3f}{'':2s}{-0.5:14.3f}", "TIME REF STATION"),
        observation_time(2026, 8, "TIME REF STAT DATE"),
    ]
    if unknown_label:
        records.append(line("forbidden", "PRIVATE DORIS POWER"))
    records.append(line("", "END OF HEADER"))
    observation_sentinel = (
        b"> 2026 09 08 00 00 00.0000000  0  1\n"
        b"D01 SECRET_PHASE SECRET_POWER SECRET_OSCILLATOR\n"
    )
    payload = ncompress.compress("".join(records).encode("ascii") + observation_sentinel)
    path.write_bytes(payload)
    return header.ProductAuthority(
        name=path.name,
        url="https://example.invalid/development",
        bytes=len(payload),
        sha256=sha256(payload).hexdigest(),
        remote_last_modified_utc="2026-08-31T22:20:14Z",
        role="SYNTHETIC_DEVELOPMENT_HEADER_ONLY",
    )


def test_header_only_parser_exposes_physical_metadata_and_no_observation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "synthetic.Z"
    authority = synthetic_product(path)

    receipt = header.parse_exact_development_header(path, authority)

    parsed = receipt["header"]
    assert parsed["satellite_name"] == "SENTINEL-3A"
    assert parsed["cospar"] == "2016-011A"
    assert parsed["observable_types"] == [
        "L1",
        "L2",
        "C1",
        "C2",
        "W1",
        "W2",
        "F",
        "P",
        "T",
        "H",
    ]
    assert parsed["stations"][0]["station_code"] == "KRWB"
    assert parsed["stations"][0]["frequency_shift_k"] == -4
    assert receipt["qualification"]["supported_shortlist_pairs"] == [
        ["KRWB", "LAPB"]
    ]
    assert receipt["qualification"]["state"] == (
        "DORIS_DEVELOPMENT_HEADER_QUALIFIED_MEASUREMENT_UNADMITTED"
    )
    assert set(receipt["observation_access"].values()) == {0}
    assert receipt["header_boundary"]["post_header_bytes_read_from_pipe"] == 0
    assert "SECRET" not in header.strict_json(receipt)


def test_hash_and_size_are_verified_before_decompressor_resolution(
    tmp_path: Path,
) -> None:
    path = tmp_path / "synthetic.Z"
    authority = synthetic_product(path)
    wrong = replace(authority, sha256="0" * 64)

    with pytest.raises(header.DorisHeaderError, match="SHA256_CHANGED"):
        header.parse_exact_development_header(
            path,
            wrong,
            gzip_executable=str(tmp_path / "does-not-exist"),
        )


def test_unknown_header_label_is_description_error(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.Z"
    authority = synthetic_product(path, unknown_label=True)

    with pytest.raises(
        header.DorisHeaderError,
        match="DESCRIPTION_ERROR_UNKNOWN_HEADER_LABEL",
    ):
        header.parse_exact_development_header(path, authority)


def test_manifest_scope_cannot_name_or_open_candidate_day_product() -> None:
    source = inspect.getsource(header)

    assert "s3arx26245" not in source
    assert "epoch_records_read" in source
    assert "observation_records_read" in source
    assert "candidate_day_product_access" in source
    assert "requests" not in source
    assert "ftplib" not in source


def test_frozen_real_receipt_preserves_header_only_refusal() -> None:
    receipt_path = (
        Path(__file__).parents[1] / "DORIS_DEVELOPMENT_HEADER_RECEIPT.json"
    )
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

    assert receipt["outcome"] == "DORIS_DEVELOPMENT_HEADER_REJECTED"
    assert receipt["artifact"]["sha256"] == header.DEVELOPMENT_SHA256
    source_path = Path(__file__).parents[1] / "doris_development_header.py"
    assert sha256(source_path.read_bytes()).hexdigest() == receipt["parser"][
        "source_sha256"
    ]
    assert receipt["parser"]["commit"] == (
        "0da158e964372cea18d55ef26a54810d678fbda2"
    )
    assert receipt["header_boundary"]["header_sha256"] == (
        "47311d675dc0130a42676e423827bd63a4ac3b9083664c52741f5f75d185012a"
    )
    assert receipt["header_boundary"]["post_header_bytes_read_from_pipe"] == 0
    assert set(receipt["observation_access"].values()) == {0}
    assert receipt["candidate_day_product_access"] == "ZERO"
    assert receipt["ephemeral_artifact_retention"] == "ZERO_AFTER_RECEIPT"
    assert receipt["orbital_score"] == "NOT_EVALUATED"
    assert receipt["missing_predeclared_header_labels"] == [
        "INTERVAL",
        "MARKER TYPE",
        "TIME OF LAST OBS",
    ]
    assert receipt["qualification"]["supported_shortlist_pairs"] == [
        ["TLSB", "WEUC"],
        ["PAUB", "RIMC"],
    ]
