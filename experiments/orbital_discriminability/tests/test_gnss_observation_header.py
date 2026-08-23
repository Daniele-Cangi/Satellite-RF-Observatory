from __future__ import annotations

import gzip
from hashlib import sha256
from pathlib import Path

import pytest

from experiments.orbital_discriminability import gnss_observation_header as header


def line(data: str, label: str) -> str:
    return f"{data:<60}{label:<20}\n"


def synthetic_product(
    path: Path,
    marker: str = "GOLD00USA",
    *,
    include_clock_record: bool = True,
    include_last_observation: bool = True,
    last_observation: str = "  2026     8     3    23    59   30.0000000     GPS",
) -> header.ProductAuthority:
    records = [
            line("     3.04           OBSERVATION DATA    M", "RINEX VERSION / TYPE"),
            line("3.0                 COMPACT RINEX FORMAT", "CRINEX VERS   / TYPE"),
            line(marker[:4], "MARKER NAME"),
            line("12345", "MARKER NUMBER"),
            line("GEODETIC", "MARKER TYPE"),
            line("SERIAL              TEST RECEIVER       1.0", "REC # / TYPE / VERS"),
            line("ANTSERIAL           TEST ANTENNA        NONE", "ANT # / TYPE"),
            line(" -2350000.0 -4650000.0 3670000.0", "APPROX POSITION XYZ"),
            line("        0.1000        0.0000        0.0000", "ANTENNA: DELTA H/E/N"),
            line("G    6 C1C L1C S1C C2W L2W S2W", "SYS / # / OBS TYPES"),
            line("      30.000", "INTERVAL"),
            line("  2026     8     3     0     0    0.0000000     GPS", "TIME OF FIRST OBS"),
    ]
    if include_last_observation:
        records.append(line(last_observation, "TIME OF LAST OBS"))
    if include_clock_record:
        records.append(line("     0", "RCV CLOCK OFFS APPL"))
    records.append(line("", "END OF HEADER"))
    text = "".join(records).encode("ascii")
    sentinel = b"> 2026 08 03 00 00 00.0000000  0  1\nG11 SECRET_MEASUREMENT\n"
    with gzip.open(path, "wb") as stream:
        stream.write(text + sentinel)
    payload = path.read_bytes()
    return header.ProductAuthority(
        station_id=marker,
        name=path.name,
        url="https://example.invalid/frozen",
        bytes=len(payload),
        sha256=sha256(payload).hexdigest(),
    )


def test_parser_stops_at_header_and_never_represents_measurement(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.crx.gz"
    authority = synthetic_product(path)

    receipt = header.parse_exact_header(path, authority)

    assert receipt["header"]["marker_name"] == "GOLD"
    assert receipt["header"]["observable_types"]["G"] == [
        "C1C",
        "L1C",
        "S1C",
        "C2W",
        "L2W",
        "S2W",
    ]
    assert set(receipt["observation_access"].values()) == {0}
    assert "SECRET" not in header.strict_json(receipt)
    assert receipt["header_boundary"]["boundary"] == "FIRST_END_OF_HEADER_NEWLINE"


def test_hash_and_size_are_checked_before_decompression(tmp_path: Path) -> None:
    path = tmp_path / "synthetic.crx.gz"
    authority = synthetic_product(path)
    corrupted = header.ProductAuthority(
        authority.station_id,
        authority.name,
        authority.url,
        authority.bytes,
        "0" * 64,
    )

    with pytest.raises(header.HeaderAdmissionError, match="SHA256_CHANGED"):
        header.parse_exact_header(path, corrupted)


def test_missing_clock_record_uses_documented_rinex_default(tmp_path: Path) -> None:
    path = tmp_path / "default-clock.crx.gz"
    authority = synthetic_product(path, include_clock_record=False)

    receipt = header.parse_exact_header(path, authority)

    assert receipt["header"]["receiver_clock_offset_applied"] == 0
    assert receipt["header"]["receiver_clock_offset_provenance"] == (
        "RINEX_3_04_TABLE_A2_STANDARD_DEFAULT_NO"
    )


def test_unknown_header_label_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "unknown.crx.gz"
    text = "".join(
        [
            line("     3.04           OBSERVATION DATA    M", "RINEX VERSION / TYPE"),
            line("value", "PRIVATE SIGNAL POWER"),
            line("", "END OF HEADER"),
        ]
    ).encode("ascii")
    with gzip.open(path, "wb") as stream:
        stream.write(text)
    payload = path.read_bytes()
    authority = header.ProductAuthority(
        "TEST", path.name, "https://example.invalid", len(payload), sha256(payload).hexdigest()
    )

    with pytest.raises(header.HeaderAdmissionError, match="UNRECOGNIZED_HEADER_LABEL"):
        header.parse_exact_header(path, authority)


def test_pair_admission_selects_predeclared_common_signal_family(tmp_path: Path) -> None:
    left_path = tmp_path / "left.crx.gz"
    right_path = tmp_path / "right.crx.gz"
    left = header.parse_exact_header(left_path, synthetic_product(left_path, "GOLD00USA"))
    right = header.parse_exact_header(right_path, synthetic_product(right_path, "NLIB00USA"))

    result = header.admit_pair(left, right)

    assert result["state"] == "PAIR_HEADER_ADMITTED"
    assert result["chosen_signal_family"] == {
        "l1_phase": "L1C",
        "l2_phase": "L2W",
        "core_phase_observables": ["L1C", "L2W"],
        "cycle_slip_continuity_witnesses": [
            "LLI_ON_L1C",
            "LLI_ON_L2W",
            "EPOCH_CONTINUITY",
        ],
        "same_path_code_witnesses": ["C1C", "C2W"],
        "optional_signal_strength_diagnostics": ["S1C", "S2W"],
    }
    assert result["measurement_values_accessed"] == 0


def test_pair_admission_does_not_make_signal_strength_core(tmp_path: Path) -> None:
    left_path = tmp_path / "left.crx.gz"
    right_path = tmp_path / "right.crx.gz"
    left = header.parse_exact_header(left_path, synthetic_product(left_path, "GOLD00USA"))
    right = header.parse_exact_header(right_path, synthetic_product(right_path, "NLIB00USA"))
    right["header"]["observable_types"]["G"].remove("S2W")

    result = header.admit_pair(left, right)

    assert result["state"] == "PAIR_HEADER_ADMITTED"
    assert result["chosen_signal_family"]["optional_signal_strength_diagnostics"] == [
        "S1C"
    ]


def test_time_of_last_observation_is_required(tmp_path: Path) -> None:
    path = tmp_path / "missing-last.crx.gz"
    authority = synthetic_product(path, include_last_observation=False)

    with pytest.raises(
        header.HeaderAdmissionError,
        match="MISSING_REQUIRED_HEADER_FIELDS:time_of_last_observation",
    ):
        header.parse_exact_header(path, authority)


def test_pair_admission_requires_complete_frozen_window_coverage(tmp_path: Path) -> None:
    left_path = tmp_path / "left.crx.gz"
    right_path = tmp_path / "right.crx.gz"
    left = header.parse_exact_header(left_path, synthetic_product(left_path, "GOLD00USA"))
    right = header.parse_exact_header(
        right_path,
        synthetic_product(
            right_path,
            "NLIB00USA",
            last_observation="  2026     8     3    12     0    0.0000000     GPS",
        ),
    )

    result = header.admit_pair(left, right)

    assert result["state"] == "PAIR_HEADER_REJECTED"
    assert "FROZEN_WINDOW_NOT_COVERED:NLIB00USA" in result["refusals"]


def test_parser_manifest_binds_authorities_and_forbidden_surface() -> None:
    manifest = header.parser_manifest()

    assert [row["sha256"] for row in manifest["authorities"]] == [
        header.GOLD_AUTHORITY.sha256,
        header.NLIB_AUTHORITY.sha256,
    ]
    assert "epoch record decoding" in manifest["forbidden"]
    assert manifest["post_boundary_policy"].startswith("COUNT_AND_STRUCTURALLY_DISCARD")
    assert len(header.parser_manifest_sha256()) == 64
