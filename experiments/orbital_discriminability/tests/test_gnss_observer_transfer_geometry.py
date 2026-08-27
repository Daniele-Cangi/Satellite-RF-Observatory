from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    gnss_observer_transfer_geometry as screen,
)


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / screen.RECEIPT_NAME
RECEIPT_SHA256 = "4982a32459d880a17abab9cf726ee6e8f6383e1d0b570abbf77fd07341d459d5"


def test_scope_is_bounded_unused_observers_and_frozen_post_ab_days() -> None:
    assert tuple(candidate.station_id for candidate in screen.CANDIDATES) == (
        "DRAO00CAN",
        "WES200USA",
        "PIE100USA",
        "AMC400USA",
    )
    assert tuple(candidate.doy for candidate in screen.NAVIGATION_CANDIDATES) == (
        221,
        222,
        223,
    )
    assert not set(screen.CANDIDATE_IDS) & {
        "GOLD00USA",
        "NLIB00USA",
        "ALGO00CAN",
        "MDO100USA",
    }


def test_manifest_is_orbit_only_and_not_a_new_gate() -> None:
    manifest = screen.manifest()

    assert manifest["new_gate"] is False
    assert manifest["generic_framework"] is False
    assert manifest["prospective_plan_frozen"] is False
    assert manifest["coordinate"]["free_rate"] is False
    assert manifest["coordinate"]["suffix_fit"] is False
    assert manifest["coordinate"]["fixed_anchor_index"] == 0
    assert manifest["partition"]["confirmation_epochs"] == 60
    assert set(manifest["observation_boundary"].values()) == {0, False}
    assert len(screen.manifest_sha256()) == 64


def test_parent_receipts_are_exact_closed_aggregate_authorities() -> None:
    parents = screen.validate_parent_receipts(ROOT)

    assert set(parents) == {
        screen.OBSERVER_SPIKE_RECEIPT,
        screen.STATION_SCOPE_RECEIPT,
        screen.NAVIGATION_SCOPE_RECEIPT,
    }
    assert all("NO_OBSERVATION_VALUES_REOPENED" in row["role"] for row in parents.values())


def test_rank_keeps_only_best_case_per_distinct_observer() -> None:
    def row(station: str, doy: int, margin: float, start: str) -> dict[str, object]:
        return {
            "station_id": station,
            "doy": doy,
            "joint_visibility_complete": True,
            "remaining_physical_margin_m": margin,
            "controlling_heldout_separation_m": margin + 100.0,
            "minimum_model_elevation_deg": 20.0,
            "raw_start_gps": start,
        }

    ranked = screen.rank_distinct_observers(
        [
            row("DRAO00CAN", 221, 50.0, "2026-08-09T01:00:00 GPS"),
            row("DRAO00CAN", 222, 60.0, "2026-08-10T01:00:00 GPS"),
            row("WES200USA", 221, 55.0, "2026-08-09T02:00:00 GPS"),
            row("PIE100USA", 223, 0.0, "2026-08-11T03:00:00 GPS"),
        ]
    )

    assert [(item["station_id"], item["doy"]) for item in ranked] == [
        ("DRAO00CAN", 222),
        ("WES200USA", 221),
    ]


def test_troposphere_term_is_finite_and_zero_for_identical_paths() -> None:
    elevation = np.linspace(20.0, 70.0, screen.RAW_EPOCHS)
    term = screen._troposphere_term(elevation, elevation)

    assert term["heldout_peak_to_peak_bound_m"] == pytest.approx(0.0)
    assert term["provenance"] == "INDEPENDENT_OF_FUTURE_C_OBSERVATION"


def test_navigation_payload_set_and_nonfinite_json_are_refused() -> None:
    with pytest.raises(screen.ObserverGeometryError, match="PAYLOAD_SET_CHANGED"):
        screen._parse_navigation_payloads({})
    with pytest.raises(ValueError):
        screen.strict_json({"bad": float("nan")})
    with pytest.raises(ValueError):
        screen.strict_json({"bad": float("inf")})


def test_manifest_round_trip_is_strict_json() -> None:
    assert json.loads(screen.strict_json(screen.manifest())) == screen.manifest()


def test_frozen_receipt_selects_three_distinct_observers_without_observation() -> None:
    payload = RECEIPT.read_bytes()
    frozen = json.loads(payload)

    assert len(payload) == 164_520
    assert sha256(payload).hexdigest() == RECEIPT_SHA256
    assert frozen["source_commit"] == (
        "48afe8e59bc97d2fc0afc5afc7015176018af89c"
    )
    assert frozen["source_sha256"] == screen.source_sha256()
    assert frozen["manifest_sha256"] == screen.manifest_sha256()
    assert frozen["outcome"] == screen.OUTCOME_SHORTLISTED
    assert len(frozen["case_results"]) == 12
    assert all(case["case_admitted"] for case in frozen["case_results"])
    assert [row["station_id"] for row in frozen["shortlist"]] == [
        "PIE100USA",
        "WES200USA",
        "AMC400USA",
    ]
    assert [row["doy"] for row in frozen["shortlist"]] == [223, 223, 221]
    selected = frozen["selected"]
    assert selected["raw_start_gps"] == "2026-08-11T05:42:00 GPS"
    assert selected["raw_stop_gps"] == "2026-08-11T06:51:00 GPS"
    assert selected["heldout_start_gps"] == "2026-08-11T06:21:30 GPS"
    assert selected["controlling_null"] == "FROZEN_AFFINE_NULL"
    assert selected["controlling_heldout_separation_m"] == pytest.approx(
        190_232.34133512143
    )
    assert selected["pairwise_comparison_envelope_m"] == pytest.approx(
        2_907.8208783974924
    )
    assert selected["remaining_physical_margin_m"] == pytest.approx(
        187_324.52045672393
    )
    assert selected["minimum_time_shifted_model_elevation_deg"] == pytest.approx(
        17.801627769079243
    )
    assert set(frozen["observation_access"].values()) == {0}
    assert frozen["capability_selected"] is False
    assert frozen["prospective_plan_frozen"] is False
