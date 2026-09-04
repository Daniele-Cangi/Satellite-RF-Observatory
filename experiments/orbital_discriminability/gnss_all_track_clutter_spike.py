"""Closed model-only spike for six orbital tracks among seven opaque tracks.

It uses the closed synthetic prediction fixture and a hash-bound, model-only
prediction artifact as structured clutter. No ALGO receipt value, observation
product, network resource or future primary is accessed.
"""

from __future__ import annotations

from hashlib import sha256
from itertools import permutations
import json
from pathlib import Path
from typing import Final, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import (
    gnss_all_track_assignment_spike as six_track_spike,
)
from experiments.orbital_discriminability import gnss_all_track_clutter_scorer as scorer
from experiments.orbital_discriminability import gnss_opaque_orbit_scorer as frozen


SPIKE_VERSION: Final = "gnss-all-track-one-clutter-spike-v2"
OUTCOME_DISCRIMINATIVE: Final = "ALL_TRACK_ONE_CLUTTER_MECHANISM_DISCRIMINATIVE"
OUTCOME_NOT_DISCRIMINATIVE: Final = "ALL_TRACK_ONE_CLUTTER_MECHANISM_NOT_DISCRIMINATIVE"
RECEIPT_NAME: Final = "GNSS_ALL_TRACK_CLUTTER_SPIKE_RECEIPT.json"
PAIRWISE_GUARD_M: Final = six_track_spike.PAIRWISE_GUARD_M
MODEL_CODES: Final = six_track_spike.MODEL_CODES
STRUCTURED_CLUTTER_FIXTURE_NAME: Final = "AMC_OBSERVER_PRIMARY_PREDICTIONS.json"
STRUCTURED_CLUTTER_FIXTURE_SHA256: Final = (
    "c9f7236f3cc221cb8485fe82f0a739e720ee3725f9dbf7c7fcc54c4167794155"
)
STRUCTURED_CLUTTER_CURVES: Final = ("WRONG_ORBIT_G01", "ORBITAL_G22")
NEAR_DEGENERATE_SHIFT_S: Final = 1.5


class ClutterSpikeError(ValueError):
    """The closed clutter spike or its controls changed."""


def strict_json(value: object, *, pretty: bool = False) -> str:
    return scorer.strict_json(value, pretty=pretty)


def canonical_sha256(path: Path) -> str:
    return sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _reject_nonfinite_json(value: str) -> object:
    raise ClutterSpikeError(f"NONFINITE_STRUCTURED_CLUTTER_FIXTURE:{value}")


def _structured_orbital_clutter(
    root: Path,
) -> tuple[dict[str, np.ndarray], dict[str, object]]:
    """Load two frozen model-only curves as structured adversarial clutter.

    The curves were compiled for another observer and pass. They exercise
    orbital-shaped clutter, but make no claim that either satellite was
    concurrently visible in the synthetic seven-track experiment.
    """

    path = Path(root) / STRUCTURED_CLUTTER_FIXTURE_NAME
    payload = path.read_bytes()
    digest = sha256(payload).hexdigest()
    if digest != STRUCTURED_CLUTTER_FIXTURE_SHA256:
        raise ClutterSpikeError("STRUCTURED_CLUTTER_FIXTURE_HASH_CHANGED")
    value = json.loads(payload, parse_constant=_reject_nonfinite_json)
    if not isinstance(value, dict):
        raise ClutterSpikeError("STRUCTURED_CLUTTER_FIXTURE_INVALID")
    epochs = value.get("raw_epochs_gps")
    source_curves = value.get("curves_m")
    access = value.get("observation_access")
    if (
        not isinstance(epochs, list)
        or len(epochs) != 139
        or not isinstance(source_curves, dict)
        or not isinstance(access, dict)
        or set(access.values()) != {0}
    ):
        raise ClutterSpikeError("STRUCTURED_CLUTTER_FIXTURE_BOUNDARY_CHANGED")
    curves: dict[str, np.ndarray] = {}
    for name in STRUCTURED_CLUTTER_CURVES:
        row = np.asarray(source_curves.get(name), dtype=np.float64)
        if row.shape != (139,) or not np.all(np.isfinite(row)):
            raise ClutterSpikeError("STRUCTURED_CLUTTER_CURVE_INVALID")
        curves[name] = row.copy()
    provenance = {
        "artifact": STRUCTURED_CLUTTER_FIXTURE_NAME,
        "sha256": digest,
        "observer_root": value.get("observer_root"),
        "gps_date": value.get("navigation", {}).get("gps_date"),
        "raw_epoch_count": len(epochs),
        "curve_names": list(STRUCTURED_CLUTTER_CURVES),
        "use": "INDEPENDENT_FROZEN_ORBITAL_SHAPE_STRESS_ONLY",
        "same_observer_or_pass_as_synthetic_tracks": False,
        "concurrent_visibility_claim": False,
        "observation_values_used": 0,
    }
    strict_json(provenance)
    return curves, provenance


def _opaque(prefix: str, payload: str) -> str:
    return prefix + sha256(payload.encode("ascii")).hexdigest()[:16].upper()


def _track_ids() -> tuple[str, ...]:
    return tuple(
        sorted(_opaque("T_", f"ONE_CLUTTER_SLOT:{index}") for index in range(7))
    )


def hypothesis_surface(
    root: Path,
) -> tuple[
    tuple[str, ...],
    tuple[scorer.OpaqueHypothesis, ...],
    dict[str, dict[str, object]],
]:
    curves = six_track_spike._fixture_curves(Path(root))
    track_ids = _track_ids()
    hypotheses: list[scorer.OpaqueHypothesis] = []
    reveal: dict[str, dict[str, object]] = {}
    zero = np.zeros((scorer.EVALUATED_TRACK_COUNT, 139), dtype=np.float64)

    for excluded_index in range(scorer.OBSERVED_TRACK_COUNT):
        included = tuple(
            index
            for index in range(scorer.OBSERVED_TRACK_COUNT)
            if index != excluded_index
        )
        excluded_track = track_ids[excluded_index]
        for assignment in permutations(MODEL_CODES):
            assignment_text = ",".join(assignment)
            orbital_id = _opaque("H_", f"ORBITAL:{excluded_index}:{assignment_text}")
            reversed_id = _opaque(
                "H_", f"TIME_REVERSED:{excluded_index}:{assignment_text}"
            )
            orbital_matrix = np.stack([curves[code] for code in assignment])
            reversed_matrix = orbital_matrix[:, ::-1].copy()
            hypotheses.append(
                scorer.OpaqueHypothesis(
                    orbital_id,
                    scorer.FAMILY_ORBITAL,
                    included,
                    orbital_matrix,
                )
            )
            hypotheses.append(
                scorer.OpaqueHypothesis(
                    reversed_id,
                    scorer.FAMILY_GEOMETRY_NULL,
                    included,
                    reversed_matrix,
                )
            )
            reveal[orbital_id] = {
                "model_class": scorer.FAMILY_ORBITAL,
                "excluded_opaque_track": excluded_track,
                "assignment_by_included_track_order": list(assignment),
            }
            reveal[reversed_id] = {
                "model_class": scorer.FAMILY_GEOMETRY_NULL,
                "excluded_opaque_track": excluded_track,
                "assignment_by_included_track_order": list(assignment),
            }
        affine_id = _opaque("H_", f"AFFINE_ONLY:{excluded_index}")
        hypotheses.append(
            scorer.OpaqueHypothesis(
                affine_id,
                scorer.FAMILY_AFFINE_NULL,
                included,
                zero.copy(),
            )
        )
        reveal[affine_id] = {
            "model_class": scorer.FAMILY_AFFINE_NULL,
            "excluded_opaque_track": excluded_track,
            "assignment_by_included_track_order": None,
        }

    if len(hypotheses) != scorer.HYPOTHESIS_COUNT:
        raise ClutterSpikeError("HYPOTHESIS_COUNT_CHANGED")
    if len(reveal) != scorer.HYPOTHESIS_COUNT:
        raise ClutterSpikeError("OPAQUE_HYPOTHESIS_COLLISION")
    for curve in curves.values():
        curve.fill(0.0)
    zero.fill(0.0)
    return track_ids, tuple(hypotheses), reveal


def _base_curve(
    code: str,
    curves: Mapping[str, Sequence[float]],
    *,
    reverse: bool,
) -> np.ndarray:
    value = np.asarray(curves[code], dtype=np.float64)
    return value[::-1].copy() if reverse else value.copy()


def synthetic_tracks(
    track_ids: Sequence[str],
    assignment_by_track: Mapping[str, str | None],
    curves: Mapping[str, Sequence[float]],
    *,
    reverse_geometry: bool = False,
    perturbation_scale_m: float = 0.25,
    extra_by_track: Mapping[str, Sequence[float]] | None = None,
) -> dict[str, np.ndarray]:
    if tuple(sorted(track_ids)) != tuple(track_ids) or len(track_ids) != 7:
        raise ClutterSpikeError("TRACK_SET_CHANGED")
    if set(assignment_by_track) != set(track_ids):
        raise ClutterSpikeError("ASSIGNMENT_TRACK_SET_CHANGED")
    index = np.arange(139, dtype=np.float64)
    elapsed = index * 30.0
    common = 9_000.0 + 0.03 * elapsed + 4.0 * np.sin(2.0 * np.pi * index / 47.0)
    result: dict[str, np.ndarray] = {}
    for slot, track_id in enumerate(track_ids):
        code = assignment_by_track[track_id]
        model = (
            np.zeros(139, dtype=np.float64)
            if code is None
            else _base_curve(code, curves, reverse=reverse_geometry)
        )
        perturbation = float(perturbation_scale_m) * (
            np.sin(2.0 * np.pi * index / (31.0 + slot))
            + 0.4 * np.cos(2.0 * np.pi * index / (17.0 + slot))
        )
        extra = (
            np.zeros(139, dtype=np.float64)
            if extra_by_track is None or track_id not in extra_by_track
            else np.asarray(extra_by_track[track_id], dtype=np.float64)
        )
        if extra.shape != (139,) or not np.all(np.isfinite(extra)):
            raise ClutterSpikeError("EXTRA_CURVE_INVALID")
        result[track_id] = (
            common
            + model
            + (80.0 * slot - 0.002 * slot * elapsed)
            + perturbation
            + extra
        )
        model.fill(0.0)
    return result


def _witness(
    track_ids: Sequence[str], assignment_by_track: Mapping[str, str | None]
) -> dict[str, object]:
    value = {
        "schema": "synthetic-seven-track-code-witness-v1",
        "track_identity": [
            {
                "track_id": track_id,
                "code_identity": assignment_by_track[track_id],
                "physical_role": (
                    "SYNTHETIC_CLUTTER"
                    if assignment_by_track[track_id] is None
                    else "SYNTHETIC_ORBIT_TRACK"
                ),
            }
            for track_id in track_ids
        ],
        "available_to_scorer": False,
        "same_fixture_family": True,
        "independent_physical_witness": False,
    }
    strict_json(value)
    return value


def _expected_orbital_reveal(
    track_ids: Sequence[str], assignment_by_track: Mapping[str, str | None]
) -> dict[str, object]:
    excluded = [
        track_id for track_id in track_ids if assignment_by_track[track_id] is None
    ]
    if len(excluded) != 1:
        raise ClutterSpikeError("EXPECTED_SINGLE_CLUTTER_TRACK")
    included_codes = [
        assignment_by_track[track_id]
        for track_id in track_ids
        if track_id != excluded[0]
    ]
    return {
        "model_class": scorer.FAMILY_ORBITAL,
        "excluded_opaque_track": excluded[0],
        "assignment_by_included_track_order": included_codes,
    }


def _final_state(
    score: Mapping[str, object],
    reveal: Mapping[str, Mapping[str, object]],
    expected_orbital: Mapping[str, object] | None,
) -> tuple[str, dict[str, object]]:
    best_id = str(score["best_global_opaque_id"])
    best = dict(reveal[best_id])
    if score["score_state"] == "ORBITAL_INJECTION_PREFERRED":
        orbital = dict(reveal[str(score["best_orbital_opaque_id"])])
        state = (
            "ORBITAL_INJECTION_CONCORDANT"
            if expected_orbital is not None and orbital == expected_orbital
            else "ORBITAL_INJECTION_DISCORDANT"
        )
        best = orbital
    elif score["score_state"] == "NONORBITAL_FAMILY_PREFERRED":
        state = "NONORBITAL_NULL_SUPPORTED"
    else:
        state = "ORBITAL_INJECTION_UNRESOLVED"
    return state, best


def _scenario(
    *,
    name: str,
    role: str,
    tracks: Mapping[str, Sequence[float]],
    witness: Mapping[str, object],
    expected_orbital: Mapping[str, object] | None,
    hypotheses: Sequence[scorer.OpaqueHypothesis],
    reveal: Mapping[str, Mapping[str, object]],
    expected_state: str,
) -> dict[str, object]:
    witness_hash = sha256(strict_json(witness).encode("ascii")).hexdigest()
    score = scorer.score_one_clutter_tracks(
        tracks, hypotheses, pairwise_guard_m=PAIRWISE_GUARD_M
    )
    score_hash = scorer.receipt_sha256(score)
    encoded = strict_json(score).lower()
    if "code_identity" in encoded or any(
        code.lower() in encoded for code in MODEL_CODES
    ):
        raise ClutterSpikeError("IDENTITY_LEAKED_INTO_SCORE_RECEIPT")
    final_state, best = _final_state(score, reveal, expected_orbital)
    if final_state != expected_state:
        raise ClutterSpikeError(f"SCENARIO_STATE_CHANGED:{name}:{final_state}")
    for values in tracks.values():
        if isinstance(values, np.ndarray):
            values.fill(0.0)
    return {
        "name": name,
        "role": role,
        "witness_sha256_before_score": witness_hash,
        "score_receipt_sha256_before_reveal": score_hash,
        "score_receipt": score,
        "reveal_after_score_hash": {
            "best_model": best,
            "witness": witness,
            "state": final_state,
        },
    }


def build_receipt(root: Path) -> dict[str, object]:
    root = Path(root)
    track_ids, hypotheses, reveal = hypothesis_surface(root)
    curves = six_track_spike._fixture_curves(root)
    structured_curves, structured_provenance = _structured_orbital_clutter(root)
    clutter_index = 3
    canonical: dict[str, str | None] = {}
    code_iter = iter(MODEL_CODES)
    for index, track_id in enumerate(track_ids):
        canonical[track_id] = None if index == clutter_index else next(code_iter)
    index = np.arange(139, dtype=np.float64)
    strong_clutter = 3.0 * PAIRWISE_GUARD_M * np.sin(2.0 * np.pi * index / 41.0)

    positive_tracks = synthetic_tracks(
        track_ids,
        canonical,
        curves,
        extra_by_track={track_ids[clutter_index]: strong_clutter},
    )
    positive_witness = _witness(track_ids, canonical)
    expected_positive = _expected_orbital_reveal(track_ids, canonical)

    structured_clutter_tracks = synthetic_tracks(
        track_ids,
        canonical,
        curves,
        extra_by_track={track_ids[clutter_index]: structured_curves["WRONG_ORBIT_G01"]},
    )

    permutation = (
        track_ids[4],
        track_ids[1],
        track_ids[6],
        track_ids[0],
        track_ids[3],
        track_ids[5],
        track_ids[2],
    )
    permuted_assignment = {
        permutation[index]: canonical[track_ids[index]] for index in range(7)
    }
    permuted_clutter = next(
        track_id for track_id in track_ids if permuted_assignment[track_id] is None
    )
    permuted_tracks = synthetic_tracks(
        track_ids,
        permuted_assignment,
        curves,
        extra_by_track={permuted_clutter: strong_clutter},
    )

    affine_assignment = {track_id: None for track_id in track_ids}
    affine_tracks = synthetic_tracks(
        track_ids,
        affine_assignment,
        curves,
        perturbation_scale_m=0.0,
    )

    reversed_tracks = synthetic_tracks(
        track_ids,
        canonical,
        curves,
        reverse_geometry=True,
        extra_by_track={track_ids[clutter_index]: strong_clutter},
    )

    two_clutter_assignment = dict(canonical)
    second_clutter_track = next(
        track_id
        for track_id in track_ids
        if two_clutter_assignment[track_id] == MODEL_CODES[0]
    )
    two_clutter_assignment[second_clutter_track] = None
    second_clutter = 3.5 * PAIRWISE_GUARD_M * np.cos(2.0 * np.pi * index / 53.0)
    two_clutter_tracks = synthetic_tracks(
        track_ids,
        two_clutter_assignment,
        curves,
        extra_by_track={
            track_ids[clutter_index]: strong_clutter,
            second_clutter_track: second_clutter,
        },
    )

    missing_candidate_assignment = dict(canonical)
    missing_candidate_track = next(
        track_id
        for track_id in track_ids
        if missing_candidate_assignment[track_id] == MODEL_CODES[0]
    )
    missing_candidate_assignment[missing_candidate_track] = None
    missing_candidate_tracks = synthetic_tracks(
        track_ids,
        missing_candidate_assignment,
        curves,
        extra_by_track={
            track_ids[clutter_index]: structured_curves["WRONG_ORBIT_G01"],
            missing_candidate_track: structured_curves["ORBITAL_G22"],
        },
    )

    discordant_assignment = dict(canonical)
    first_discordant_track = next(
        track_id
        for track_id in track_ids
        if discordant_assignment[track_id] == MODEL_CODES[0]
    )
    second_discordant_track = next(
        track_id
        for track_id in track_ids
        if discordant_assignment[track_id] == MODEL_CODES[1]
    )
    discordant_assignment[first_discordant_track] = MODEL_CODES[1]
    discordant_assignment[second_discordant_track] = MODEL_CODES[0]
    discordant_tracks = synthetic_tracks(
        track_ids,
        canonical,
        curves,
        extra_by_track={track_ids[clutter_index]: strong_clutter},
    )

    duplicate_assignment = dict(canonical)
    duplicate_assignment[track_ids[clutter_index]] = MODEL_CODES[0]
    duplicate_tracks = synthetic_tracks(
        track_ids,
        duplicate_assignment,
        curves,
        perturbation_scale_m=0.0,
    )
    shift_samples = NEAR_DEGENERATE_SHIFT_S / 30.0
    base = np.asarray(curves[MODEL_CODES[0]], dtype=np.float64)
    shifted = np.interp(index + shift_samples, index, base)
    near_degenerate_tracks = synthetic_tracks(
        track_ids,
        duplicate_assignment,
        curves,
        perturbation_scale_m=0.0,
        extra_by_track={track_ids[clutter_index]: shifted - base},
    )
    shifted.fill(0.0)

    scenarios = [
        _scenario(
            name="six_orbits_plus_one_arbitrary_clutter",
            role="POSITIVE_CONTROL",
            tracks=positive_tracks,
            witness=positive_witness,
            expected_orbital=expected_positive,
            hypotheses=hypotheses,
            reveal=reveal,
            expected_state="ORBITAL_INJECTION_CONCORDANT",
        ),
        _scenario(
            name="track_and_clutter_slot_permutation",
            role="OPAQUE_SELECTION_INVARIANCE_CONTROL",
            tracks=permuted_tracks,
            witness=_witness(track_ids, permuted_assignment),
            expected_orbital=_expected_orbital_reveal(track_ids, permuted_assignment),
            hypotheses=hypotheses,
            reveal=reveal,
            expected_state="ORBITAL_INJECTION_CONCORDANT",
        ),
        _scenario(
            name="six_orbits_plus_independent_compiled_orbital_shape",
            role="STRUCTURED_CLUTTER_POSITIVE_CONTROL",
            tracks=structured_clutter_tracks,
            witness=positive_witness,
            expected_orbital=expected_positive,
            hypotheses=hypotheses,
            reveal=reveal,
            expected_state="ORBITAL_INJECTION_CONCORDANT",
        ),
        _scenario(
            name="all_tracks_prefix_affine",
            role="AFFINE_NULL_CONTROL",
            tracks=affine_tracks,
            witness=_witness(track_ids, affine_assignment),
            expected_orbital=None,
            hypotheses=hypotheses,
            reveal=reveal,
            expected_state="NONORBITAL_NULL_SUPPORTED",
        ),
        _scenario(
            name="time_reversed_geometry",
            role="GEOMETRY_DESTROYING_NULL_CONTROL",
            tracks=reversed_tracks,
            witness=positive_witness,
            expected_orbital=None,
            hypotheses=hypotheses,
            reveal=reveal,
            expected_state="NONORBITAL_NULL_SUPPORTED",
        ),
        _scenario(
            name="two_arbitrary_clutter_tracks_with_budget_one",
            role="CLUTTER_BUDGET_NEGATIVE_CONTROL",
            tracks=two_clutter_tracks,
            witness=_witness(track_ids, two_clutter_assignment),
            expected_orbital=None,
            hypotheses=hypotheses,
            reveal=reveal,
            expected_state="ORBITAL_INJECTION_UNRESOLVED",
        ),
        _scenario(
            name="missing_expected_candidate_plus_two_compiled_orbital_shapes",
            role="PHYSICAL_CANDIDATE_ABSENCE_NEGATIVE_CONTROL",
            tracks=missing_candidate_tracks,
            witness=_witness(track_ids, missing_candidate_assignment),
            expected_orbital=None,
            hypotheses=hypotheses,
            reveal=reveal,
            expected_state="ORBITAL_INJECTION_UNRESOLVED",
        ),
        _scenario(
            name="post_score_code_witness_disagrees_with_selected_orbits",
            role="IDENTITY_WITNESS_DISCORDANCE_CONTROL",
            tracks=discordant_tracks,
            witness=_witness(track_ids, discordant_assignment),
            expected_orbital=_expected_orbital_reveal(track_ids, discordant_assignment),
            hypotheses=hypotheses,
            reveal=reveal,
            expected_state="ORBITAL_INJECTION_DISCORDANT",
        ),
        _scenario(
            name="orbit_like_duplicate_clutter",
            role="NONIDENTIFIABLE_CLUTTER_CONTROL",
            tracks=duplicate_tracks,
            witness=_witness(track_ids, duplicate_assignment),
            expected_orbital=None,
            hypotheses=hypotheses,
            reveal=reveal,
            expected_state="ORBITAL_INJECTION_UNRESOLVED",
        ),
        _scenario(
            name="locally_time_shifted_orbit_like_clutter",
            role="NEAR_DEGENERATE_NONIDENTICAL_CLUTTER_CONTROL",
            tracks=near_degenerate_tracks,
            witness=_witness(track_ids, duplicate_assignment),
            expected_orbital=None,
            hypotheses=hypotheses,
            reveal=reveal,
            expected_state="ORBITAL_INJECTION_UNRESOLVED",
        ),
    ]

    scenario_states = {
        row["name"]: row["reveal_after_score_hash"]["state"] for row in scenarios
    }
    required = {
        "six_orbits_plus_one_arbitrary_clutter": "ORBITAL_INJECTION_CONCORDANT",
        "track_and_clutter_slot_permutation": "ORBITAL_INJECTION_CONCORDANT",
        "six_orbits_plus_independent_compiled_orbital_shape": "ORBITAL_INJECTION_CONCORDANT",
        "all_tracks_prefix_affine": "NONORBITAL_NULL_SUPPORTED",
        "time_reversed_geometry": "NONORBITAL_NULL_SUPPORTED",
        "two_arbitrary_clutter_tracks_with_budget_one": "ORBITAL_INJECTION_UNRESOLVED",
        "missing_expected_candidate_plus_two_compiled_orbital_shapes": "ORBITAL_INJECTION_UNRESOLVED",
        "post_score_code_witness_disagrees_with_selected_orbits": "ORBITAL_INJECTION_DISCORDANT",
        "orbit_like_duplicate_clutter": "ORBITAL_INJECTION_UNRESOLVED",
        "locally_time_shifted_orbit_like_clutter": "ORBITAL_INJECTION_UNRESOLVED",
    }
    outcome = (
        OUTCOME_DISCRIMINATIVE
        if scenario_states == required
        else OUTCOME_NOT_DISCRIMINATIVE
    )
    surface_definition = [
        {
            "opaque_id": row.opaque_id,
            "family": row.family,
            "included_track_indices": list(row.included_track_indices),
            "matrix_sha256": sha256(
                np.asarray(row.model_matrix_m, dtype="<f8").tobytes(order="C")
            ).hexdigest(),
        }
        for row in hypotheses
    ]
    surface_sha256 = sha256(strict_json(surface_definition).encode("ascii")).hexdigest()
    result = {
        "schema": "gnss-all-track-clutter-spike-receipt-v2",
        "version": SPIKE_VERSION,
        "outcome": outcome,
        "claim_scope": "SYNTHETIC_ONE_CLUTTER_MECHANISM_ONLY",
        "physical_question": (
            "CAN_SIX_ORBITAL_CURVES_BE_IDENTIFIED_INSIDE_SEVEN_OPAQUE_TRACKS_"
            "WITH_ONE_PREDECLARED_ARBITRARY_CLUTTER_ALLOWANCE"
        ),
        "information_gain": (
            "TESTS_WHETHER_THE_REAL_ALGO_SEVEN_COMPLETE_TRACK_TOPOLOGY_REQUIRES_"
            "ABANDONMENT_OR_ONLY_AN_EXPLICIT_SYMMETRIC_CLUTTER_MODEL"
        ),
        "why_existing_result_cannot_answer": (
            "THE_FROZEN_SIX_TRACK_SCORER_HAS_NO_REPRESENTATION_FOR_AN_EXTRA_"
            "COMPLETE_TRACK_AND_CORRECTLY_REFUSED_BEFORE_MEASUREMENT_SCORING"
        ),
        "minimum_experiment": (
            "CLOSED_SYNTHETIC_SEVEN_TRACK_SURFACE_WITH_ONE_CLUTTER_BUDGET_"
            "ORBITAL_INJECTION_AFFINE_NULL_AND_TIME_REVERSED_GEOMETRY_NULL"
        ),
        "closed_development_fixture": {
            "prediction_bundle_sha256": frozen.BUNDLE_CANONICAL_SHA256,
            "structured_clutter_fixture": structured_provenance,
            "consumed_algo_receipts_used_as_numerical_input": False,
            "algo_observation_values_used": 0,
            "network_requests": 0,
        },
        "source": {
            "spike_sha256": canonical_sha256(Path(__file__)),
            "scorer_sha256": canonical_sha256(Path(scorer.__file__)),
        },
        "selection_boundary": {
            "input": "ALL_SEVEN_OPAQUE_TRACKS",
            "clutter_budget": 1,
            "tracks_evaluated_per_hypothesis": 6,
            "prn_available_to_scorer": False,
            "posthoc_track_exclusion": False,
            "all_exclusions_enumerated": True,
            "same_exclusion_budget_for_orbital_and_null_families": True,
        },
        "opaque_surface": {
            "observed_tracks": 7,
            "orbital_injections": scorer.ORBITAL_HYPOTHESIS_COUNT,
            "time_reversed_geometry_nulls": scorer.GEOMETRY_NULL_COUNT,
            "affine_only_nulls": scorer.AFFINE_NULL_COUNT,
            "hypothesis_count": scorer.HYPOTHESIS_COUNT,
            "surface_definition_sha256": surface_sha256,
            "mapping_available_to_scorer": False,
        },
        "scoring": {
            "common_mode": "PER_HYPOTHESIS_INCLUDED_SIX_TRACK_CENTERING",
            "nuisance": "PREFIX_ONLY_CONSTANT_AND_RATE_PER_CENTERED_TRACK",
            "effective_parameters_per_hypothesis": 10,
            "heldout_refit": False,
            "free_time_phase": False,
            "preference_guard_m": PAIRWISE_GUARD_M,
            "absolute_fit_guard_m": PAIRWISE_GUARD_M,
            "receipt_metric_quantization_decimal_places": scorer.METRIC_DECIMALS,
        },
        "scenarios": scenarios,
        "observation_access": {
            "network_requests": 0,
            "product_locators": 0,
            "headers": 0,
            "payload_bytes": 0,
            "values": 0,
        },
        "algo_retry_consumed_again": False,
        "real_measurement_score": "NOT_EVALUATED",
        "primary_selected": False,
        "new_gate": False,
        "stop": ("STOP_AFTER_SYNTHETIC_MECHANISM;_DO_NOT_SCORE_ALGO_OR_SELECT_PRIMARY"),
    }
    strict_json(result)
    for hypothesis in hypotheses:
        hypothesis.model_matrix_m.fill(0.0)
    for curve in curves.values():
        curve.fill(0.0)
    for curve in structured_curves.values():
        curve.fill(0.0)
    strong_clutter.fill(0.0)
    second_clutter.fill(0.0)
    return result


def main() -> int:
    build_receipt(Path(__file__).resolve().parent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
