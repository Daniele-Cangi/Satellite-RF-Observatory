from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.orbital_discriminability import gnss_phase_repeated_pass as compiler
from experiments.orbital_discriminability import (
    gnss_phase_repeated_pass_plan as frozen,
)


ROOT = Path(__file__).resolve().parents[1]


def test_sources_are_exact_and_primary_is_terminal() -> None:
    duration, primary = frozen.verify_sources(ROOT)

    assert duration["outcome"] == "PHASE_SHORTER_WINDOW_PHYSICALLY_AVAILABLE"
    assert primary["outcome"] == "ORBITAL_MODEL_PREDICTIVELY_PREFERRED"
    assert primary["persistence"]["observation_values"] == 0


def test_selection_uses_only_the_pre_outcome_ranking() -> None:
    plan = frozen.plan()

    assert plan["selection"]["pre_outcome_ranking"] == [220, 219, 218, 217]
    assert plan["selection"]["excluded_consumed_dates"] == [217, 220]
    assert plan["roles"]["replication"]["doy"] == 219
    assert plan["roles"]["reserve"]["doy"] == 218
    assert plan["selection"]["product_availability_used"] is False
    assert plan["selection"]["observation_information_used"] is False


def test_replication_changes_pass_but_not_hypothesis_or_thresholds() -> None:
    plan = frozen.plan()

    assert plan["routes"]["selected_same_roots_distinct_pass"]["independent"] == [
        "DATE",
        "PASS_GEOMETRY",
        "OBSERVATION_ARTIFACT",
    ]
    assert plan["routes"]["selected_same_roots_distinct_pass"]["shared"] == [
        "STATION_PAIR",
        "RECEIVER_FAMILIES",
        "SCORER",
    ]
    assert plan["scoring"] == {
        "nuisance": "CONSTANT_RATE_PREFIX_ONLY",
        "one_model_envelope_m": 1188.851495144414,
        "pairwise_guard_m": 2377.702990288828,
        "controlling_separation_m": 8986.714337965008,
        "remaining_physical_margin_m": 6609.01134767618,
        "suffix_refit": False,
        "free_time_phase": False,
        "threshold_change": False,
    }


def test_grid_and_reserve_are_exactly_sealed() -> None:
    plan = frozen.plan()
    replication = plan["roles"]["replication"]
    reserve = plan["roles"]["reserve"]

    assert replication["raw_start_gps"] == "2026-08-07T05:46:00 GPS"
    assert replication["raw_stop_gps"] == "2026-08-07T06:55:00 GPS"
    assert replication["heldout_start_gps"] == "2026-08-07T06:25:00 GPS"
    assert reserve["raw_start_gps"] == "2026-08-06T05:50:00 GPS"
    assert plan["retry"]["reserve_on_failure"] is False
    assert plan["access"]["replication"] == "FORBIDDEN"
    assert plan["access"]["reserve"] == "FORBIDDEN"


def test_compiler_has_no_observation_or_network_capability() -> None:
    manifest = compiler.compiler_manifest()

    assert manifest["navigation"]["doy"] == 219
    assert not any(manifest["observation_boundary"].values())
    assert manifest["navigation_input"]["network_capability"] is False
    assert manifest["navigation_input"]["gzip_persistence_required"] is False
    assert "DOY219_OR_DOY218_PRODUCT_DISCOVERY" in manifest["forbidden"]
    assert compiler.expected_raw_gps_epochs()[0] == frozen.REPLICATION_RAW_START
    assert len(compiler.expected_raw_gps_epochs()) == frozen.RAW_EPOCHS


def test_in_memory_navigation_requires_complete_exact_hash_payload() -> None:
    with pytest.raises(
        compiler.RepeatedPassDescriptionError,
        match="REPLICATION_NAVIGATION_GZIP_SIZE_CHANGED",
    ):
        compiler.parse_navigation_gzip(b"partial")


def test_json_is_strict_and_manifest_is_stable() -> None:
    with pytest.raises(ValueError):
        frozen.strict_json({"bad": float("nan")})
    with pytest.raises(ValueError):
        compiler.strict_json({"bad": float("inf")})
    assert json.loads(frozen.strict_json(frozen.plan())) == frozen.plan()
    assert len(frozen.manifest_sha256()) == 64
    assert len(compiler.compiler_manifest_sha256()) == 64
