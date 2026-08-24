from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from experiments.orbital_discriminability import gnss_phase_geometry_screen as screen


ROOT = Path(__file__).resolve().parents[1]
PHASE_RECEIPT = ROOT / screen.PHASE_SPIKE_RECEIPT_NAME
SCREEN_RECEIPT = ROOT / "GNSS_PHASE_GEOMETRY_SCREEN_RECEIPT.json"


def _candidate(
    target: str,
    reference: str,
    margin: float,
    *,
    separation: float = 1000.0,
    elevation: float = 30.0,
    doy: int = 216,
) -> dict[str, object]:
    return {
        "target": target,
        "reference": reference,
        "remaining_physical_margin_m": margin,
        "controlling_heldout_separation_m": separation,
        "guarded_block_minimum_elevation_deg": elevation,
        "doy": doy,
    }


def test_manifest_freezes_bounded_non_observational_candidate_set() -> None:
    manifest = screen.manifest()

    assert manifest["excluded_satellites"] == ["G14", "G17"]
    assert manifest["excluded_pairs"] == [["G11", "G21"]]
    assert manifest["signal_family"]["core_phase"] == ["L1C", "L2W"]
    assert len(manifest["navigation"]) == 5
    assert manifest["stations"] == ["GOLD00USA", "NLIB00USA"]
    assert manifest["measurement_envelope"][
        "structural_coverage_and_witnesses"
    ] == "NOT_EVALUATED"
    assert screen.manifest_sha256() == (
        "c174204a82a14b8c0490a96c79f0da0ef233c817408e16ef5d3281c2a850f7e2"
    )


@pytest.mark.parametrize(
    ("target", "reference", "expected", "reason"),
    [
        ("G14", "G22", False, "HISTORICAL_PHASE_DEVELOPMENT_SATELLITE_EXCLUDED"),
        ("G03", "G17", False, "HISTORICAL_PHASE_DEVELOPMENT_SATELLITE_EXCLUDED"),
        ("G11", "G21", False, "CLOSED_G11_G21_PAIR_EXCLUDED"),
        ("G21", "G11", False, "CLOSED_G11_G21_PAIR_EXCLUDED"),
        ("G03", "G22", True, None),
    ],
)
def test_historical_candidates_are_excluded(
    target: str,
    reference: str,
    expected: bool,
    reason: str | None,
) -> None:
    admitted, actual_reason = screen.candidate_is_allowed(
        {"target": target, "reference": reference}
    )

    assert admitted is expected
    assert actual_reason == reason


def test_ranking_uses_positive_margin_and_distinct_pairs() -> None:
    ranked = screen._rank_candidates(
        [
            _candidate("G01", "G02", 10.0, doy=216),
            _candidate("G01", "G02", 12.0, doy=217),
            _candidate("G03", "G04", 11.0),
            _candidate("G05", "G06", 9.0),
            _candidate("G07", "G08", -1.0),
        ]
    )

    assert [(row["target"], row["reference"]) for row in ranked] == [
        ("G01", "G02"),
        ("G03", "G04"),
        ("G05", "G06"),
    ]
    assert [row["rank"] for row in ranked] == [1, 2, 3]
    assert ranked[0]["doy"] == 217
    assert ranked[0]["selection_state"] == "PHASE_GEOMETRY_SELECTED"
    assert ranked[1]["selection_state"] == "LOWER_RANKED_NOT_SELECTED"


def test_raw_separation_cannot_beat_smaller_positive_remaining_margin() -> None:
    ranked = screen._rank_candidates(
        [
            _candidate("G01", "G02", 5.0, separation=1_000_000.0),
            _candidate("G03", "G04", 6.0, separation=10.0),
        ]
    )

    assert (ranked[0]["target"], ranked[0]["reference"]) == ("G03", "G04")


def test_frozen_phase_receipt_is_development_only_and_value_free() -> None:
    receipt = screen.validate_phase_spike_receipt(PHASE_RECEIPT)

    assert receipt["fixture_role"] == "HISTORICAL_DEVELOPMENT_ONLY_NEVER_PRIMARY"
    assert set(receipt["observation_access"].values()) == {0}
    assert receipt["new_candidate_selected"] is False


def test_manifest_and_future_receipts_are_strict_json() -> None:
    encoded = screen.strict_json(screen.manifest())

    assert json.loads(encoded) == screen.manifest()
    with pytest.raises(ValueError):
        screen.strict_json({"bad": float("nan")})


def test_frozen_screen_selects_one_new_geometry_without_observation_access() -> None:
    canonical = SCREEN_RECEIPT.read_bytes().replace(b"\r\n", b"\n")
    receipt = json.loads(canonical)

    assert sha256(canonical).hexdigest() == (
        "228359ad8e65dfe0191562ca601c6f47dad44ab36bab07736c63e8f9188f293c"
    )
    assert receipt["manifest_sha256"] == (
        "c174204a82a14b8c0490a96c79f0da0ef233c817408e16ef5d3281c2a850f7e2"
    )
    assert receipt["outcome"] == screen.OUTCOME_SELECTED
    assert receipt["compiled_candidate_count"] == 5
    assert receipt["positive_margin_candidate_count"] == 5
    assert len(receipt["shortlist"]) == 1
    selected = receipt["selected_geometry"]
    assert (selected["target"], selected["reference"]) == ("G22", "G30")
    assert selected["doy"] == 220
    assert selected["wrong_orbit_null"]["controlling_alternative"] == "G14"
    assert selected["controlling_heldout_separation_m"] == pytest.approx(
        824_736.0253644681
    )
    assert selected["pairwise_comparison_envelope_m"] == pytest.approx(
        19_767.924052498845
    )
    assert selected["remaining_physical_margin_m"] == pytest.approx(
        804_968.1013119692
    )
    assert set(receipt["observation_access"].values()) == {0}
    assert receipt["prospective_plan_frozen"] is False
    assert receipt["measurement_authorized"] is False
