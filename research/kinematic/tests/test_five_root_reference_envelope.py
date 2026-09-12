"""Offline boundaries for the five-root reference residual envelope."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import pytest

from research.kinematic.five_root_reference_envelope import (
    admit_archive_age,
    parse_numeric_window,
    validate_plan,
)
from research.kinematic.phase_bridge_study import PHASE_TYPES, phase_fixture_texts


ROOT = Path(__file__).resolve().parents[3]
PLAN = json.loads((ROOT / "research/kinematic/five_root_reference_envelope_plan.json").read_text())


def _fixture() -> tuple[str, list[float]]:
    observations, _ = phase_fixture_texts()
    content = observations.replace("2026     9    10", "2026     8    28")
    content = content.replace("2026 09 10", "2026 08 28")
    tags = [42870.0 + 30.0 * index for index in range(11)]
    return content, tags


def _replace_field(content: str, satellite: str, name: str, transform) -> str:
    rows = content.splitlines()
    index = PHASE_TYPES.index(name)
    start = 3 + 16 * index
    for row_index, row in enumerate(rows):
        if row.startswith(satellite):
            field = row[start:start + 16].ljust(16)
            rows[row_index] = row[:start] + transform(field) + row[start + 16:]
    return "\n".join(rows) + "\n"


def test_plan_is_bounded_distinct_and_target_excluding():
    validate_plan(PLAN)
    assert PLAN["day_of_year"] == 240
    assert PLAN["artifact_selection"]["forbidden_days"] == [241, 242]
    assert PLAN["excluded_identity"] == "G14"
    assert "G14" not in PLAN["reference_candidate_pool"]
    assert len(PLAN["reference_candidate_pool"]) == 31
    admit_archive_age(PLAN, datetime(2026, 8, 31, 23, 59, 31, tzinfo=timezone.utc))


def test_numeric_parser_reads_only_selected_reference_fields():
    content, tags = _fixture()
    poisoned = _replace_field(
        content, "G08", "C1C", lambda field: "ABCDEFGHIJKLMN" + field[14:16]
    )
    parsed = parse_numeric_window(poisoned, PLAN, ["G01", "G02", "G03", "G04"],
                                  tags, "FIT")
    assert parsed["code_m"].shape == (44,)
    assert parsed["phase_path_m"].shape == (44,)
    assert np.isfinite(parsed["code_m"]).all()


def test_gold_code_path_does_not_decode_phase_values():
    content, tags = _fixture()
    poisoned = _replace_field(
        content, "G01", "L1C", lambda field: "ABCDEFGHIJKLMN" + field[14:16]
    )
    parsed = parse_numeric_window(poisoned, PLAN, ["G01", "G02", "G03", "G04"],
                                  tags, "HELDOUT_CODE")
    assert "phase_path_m" not in parsed
    with pytest.raises(ValueError, match="INVALID_SELECTED_FIELD:L1C"):
        parse_numeric_window(poisoned, PLAN, ["G01", "G02", "G03", "G04"], tags, "FIT")


def test_static_phase_offset_cancels_from_interval_rate():
    content, tags = _fixture()
    baseline = parse_numeric_window(content, PLAN, ["G01", "G02", "G03", "G04"],
                                    tags, "FIT")["phase_path_m"].reshape(11, 4)

    def add_quarter_cycle(field: str) -> str:
        return f"{float(field[:14]) + 0.25:14.3f}" + field[14:16]

    shifted_content = _replace_field(content, "G01", "L1C", add_quarter_cycle)
    shifted = parse_numeric_window(
        shifted_content, PLAN, ["G01", "G02", "G03", "G04"], tags, "FIT"
    )["phase_path_m"].reshape(11, 4)
    assert np.allclose(np.diff(shifted, axis=0), np.diff(baseline, axis=0), atol=1e-9)


def test_threshold_date_or_exclusion_cannot_change():
    changed = deepcopy(PLAN)
    changed["admission"]["maximum_fit_phase_rate_absolute_residual_m_s"] = 0.051
    with pytest.raises(ValueError, match="inherited numerical limit differs"):
        validate_plan(changed)
    changed = deepcopy(PLAN)
    changed["day_of_year"] = 241
    with pytest.raises(ValueError, match="frozen distinct day differs"):
        validate_plan(changed)
    changed = deepcopy(PLAN)
    changed["excluded_identity"] = "G15"
    with pytest.raises(ValueError, match="excluded identity differs"):
        validate_plan(changed)
