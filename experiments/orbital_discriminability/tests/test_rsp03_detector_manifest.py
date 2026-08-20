"""Strict offline validation for the frozen RSP-03 detector manifest."""

from dataclasses import asdict
import json
from math import isfinite
from pathlib import Path

from experiments.orbital_discriminability.rsp03_forward_plan import (
    PLAN,
    primary_analysis_blockers,
)
from experiments.orbital_discriminability.rsp03_ridge_detector import PARAMETERS


MANIFEST_PATH = (
    Path(__file__).parents[1] / "RSP03_DETECTOR_MANIFEST.json"
)


def _assert_strict_numeric_tree(value: object) -> None:
    if isinstance(value, float):
        assert isfinite(value)
    elif isinstance(value, dict):
        for nested in value.values():
            _assert_strict_numeric_tree(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_strict_numeric_tree(nested)


def test_manifest_is_strict_json_and_matches_every_detector_parameter() -> None:
    raw = MANIFEST_PATH.read_text(encoding="utf-8")
    manifest = json.loads(raw, parse_constant=lambda token: (_ for _ in ()).throw(
        ValueError(f"non-finite JSON token {token}")
    ))
    _assert_strict_numeric_tree(manifest)
    assert manifest["strict_json_allow_nan"] is False
    assert manifest["transform_parameters"] == asdict(PARAMETERS)


def test_manifest_binds_source_plan_authority_and_only_development_artifact() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["source_commit"] == "03af6172ba58c1132c263a0762fc5151388fb484"
    assert manifest["structural_plan_hash"] == PLAN.plan_hash
    assert manifest["authorized_role"] == "DEVELOPMENT_FIXTURE"
    assert manifest["primary_accessed"] is False
    assert manifest["replication_reserve_accessed"] is False
    assert manifest["orbital_model_input_used"] is False
    assert manifest["absolute_time_error_bound_s"] is None
    assert manifest["development_artifact"]["sha256"] == (
        "4875e4cfdf99beaa981238bdb6fff6ebe25ce5ddbe800aec58b26c598e479d9b"
    )
    assert manifest["development_artifact"]["byte_count"] == 1_759_400_000


def test_manifest_records_development_result_without_unblocking_time() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    result = manifest["development_result"]
    assert result["status"] == "RIDGE_ADMITTED"
    assert result["admitted_point_count"] == 275
    assert result["ambiguous_frame_count"] == 4
    assert result["clipped_frame_count"] == 0
    assert manifest["remaining_primary_blockers"] == [
        "NO_DEFENSIBLE_FINITE_PPS_TO_ADC_UTC_ERROR_BOUND"
    ]
    assert primary_analysis_blockers(detector_manifest_sha256="f" * 64) == (
        "NO_DEFENSIBLE_FINITE_PPS_TO_ADC_UTC_ERROR_BOUND",
    )
