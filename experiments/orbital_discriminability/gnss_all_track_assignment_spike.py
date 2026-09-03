"""Synthetic all-track assignment spike with post-score identity reveal.

This uses only the already closed opaque prediction bundle as a development
fixture.  It opens no observation product and selects no future primary.
"""

from __future__ import annotations

from hashlib import sha256
from itertools import permutations
from pathlib import Path
from typing import Final, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import gnss_all_track_assignment_scorer as blind
from experiments.orbital_discriminability import gnss_anonymous_track_spike as pair
from experiments.orbital_discriminability import gnss_opaque_orbit_scorer as frozen


SPIKE_VERSION: Final = "gnss-all-track-blind-assignment-spike-v1"
OUTCOME: Final = "ALL_TRACK_BLIND_ASSIGNMENT_MECHANISM_DISCRIMINATIVE"
RECEIPT_NAME: Final = "GNSS_ALL_TRACK_ASSIGNMENT_SPIKE_RECEIPT.json"
PAIRWISE_GUARD_M: Final = 7_339.701234647398
REFERENCE_CODE: Final = "G30"
MODEL_CODES: Final = ("G06", "G14", "G17", "G19", "G22", REFERENCE_CODE)


class AllTrackSpikeError(ValueError):
    """The closed development fixture or reveal order changed."""


def strict_json(value: object, *, pretty: bool = False) -> str:
    return blind.strict_json(value, pretty=pretty)


def canonical_sha256(path: Path) -> str:
    return sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _opaque(prefix: str, payload: str) -> str:
    return prefix + sha256(payload.encode("ascii")).hexdigest()[:16].upper()


def _fixture_curves(root: Path) -> dict[str, np.ndarray]:
    surface, reveal, _ = pair.hypothesis_surface(Path(root))
    curves = {REFERENCE_CODE: np.zeros(blind.RAW_EPOCHS, dtype=np.float64)}
    for identifier, row in reveal.items():
        if row["orientation"] != "TRACK_A_MINUS_TRACK_B":
            continue
        if row["model_class"] != "ORBITAL_CANDIDATE":
            continue
        target, reference = row["model"].split("_RELATIVE_TO_")
        if reference != REFERENCE_CODE or target in curves:
            raise AllTrackSpikeError("CLOSED_FIXTURE_MODEL_SURFACE_INVALID")
        curves[target] = np.asarray(surface[identifier], dtype=np.float64).copy()
    if tuple(sorted(curves)) != tuple(sorted(MODEL_CODES)):
        raise AllTrackSpikeError("CLOSED_FIXTURE_CODE_SET_CHANGED")
    return curves


def hypothesis_surface(
    root: Path,
) -> tuple[tuple[str, ...], dict[str, np.ndarray], dict[str, dict[str, object]]]:
    curves = _fixture_curves(root)
    track_ids = tuple(
        sorted(_opaque("T_", f"ALL_TRACK_SLOT:{index}") for index in range(6))
    )
    surface: dict[str, np.ndarray] = {}
    reveal: dict[str, dict[str, object]] = {}
    for assignment in permutations(MODEL_CODES):
        identifier = _opaque("H_", "ASSIGNMENT:" + ",".join(assignment))
        if identifier in surface:
            raise AllTrackSpikeError("OPAQUE_ASSIGNMENT_ID_COLLISION")
        surface[identifier] = np.stack([curves[code] for code in assignment])
        reveal[identifier] = {
            "model_class": "BIJECTIVE_ORBIT_ASSIGNMENT",
            "assignment_by_track_order": list(assignment),
        }
    null_id = _opaque("H_", "PREFIX_AFFINE_ONLY_ALL_TRACK_NULL")
    if null_id in surface:
        raise AllTrackSpikeError("OPAQUE_NULL_ID_COLLISION")
    surface[null_id] = np.zeros(
        (blind.TRACK_COUNT, blind.RAW_EPOCHS), dtype=np.float64
    )
    reveal[null_id] = {
        "model_class": "PREFIX_AFFINE_ONLY_NULL",
        "assignment_by_track_order": None,
    }
    if len(surface) != blind.HYPOTHESIS_COUNT or set(surface) != set(reveal):
        raise AllTrackSpikeError("OPAQUE_ASSIGNMENT_SURFACE_CHANGED")
    for curve in curves.values():
        curve.fill(0.0)
    return track_ids, surface, reveal


def _synthetic_tracks(
    track_ids: Sequence[str],
    assignment: Sequence[str],
    curves: Mapping[str, Sequence[float]],
    *,
    perturbation_scale_m: float = 0.25,
    extra_by_track: Mapping[str, Sequence[float]] | None = None,
) -> dict[str, np.ndarray]:
    if len(track_ids) != blind.TRACK_COUNT or len(assignment) != blind.TRACK_COUNT:
        raise AllTrackSpikeError("SYNTHETIC_TRACK_ASSIGNMENT_SIZE_CHANGED")
    index = np.arange(blind.RAW_EPOCHS, dtype=np.float64)
    elapsed = index * blind.STEP_S
    common = 9_000.0 + 0.03 * elapsed + 4.0 * np.sin(2.0 * np.pi * index / 47.0)
    result: dict[str, np.ndarray] = {}
    for slot, (track_id, code) in enumerate(zip(track_ids, assignment, strict=True)):
        perturbation = float(perturbation_scale_m) * (
            np.sin(2.0 * np.pi * index / (31.0 + slot))
            + 0.4 * np.cos(2.0 * np.pi * index / (17.0 + slot))
        )
        extra = (
            np.zeros(blind.RAW_EPOCHS, dtype=np.float64)
            if extra_by_track is None or track_id not in extra_by_track
            else np.asarray(extra_by_track[track_id], dtype=np.float64)
        )
        result[track_id] = (
            common
            + np.asarray(curves[code], dtype=np.float64)
            + (80.0 * slot - 0.002 * slot * elapsed)
            + perturbation
            + extra
        )
    return result


def _witness(track_ids: Sequence[str], codes: Sequence[str]) -> dict[str, object]:
    value = {
        "schema": "synthetic-all-track-code-witness-v1",
        "track_identity": [
            {"track_id": track_id, "code_identity": code}
            for track_id, code in zip(track_ids, codes, strict=True)
        ],
        "available_to_orbit_scorer": False,
        "same_samples_and_tracking_output": True,
        "independent_physical_witness": False,
    }
    strict_json(value)
    return value


def _final_state(
    score: Mapping[str, object],
    reveal: Mapping[str, Mapping[str, object]],
    witness_codes: Sequence[str],
) -> tuple[str, dict[str, object]]:
    row = dict(reveal[str(score["best_opaque_id"])])
    if score["orbital_score_state"] != "OPAQUE_ASSIGNMENT_PREFERRED":
        state = "ORBIT_ASSIGNMENT_UNRESOLVED"
    elif row["model_class"] == "PREFIX_AFFINE_ONLY_NULL":
        state = "NON_ORBITAL_NULL_SUPPORTED"
    elif list(witness_codes) == row["assignment_by_track_order"]:
        state = "ORBIT_CODE_CONCORDANT"
    else:
        state = "ORBIT_CODE_DISCORDANT"
    return state, row


def _scenario(
    *,
    name: str,
    role: str,
    tracks: Mapping[str, Sequence[float]],
    witness_codes: Sequence[str],
    surface: Mapping[str, Sequence[Sequence[float]]],
    reveal: Mapping[str, Mapping[str, object]],
    expected_state: str,
) -> dict[str, object]:
    witness = _witness(tuple(sorted(tracks)), witness_codes)
    witness_hash = sha256(strict_json(witness).encode("ascii")).hexdigest()
    score = blind.score_anonymous_tracks(
        tracks, surface, pairwise_guard_m=PAIRWISE_GUARD_M
    )
    score_hash = blind.receipt_sha256(score)
    rendered = strict_json(score)
    if any(code in rendered for code in MODEL_CODES) or "code_identity" in rendered:
        raise AllTrackSpikeError("IDENTITY_LEAKED_INTO_SCORE_RECEIPT")
    final_state, best = _final_state(score, reveal, witness_codes)
    if final_state != expected_state:
        raise AllTrackSpikeError(f"SCENARIO_STATE_CHANGED:{name}:{final_state}")
    for values in tracks.values():
        if isinstance(values, np.ndarray):
            values.fill(0.0)
    return {
        "name": name,
        "role": role,
        "code_witness_sha256_before_score": witness_hash,
        "score_receipt_sha256_before_reveal": score_hash,
        "score_receipt": score,
        "reveal_after_score_hash": {
            "best_opaque_id": score["best_opaque_id"],
            "best_model": best,
            "code_witness": witness,
            "state": final_state,
        },
    }


def build_receipt(root: Path) -> dict[str, object]:
    root = Path(root)
    track_ids, surface, reveal = hypothesis_surface(root)
    curves = _fixture_curves(root)
    canonical_assignment = MODEL_CODES
    permuted_assignment = ("G22", "G06", "G30", "G14", "G19", "G17")

    exact_tracks = _synthetic_tracks(
        track_ids, canonical_assignment, curves, perturbation_scale_m=0.0
    )
    exact_score = blind.score_anonymous_tracks(
        exact_tracks, surface, pairwise_guard_m=PAIRWISE_GUARD_M
    )
    if exact_score["orbital_score_state"] != "OPAQUE_ASSIGNMENT_PREFERRED":
        raise AllTrackSpikeError("EXACT_ALL_TRACK_FIXTURE_NOT_DISCRIMINATIVE")
    correct_id = str(exact_score["best_opaque_id"])
    runner_up_id = str(exact_score["runner_up_opaque_id"])
    for values in exact_tracks.values():
        values.fill(0.0)

    correct_tracks = _synthetic_tracks(track_ids, canonical_assignment, curves)
    discordant_codes = list(canonical_assignment)
    discordant_codes[0], discordant_codes[4] = (
        discordant_codes[4],
        discordant_codes[0],
    )
    permuted_tracks = _synthetic_tracks(track_ids, permuted_assignment, curves)
    affine_curves = {
        code: np.zeros(blind.RAW_EPOCHS, dtype=np.float64) for code in MODEL_CODES
    }
    affine_tracks = _synthetic_tracks(track_ids, canonical_assignment, affine_curves)
    index = np.arange(blind.RAW_EPOCHS, dtype=np.float64)
    mismatch = 2.5 * PAIRWISE_GUARD_M * np.sin(2.0 * np.pi * index / 103.0)
    mismatch_tracks = _synthetic_tracks(
        track_ids,
        canonical_assignment,
        curves,
        extra_by_track={track_ids[0]: mismatch},
    )

    midpoint_tracks: dict[str, np.ndarray] = {}
    midpoint_matrix = 0.5 * (surface[correct_id] + surface[runner_up_id])
    common = 4_000.0 + 0.01 * index * blind.STEP_S
    for slot, track_id in enumerate(track_ids):
        midpoint_tracks[track_id] = common + midpoint_matrix[slot]

    scenarios = [
        _scenario(
            name="complete_correct_assignment",
            role="POSITIVE_CONTROL",
            tracks=correct_tracks,
            witness_codes=canonical_assignment,
            surface=surface,
            reveal=reveal,
            expected_state="ORBIT_CODE_CONCORDANT",
        ),
        _scenario(
            name="complete_code_discordance",
            role="SEPARATE_WITNESS_NEGATIVE_CONTROL",
            tracks=_synthetic_tracks(track_ids, canonical_assignment, curves),
            witness_codes=discordant_codes,
            surface=surface,
            reveal=reveal,
            expected_state="ORBIT_CODE_DISCORDANT",
        ),
        _scenario(
            name="track_slot_permutation",
            role="TARGET_SELECTION_INVARIANCE_CONTROL",
            tracks=permuted_tracks,
            witness_codes=permuted_assignment,
            surface=surface,
            reveal=reveal,
            expected_state="ORBIT_CODE_CONCORDANT",
        ),
        _scenario(
            name="prefix_affine_tracks",
            role="NON_ORBITAL_NULL_CONTROL",
            tracks=affine_tracks,
            witness_codes=canonical_assignment,
            surface=surface,
            reveal=reveal,
            expected_state="NON_ORBITAL_NULL_SUPPORTED",
        ),
        _scenario(
            name="out_of_family_curvature",
            role="ABSOLUTE_FIT_MODEL_MISMATCH_CONTROL",
            tracks=mismatch_tracks,
            witness_codes=canonical_assignment,
            surface=surface,
            reveal=reveal,
            expected_state="ORBIT_ASSIGNMENT_UNRESOLVED",
        ),
        _scenario(
            name="assignment_midpoint",
            role="AMBIGUITY_CONTROL",
            tracks=midpoint_tracks,
            witness_codes=canonical_assignment,
            surface=surface,
            reveal=reveal,
            expected_state="ORBIT_ASSIGNMENT_UNRESOLVED",
        ),
    ]

    surface_hashes = {
        identifier: sha256(
            strict_json([[float(value) for value in row] for row in matrix]).encode(
                "ascii"
            )
        ).hexdigest()
        for identifier, matrix in sorted(surface.items())
    }
    surface_sha256 = sha256(strict_json(surface_hashes).encode("ascii")).hexdigest()
    result = {
        "schema": "gnss-all-track-assignment-spike-receipt-v1",
        "version": SPIKE_VERSION,
        "outcome": OUTCOME,
        "claim_scope": "SYNTHETIC_ALL_TRACK_SELECTION_MECHANISM_ONLY",
        "physical_question": (
            "CAN_HELDOUT_ORBIT_DYNAMICS_ASSIGN_EVERY_CONTINUOUS_TRACK_WITHOUT_"
            "PRN_CONDITIONED_TRACK_PRESELECTION"
        ),
        "closed_development_fixture": {
            "prediction_bundle_sha256": frozen.BUNDLE_CANONICAL_SHA256,
            "mapping_seal_sha256": pair.MAPPING_CANONICAL_SHA256,
            "consumed_primary_reopened_or_rescored": False,
            "observation_values_used": 0,
        },
        "source": {
            "spike_sha256": canonical_sha256(Path(__file__)),
            "scorer_sha256": canonical_sha256(Path(blind.__file__)),
        },
        "selection_boundary": {
            "input": "ALL_SIX_COMPLETE_TRACKS_IN_THE_FROZEN_SYNTHETIC_SET",
            "target_prn_available_to_scorer": False,
            "reference_prn_available_to_scorer": False,
            "fixture_prediction_gauge": (
                "G30_ZERO_COMMON_CURVE_ONLY; ENSEMBLE_CENTERING_MAKES_THE_"
                "SCORER_INVARIANT_TO_THIS_COMMON_GAUGE"
            ),
            "posthoc_track_exclusion": False,
            "assignment_family": "ALL_6_FACTORIAL_BIJECTIONS_PLUS_AFFINE_NULL",
        },
        "opaque_surface": {
            "track_count": blind.TRACK_COUNT,
            "bijective_assignments": 720,
            "non_orbital_nulls": 1,
            "hypothesis_count": blind.HYPOTHESIS_COUNT,
            "curve_matrix_manifest_sha256": surface_sha256,
            "mapping_available_to_scorer": False,
        },
        "scoring": {
            "common_mode": "PER_EPOCH_ENSEMBLE_CENTERING",
            "nuisance": "PREFIX_ONLY_CONSTANT_AND_RATE_PER_CENTERED_TRACK",
            "effective_parameters_per_hypothesis": 10,
            "heldout_refit": False,
            "free_time_phase": False,
            "preference_guard_m": PAIRWISE_GUARD_M,
            "absolute_fit_guard_m": PAIRWISE_GUARD_M,
            "receipt_metric_quantization_decimal_places": blind.METRIC_DECIMALS,
            "exact_fixture_preference_margin_m": exact_score[
                "preference_margin_m"
            ],
            "exact_fixture_best_residual_m": exact_score[
                "best_heldout_max_track_peak_to_peak_m"
            ],
        },
        "scenarios": scenarios,
        "remaining_real_capability_limits": [
            "RINEX_RECEIVER_CODE_CORRELATION_REMAINS_UPSTREAM_AND_NOT_INDEPENDENT",
            "ALL_TRACK_INCLUSION_REQUIRES_A_VALUE_BLIND_STRUCTURAL_RULE",
            "REAL_CANDIDATE_CODEBOOK_AND_VISIBILITY_MUST_BE_FROZEN_ORBIT_FIRST",
            "EVENT_TIME_PROPAGATION_PHASE_AND_HARDWARE_ENVELOPES_REMAIN_REQUIRED",
            "ONE_DISTINCT_QUALIFICATION_AND_ONE_LATER_PRIMARY_WOULD_BE_REQUIRED",
        ],
        "observation_access": {
            "network_requests": 0,
            "product_locators": 0,
            "headers": 0,
            "payload_bytes": 0,
            "values": 0,
        },
        "real_capability_admission": "NOT_EVALUATED",
        "primary_selected": False,
        "new_gate": False,
        "next_maximum_action": (
            "ORBIT_ONLY_SEARCH_FOR_ONE_ALL_TRACK_GEOMETRY_WITH_A_PREDECLARED_"
            "BOUNDED_STATION_DATE_SET"
        ),
        "shock": (
            "RAW_IQ_IS_NOT_REQUIRED_TO_REMOVE_EXPERIMENT_SIDE_PRN_PRESELECTION;_"
            "ALL_TRACK_RINEX_ASSIGNMENT_CAN_TEST_DYNAMICS_FIRST_WHILE_RETAINING_"
            "RECEIVER_CODE_IDENTITY_AS_AN_EXPLICIT_NONINDEPENDENT_WITNESS"
        ),
    }
    strict_json(result)
    for matrix in surface.values():
        matrix.fill(0.0)
    for curve in curves.values():
        curve.fill(0.0)
    return result


def main() -> int:
    build_receipt(Path(__file__).resolve().parent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
