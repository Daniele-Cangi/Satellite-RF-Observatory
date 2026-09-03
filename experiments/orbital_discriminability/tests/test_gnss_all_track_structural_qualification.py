from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.orbital_discriminability import (
    gnss_all_track_structural_qualification as qualification,
)


SIX_TRACKS = ("G05", "G15", "G18", "G20", "G21", "G29")
SECRET = "987654321.123"
OUTCOME = (
    Path(__file__).resolve().parents[1]
    / "GNSS_ALL_TRACK_QUALIFICATION_OUTCOME.json"
)


def header_line(data: str, label: str) -> str:
    return f"{data:<60}{label:<20}\n"


def field(value: str | None, lli: str = " ") -> str:
    if value is None:
        return " " * 16
    return f"{value:>14}{lli} "


def fixture(
    *,
    satellites: tuple[str, ...] = SIX_TRACKS,
    blank: tuple[int, str, str] | None = None,
    lli: tuple[int, str, str] | None = None,
    code_blank: tuple[int, str, str] | None = None,
    epoch_flag: tuple[int, int] | None = None,
    antenna_model: str = qualification.EXPECTED_ANTENNA_TYPE,
    antenna_radome: str = qualification.EXPECTED_RADOME,
) -> bytearray:
    observables = ("C1C", "L1C", "C2W", "L2W", "D1C", "S1C")
    lines = [
        header_line(
            "     3.04           OBSERVATION DATA    M",
            "RINEX VERSION / TYPE",
        ),
        header_line("ALGO", "MARKER NAME"),
        header_line(
            f"SERIAL              {qualification.EXPECTED_RECEIVER_TYPE:<20}"
            f"{qualification.EXPECTED_RECEIVER_VERSION:<20}",
            "REC # / TYPE / VERS",
        ),
        header_line(
            f"{'ANTENNA':<20}{antenna_model:<16}{antenna_radome:<4}",
            "ANT # / TYPE",
        ),
        header_line(" 918129.0 -4346071.0 4561977.0", "APPROX POSITION XYZ"),
        header_line("G    6 C1C L1C C2W L2W D1C S1C", "SYS / # / OBS TYPES"),
        header_line("      30.000", "INTERVAL"),
        header_line(
            "  2026     8    17     0     0    0.0000000     GPS",
            "TIME OF FIRST OBS",
        ),
        header_line(
            "  2026     8    17    23    59   30.0000000     GPS",
            "TIME OF LAST OBS",
        ),
        header_line("", "END OF HEADER"),
    ]
    for index, epoch in enumerate(qualification.expected_epochs()):
        flag = epoch_flag[1] if epoch_flag and epoch_flag[0] == index else 0
        lines.append(
            f"> {epoch.year:4d} {epoch.month:02d} {epoch.day:02d} "
            f"{epoch.hour:02d} {epoch.minute:02d} {float(epoch.second):10.7f}  "
            f"{flag:d} {len(satellites):2d}\n"
        )
        for satellite in satellites:
            fields = []
            for observable in observables:
                is_blank = blank == (index, satellite, observable)
                is_blank = is_blank or code_blank == (index, satellite, observable)
                lli_token = "1" if lli == (index, satellite, observable) else " "
                fields.append(field(None if is_blank else SECRET, lli_token))
            lines.append(satellite + "".join(fields) + "\n")
    return bytearray("".join(lines).encode("ascii"))


def scan_fixture(**kwargs) -> qualification.StructuralScan:
    return qualification.scan_decoded(fixture(**kwargs))


def test_exact_six_complete_tracks_pass_without_prn_in_structure() -> None:
    scan = scan_fixture()
    try:
        structure = qualification.evaluate(scan)
        encoded = qualification.strict_json(structure)
    finally:
        scan.erase()

    assert structure["outcome"] == "GNSS_ALL_TRACK_STRUCTURAL_QUALIFICATION_PASSED"
    assert structure["complete_track_count"] == 6
    assert structure["complete_opaque_tracks"] == [
        "T001", "T002", "T003", "T004", "T005", "T006"
    ]
    assert not any(prn in encoded for prn in SIX_TRACKS)
    assert SECRET not in encoded
    assert '"value"' not in encoded


def test_seventh_complete_track_fails_without_posthoc_removal() -> None:
    scan = scan_fixture(satellites=SIX_TRACKS + ("G31",))
    try:
        structure = qualification.evaluate(scan)
    finally:
        scan.erase()

    assert structure["outcome"] == "GNSS_ALL_TRACK_STRUCTURAL_QUALIFICATION_FAILED"
    assert structure["complete_track_count"] == 7
    assert structure["count_clause"] == "UNSATISFIED"


def test_missing_core_and_nonzero_lli_break_segments_without_bridging() -> None:
    missing = scan_fixture(blank=(50, "G05", "L1C"))
    slipped = scan_fixture(lli=(80, "G15", "L2W"))
    try:
        missing_structure = qualification.evaluate(missing)
        slipped_structure = qualification.evaluate(slipped)
    finally:
        missing.erase()
        slipped.erase()

    missing_track = missing_structure["track_summaries"][0]
    slipped_track = slipped_structure["track_summaries"][1]
    assert [row["epoch_count"] for row in missing_track["maximal_core_segments"]] == [50, 88]
    assert [row["epoch_count"] for row in slipped_track["maximal_core_segments"]] == [80, 58]
    assert missing_structure["complete_track_count"] == 5
    assert slipped_structure["complete_track_count"] == 5


def test_same_path_code_blank_is_descriptive_not_fatal() -> None:
    scan = scan_fixture(code_blank=(20, "G18", "C2W"))
    try:
        structure = qualification.evaluate(scan)
    finally:
        scan.erase()

    assert structure["outcome"] == "GNSS_ALL_TRACK_STRUCTURAL_QUALIFICATION_PASSED"
    witness = next(
        row
        for row in structure["same_path_code_witness"]["tracks"]
        if row["opaque_track"] == "T003" and row["observable"] == "C2W"
    )
    assert witness["present_epochs"] == qualification.EPOCH_COUNT - 1
    assert witness["role"] == "DESCRIPTIVE_NOT_FATAL"


def test_nonzero_epoch_flag_prevents_qualification() -> None:
    scan = scan_fixture(epoch_flag=(30, 1))
    try:
        structure = qualification.evaluate(scan)
    finally:
        scan.erase()

    assert structure["epoch_grid_complete"] is False
    assert structure["outcome"] == "GNSS_ALL_TRACK_STRUCTURAL_QUALIFICATION_FAILED"
    assert any(issue["reason"] == "EPOCH_FLAG_NOT_ZERO_1" for issue in structure["parser_issues"])


def test_reveal_is_bound_to_prior_structural_hash_and_cannot_rescue() -> None:
    scan = scan_fixture()
    try:
        structure = qualification.evaluate(scan)
        structural_hash = "a" * 64
        reveal = qualification.reveal_after_structural_hash(scan, structural_hash)
    finally:
        scan.erase()

    assert structure["prn_identity"] == "SEALED_UNTIL_THIS_RECEIPT_IS_HASHED"
    assert reveal["structural_receipt_sha256_before_reveal"] == structural_hash
    assert reveal["codebook_relation"] == "CONCORDANT"
    assert reveal["membership_changed_by_reveal"] is False
    assert reveal["qualification_rescued_by_reveal"] is False


def test_manifest_is_bounded_and_selection_is_hash_bound() -> None:
    root = Path(qualification.__file__).resolve().parent
    manifest = qualification.manifest()
    selection = qualification.verify_frozen_selection(root)

    assert selection["primary_selected"] is False
    assert manifest["product"]["name"] == qualification.PRODUCT_NAME
    assert manifest["post_complete_hash_retry"] == 0
    assert manifest["antenna_record_semantics"] == {
        "rinex_format": "2A20_ANTENNA_NUMBER_AND_TYPE",
        "igs_type_partition": "A16_MODEL_PLUS_A4_RADOME",
        "specification": "RINEX_3_04_TABLE_A2",
    }
    assert "Doppler or signal-strength field reads" in manifest["forbidden"]
    assert manifest["selection_receipt_canonical_sha256"] == (
        qualification.canonical_file_sha256(root / qualification.SELECTION_NAME)
    )


def test_failure_kinds_do_not_become_physical_scores() -> None:
    materialization = qualification._failure_outcome(
        "QUALIFICATION_ARTIFACT_MATERIALIZATION_FAILED", "TIMEOUT"
    )
    description = qualification._failure_outcome(
        "QUALIFICATION_DESCRIPTION_ERROR", "HEADER_CHANGED"
    )

    for receipt in (materialization, description):
        assert receipt["structure"] == "NOT_EVALUATED"
        assert receipt["measurement_admission"] == "NOT_EVALUATED"
        assert receipt["orbital_score"] == "NOT_EVALUATED"
        assert receipt["primary_selection"] == "NOT_EVALUATED"
        assert receipt["observation_values_persisted"] == 0


def test_recorded_description_error_preserves_physical_nondecision() -> None:
    receipt = json.loads(OUTCOME.read_text(encoding="utf-8"))

    assert receipt["outcome"] == "QUALIFICATION_DESCRIPTION_ERROR"
    assert receipt["reason"] == "ANTENNA_TYPE_CHANGED"
    assert receipt["artifact"]["complete_file_bytes"] == 4_317_738
    assert receipt["artifact"]["complete_file_sha256"] == (
        "88aa876b787cac583345d512b2f705ec19062a5f71c38c3a4ae0da45f8095f24"
    )
    assert receipt["structure"] == "NOT_EVALUATED"
    assert receipt["measurement_admission"] == "NOT_EVALUATED"
    assert receipt["orbital_score"] == "NOT_EVALUATED"
    assert receipt["primary_selection"] == "NOT_EVALUATED"
    assert receipt["observation_values_parsed"] == 0
    assert receipt["observation_values_persisted"] == 0
    assert receipt["observation_artifact_bytes_persisted"] == 0


def test_rinex_antenna_record_uses_two_a20_and_igs_model_radome_partition() -> None:
    parsed = qualification.headers.parse_antenna_two_a20(
        f"{'725235':<20}{'LEIAR25.R4':<16}{'NONE':<4}" + " " * 20
    )

    assert parsed == {
        "serial": "725235",
        "type_field": "LEIAR25.R4      NONE",
        "model": "LEIAR25.R4",
        "radome": "NONE",
        "rinex_format": "2A20_ANTENNA_NUMBER_AND_TYPE",
        "igs_type_partition": "A16_MODEL_PLUS_A4_RADOME",
    }


def test_third_a20_receiver_shape_is_rejected_for_antenna() -> None:
    invalid = f"{'ANTENNA':<20}{qualification.EXPECTED_ANTENNA_TYPE:<20}{'NONE':<20}"

    try:
        qualification.headers.parse_antenna_two_a20(invalid)
    except qualification.headers.HeaderAdmissionError as exc:
        assert str(exc) == "ANTENNA_RECORD_EXCEEDS_2A20"
    else:  # pragma: no cover - protects the specification boundary
        raise AssertionError("receiver-shaped antenna record was accepted")


def test_description_error_retains_observed_and_expected_antenna_model() -> None:
    try:
        qualification.scan_decoded(fixture(antenna_model="WRONG_MODEL"))
    except qualification.DescriptionError as exc:
        reason = str(exc)
    else:  # pragma: no cover - protects typed failure attribution
        raise AssertionError("mismatched antenna model was accepted")

    assert reason == (
        "ANTENNA_TYPE_CHANGED:OBSERVED=WRONG_MODEL:EXPECTED=AOAD/M_T"
    )


def test_repaired_parser_cannot_overwrite_or_repeat_frozen_execution() -> None:
    root = Path(qualification.__file__).resolve().parent

    with pytest.raises(
        qualification.DescriptionError,
        match="QUALIFICATION_EXECUTION_ALREADY_RECORDED",
    ):
        qualification.run_once(root)
