"""Offline transfer audit for the frozen KIRU/MAT1 native-Doppler route.

This module composes only frozen receipts.  It opens no navigation or
observation artifact and deliberately leaves the future broadcast-orbit error
bound unresolved when that bound is not present in the frozen lineage.
"""

from __future__ import annotations

from hashlib import sha256
import importlib.metadata
import json
from math import radians, sin
from pathlib import Path
from typing import Final

import numpy as np

from experiments.orbital_discriminability import gnss_double_difference_envelope as envelope
from experiments.orbital_discriminability import gnss_double_difference_screen as screen


TRANSFER_VERSION: Final = "gnss-kiru-mat1-native-doppler-transfer-v1"
ORBITALITY_RECEIPT_NAME: Final = "GNSS_NATIVE_DOPPLER_ORBITALITY_RECEIPT.json"
ORBITALITY_RECEIPT_SHA256: Final = "036413c60dc10f7a0ca41810904b3b081def91288b7b6247522938e005e3d225"
DEVELOPMENT_RECEIPT_NAME: Final = "GNSS_NATIVE_DOPPLER_DEVELOPMENT_RECEIPT.json"
DEVELOPMENT_RECEIPT_SHA256: Final = "698c1ee3e4eeca460fc0e3b81c5373e49ee7b2d7970e45823f902b2e53d73711"
TRANSFORM_MANIFEST_NAME: Final = "GNSS_NATIVE_DOPPLER_DEVELOPMENT_TRANSFORM_MANIFEST.json"
TRANSFORM_MANIFEST_SHA256: Final = "344c819697d7b6e707bd09629fc1e5fb1b634d66e5a986ea9dc267bbaae3fb0c"

WINDOW_RECORDS: Final = 380
CALIBRATION_RECORDS: Final = 76
HELDOUT_RECORDS: Final = 304
STEP_S: Final = 30.0
MAX_ZENITH_TROPOSPHERE_M: Final = 3.5
PAIRWISE_MULTIPLIER: Final = 2.0
DEVELOPMENT_ENVELOPE_HZ: Final = 1.7027139799721753
DEVELOPMENT_DISPERSIVE_WITNESS_HZ: Final = 0.2717166666666344

NON_ORBIT_PATH_TERMS: Final = tuple(
    item
    for item in envelope.GENERIC_PATH_BOUNDS_M
    if item["term"] != "BROADCAST_ORBIT_SV_ACCURACY"
)


class TransferAuditError(ValueError):
    """Frozen lineage or transfer semantics are inconsistent."""


def file_sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def strict_json(value: object) -> str:
    _validate_standard_json(value)
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _validate_standard_json(value: object) -> None:
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float:
        if not np.isfinite(value):
            raise ValueError("NONFINITE_JSON_SCALAR")
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _validate_standard_json(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if type(key) is not str:
                raise TypeError("NONSTRING_JSON_KEY")
            _validate_standard_json(item)
        return
    raise TypeError(f"NONSTANDARD_JSON_SCALAR:{type(value).__name__}")


def load_exact(root: Path, name: str, expected_sha256: str) -> dict[str, object]:
    path = Path(root) / name
    if not path.is_file() or file_sha256(path) != expected_sha256:
        raise TransferAuditError(f"FROZEN_LINEAGE_MISMATCH:{name}")
    try:
        return json.loads(
            path.read_text(encoding="ascii"),
            parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)),
        )
    except (UnicodeError, ValueError, TypeError) as exc:
        raise TransferAuditError(f"INVALID_STRICT_JSON:{name}") from exc


def projection_gain_hz_per_path_m() -> float:
    """Conservative path-bound transfer through Doppler and prefix affine fit.

    Four signed links and two endpoints give 8*B over the 2*step central
    baseline.  A further frozen factor of two is applied before the exact
    L-infinity affine p-p gain; no temporal or cross-link cancellation is used.
    """
    affine_gain = envelope.affine_projection_peak_to_peak_gain(
        WINDOW_RECORDS, CALIBRATION_RECORDS, STEP_S
    )
    return float(
        affine_gain
        * 8.0
        / STEP_S
        * envelope.GPS_L1_HZ
        / screen.SPEED_OF_LIGHT_M_S
    )


def transfer_contract() -> dict[str, object]:
    return {
        "coordinate": {
            "stations": ["KIRU00SWE", "MAT100ITA"],
            "target": "G15",
            "reference": "G22",
            "observables": ["C1C", "D1C", "S1C", "C2W", "D2W", "S2W"],
            "network_order": "(KIRU_G15-KIRU_G22)-(MAT1_G15-MAT1_G22)",
            "doppler_sign": "POSITIVE_FOR_APPROACHING_SATELLITES",
            "ionosphere_free_formula": (
                "alpha*D1C+beta*(GPS_L1_HZ/GPS_L2_HZ)*D2W"
            ),
        },
        "timing": {
            "time_system": "GPS",
            "step_s": STEP_S,
            "records": WINDOW_RECORDS,
            "calibration_records": CALIBRATION_RECORDS,
            "heldout_records": HELDOUT_RECORDS,
            "station_clock_interval_s": [-15.0, 15.0],
            "clock_envelope_already_subtracted_from_geometry": True,
        },
        "pre_heldout_clauses": {
            "artifact_identity_and_complete_hash_before_decode": "REQUIRED",
            "all_380_epochs_and_four_links_present": "REQUIRED",
            "all_selected_D_C_S_scalars_finite": "REQUIRED",
            "code_and_snr_positive_on_every_link": "REQUIRED",
            "prefix_model_residual_peak_to_peak_max_hz": DEVELOPMENT_ENVELOPE_HZ,
            "prefix_dispersive_network_peak_to_peak_max_hz": (
                DEVELOPMENT_DISPERSIVE_WITNESS_HZ
            ),
        },
        "heldout_health_clauses": {
            "zero_missing_or_non_30s_epochs": "REQUIRED",
            "all_D_C_S_scalars_finite": "REQUIRED",
            "same_link_snr_not_below_its_prefix_minimum": "REQUIRED",
            "dispersive_network_peak_to_peak_max_hz": (
                DEVELOPMENT_DISPERSIVE_WITNESS_HZ
            ),
            "health_values_may_gate_detectability_but_may_not_fit_hypotheses": True,
        },
        "snr_policy": {
            "absolute_db_hz_threshold": None,
            "reason": (
                "NO_OUTCOME_INDEPENDENT_ABSOLUTE_TRACKING_THRESHOLD_IS_IN_"
                "THE_FROZEN_LINEAGE; USE_PREFIX_COMPATIBILITY_AND_SAME_LINK_"
                "NONDEGRADATION_INSTEAD"
            ),
            "development_minimum_2_25_db_hz_promoted_to_threshold": False,
        },
        "outcome_semantics": {
            "MEASUREMENT_INVALID": "IDENTITY_CADENCE_FIELD_OR_CONTINUITY_FAILURE",
            "NOT_DETECTABLE": "PREFIX_OR_HELDOUT_HEALTH_CLAUSE_OR_PHYSICAL_MARGIN_FAILURE",
            "ORBITAL_MODEL_PREDICTIVELY_PREFERRED": "ORBITAL_HELDOUT_SCORE_WINS_BY_FROZEN_GUARD",
            "PREFIX_AFFINE_NULL_PREFERRED": "AFFINE_HELDOUT_SCORE_WINS_BY_FROZEN_GUARD",
            "AMBIGUOUS": "NEITHER_SCORE_WINS_BY_FROZEN_GUARD",
        },
        "claim_ceiling": "ORBITAL_MODEL_PREDICTIVELY_PREFERRED",
        "specific_orbit_claim_authorized": False,
        "post_freeze_retry": 0,
    }


def fixed_non_orbit_terms(candidate: dict[str, object]) -> tuple[list[dict[str, object]], float]:
    elevation_deg = float(
        candidate["minimum_elevation_across_stations_and_clock_shifts_deg"]
    )
    troposphere_m = MAX_ZENITH_TROPOSPHERE_M / sin(radians(elevation_deg))
    definitions = [
        {
            "term": "TROPOSPHERE",
            "per_link_path_bound_m": float(troposphere_m),
            "state": "MODELED_INTERVAL",
            "provenance": "INDEPENDENT_OF_TARGET_OBSERVATION",
            "basis": "3_5_M_ZENITH_BOUND_OVER_SIN_FROZEN_MINIMUM_ELEVATION",
        },
        *NON_ORBIT_PATH_TERMS,
    ]
    coefficient = projection_gain_hz_per_path_m()
    rows = []
    for definition in definitions:
        path_bound = float(definition["per_link_path_bound_m"])
        rows.append(
            {
                **definition,
                "heldout_non_affine_peak_to_peak_bound_hz": float(
                    coefficient * path_bound
                ),
            }
        )
    return rows, float(sum(float(row["per_link_path_bound_m"]) for row in rows))


def audit_candidate(candidate: dict[str, object]) -> dict[str, object]:
    terms, fixed_path_m = fixed_non_orbit_terms(candidate)
    coefficient = projection_gain_hz_per_path_m()
    geometry_margin = float(candidate["remaining_after_direct_clock_envelope_hz"])
    single_hypothesis_budget = geometry_margin / PAIRWISE_MULTIPLIER
    path_budget_hz = single_hypothesis_budget - DEVELOPMENT_ENVELOPE_HZ
    total_path_budget_m = path_budget_hz / coefficient
    maximum_orbit_bound_m = total_path_budget_m - fixed_path_m
    illustrative_orbit_bound_m = 4.0
    illustrative_physical_envelope = coefficient * (
        fixed_path_m + illustrative_orbit_bound_m
    )
    illustrative_pairwise_guard = PAIRWISE_MULTIPLIER * (
        DEVELOPMENT_ENVELOPE_HZ + illustrative_physical_envelope
    )
    return {
        "prospective_role": candidate["prospective_role"],
        "doy": candidate["doy"],
        "target": candidate["target"],
        "reference": candidate["reference"],
        "start_observation_epoch_gps": candidate[
            "start_observation_epoch_gps"
        ],
        "stop_observation_epoch_gps": candidate[
            "stop_observation_epoch_gps"
        ],
        "geometry_margin_after_clock_hz": geometry_margin,
        "development_measurement_path_envelope_hz": DEVELOPMENT_ENVELOPE_HZ,
        "fixed_non_orbit_path_bound_m": fixed_path_m,
        "fixed_non_orbit_terms": terms,
        "path_projection_hz_per_m": coefficient,
        "maximum_admissible_broadcast_orbit_per_link_path_bound_m": float(
            maximum_orbit_bound_m
        ),
        "broadcast_orbit_bound_state": "UNRESOLVED_IN_FROZEN_RECEIPTS",
        "illustrative_not_admitted_4m_bound": {
            "per_link_path_bound_m": illustrative_orbit_bound_m,
            "physical_envelope_hz": float(illustrative_physical_envelope),
            "pairwise_guard_hz": float(illustrative_pairwise_guard),
            "remaining_margin_hz": float(
                geometry_margin - illustrative_pairwise_guard
            ),
            "may_satisfy_contract": False,
            "reason": "4M_VALUE_NOT_RETAINED_FOR_G15_G22_IN_FROZEN_RECEIPT",
        },
        "conditional_negative_result_interpretable": maximum_orbit_bound_m > 0.0,
        "actual_negative_result_interpretable": False,
    }


def compiler_manifest() -> dict[str, object]:
    return {
        "transfer_version": TRANSFER_VERSION,
        "compiler_source_sha256": file_sha256(Path(__file__)),
        "dependencies": {"numpy": importlib.metadata.version("numpy")},
        "lineage": {
            "orbitality_receipt_sha256": ORBITALITY_RECEIPT_SHA256,
            "development_receipt_sha256": DEVELOPMENT_RECEIPT_SHA256,
            "development_transform_manifest_sha256": TRANSFORM_MANIFEST_SHA256,
        },
        "physical_question": (
            "DO_THE_FROZEN_MEASUREMENT_TRANSFER_AND_CONSERVATIVE_PATH_BOUNDS_"
            "LEAVE_ROOM_FOR_AN_OUTCOME_INDEPENDENT_G15_G22_BROADCAST_MODEL_BOUND"
        ),
        "new_information": (
            "MAXIMUM_ADMISSIBLE_BROADCAST_ORBIT_PATH_ERROR_AND_EXACT_"
            "SAME_PATH_WITNESS_RULE_BEFORE_PRIMARY_ACCESS"
        ),
        "contract": transfer_contract(),
        "path_projection": {
            "formula": (
                "AFFINE_PTP_GAIN*2_SAFETY*(8_LINK_ENDPOINTS*B/(2*30S))*GPS_L1_HZ/C"
            ),
            "central_difference_algebraic_bound_doubled_for_safety": True,
            "no_temporal_or_cross_link_cancellation_assumed": True,
            "heldout_peak_to_peak_hz_per_path_m": (
                projection_gain_hz_per_path_m()
            ),
        },
        "observation_access_forbidden": True,
        "new_gate_created": False,
    }


def compiler_manifest_sha256() -> str:
    return sha256(strict_json(compiler_manifest()).encode("ascii")).hexdigest()


def compile_transfer(root: Path) -> dict[str, object]:
    orbitality = load_exact(root, ORBITALITY_RECEIPT_NAME, ORBITALITY_RECEIPT_SHA256)
    development = load_exact(root, DEVELOPMENT_RECEIPT_NAME, DEVELOPMENT_RECEIPT_SHA256)
    transform = load_exact(root, TRANSFORM_MANIFEST_NAME, TRANSFORM_MANIFEST_SHA256)
    if orbitality.get("outcome") != "NATIVE_DOPPLER_ORBITALITY_GEOMETRY_SHORTLIST_READY":
        raise TransferAuditError("ORBITALITY_SHORTLIST_NOT_READY")
    if development.get("outcome") != "NATIVE_DOPPLER_DEVELOPMENT_ENVELOPE_FROZEN":
        raise TransferAuditError("DEVELOPMENT_ENVELOPE_NOT_FROZEN")
    if transform.get("state") != "FROZEN_DEVELOPMENT_TRANSFORM":
        raise TransferAuditError("DEVELOPMENT_TRANSFORM_NOT_FROZEN")
    if float(development["characterization"]["provisional_future_measurement_envelope_hz"]) != DEVELOPMENT_ENVELOPE_HZ:
        raise TransferAuditError("DEVELOPMENT_ENVELOPE_CHANGED")
    shortlist = orbitality.get("shortlist")
    if not isinstance(shortlist, list) or len(shortlist) != 3:
        raise TransferAuditError("FROZEN_SHORTLIST_CHANGED")
    audits = [audit_candidate(item) for item in shortlist]
    positive = all(
        float(item["maximum_admissible_broadcast_orbit_per_link_path_bound_m"])
        > 0.0
        for item in audits
    )
    result = {
        "outcome": (
            "NATIVE_DOPPLER_TRANSFER_RULE_FROZEN_MODEL_BOUND_REQUIRED"
            if positive
            else "NATIVE_DOPPLER_TRANSFER_MARGIN_NOT_PLAUSIBLE"
        ),
        "transfer_version": TRANSFER_VERSION,
        "compiler_manifest_sha256": compiler_manifest_sha256(),
        "compiler_manifest": compiler_manifest(),
        "candidate_audits": audits,
        "transfer_contract": transfer_contract(),
        "broadcast_model_admission": {
            "state": "UNRESOLVED",
            "required_evidence": (
                "OUTCOME_INDEPENDENT_G15_G22_PER_LINK_PATH_BOUND_ON_THE_EXACT_"
                "FROZEN_HEADER_GRID"
            ),
            "rinex_sv_accuracy_field_not_retained_in_parent_receipt": True,
            "unresolved_as_zero": False,
        },
        "authority": {
            "primary_plan_frozen": False,
            "primary_observation_access_authorized": False,
            "reserve_observation_access_authorized": False,
        },
        "observation_access": {
            "products_opened": 0,
            "headers_opened": 0,
            "bytes_opened": 0,
            "numeric_values_decoded": 0,
        },
        "claim_scope": "OFFLINE_TRANSFER_AND_MAXIMUM_ADMISSIBLE_MODEL_ERROR_ONLY",
        "next_exact_blocker": (
            "MATERIALIZE_OUTCOME_INDEPENDENT_G15_G22_BROADCAST_ORBIT_PATH_BOUND_"
            "BELOW_THE_REPORTED_PER_CANDIDATE_MAXIMUM_BEFORE_PRIMARY_FREEZE"
        ),
        "new_gate_created": False,
    }
    strict_json(result)
    return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    print(strict_json(compile_transfer(args.root)))


if __name__ == "__main__":
    main()
