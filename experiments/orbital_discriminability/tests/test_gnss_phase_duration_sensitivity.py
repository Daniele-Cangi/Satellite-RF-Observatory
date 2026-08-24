from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.orbital_discriminability import (
    gnss_phase_duration_sensitivity as sensitivity,
)


ROOT = Path(__file__).resolve().parents[1]
STRUCTURAL_OUTCOME = ROOT / sensitivity.STRUCTURAL_OUTCOME_NAME


def synthetic_rows(
    positive: dict[int, set[int]],
) -> list[dict[str, object]]:
    rows = []
    for doy in sensitivity.ELIGIBLE_DOYS:
        for heldout in sensitivity.HELDOUT_EPOCH_GRID:
            margin = 2.0 if doy in positive.get(heldout, set()) else -1.0
            rows.append(
                {
                    "doy": doy,
                    "heldout_epochs": heldout,
                    "state": "PHYSICAL_MARGIN_COMPILED",
                    "remaining_physical_margin_m": margin,
                    "guarded_block_minimum_elevation_deg": 30.0 - doy / 1000.0,
                }
            )
    return rows


def test_manifest_excludes_observed_day_and_observation_inputs() -> None:
    manifest = sensitivity.manifest()

    assert manifest["eligible_doys"] == [217, 218, 219, 220]
    assert [item["doy"] for item in manifest["navigation"]] == [
        217,
        218,
        219,
        220,
    ]
    assert manifest["excluded_doy"] == {
        "doy": 216,
        "reason": "MEASUREMENT_STRUCTURE_ALREADY_OBSERVED",
    }
    assert manifest["closed_structural_outcome"][
        "coverage_and_summary_as_numerical_inputs"
    ] == "FORBIDDEN"
    assert manifest["grid"]["heldout_epochs"] == [60, 120, 180, 240, 307]


def test_guarded_block_uses_variable_length_and_earliest_tie() -> None:
    values = [10.0, 16.0, 20.0, 20.0, 16.0, 10.0, 16.0, 20.0, 20.0, 16.0]

    assert sensitivity.select_guarded_block(values, 4) == pytest.approx((1, 16.0))
    assert sensitivity.select_guarded_block(values, 3) == pytest.approx((1, 16.0))
    assert sensitivity.select_guarded_block(values, 5) is None


def test_shortest_duration_requires_two_distinct_positive_dates() -> None:
    decision = sensitivity.summarize(
        synthetic_rows(
            {
                60: {217},
                120: {217, 219},
                180: {217, 218, 219},
                307: {217, 218, 219, 220},
            }
        )
    )

    assert decision["outcome"] == sensitivity.OUTCOME_AVAILABLE
    assert decision["shortest_available_heldout_epochs"] == 120
    assert [row["doy"] for row in decision["diagnostic_date_ranking"]] == [
        217,
        219,
    ]
    assert decision["roles_assigned"] is False
    assert decision["prospective_plan_frozen"] is False


def test_original_duration_alone_does_not_claim_shorter_window() -> None:
    decision = sensitivity.summarize(
        synthetic_rows({307: {217, 218, 219, 220}})
    )

    assert decision["outcome"] == sensitivity.OUTCOME_NONE
    assert decision["shortest_available_heldout_epochs"] is None


def test_structural_closure_is_exact_and_keeps_primary_sealed(tmp_path: Path) -> None:
    sensitivity.validate_structural_closure(STRUCTURAL_OUTCOME)
    changed = json.loads(STRUCTURAL_OUTCOME.read_text(encoding="utf-8"))
    changed["primary_doy220_access"]["headers"] = 1
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(changed), encoding="utf-8")

    with pytest.raises(sensitivity.DurationSensitivityError):
        sensitivity.validate_structural_closure(path)


def test_strict_json_rejects_nonfinite_numbers() -> None:
    assert json.loads(sensitivity.strict_json(sensitivity.manifest())) == (
        sensitivity.manifest()
    )
    with pytest.raises(ValueError):
        sensitivity.strict_json({"bad": float("nan")})
