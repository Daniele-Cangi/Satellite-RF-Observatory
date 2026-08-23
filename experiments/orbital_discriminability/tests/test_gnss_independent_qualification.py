from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    gnss_independent_qualification as qualification,
)


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / qualification.PLAN_NAME


def header_line(data: str, label: str) -> str:
    return f"{data:<60}{label:<20}\n"


def split_fields(values: dict[str, tuple[float | None, int]]) -> str:
    fields = []
    for observable in CURRENT_OBSERVABLES:
        value, lli = values[observable]
        if value is None:
            fields.append(" " * 16)
        else:
            fields.append(f"{value:14.3f}{' ' if lli == 0 else lli} ")
    return "".join(fields)


CURRENT_OBSERVABLES = qualification.RELEVANT_OBSERVABLES


def plain_fixture(
    authority,
    *,
    observables: tuple[str, ...] | None = None,
    blank: tuple[int, str, str] | None = None,
    nonzero_lli: tuple[int, str, str] | None = None,
    phase_jump: tuple[int, str] | None = None,
    omit_final: tuple[int, str] | None = None,
    omit_last_header: bool = False,
) -> bytearray:
    global CURRENT_OBSERVABLES
    CURRENT_OBSERVABLES = observables or qualification.RELEVANT_OBSERVABLES
    config = qualification.FROZEN_CONFIGURATION[authority.station_id]
    receiver = config["receiver"]
    antenna = config["antenna"]
    lines = [
        header_line("     3.04           OBSERVATION DATA    G", "RINEX VERSION / TYPE"),
        header_line(authority.station_id[:4], "MARKER NAME"),
        header_line(
            f"{receiver['serial']:<20}{receiver['type']:<20}{receiver['version_or_radome']:<20}",
            "REC # / TYPE / VERS",
        ),
        header_line(
            f"{antenna['serial']:<20}{antenna['type']:<20}{antenna['version_or_radome']:<20}",
            "ANT # / TYPE",
        ),
        header_line(" -2350000.0 -4650000.0 3670000.0", "APPROX POSITION XYZ"),
        header_line(
            f"G  {len(CURRENT_OBSERVABLES):3d} "
            + "".join(f"{item:>3} " for item in CURRENT_OBSERVABLES),
            "SYS / # / OBS TYPES",
        ),
        header_line("      30.000", "INTERVAL"),
        header_line("  2026     8     2     0     0    0.0000000     GPS", "TIME OF FIRST OBS"),
    ]
    if not omit_last_header:
        lines.append(
            header_line(
                "  2026     8     2    23    59   30.0000000     GPS",
                "TIME OF LAST OBS",
            )
        )
    lines.append(header_line("", "END OF HEADER"))
    for epoch_index, epoch in enumerate(qualification.expected_epochs()):
        lines.append(
            f"> {epoch.year:4d} {epoch.month:02d} {epoch.day:02d} {epoch.hour:02d} "
            f"{epoch.minute:02d} {epoch.second:10.7f}  0  2\n"
        )
        for sat_index, satellite in enumerate(qualification.SATELLITES):
            values: dict[str, tuple[float | None, int]] = {}
            for observable in CURRENT_OBSERVABLES:
                if observable.startswith("C"):
                    value = 22_000_000.0 + epoch_index + sat_index * 10.0
                elif observable == "L1C":
                    value = 115_000_000.0 + epoch_index * 0.02 + sat_index
                elif observable == "L2W":
                    value = 89_000_000.0 + epoch_index * 0.015 + sat_index
                else:
                    value = 45.0
                if phase_jump == (epoch_index, satellite) and observable == "L1C":
                    value += 1.0
                values[observable] = (value, 0)
            if blank and blank[:2] == (epoch_index, satellite):
                values[blank[2]] = (None, 0)
            if nonzero_lli and nonzero_lli[:2] == (epoch_index, satellite):
                value, _ = values[nonzero_lli[2]]
                values[nonzero_lli[2]] = (value, 1)
            record = satellite + split_fields(values)
            if omit_final == (epoch_index, satellite):
                record = record[:-16]
            lines.append(record + "\n")
    return bytearray("".join(lines).encode("ascii"))


def scans(**left_kwargs):
    left_payload = plain_fixture(qualification.GOLD_PRODUCT, **left_kwargs)
    right_payload = plain_fixture(qualification.NLIB_PRODUCT)
    left = qualification.scan_plain_station(left_payload, qualification.GOLD_PRODUCT)
    right = qualification.scan_plain_station(right_payload, qualification.NLIB_PRODUCT)
    return left, right


def test_complete_structural_coverage_and_full_joint_segment_pass() -> None:
    left, right = scans()
    try:
        summary = qualification.evaluate_scans((left, right))
    finally:
        left.erase()
        right.erase()

    assert len(left.coverage) == qualification.RAW_EPOCHS * 2 * 6
    assert summary["structural_counts"]["PRESENT"] == (
        qualification.RAW_EPOCHS * 2 * 6 * 2
    )
    assert summary["joint_maximal_segments"] == [
        {
            "start_gps": "2026-08-02T10:05:30.000000Z",
            "stop_gps": "2026-08-02T13:18:00.000000Z",
            "epoch_count": 386,
            "duration_s": 11550.0,
        }
    ]
    assert summary["outcome"] == "GNSS_INDEPENDENT_QUALIFICATION_PASSED"


def test_optional_signal_strength_may_be_undeclared_and_is_never_fatal() -> None:
    observables = qualification.CORE_PHASE + qualification.SAME_PATH_CODE
    left, right = scans(observables=observables)
    try:
        summary = qualification.evaluate_scans((left, right))
        optional = [
            row for row in left.coverage if row["observable"] in {"S1C", "S2W"}
        ]
    finally:
        left.erase()
        right.erase()

    assert {row["state"] for row in optional} == {"BLANK"}
    assert {row["source_line_class"] for row in optional} == {
        "OBSERVABLE_NOT_DECLARED_OPTIONAL"
    }
    assert summary["outcome"] == "GNSS_INDEPENDENT_QUALIFICATION_PASSED"


def test_missing_core_phase_breaks_without_gap_bridging() -> None:
    left, right = scans(blank=(100, "G11", "L2W"))
    try:
        summary = qualification.evaluate_scans((left, right))
    finally:
        left.erase()
        right.erase()

    segments = summary["per_link_maximal_segments"][0]["segments"]
    assert [segment["epoch_count"] for segment in segments] == [100, 285]
    assert summary["full_joint_window"] is False
    assert summary["outcome"] == "GNSS_INDEPENDENT_QUALIFICATION_FAILED"


def test_nonzero_lli_breaks_core_segment() -> None:
    left, right = scans(nonzero_lli=(200, "G21", "L1C"))
    try:
        summary = qualification.evaluate_scans((left, right))
    finally:
        left.erase()
        right.erase()

    assert summary["outcome"] == "GNSS_INDEPENDENT_QUALIFICATION_FAILED"
    row = next(
        row for row in left.coverage
        if row["gps_epoch"] == qualification.structural.format_gps_epoch(
            qualification.expected_epochs()[200]
        ) and row["satellite"] == "G21" and row["observable"] == "L1C"
    )
    assert row["lli_state"] == "NONZERO"


def test_geometry_free_violation_fails_preselected_window_without_reselection() -> None:
    left, right = scans(phase_jump=(150, "G11"))
    try:
        summary = qualification.evaluate_scans((left, right))
    finally:
        left.erase()
        right.erase()

    assert summary["full_joint_window"] is True
    assert summary["geometry_free_phase_continuity"]["state"] == "UNSATISFIED"
    assert summary["segment_selection"].startswith("FULL_PREDECLARED_WINDOW_OR_FAIL")
    assert summary["outcome"] == "GNSS_INDEPENDENT_QUALIFICATION_FAILED"


def test_code_witness_is_not_fatal_at_every_epoch() -> None:
    left, right = scans(blank=(100, "G11", "C1C"))
    try:
        summary = qualification.evaluate_scans((left, right))
    finally:
        left.erase()
        right.erase()

    assert summary["same_path_code_witness"]["state"] == "SATISFIED"
    assert summary["outcome"] == "GNSS_INDEPENDENT_QUALIFICATION_PASSED"


def test_code_witness_frozen_partition_boundary_is_fatal() -> None:
    left, right = scans(blank=(77, "G11", "C1C"))
    try:
        summary = qualification.evaluate_scans((left, right))
    finally:
        left.erase()
        right.erase()

    assert summary["same_path_code_witness"]["state"] == "UNSATISFIED"
    assert summary["outcome"] == "GNSS_INDEPENDENT_QUALIFICATION_FAILED"


def test_trailing_field_omission_is_classified_without_value_persistence() -> None:
    observables = ("L1C", "L2W", "C1C", "S1C", "S2W", "C2W")
    payload = plain_fixture(
        qualification.GOLD_PRODUCT,
        observables=observables,
        omit_final=(20, "G11"),
    )
    scan = qualification.scan_plain_station(payload, qualification.GOLD_PRODUCT)
    try:
        row = next(
            row for row in scan.coverage
            if row["gps_epoch"] == qualification.structural.format_gps_epoch(
                qualification.expected_epochs()[20]
            ) and row["satellite"] == "G11" and row["observable"] == "C2W"
        )
    finally:
        scan.erase()

    assert row["state"] == "TRAILING_FIELD_OMITTED"
    assert "value" not in row


def test_time_of_last_observation_is_required_for_qualification() -> None:
    payload = plain_fixture(qualification.GOLD_PRODUCT, omit_last_header=True)

    with pytest.raises(Exception, match="time_of_last_observation"):
        qualification.scan_plain_station(payload, qualification.GOLD_PRODUCT)


def test_plan_freezes_no_primary_and_exact_products() -> None:
    plan = PLAN.read_text(encoding="utf-8")

    assert "FROZEN_BEFORE_OBSERVATION_RECORD_ACCESS" in plan
    assert qualification.GOLD_PRODUCT.sha256 in plan
    assert qualification.NLIB_PRODUCT.sha256 in plan
    assert "does not select a primary" in plan
    assert "`S1C`, `S2W`" in plan
    assert "Never fatal" in plan


def test_no_orbital_surface_enters_summary() -> None:
    left, right = scans()
    try:
        summary = qualification.evaluate_scans((left, right))
        encoded = qualification.strict_json(summary)
    finally:
        left.erase()
        right.erase()

    assert summary["orbital_scores_produced"] == 0
    assert "trajectory" not in encoded.lower()
    assert "doppler" not in encoded.lower()
    assert np.all(left.phase_cycles == 0.0)
