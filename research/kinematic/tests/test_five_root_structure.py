"""Offline boundaries for the target-free five-root structural qualification."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pytest

from research.kinematic.five_root_structure import (
    admit_archive_age,
    evaluate_capacity,
    scan_structure,
    validate_plan,
)
from research.kinematic.phase_bridge_study import phase_fixture_texts
from research.kinematic.phase_bridge_study import PHASE_TYPES


ROOT = Path(__file__).resolve().parents[3]
PLAN = json.loads((ROOT / "research/kinematic/five_root_structure_plan.json").read_text())


def _fixture() -> str:
    observations, _ = phase_fixture_texts()
    rows = observations.splitlines()
    end = next(i for i, row in enumerate(rows) if row[60:80].strip() == "END OF HEADER")
    def header(value, label):
        return f"{value:<60}{label:<20}"
    def phase_shift(name):
        value = [" "] * 60
        value[0] = "G"
        value[2:5] = name
        value[16:18] = " 0"
        return header("".join(value), "SYS / PHASE SHIFT")
    rows.insert(end, header("  2026     8    30    12     0   30.0000000     GPS", "TIME OF LAST OBS"))
    rows.insert(end + 1, phase_shift("L1C"))
    rows.insert(end + 2, phase_shift("L2W"))
    rows = [row.replace("2026     9    10", "2026     8    30") for row in rows]
    rows = [row.replace("2026 09 10", "2026 08 30") for row in rows]
    return "\n".join(rows) + "\n"


def _fixture_plan() -> tuple[dict, dict]:
    plan = deepcopy(PLAN)
    plan["observation"]["required_first_epoch"] = [2026, 8, 30, 11, 54, 30.0]
    plan["observation"]["required_last_epoch"] = [2026, 8, 30, 12, 0, 30.0]
    station = {"id": "SYN0", "marker": "SYN0",
               "expected_receiver": ["SYNTHETIC-001", "INERTIAL-GENERATOR", "1"]}
    return plan, station


def test_plan_is_target_free_bounded_and_mature():
    validate_plan(PLAN)
    assert [row["id"] for row in PLAN["fit_roots"]] == [
        "ALGO00CAN", "BOGT00COL", "MKEA00USA", "PIE100USA"
    ]
    assert PLAN["heldout_root"]["id"] == "GOLD00USA"
    assert not PLAN["observation"]["observation_numeric_conversion"]
    assert not PLAN["structural_capacity"]["candidate_identity_persisted"]
    admit_archive_age(PLAN, datetime(2026, 9, 2, 23, 59, 31, tzinfo=timezone.utc))


def test_structure_scan_uses_presence_and_lli_not_numbers():
    plan, station = _fixture_plan()
    content = _fixture().replace("SYN0", "SYN0")
    first, eligible = scan_structure(content, plan, station, "FIT")
    poisoned = content.replace("21515935.357", "ABCDEFGHIJKL")
    second, eligible_poisoned = scan_structure(poisoned, plan, station, "FIT")
    assert eligible_poisoned == eligible
    assert first["observation_numbers_converted"] == 0
    assert second["structural_counts"] == first["structural_counts"]


def test_nonzero_phase_lli_breaks_fit_but_not_code_heldout():
    plan, station = _fixture_plan()
    content = _fixture()
    rows = content.splitlines()
    row_index = next(i for i, row in enumerate(rows) if row.startswith("G01"))
    offset = 3 + 16 * PHASE_TYPES.index("L1C") + 14
    rows[row_index] = rows[row_index][:offset] + "1" + rows[row_index][offset + 1:]
    changed = "\n".join(rows) + "\n"
    _, fit = scan_structure(changed, plan, station, "FIT")
    _, heldout = scan_structure(changed, plan, station, "HELDOUT_CODE")
    first_tag = min(fit)
    assert "G01" not in fit[first_tag]
    assert "G01" in heldout[first_tag]


def test_capacity_counts_without_persisting_candidate_identity():
    structures = {}
    tags = [30.0 * index for index in range(12)]
    satellites = {"G01", "G02", "G03", "G04", "G05"}
    for root in [*PLAN["fit_roots"], PLAN["heldout_root"]]:
        structures[root["id"]] = {tag: set(satellites) for tag in tags}
    result = evaluate_capacity(structures, PLAN)
    assert result["qualified"]
    assert result["capable_window_count"] == 2
    assert result["maximum_unselected_common_candidate_count"] == 5
    assert result["candidate_identity_persisted"] is False


def test_threshold_or_root_allocation_cannot_change():
    changed = deepcopy(PLAN)
    changed["structural_capacity"]["endpoint_count"] = 10
    with pytest.raises(ValueError, match="capacity rule differs"):
        validate_plan(changed)
    changed = deepcopy(PLAN)
    changed["fit_roots"][0]["id"] = "DRAO00CAN"
    with pytest.raises(ValueError, match="root topology differs"):
        validate_plan(changed)


def test_frozen_failure_is_hash_bound_and_clause_attributed():
    result_path = ROOT / "research/kinematic/results/s2_five_root_structure_2026242_v1.json"
    result = json.loads(result_path.read_text())
    assert hashlib.sha256(result_path.read_bytes()).hexdigest() == (
        "af13370e6d2537c6497e70ef842662f768f4e2de37f29d8643fda6b1789893d0"
    )
    assert result["status"] == "FIVE_ROOT_STRUCTURE_NOT_QUALIFIED"
    assert len(result["source_receipts"]) == 5
    assert all("sha256" in receipt for receipt in result["source_receipts"])
    assert set(result["station_structures"]) == {"ALGO00CAN", "MKEA00USA", "PIE100USA"}
    assert all(row["epoch_count"] == 2880 for row in result["station_structures"].values())
    assert all(row["observation_numbers_converted"] == 0
               for row in result["station_structures"].values())
    assert result["clauses"]["STRUCTURAL_COMMON_WINDOW"] == "NOT_EVALUATED"
    attribution = json.loads((
        ROOT / "research/kinematic/results/s2_five_root_structure_failure_attribution_v1.json"
    ).read_text())
    assert attribution["source_result_sha256"] == hashlib.sha256(result_path.read_bytes()).hexdigest()
    assert attribution["station_attribution"]["GOLD00USA"] == (
        "ROLE_IRRELEVANT_PHASE_CLAUSE_APPLIED_TO_CODE_ONLY_ROOT"
    )
    assert attribution["retry_same_artifacts_authorized"] is False
