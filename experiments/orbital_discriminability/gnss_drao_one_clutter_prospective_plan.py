"""Freeze a DRAO seven-track/one-clutter proof before artifact selection.

Only already committed model-only receipts are read. No observation locator,
header, payload or value is selected or accessed by this module.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Final, Mapping

from experiments.orbital_discriminability import gnss_all_track_clutter_scorer as scorer


PLAN_VERSION: Final = "drao-seven-track-one-clutter-prospective-plan-v1"
OUTCOME: Final = "DRAO_ONE_CLUTTER_PROSPECTIVE_PLAN_FROZEN"
PLAN_NAME: Final = "GNSS_DRAO_ONE_CLUTTER_PROSPECTIVE_PLAN.json"

GEOMETRY_NAME: Final = "GNSS_ALL_TRACK_GEOMETRY_SCREEN_RECEIPT.json"
GEOMETRY_SHA256: Final = (
    "09456cae2dcb97550f44a16e45d8cb4b0b5d28a19e0a5b3ef25893c45710089c"
)
ROOTS_NAME: Final = "GNSS_PHASE_INDEPENDENT_PAIR_SCREEN_RECEIPT.json"
ROOTS_SHA256: Final = "24ea926f667749500cd380ebf3c2bd68d730e7faaa84572b0b0bc31bfaba679c"
ALGO_TERMINAL_NAME: Final = "GNSS_ALL_TRACK_QUALIFICATION_RETRY_OUTCOME.json"
ALGO_TERMINAL_SHA256: Final = (
    "233e34084c0ffe86749919dd3f9b73ff243f9a51f530749328a7456dc7ad828e"
)
WES_TERMINAL_NAME: Final = "GNSS_CROSS_FAMILY_BOUNDED_SCREEN_RECEIPT.json"
WES_TERMINAL_SHA256: Final = (
    "59125fedbe1afbfa40255681f82d575a516589ca0f7d40186f601a23495e88f0"
)

STATION: Final = "DRAO00CAN"
QUALIFICATION_DOY: Final = 230
PRIMARY_DOY: Final = 231
EXPECTED_CODEBOOK: Final = ("G07", "G08", "G09", "G21", "G27", "G30")
PAIRWISE_GUARD_M: Final = 7_339.701234647398
RAW_EPOCHS: Final = 139
PREFIX_EPOCHS: Final = 79
HELDOUT_EPOCHS: Final = 60


class DraoPlanError(ValueError):
    """A frozen source or proof boundary changed."""


def strict_json(value: object, *, pretty: bool = False) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
        sort_keys=True,
    )


def canonical_sha256(path: Path) -> str:
    return sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _reject_nonfinite(value: str) -> object:
    raise DraoPlanError(f"NONFINITE_FROZEN_RECEIPT:{value}")


def _load_bound(root: Path, name: str, expected_sha256: str) -> dict[str, object]:
    payload = (Path(root) / name).read_bytes()
    if sha256(payload).hexdigest() != expected_sha256:
        raise DraoPlanError(f"FROZEN_RECEIPT_HASH_CHANGED:{name}")
    value = json.loads(payload, parse_constant=_reject_nonfinite)
    if not isinstance(value, dict):
        raise DraoPlanError(f"FROZEN_RECEIPT_INVALID:{name}")
    return value


def _require_zero_access(value: Mapping[str, object], *, name: str) -> None:
    access = value.get("observation_access")
    if not isinstance(access, dict) or not access or set(access.values()) != {0}:
        raise DraoPlanError(f"SOURCE_OBSERVATION_ACCESS_NOT_ZERO:{name}")


def _drao_root(value: Mapping[str, object]) -> dict[str, object]:
    candidates = value.get("candidate_set")
    if not isinstance(candidates, list):
        raise DraoPlanError("ROOT_CANDIDATE_SET_INVALID")
    rows = [row for row in candidates if row.get("station_id") == STATION]
    if len(rows) != 1:
        raise DraoPlanError("DRAO_ROOT_NOT_UNIQUE")
    return dict(rows[0])


def _geometry_row(value: Mapping[str, object], doy: int) -> dict[str, object]:
    days = value.get("day_results")
    if not isinstance(days, list):
        raise DraoPlanError("GEOMETRY_DAY_RESULTS_INVALID")
    rows = []
    for day in days:
        if day.get("doy") != doy:
            continue
        for station in day.get("station_results", []):
            if station.get("station_id") == STATION:
                rows.append(station.get("selected_cell_window"))
    if len(rows) != 1 or not isinstance(rows[0], dict):
        raise DraoPlanError(f"DRAO_GEOMETRY_NOT_UNIQUE:{doy}")
    row = dict(rows[0])
    if (
        row.get("candidate_codebook") != list(EXPECTED_CODEBOOK)
        or row.get("robustly_discriminative") is not True
        or float(row.get("robust_scorer_margin_lower_bound_m", 0.0)) <= 0.0
    ):
        raise DraoPlanError(f"DRAO_GEOMETRY_BOUNDARY_CHANGED:{doy}")
    return row


def build_plan(root: Path) -> dict[str, object]:
    """Build the prospective proof without selecting an observation artifact."""

    root = Path(root)
    geometry = _load_bound(root, GEOMETRY_NAME, GEOMETRY_SHA256)
    roots = _load_bound(root, ROOTS_NAME, ROOTS_SHA256)
    algo = _load_bound(root, ALGO_TERMINAL_NAME, ALGO_TERMINAL_SHA256)
    wes = _load_bound(root, WES_TERMINAL_NAME, WES_TERMINAL_SHA256)

    _require_zero_access(geometry, name=GEOMETRY_NAME)
    _require_zero_access(roots, name=ROOTS_NAME)
    _require_zero_access(wes, name=WES_TERMINAL_NAME)
    if (
        geometry.get("outcome")
        != "ALL_TRACK_GEOMETRY_SHORTLISTED_MEASUREMENT_UNADMITTED"
    ):
        raise DraoPlanError("GEOMETRY_OUTCOME_CHANGED")
    if roots.get("outcome") != "INDEPENDENT_PAIR_GEOMETRY_SHORTLISTED":
        raise DraoPlanError("ROOT_METADATA_OUTCOME_CHANGED")
    if algo.get("outcome") != "GNSS_ALL_TRACK_STRUCTURAL_QUALIFICATION_FAILED":
        raise DraoPlanError("ALGO_TERMINAL_CHANGED")
    wes_rows = [
        row
        for row in wes.get("candidate_outcomes", [])
        if row.get("station_id") == "WES200USA"
    ]
    if len(wes_rows) != 1 or wes_rows[0].get("admission_state") != (
        "CAPABILITY_REJECTED_SIGNAL_PRODUCT_SEMANTICS"
    ):
        raise DraoPlanError("WES_TERMINAL_CHANGED")

    qualification = _geometry_row(geometry, QUALIFICATION_DOY)
    primary = _geometry_row(geometry, PRIMARY_DOY)
    drao = _drao_root(roots)
    exact = float(primary["exact_controlling_separation_m"])
    robust = float(primary["robust_scorer_margin_lower_bound_m"])
    if abs(robust - (exact - 3.0 * PAIRWISE_GUARD_M)) > 1e-9:
        raise DraoPlanError("PRIMARY_THREE_GUARD_REGRESSION_CHANGED")

    result = {
        "schema": "gnss-drao-one-clutter-prospective-plan-v1",
        "version": PLAN_VERSION,
        "outcome": OUTCOME,
        "physical_question": (
            "CAN_SIX_PREDECLARED_ORBIT_CURVES_BE_ASSIGNED_TO_SEVEN_OPAQUE_"
            "DRAO_PHASE_TRACKS_WITH_ONE_SYMMETRIC_CLUTTER_ALLOWANCE_AND_"
            "PREDICT_THE_HELDOUT_SUFFIX_BETTER_THAN_FROZEN_NULLS"
        ),
        "new_information": (
            "A_REAL_PREVIOUSLY_UNOPENED_OBSERVER_EITHER_PRESERVES_OR_REFUSES_"
            "THE_ANONYMOUS_ORBIT_ASSIGNMENT_UNDER_ONE_PREDECLARED_EXCLUSION"
        ),
        "why_existing_experiment_cannot_answer": (
            "THE_CLOSED_SPIKE_IS_MODEL_ONLY_AND_ALGO_CANNOT_BE_RESCORED_"
            "PROSPECTIVELY_WITH_A_MODEL_CREATED_AFTER_ITS_STRUCTURAL_OUTCOME"
        ),
        "minimum_experiment": (
            "ONE_DRAO_STRUCTURAL_QUALIFICATION_DAY_THEN_ONE_DISTINCT_"
            "ZERO_RETRY_PRIMARY_WITH_SEVEN_OPAQUE_TRACKS"
        ),
        "stop_condition": (
            "STOP_NOW_BEFORE_ARTIFACT_SELECTION;_LATER_STOP_AFTER_ONE_"
            "PRIMARY_TERMINAL_WITH_NO_RETRY"
        ),
        "bounded_route_review": [
            {
                "route": "ALGO00CAN",
                "state": "EXCLUDED_CONSUMED_AND_OUTCOME_CONDITIONED",
                "evidence": ALGO_TERMINAL_NAME,
            },
            {
                "route": "WES200USA",
                "state": "EXCLUDED_SIGNAL_PRODUCT_SEMANTICS",
                "evidence": WES_TERMINAL_NAME,
            },
            {
                "route": STATION,
                "state": "SELECTED_FROM_EXISTING_ORBIT_ONLY_SCOPE",
                "reason": (
                    "UNCONSUMED_RINEX3_CAPABLE_ROOT_WITH_POSITIVE_REPEATED_"
                    "GEOMETRY_AND_NO_NEW_SEARCH"
                ),
            },
        ],
        "frozen_sources": {
            GEOMETRY_NAME: GEOMETRY_SHA256,
            ROOTS_NAME: ROOTS_SHA256,
            ALGO_TERMINAL_NAME: ALGO_TERMINAL_SHA256,
            WES_TERMINAL_NAME: WES_TERMINAL_SHA256,
            "plan_source_canonical_sha256": canonical_sha256(Path(__file__)),
        },
        "observer": {
            "station_id": drao["station_id"],
            "domes": drao["domes"],
            "latitude_deg": drao["latitude_deg"],
            "longitude_deg": drao["longitude_deg"],
            "height_m": drao["height_m"],
            "receiver_metadata": drao["receiver"],
            "antenna_metadata": drao["antenna"],
            "equipment_effective": drao["equipment_effective"],
            "station_log_sha256": drao["station_log_sha256"],
            "metadata_is_not_product_qualification": True,
            "receiver_family_independence_claimed": False,
        },
        "roles": {
            "qualification": {
                "doy": QUALIFICATION_DOY,
                "gps_date": qualification["gps_date"],
                "raw_start_gps": qualification["raw_start_gps"],
                "heldout_start_gps": qualification["heldout_start_gps"],
                "raw_stop_gps": qualification["raw_stop_gps"],
                "artifact_locator": None,
                "role": "STRUCTURAL_ONLY_NEVER_SCORED",
            },
            "primary": {
                "doy": PRIMARY_DOY,
                "gps_date": primary["gps_date"],
                "raw_start_gps": primary["raw_start_gps"],
                "heldout_start_gps": primary["heldout_start_gps"],
                "raw_stop_gps": primary["raw_stop_gps"],
                "artifact_locator": None,
                "role": "HELDOUT_PRIMARY_GEOMETRY_FROZEN_ARTIFACT_UNSELECTED",
            },
            "reserve": None,
        },
        "geometry": {
            "candidate_codebook": list(EXPECTED_CODEBOOK),
            "codebook_available_to_scorer": False,
            "raw_epochs": RAW_EPOCHS,
            "prefix_epochs": PREFIX_EPOCHS,
            "heldout_epochs": HELDOUT_EPOCHS,
            "primary_controlling_runner": primary["controlling_runner"],
            "primary_exact_controlling_separation_m": exact,
            "pairwise_guard_m": PAIRWISE_GUARD_M,
            "three_guard_required_separation_m": 3.0 * PAIRWISE_GUARD_M,
            "primary_robust_lower_margin_m": robust,
            "primary_minimum_time_shifted_elevation_deg": primary[
                "minimum_time_shifted_elevation_deg"
            ],
        },
        "root_topology": {
            "observed_tracks_required": 7,
            "evaluated_tracks_per_hypothesis": 6,
            "clutter_budget": 1,
            "all_exclusions_enumerated": True,
            "posthoc_track_removal": False,
            "orbital_hypotheses": scorer.ORBITAL_HYPOTHESIS_COUNT,
            "time_reversed_null_hypotheses": scorer.GEOMETRY_NULL_COUNT,
            "affine_null_hypotheses": scorer.AFFINE_NULL_COUNT,
            "total_hypotheses": scorer.HYPOTHESIS_COUNT,
            "same_exclusion_budget_for_every_family": True,
        },
        "measurement_contract": {
            "core_phase": ["L1C", "L2W"],
            "continuity": [
                "EXACT_30_SECOND_GRID",
                "ZERO_LLI_ON_BOTH_CORE_FIELDS",
                "NO_INTERPOLATION",
                "NO_GAP_BRIDGING",
            ],
            "same_path_code_witness": {
                "fields": ["C1C", "C2W"],
                "minimum_coverage_fraction_per_track": 0.95,
                "required_raw_indices": [1, 77, 78, 137],
                "may_correct_phase": False,
            },
            "identity_boundary": (
                "PRN_LABELS_SEALED_UNTIL_AFTER_OPAQUE_SCORE_RECEIPT_HASH"
            ),
            "persisted_observation_values": 0,
        },
        "scoring_contract": {
            "common_mode": "PER_HYPOTHESIS_INCLUDED_SIX_TRACK_CENTERING",
            "prefix_nuisance": "CONSTANT_AND_RATE_PER_CENTERED_INCLUDED_TRACK",
            "effective_continuous_parameters": 10,
            "heldout_refit": False,
            "free_time_phase": False,
            "null_families": [
                scorer.FAMILY_AFFINE_NULL,
                scorer.FAMILY_GEOMETRY_NULL,
            ],
            "absolute_fit_guard_m": PAIRWISE_GUARD_M,
            "assignment_margin_guard_m": PAIRWISE_GUARD_M,
            "orbital_vs_null_margin_guard_m": PAIRWISE_GUARD_M,
        },
        "pre_artifact_admission": {
            "state": "REQUIRED_NOT_YET_EVALUATED",
            "maximum_aggregate_effect_m": PAIRWISE_GUARD_M,
            "terms_that_cannot_default_to_zero": [
                "EVENT_TIME_DIRECT_TRAJECTORY_ENVELOPE",
                "BROADCAST_ORBIT_AND_CLOCK",
                "DIFFERENTIAL_TROPOSPHERE",
                "IONOSPHERE_FREE_AND_HIGHER_ORDER_REMAINDER",
                "ANTENNA_PCV_AND_PHASE_WINDUP",
                "MULTIPATH_AND_SIGNAL_SPECIFIC_HARDWARE",
                "RECEIVER_CLOCK_AND_IMPLEMENTATION",
                "RINEX_QUANTIZATION",
            ],
            "failure_terminal": "DRAO_PHYSICAL_ENVELOPE_NOT_ADMITTED",
            "artifact_selection_allowed_before_admission": False,
        },
        "future_outcomes": [
            "DRAO_PHYSICAL_ENVELOPE_NOT_ADMITTED",
            "NO_QUALIFICATION_ARTIFACT_AVAILABLE",
            "QUALIFICATION_DESCRIPTION_ERROR",
            "QUALIFICATION_TOPOLOGY_REJECTED",
            "QUALIFICATION_PASSED_PRIMARY_STILL_SEALED",
            "MEASUREMENT_INVALID",
            "NO_ADMISSIBLE_HYPOTHESIS",
            "AMBIGUOUS",
            "NONORBITAL_NULL_SUPPORTED",
            "ORBITAL_INJECTION_DISCORDANT",
            "ORBITAL_INJECTION_CONCORDANT",
        ],
        "maximum_authorized_claim": (
            "WITHIN_ONE_FROZEN_DRAO_SIX_ORBIT_CODEBOOK_ANONYMOUS_HELDOUT_"
            "PHASE_DYNAMICS_AND_THE_POSTHASH_RECEIVER_LABEL_WITNESS_ARE_"
            "CONCORDANT_OR_DISCORDANT"
        ),
        "claim_exclusions": [
            "UNCONSTRAINED_ORBIT_RECOVERY",
            "CODE_FREE_IDENTITY",
            "RECEIVER_FAMILY_INDEPENDENCE",
            "MULTI_OBSERVER_GEOMETRY",
            "CATALOG_WIDE_IDENTITY",
        ],
        "retry_policy": {
            "before_artifact_selection": "ZERO",
            "qualification_transport_budget": (
                "MUST_BE_FINITE_AND_FROZEN_WITH_LOCATOR_BEFORE_ACCESS"
            ),
            "post_primary_freeze": "ZERO_RETRY_ZERO_NEW_WINDOW_ZERO_REFIT",
        },
        "artifact_access": {
            "qualification_locators": 0,
            "qualification_headers": 0,
            "qualification_payload_bytes": 0,
            "primary_locators": 0,
            "primary_headers": 0,
            "primary_payload_bytes": 0,
            "observation_values": 0,
        },
        "new_gate": False,
        "stop": "STOP_BEFORE_ANY_DRAO_OBSERVATION_ARTIFACT_SELECTION_OR_ACCESS",
    }
    strict_json(result)
    return result


def main() -> int:
    root = Path(__file__).resolve().parent
    target = root / PLAN_NAME
    target.write_text(
        strict_json(build_plan(root), pretty=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
