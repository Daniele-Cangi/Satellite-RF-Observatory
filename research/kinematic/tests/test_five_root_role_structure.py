"""Offline boundaries for role-specific five-root structural qualification."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pytest

from research.kinematic.five_root_role_structure import (
    _audit_code_header,
    admit_archive_age,
    scan_structure,
    validate_plan,
)
from research.kinematic.phase_bridge_study import PHASE_TYPES, phase_fixture_texts
from research.kinematic.phase_transform_header_audit import HeaderRejected


ROOT = Path(__file__).resolve().parents[3]
PLAN = json.loads((ROOT / "research/kinematic/five_root_role_structure_plan.json").read_text())


def _header(value: str, label: str) -> str:
    return f"{value:<60}{label:<20}"


def _phase_shift(name: str, shift: float = 0.0, satellites: tuple[str, ...] = ()) -> str:
    value = [" "] * 60
    value[0] = "G"
    value[2:5] = name
    value[6:14] = f"{shift:8.5f}"
    value[16:18] = f"{len(satellites):2d}"
    for index, satellite in enumerate(satellites):
        offset = 18 + 4 * index
        value[offset + 1:offset + 4] = satellite
    return _header("".join(value), "SYS / PHASE SHIFT")


def _fixture(*, shift: float = 0.0, malformed_phase: bool = False) -> str:
    observations, _ = phase_fixture_texts()
    rows = observations.splitlines()
    end = next(i for i, row in enumerate(rows) if row[60:80].strip() == "END OF HEADER")
    rows.insert(end, _header(
        "  2026     8    29    12     0   30.0000000     GPS", "TIME OF LAST OBS"
    ))
    if malformed_phase:
        rows.insert(end + 1, _header("this is deliberately uninterpretable", "SYS / PHASE SHIFT"))
    else:
        rows.insert(end + 1, _phase_shift("L1C", shift))
        rows.insert(end + 2, _phase_shift("L2W", -shift, ("G01",) if shift else ()))
    rows = [row.replace("2026     9    10", "2026     8    29") for row in rows]
    rows = [row.replace("2026 09 10", "2026 08 29") for row in rows]
    return "\n".join(rows) + "\n"


def _fixture_plan() -> tuple[dict, dict]:
    plan = deepcopy(PLAN)
    plan["observation"]["required_first_epoch"] = [2026, 8, 29, 11, 54, 30.0]
    plan["observation"]["required_last_epoch"] = [2026, 8, 29, 12, 0, 30.0]
    station = {"id": "SYN0", "marker": "SYN0",
               "expected_receiver": ["SYNTHETIC-001", "INERTIAL-GENERATOR", "1"]}
    return plan, station


def test_plan_is_distinct_target_free_and_role_specific():
    validate_plan(PLAN)
    assert PLAN["day_of_year"] == 241
    assert PLAN["artifact_selection"]["forbidden_retry_day_of_year"] == 242
    assert PLAN["transform_admission"]["fit"][
        "phase_shift_semantics"
    ] == "DECLARED_STATIC_OFFSETS_RETAINED_AND_REVERSIBLE"
    assert not PLAN["transform_admission"]["heldout_code"][
        "phase_transform_in_causal_path"
    ]
    admit_archive_age(PLAN, datetime(2026, 9, 1, 23, 59, 31, tzinfo=timezone.utc))


def test_fit_retains_declared_static_default_and_satellite_override():
    plan, station = _fixture_plan()
    summary, eligible = scan_structure(_fixture(shift=0.25), plan, station, "FIT")
    phase = summary["transform_ledger"]["phase_shift"]
    assert phase["L1C"]["default_cycles"] == 0.25
    assert phase["L2W"]["satellite_overrides_cycles"] == {"G01": -0.25}
    assert eligible
    assert summary["observation_numbers_converted"] == 0


def test_code_heldout_does_not_interpret_phase_transform_headers():
    plan, station = _fixture_plan()
    content = _fixture(malformed_phase=True)
    summary, eligible = scan_structure(content, plan, station, "HELDOUT_CODE")
    assert summary["transform_ledger"]["phase_transform"] == (
        "NOT_INTERPRETED_OUTSIDE_CAUSAL_PATH"
    )
    assert eligible
    with pytest.raises(HeaderRejected):
        scan_structure(content, plan, station, "FIT")


def test_code_header_requires_only_code_coordinate():
    plan, _ = _fixture_plan()
    lines = _fixture(malformed_phase=True).splitlines()
    header_end = next(i for i, row in enumerate(lines) if row[60:80].strip() == "END OF HEADER")
    result = _audit_code_header(lines[:header_end + 1], plan, "SYN0")
    assert result["transform_ledger"]["stored_value_scale_divisor"] == {"C1C": 1, "C2W": 1}
    assert "phase_shift" not in result["transform_ledger"]


def test_nonzero_lli_breaks_fit_but_not_code_heldout():
    plan, station = _fixture_plan()
    rows = _fixture(shift=0.25).splitlines()
    row_index = next(i for i, row in enumerate(rows) if row.startswith("G01"))
    offset = 3 + 16 * PHASE_TYPES.index("L1C") + 14
    rows[row_index] = rows[row_index][:offset] + "1" + rows[row_index][offset + 1:]
    changed = "\n".join(rows) + "\n"
    _, fit = scan_structure(changed, plan, station, "FIT")
    _, heldout = scan_structure(changed, plan, station, "HELDOUT_CODE")
    first = min(fit)
    assert "G01" not in fit[first]
    assert "G01" in heldout[first]


def test_role_or_day_cannot_change_after_freeze():
    changed = deepcopy(PLAN)
    changed["day_of_year"] = 242
    with pytest.raises(ValueError, match="distinct frozen day differs"):
        validate_plan(changed)
    changed = deepcopy(PLAN)
    changed["transform_admission"]["heldout_code"]["phase_transform_in_causal_path"] = True
    with pytest.raises(ValueError, match="heldout code transform semantics differ"):
        validate_plan(changed)


def test_frozen_role_specific_result_is_hash_bound_and_structural_only():
    path = ROOT / "research/kinematic/results/s2_five_root_role_structure_2026241_v1.json"
    result = json.loads(path.read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        "3dc57bb1011e05e3b7f046083f4c2f089d1b33682720d408c8339cce118f7e67"
    )
    assert result["status"] == "FIVE_ROOT_ROLE_STRUCTURE_QUALIFIED"
    assert result["failures"] == []
    assert len(result["source_receipts"]) == 5
    assert all("sha256" in row and "decoded_sha256" in row
               for row in result["source_receipts"])
    assert set(result["station_structures"]) == {
        "ALGO00CAN", "BOGT00COL", "MKEA00USA", "PIE100USA", "GOLD00USA"
    }
    assert all(row["epoch_count"] == 2880 and row["non_nominal_gap_count"] == 0
               for row in result["station_structures"].values())
    assert all(row["observation_numbers_converted"] == 0
               for row in result["station_structures"].values())
    bogt = result["station_structures"]["BOGT00COL"]["transform_ledger"]["phase_shift"]
    assert set(bogt["L1C"]["satellite_overrides_cycles"]) == {
        f"G{number:02d}" for number in range(1, 33)
    }
    assert set(bogt["L1C"]["satellite_overrides_cycles"].values()) == {0.0}
    gold = result["station_structures"]["GOLD00USA"]["transform_ledger"]
    assert gold["phase_transform"] == "NOT_INTERPRETED_OUTSIDE_CAUSAL_PATH"
    assert "phase_shift" not in gold
    assert result["cross_root_capacity"]["capable_window_count"] == 2834
    assert result["cross_root_capacity"]["candidate_identity_persisted"] is False
    assert result["clauses"]["OBSERVATION_NUMERIC_ADMISSION"] == "NOT_EVALUATED"
    assert result["clauses"]["TOTAL_PHYSICAL_ERROR_ENVELOPE"] == "NOT_EVALUATED"
    assert result["interpretation"]["closed_doy242_retried_or_rescored"] is False
