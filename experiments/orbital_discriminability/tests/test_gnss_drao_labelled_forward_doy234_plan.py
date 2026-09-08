from __future__ import annotations

from pathlib import Path

import pytest

from experiments.orbital_discriminability import (
    gnss_drao_labelled_forward_doy234_plan as plan,
)


ROOT = Path(__file__).resolve().parents[1]


def test_manifest_binds_only_remaining_pre_observation_shortlist_member() -> None:
    value = plan.manifest(ROOT)

    assert value["geometry"]["doy"] == 234
    assert value["geometry"]["codebook"] == list(plan.CODEBOOK)
    assert value["authority"]["selection_rule"].startswith("ONLY_REMAINING")
    assert value["authority"]["doy237_reopened"] is False
    assert value["authority"]["doy238_reopened"] is False
    assert value["observation_access_at_freeze"] == 0


def test_grid_is_exact_and_independent() -> None:
    epochs = plan.expected_utc_epochs()

    assert len(epochs) == 139
    assert (epochs[-1] - epochs[0]).total_seconds() == 138 * 30
    assert epochs[0].date().isoformat() == "2026-08-22"


def test_navigation_rejects_wrong_bytes_before_parse() -> None:
    with pytest.raises(plan.Doy234PlanError, match="NAVIGATION_COMPRESSED_BYTES_CHANGED"):
        plan.parse_navigation(b"wrong")


def test_json_is_strict() -> None:
    with pytest.raises(ValueError):
        plan.strict_json({"bad": float("nan")})
