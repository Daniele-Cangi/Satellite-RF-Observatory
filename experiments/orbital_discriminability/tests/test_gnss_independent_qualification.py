from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from experiments.orbital_discriminability import gnss_independent_qualification as q
from experiments.orbital_discriminability import gnss_observation_header as headers


OBSERVABLES = ("C1C", "C2W", "L1C", "L2W", "S1C", "S2W")


def header_line(data: str, label: str) -> str:
    return f"{data:<60}{label:<20}\n"


def opaque_field(token: str = "NOT_A_NUMBER") -> str:
    return f"{token:<14}  "


def structural_fixture(
    epochs: tuple[datetime, ...], *, missing: tuple[int, str, str] | None = None
) -> bytearray:
    declared = OBSERVABLES + ("D1C", "D2W")
    lines = [
        header_line("     3.04           OBSERVATION DATA    M", "RINEX VERSION / TYPE"),
        header_line(
            f"G  {len(declared):3d} " + "".join(f"{item:>3} " for item in declared),
            "SYS / # / OBS TYPES",
        ),
        header_line("", "END OF HEADER"),
    ]
    for epoch_index, epoch in enumerate(epochs):
        lines.append(
            f"> {epoch.year:4d} {epoch.month:02d} {epoch.day:02d} "
            f"{epoch.hour:02d} {epoch.minute:02d} {epoch.second:10.7f}  0  2\n"
        )
        for satellite in q.TARGETS:
            fields = []
            for observable in OBSERVABLES:
                absent = missing == (epoch_index, satellite, observable)
                fields.append(" " * 16 if absent else opaque_field("SECRET_VALUE"))
            # The two final declared fields are deliberately unserialized.  The
            # decoder-native rule treats them as absent trailing fields.
            lines.append(satellite + "".join(fields[:4]) + "\n")
            lines.append("   " + "".join(fields[4:]) + "\n")
    return bytearray("".join(lines).encode("ascii"))


def epochs(count: int = 3, *, gap_after: int | None = None) -> tuple[datetime, ...]:
    start = datetime(2026, 8, 2, 15, 41, tzinfo=timezone.utc)
    result = []
    elapsed = 0
    for index in range(count):
        result.append(start + timedelta(seconds=elapsed))
        elapsed += 60 if gap_after == index else 30
    return tuple(result)


def authority() -> headers.ProductAuthority:
    return headers.ProductAuthority(
        station_id="SYNTH",
        name="synthetic.crx.gz",
        url="https://example.invalid/synthetic",
        bytes=1,
        sha256="0" * 64,
    )


def test_parser_is_value_blind_and_accepts_continuations_and_trailing_blanks() -> None:
    result = q.parse_decompressed_structure(
        structural_fixture(epochs()), authority(), OBSERVABLES
    )

    assert result.summary["epoch_records"] == 3
    assert result.summary["continuation_lines"] == 6
    assert result.summary["records_with_unserialized_trailing_declared_fields"] == 6
    assert result.summary["structurally_usable_target_epochs"] == 3
    assert result.summary["value_blindness"]["numeric_observation_values_decoded"] == 0
    assert "SECRET_VALUE" not in q.strict_json(result.summary)


def test_blank_required_field_is_absent_without_numeric_interpretation() -> None:
    result = q.parse_decompressed_structure(
        structural_fixture(epochs(), missing=(1, "G20", "L2W")),
        authority(),
        OBSERVABLES,
    )

    assert result.summary["selected_field_presence_counts"]["G20"]["L2W"] == 2
    assert result.summary["structurally_usable_target_epochs"] == 2


def test_final_field_may_omit_blank_lli_and_ssi_at_end_of_line() -> None:
    fixture = structural_fixture(epochs(2))
    # Strip the two optional indicator blanks from each continuation line,
    # matching the exact Hatanaka 2.8.1 output seen in qualification.
    fixture = bytearray(
        b"\n".join(
            line[:-2] if line.startswith(b"   SECRET_VALUE") else line
            for line in bytes(fixture).split(b"\n")
        )
    )

    result = q.parse_decompressed_structure(fixture, authority(), OBSERVABLES)

    assert result.summary["structurally_usable_target_epochs"] == 2


def test_gap_is_capability_rejection_not_qualification_error() -> None:
    with pytest.raises(q.CapabilityRejected, match="NON_30S_OR_GAPPED"):
        q.parse_decompressed_structure(
            structural_fixture(epochs(gap_after=0)), authority(), OBSERVABLES
        )


def test_invalid_record_is_qualification_error_not_capability_rejection() -> None:
    fixture = structural_fixture(epochs(1))
    marker = fixture.find(b"G20")
    fixture[marker : marker + 3] = b"???"

    with pytest.raises(q.QualificationError, match="INVALID_SATELLITE_RECORD"):
        q.parse_decompressed_structure(fixture, authority(), OBSERVABLES)


def test_artifact_hash_is_checked_before_hatanaka(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "synthetic.crx.gz"
    path.write_bytes(b"wrong")
    bad = headers.ProductAuthority(
        "SYNTH", path.name, "https://example.invalid", 5, "0" * 64
    )
    called = False

    def forbidden(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("decoder must not be called")

    monkeypatch.setattr(q.hatanaka, "decompress", forbidden)
    with pytest.raises(headers.HeaderAdmissionError, match="SHA256_CHANGED"):
        q.decode_exact_structure(path, bad, OBSERVABLES)
    assert called is False


def test_longest_contiguous_run_uses_exact_30_second_adjacency() -> None:
    start = datetime(2026, 8, 2, tzinfo=timezone.utc)
    values = {
        start,
        start + timedelta(seconds=30),
        start + timedelta(seconds=90),
        start + timedelta(seconds=120),
        start + timedelta(seconds=150),
    }
    run = q.longest_contiguous_run(values, 30.0)
    assert run == (
        start + timedelta(seconds=90),
        start + timedelta(seconds=120),
        start + timedelta(seconds=150),
    )


def test_manifest_keeps_primary_access_and_value_decoding_forbidden() -> None:
    manifest = q.qualification_manifest()
    assert q.PRIMARY_REQUIRED_RECORDS == 380
    assert "DOY_215_PRIMARY_ACCESS" in manifest["forbidden"]
    assert "NUMERIC_OBSERVATION_CONVERSION" in manifest["forbidden"]
    assert [item["sha256"] for item in manifest["authorities"]] == [
        "06db32b758483448fa4420758a0783a1ede144e6812e794f2b5311aeef0547c0",
        "3e1a55a4be23ec5a6b7c62589366f444cd0d3777a9a7ad37daad4757e28dfae2",
    ]
    q.strict_json(manifest)


def test_frozen_real_receipt_keeps_primary_sealed() -> None:
    path = Path(q.__file__).with_name("GNSS_INDEPENDENT_QUALIFICATION_RECEIPT.json")
    receipt = json.loads(path.read_text(encoding="ascii"))

    assert receipt["outcome"] == q.OUTCOME_ADMITTED
    assert receipt["longest_common_continuous_run"]["records"] == 493
    assert receipt["primary_requirement"]["records"] == 380
    assert receipt["measurement_access"]["numeric_observation_values_decoded"] == 0
    assert receipt["measurement_access"]["decompressed_rinex_persisted_bytes"] == 0
    assert receipt["measurement_access"]["primary_payload_bytes_opened"] == 0
    assert receipt["primary_access_authorized"] is False
    assert receipt["prospective_plan_frozen"] is False
    assert all(not item["payload_opened"] for item in receipt["primary_products"])
