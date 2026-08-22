from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "GNSS_INDEPENDENT_PRIMARY_PROSPECTIVE_PLAN.md"
RECEIPT = ROOT / "GNSS_INDEPENDENT_PRIMARY_PROSPECTIVE_PLAN_RECEIPT.json"


def canonical_lf(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def receipt() -> dict[str, object]:
    return json.loads(
        RECEIPT.read_text(encoding="ascii"),
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
    )


def gps_epoch(value: str) -> datetime:
    return datetime.strptime(value.removesuffix(" GPS"), "%Y-%m-%dT%H:%M:%S")


def test_receipt_binds_exact_plan_and_frozen_lineage() -> None:
    frozen = receipt()
    plan = canonical_lf(PLAN)

    assert frozen["plan_markdown"] == {
        "bytes": 10595,
        "hash_normalization": "CANONICAL_LF",
        "name": PLAN.name,
        "sha256": "763fa4c5c2b5ea77faaedc75c753c360fd848294ab789a8868d1e91458b2c000",
    }
    assert sha256(plan).hexdigest() == frozen["plan_markdown"]["sha256"]
    assert frozen["lineage"]["navigation_review_receipt_sha256"] == (
        "87a869afa1fa6a66e0cc4144c2ca7f261364e33867fe5ced9b9ee9620257df78"
    )
    assert frozen["lineage"]["qualification_receipt_sha256"] == (
        "5e2d319ba633dce788bfa0a8b8961fa228a4b6ffd0ed47787b92c59520b37f0d"
    )


def test_primary_products_remain_fully_sealed() -> None:
    frozen = receipt()

    assert frozen["primary_access_authorized"] is False
    assert set(frozen["observation_access"].values()) == {0}
    assert all(item["sha256"] is None for item in frozen["primary_products"])
    assert all(item["header_opened"] is False for item in frozen["primary_products"])
    assert all(item["payload_opened"] is False for item in frozen["primary_products"])
    assert frozen["future_evaluator_seal"] == {
        "manifest_sha256": None,
        "required_before_primary_access": True,
        "source_sha256": None,
        "state": "NOT_YET_MATERIALIZED",
    }


def test_time_grid_and_prefix_suffix_partition_are_exact() -> None:
    selected = receipt()["selected_plan"]

    assert selected["raw_records"] == 380
    assert selected["feature_records"] == 378
    assert selected["calibration_records"] == 76
    assert selected["heldout_records"] == 302
    assert selected["raw_records"] == selected["feature_records"] + 2
    assert selected["feature_records"] == (
        selected["calibration_records"] + selected["heldout_records"]
    )
    raw_duration = (
        gps_epoch(selected["raw_input_epoch_stop_gps"])
        - gps_epoch(selected["raw_input_epoch_start_gps"])
    ).total_seconds()
    assert raw_duration == (selected["raw_records"] - 1) * selected["step_s"]
    boundary_step = (
        gps_epoch(selected["heldout_epoch_start_gps"])
        - gps_epoch(selected["calibration_epoch_stop_gps"])
    ).total_seconds()
    assert boundary_step == pytest.approx(selected["step_s"])


def test_frozen_margin_uses_controlling_g14_and_symmetric_envelope() -> None:
    detectability = receipt()["detectability"]

    assert detectability["pairwise_decision_guard_hz"] == pytest.approx(
        2.0 * detectability["one_model_envelope_hz"]
    )
    assert detectability["g14_controlling_separation_hz"] < (
        detectability["prefix_affine_separation_hz"]
    )
    assert detectability["remaining_physical_margin_hz"] == pytest.approx(
        detectability["g14_controlling_separation_hz"]
        - detectability["pairwise_decision_guard_hz"]
    )
    assert detectability["remaining_physical_margin_hz"] > 0.0


def test_signal_family_nulls_and_nuisance_cannot_change() -> None:
    frozen = receipt()
    selected = frozen["selected_plan"]

    assert selected["target"] == "G20"
    assert selected["reference"] == "G22"
    assert selected["wrong_orbit"] == "G14"
    assert selected["signal_family"] == {
        "l1": ["C1C", "L1C", "S1C"],
        "l2": ["C2W", "L2W", "S2W"],
        "selection_frozen_before_primary_access": True,
    }
    assert selected["nulls"] == ["PREFIX_AFFINE", "G14_G22_WRONG_ORBIT"]
    assert frozen["retry_policy"]["after_first_decompression_byte"] == "ZERO_RETRY"
    assert frozen["retry_policy"]["alternate_window"] is False
    assert frozen["retry_policy"]["alternate_signal_family"] is False
    assert frozen["retry_policy"]["threshold_change"] is False
    text = PLAN.read_text(encoding="utf-8")
    assert "No fitted time phase is allowed" in text
    assert "No held-out record may choose a field" in text


def test_description_failure_is_not_an_epistemic_rejection() -> None:
    frozen = receipt()

    assert frozen["failure_semantics"]["PRIMARY_EVALUATION_ERROR"] == (
        "DESCRIPTION_OR_SOFTWARE_FAILURE_NO_EPISTEMIC_REJECTION"
    )
    assert frozen["failure_semantics"]["MEASUREMENT_INVALID"].startswith(
        "PHYSICAL_MEASUREMENT_ADMISSION_FAILED"
    )
    assert frozen["outcome"] == "READY_FOR_GNSS_PRIMARY_EVALUATOR_FREEZE"
    assert frozen["prospective_plan_frozen"] is True
    assert frozen["new_gate_created"] is False
