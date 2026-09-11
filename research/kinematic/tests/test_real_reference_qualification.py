"""Offline boundaries for the bounded real-reference qualification."""
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest

from research.kinematic.phase_bridge_study import PHASE_TYPES, phase_fixture_texts
from research.kinematic.real_reference_qualification import (
    _native,
    scan_reference_structure,
    strip_target_observations,
    validate_plan,
)


ROOT = Path(__file__).resolve().parents[3]
PLAN = json.loads((ROOT / "research/kinematic/real_reference_qualification_plan.json").read_text())
PLAN_V2 = json.loads((ROOT / "research/kinematic/real_reference_qualification_plan_v2.json").read_text())


def _fixture_with_last():
    observations, _ = phase_fixture_texts()
    rows = observations.splitlines()
    end = next(i for i, row in enumerate(rows) if row[60:80].strip() == "END OF HEADER")
    last = f"  2026     9    10    12     0   30.0000000     GPS{'':9}TIME OF LAST OBS"
    rows.insert(end, last)
    return "\n".join(rows) + "\n"


def _fixture_plan():
    plan = deepcopy(PLAN)
    plan["date_gpst"] = "2026-09-10"
    plan["day_of_year"] = 253
    plan["reserved_target"] = "G08"
    plan["observation"]["required_first_epoch_s"] = 42870.0
    plan["observation"]["required_last_epoch_s"] = 43230.0
    plan["stations"] = [{
        "id": "SYN0",
        "expected_receiver": ["SYNTHETIC-001", "INERTIAL-GENERATOR", "1"],
    }]
    return plan


def test_frozen_plan_is_valid_and_has_two_exact_terminals():
    validate_plan(PLAN)
    assert set(PLAN["outcomes"]) == {
        "REFERENCE_PHASE_PATH_QUALIFIED", "PHYSICAL_ERROR_ENVELOPE_NOT_SUPPORTED"
    }
    assert PLAN["selection"]["no_reselection_after_numeric_access"]


def test_repaired_plan_has_typed_execution_terminal_and_no_marker_gate():
    validate_plan(PLAN_V2)
    assert set(PLAN_V2["outcomes"]) == {
        "REFERENCE_PHASE_PATH_QUALIFIED",
        "PHYSICAL_ERROR_ENVELOPE_NOT_SUPPORTED",
        "QUALIFICATION_EXECUTION_INVALID",
    }
    assert "descriptive metadata" in PLAN_V2["observation"]["marker_type_policy"]


def test_structure_scan_reads_presence_but_never_target_fields():
    content = _fixture_with_last()
    plan = _fixture_plan()
    structure = scan_reference_structure(content, plan=plan, station_plan=plan["stations"][0])
    assert structure["epoch_count"] == 13
    assert structure["target_rows_discarded_without_field_access"] == 13
    assert structure["eligible"][42870.0] == {"G01", "G02", "G03", "G04"}
    poisoned = content.replace("TARGET PAYLOAD MUST NEVER BE DECODED", "nan inf 1e999 SECRET")
    changed = scan_reference_structure(poisoned, plan=plan, station_plan=plan["stations"][0])
    assert changed["eligible"] == structure["eligible"]


def test_marker_type_is_descriptive_not_an_epistemic_gate():
    content = _fixture_with_last().replace("GEODETIC                                                    MARKER TYPE", "NON_GEODETIC                                                MARKER TYPE")
    plan = _fixture_plan()
    structure = scan_reference_structure(content, plan=plan, station_plan=plan["stations"][0])
    assert structure["reported_marker_type"] == "NON_GEODETIC"
    assert structure["epoch_count"] == 13


def test_target_rows_are_removed_before_numeric_parser_boundary():
    content = _fixture_with_last()
    stripped, count = strip_target_observations(content, "G08")
    assert count == 13
    assert "TARGET PAYLOAD" not in stripped
    for line in stripped.splitlines():
        assert not line.startswith("G08")
    epoch = next(line for line in stripped.splitlines() if line.startswith(">"))
    assert epoch.split()[8] == "4"


@pytest.mark.parametrize("case", ["missing_last", "wrong_last", "receiver_change"])
def test_full_header_coverage_and_receiver_identity_are_fatal(case):
    content = _fixture_with_last()
    plan = _fixture_plan()
    if case == "missing_last":
        content = "\n".join(row for row in content.splitlines() if row[60:80].strip() != "TIME OF LAST OBS") + "\n"
    elif case == "wrong_last":
        content = content.replace("12     0   30.0000000", "11    59   30.0000000")
    else:
        plan["stations"][0]["expected_receiver"][2] = "2"
    with pytest.raises(ValueError):
        scan_reference_structure(content, plan=plan, station_plan=plan["stations"][0])


def test_missing_phase_and_nonzero_lli_remove_reference_structurally():
    content = _fixture_with_last()
    rows = content.splitlines()
    index = next(i for i, row in enumerate(rows) if row.startswith("G01"))
    start = 3 + 16 * PHASE_TYPES.index("L1C")
    rows[index] = rows[index][:start] + " " * 16 + rows[index][start + 16:]
    changed = "\n".join(rows) + "\n"
    plan = _fixture_plan()
    structure = scan_reference_structure(changed, plan=plan, station_plan=plan["stations"][0])
    assert "G01" not in structure["eligible"][42870.0]

    rows = content.splitlines()
    index = next(i for i, row in enumerate(rows) if row.startswith("G01"))
    field = rows[index][start:start + 16].ljust(16)
    rows[index] = rows[index][:start] + field[:14] + "1" + field[15:] + rows[index][start + 16:]
    structure = scan_reference_structure("\n".join(rows) + "\n", plan=plan, station_plan=plan["stations"][0])
    assert "G01" not in structure["eligible"][42870.0]


def test_receipt_conversion_rejects_nonfinite_and_converts_numpy_scalars():
    assert _native({"ok": np.bool_(True), "count": np.int64(3)}) == {"ok": True, "count": 3}
    for value in (np.nan, np.inf, -np.inf):
        with pytest.raises(ValueError, match="non-finite"):
            _native({"bad": value})
