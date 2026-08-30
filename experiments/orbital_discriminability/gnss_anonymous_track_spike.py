"""Closed synthetic anonymous-track/code-witness mechanism spike.

This module uses only the already frozen orbital prediction bundle as a
historical development fixture.  It accesses no observation product or value.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from typing import Final, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import gnss_anonymous_track_scorer as blind
from experiments.orbital_discriminability import gnss_opaque_orbit_scorer as frozen


SPIKE_VERSION: Final = "gnss-anonymous-track-sealed-code-witness-spike-v1"
RECEIPT_NAME: Final = "GNSS_ANONYMOUS_TRACK_SPIKE_RECEIPT.json"
MAPPING_NAME: Final = "GNSS_BLIND_ORBIT_ASSIGNMENT_MAPPING_SEAL.json"
MAPPING_CANONICAL_SHA256: Final = (
    "b719a2bf17e66fcafa3597c4018d6acd039bdac4e33ecb173795646ff47245db"
)
DEVELOPMENT_GUARD_M: Final = 7_339.701234647398
TARGET_MODEL: Final = "G22_RELATIVE_TO_G30"
WRONG_ORBIT_MODEL: Final = "G06_RELATIVE_TO_G30"
AFFINE_MODEL: Final = "PREFIX_AFFINE_ONLY"
REFERENCE_TOKEN: Final = "G30"


class AnonymousTrackSpikeError(ValueError):
    """The closed synthetic fixture or reveal order changed."""


def strict_json(value: object, *, pretty: bool = False) -> str:
    return blind.strict_json(value, pretty=pretty)


def canonical_sha256(path: Path) -> str:
    payload = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return sha256(payload).hexdigest()


def source_sha256(path: Path) -> str:
    return canonical_sha256(path)


def _read_strict_object(path: Path) -> dict[str, object]:
    value = json.loads(
        Path(path).read_text(encoding="ascii"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    if not isinstance(value, dict):
        raise AnonymousTrackSpikeError(f"NOT_OBJECT:{path.name}")
    return value


def _mapping(root: Path) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    path = Path(root) / MAPPING_NAME
    if canonical_sha256(path) != MAPPING_CANONICAL_SHA256:
        raise AnonymousTrackSpikeError("FROZEN_MAPPING_CHANGED")
    value = _read_strict_object(path)
    rows = value.get("mapping")
    if not isinstance(rows, list) or len(rows) != 6:
        raise AnonymousTrackSpikeError("FROZEN_MAPPING_SURFACE_CHANGED")
    by_id: dict[str, dict[str, str]] = {}
    by_model: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise AnonymousTrackSpikeError("FROZEN_MAPPING_ROW_INVALID")
        identifier = str(row.get("opaque_id"))
        model = str(row.get("model"))
        model_class = str(row.get("model_class"))
        by_id[identifier] = {
            "model": model,
            "model_class": model_class,
            "orientation": "TRACK_A_MINUS_TRACK_B",
        }
        by_model[model] = identifier
    if set(by_id) != set(value_id for value_id in by_model.values()):
        raise AnonymousTrackSpikeError("FROZEN_MAPPING_NOT_BIJECTIVE")
    return by_id, by_model


def _reverse_id(identifier: str) -> str:
    token = sha256(f"TRACK_ORDER_REVERSED:{identifier}".encode("ascii")).hexdigest()
    return "H_" + token[:16].upper()


def hypothesis_surface(
    root: Path,
) -> tuple[dict[str, np.ndarray], dict[str, dict[str, str]], dict[str, str]]:
    bundle = frozen.load_exact_bundle(Path(root) / frozen.BUNDLE_NAME)
    reveal, by_model = _mapping(root)
    curves = {
        identifier: np.asarray(values, dtype=np.float64).copy()
        for identifier, values in bundle["curves_m"].items()
    }
    for identifier, row in tuple(reveal.items()):
        if row["model_class"] != "ORBITAL_CANDIDATE":
            continue
        reversed_identifier = _reverse_id(identifier)
        if reversed_identifier in curves:
            raise AnonymousTrackSpikeError("REVERSED_ID_COLLISION")
        curves[reversed_identifier] = -curves[identifier]
        reveal[reversed_identifier] = {
            **row,
            "orientation": "TRACK_B_MINUS_TRACK_A",
        }
    if len(curves) != blind.HYPOTHESIS_COUNT or set(curves) != set(reveal):
        raise AnonymousTrackSpikeError("ANONYMOUS_SURFACE_CHANGED")
    return curves, reveal, by_model


def _synthetic_tracks(
    relative_m: Sequence[float], *, perturbation_scale_m: float = 0.25
) -> tuple[np.ndarray, np.ndarray]:
    relative = np.asarray(relative_m, dtype=np.float64)
    if relative.shape != (blind.RAW_EPOCHS,) or not np.all(np.isfinite(relative)):
        raise AnonymousTrackSpikeError("SYNTHETIC_RELATIVE_TRACK_INVALID")
    index = np.arange(blind.RAW_EPOCHS, dtype=np.float64)
    elapsed = index * blind.STEP_S
    common_clock = 2_500.0 + 0.02 * elapsed + 3.0 * np.sin(2.0 * np.pi * index / 43.0)
    differential_affine = 120.0 - 0.004 * elapsed
    perturbation = float(perturbation_scale_m) * (
        np.sin(2.0 * np.pi * index / 37.0)
        + 0.5 * np.cos(2.0 * np.pi * index / 19.0)
    )
    coordinate = relative + differential_affine + perturbation
    track_a = common_clock + 0.5 * coordinate
    track_b = common_clock - 0.5 * coordinate
    return track_a, track_b


def _code_witness(track_a_code: str, track_b_code: str) -> dict[str, object]:
    result = {
        "schema": "gnss-synthetic-code-witness-v1",
        "source": "SYNTHETIC_ORTHOGONAL_FEATURE",
        "track_identity": [
            {"track_id": "TRACK_A", "code_identity": track_a_code},
            {"track_id": "TRACK_B", "code_identity": track_b_code},
        ],
        "available_to_orbit_scorer": False,
        "same_samples_as_orbital_tracks": True,
        "independent_hardware_root": False,
    }
    strict_json(result)
    return result


def _expected_pair(row: Mapping[str, str]) -> tuple[str, str] | None:
    if row["model_class"] != "ORBITAL_CANDIDATE":
        return None
    target = row["model"].split("_RELATIVE_TO_")[0]
    if row["orientation"] == "TRACK_A_MINUS_TRACK_B":
        return target, REFERENCE_TOKEN
    return REFERENCE_TOKEN, target


def _scenario(
    *,
    name: str,
    role: str,
    relative_m: Sequence[float],
    track_a_code: str,
    track_b_code: str,
    surface: Mapping[str, Sequence[float]],
    reveal: Mapping[str, Mapping[str, str]],
    expected_orbit_model: str | None,
) -> dict[str, object]:
    witness = _code_witness(track_a_code, track_b_code)
    witness_hash = sha256(strict_json(witness).encode("ascii")).hexdigest()
    track_a, track_b = _synthetic_tracks(relative_m)
    score = blind.score_anonymous_pair(
        track_a,
        track_b,
        surface,
        pairwise_guard_m=DEVELOPMENT_GUARD_M,
    )
    score_hash = blind.receipt_sha256(score)
    rendered_score = strict_json(score)
    if any(token in rendered_score for token in ("G22", "G30", "G06", "code_identity")):
        raise AnonymousTrackSpikeError("IDENTITY_LEAKED_INTO_SCORE_RECEIPT")
    if score["identity_reveal_performed"] is not False:
        raise AnonymousTrackSpikeError("IDENTITY_REVEALED_BEFORE_SCORE_HASH")
    best_id = str(score["best_opaque_id"])
    best = reveal[best_id]
    witness_pair = (track_a_code, track_b_code)
    expected_pair = _expected_pair(best)
    if score["orbital_score_state"] != "OPAQUE_HYPOTHESIS_PREFERRED":
        final_state = "ORBIT_ASSIGNMENT_UNRESOLVED"
    elif expected_pair is not None and expected_pair == witness_pair:
        final_state = "ORBIT_CODE_CONCORDANT"
    else:
        final_state = "ORBIT_CODE_DISCORDANT"
    if expected_orbit_model is not None and (
        best["model"] != expected_orbit_model
        or score["orbital_score_state"] != "OPAQUE_HYPOTHESIS_PREFERRED"
    ):
        raise AnonymousTrackSpikeError(f"SCENARIO_ORBIT_RESULT_CHANGED:{name}")
    track_a.fill(0.0)
    track_b.fill(0.0)
    return {
        "name": name,
        "role": role,
        "code_witness_sha256_before_scoring": witness_hash,
        "score_receipt_sha256_before_reveal": score_hash,
        "score_receipt": score,
        "reveal_after_score_receipt_hash": {
            "best_opaque_id": best_id,
            "model": best["model"],
            "model_class": best["model_class"],
            "orientation": best["orientation"],
            "code_witness": witness,
            "state": final_state,
        },
    }


def build_receipt(root: Path) -> dict[str, object]:
    root = Path(root)
    surface, reveal, by_model = hypothesis_surface(root)
    target_id = by_model[TARGET_MODEL]
    wrong_id = by_model[WRONG_ORBIT_MODEL]
    affine_id = by_model[AFFINE_MODEL]
    target = surface[target_id]
    wrong = surface[wrong_id]
    affine = surface[affine_id]
    reversed_target = surface[_reverse_id(target_id)]

    exact_a, exact_b = _synthetic_tracks(target, perturbation_scale_m=0.0)
    exact_score = blind.score_anonymous_pair(
        exact_a, exact_b, surface, pairwise_guard_m=0.0
    )
    maximum_guard = float(exact_score["preference_margin_m"])
    if not maximum_guard > DEVELOPMENT_GUARD_M:
        raise AnonymousTrackSpikeError(
            "DEVELOPMENT_GUARD_NOT_BELOW_EXACT_FIXTURE_MARGIN"
        )
    exact_a.fill(0.0)
    exact_b.fill(0.0)

    scenarios = [
        _scenario(
            name="correct_model",
            role="POSITIVE_CONTROL",
            relative_m=target,
            track_a_code="G22",
            track_b_code="G30",
            surface=surface,
            reveal=reveal,
            expected_orbit_model=TARGET_MODEL,
        ),
        _scenario(
            name="wrong_orbit_truth",
            role="ANTI_AUTO_CONFIRMATION_CONTROL",
            relative_m=wrong,
            track_a_code="G06",
            track_b_code="G30",
            surface=surface,
            reveal=reveal,
            expected_orbit_model=WRONG_ORBIT_MODEL,
        ),
        _scenario(
            name="code_orbit_discordance",
            role="ORTHOGONAL_WITNESS_NEGATIVE_CONTROL",
            relative_m=target,
            track_a_code="G06",
            track_b_code="G30",
            surface=surface,
            reveal=reveal,
            expected_orbit_model=TARGET_MODEL,
        ),
        _scenario(
            name="track_order_reversed",
            role="PERMUTATION_CONTROL",
            relative_m=reversed_target,
            track_a_code="G30",
            track_b_code="G22",
            surface=surface,
            reveal=reveal,
            expected_orbit_model=TARGET_MODEL,
        ),
        _scenario(
            name="below_detectability_midpoint",
            role="AMBIGUITY_CONTROL",
            relative_m=0.5 * (target + affine),
            track_a_code="G22",
            track_b_code="G30",
            surface=surface,
            reveal=reveal,
            expected_orbit_model=None,
        ),
    ]
    expected_states = {
        "correct_model": "ORBIT_CODE_CONCORDANT",
        "wrong_orbit_truth": "ORBIT_CODE_CONCORDANT",
        "code_orbit_discordance": "ORBIT_CODE_DISCORDANT",
        "track_order_reversed": "ORBIT_CODE_CONCORDANT",
        "below_detectability_midpoint": "ORBIT_ASSIGNMENT_UNRESOLVED",
    }
    for scenario in scenarios:
        if scenario["reveal_after_score_receipt_hash"]["state"] != expected_states[
            scenario["name"]
        ]:
            raise AnonymousTrackSpikeError(
                f"SCENARIO_FINAL_STATE_CHANGED:{scenario['name']}"
            )

    surface_manifest = {
        identifier: sha256(
            strict_json([float(value) for value in surface[identifier]]).encode("ascii")
        ).hexdigest()
        for identifier in sorted(surface)
    }
    result = {
        "schema": "gnss-anonymous-track-spike-receipt-v1",
        "version": SPIKE_VERSION,
        "outcome": "ANONYMOUS_TRACK_SEALED_WITNESS_MECHANISM_DISCRIMINATIVE",
        "claim_scope": "SYNTHETIC_INTERFACE_MECHANISM_ONLY",
        "closed_development_fixture": {
            "prediction_bundle_sha256": frozen.BUNDLE_CANONICAL_SHA256,
            "mapping_seal_sha256": MAPPING_CANONICAL_SHA256,
            "observation_values_used": 0,
            "consumed_primary_reopened_or_rescored": False,
        },
        "source": {
            "spike_sha256": source_sha256(Path(__file__)),
            "scorer_sha256": source_sha256(Path(blind.__file__)),
        },
        "anonymous_hypothesis_surface": {
            "opaque_hypotheses": len(surface),
            "normal_family": 6,
            "track_order_reversed_family": 5,
            "curve_hashes": surface_manifest,
            "mapping_available_to_scorer": False,
        },
        "derived_detectability_boundary": {
            "exact_fixture_preference_margin_m": maximum_guard,
            "development_guard_m": DEVELOPMENT_GUARD_M,
            "remaining_synthetic_margin_m": maximum_guard - DEVELOPMENT_GUARD_M,
            "real_capability_interpretation": (
                "TOTAL_PAIRWISE_NONAFFINE_ENVELOPE_MUST_REMAIN_BELOW_"
                "EXACT_FIXTURE_PREFERENCE_MARGIN"
            ),
            "calibrated_probability_claimed": False,
        },
        "real_capability_terms": [
            {
                "term": "sample_zero_event_time_and_sample_rate",
                "state": "OPEN_TERM",
            },
            {
                "term": "common_oscillator_constant_and_rate",
                "state": "CANCELLED_OR_PREFIX_PROJECTED_IN_SYNTHETIC_TOPOLOGY",
            },
            {
                "term": "differential_nonaffine_oscillator",
                "state": "OPEN_TERM",
            },
            {"term": "ionosphere_and_propagation", "state": "OPEN_TERM"},
            {
                "term": "cycle_slip_or_midwindow_ambiguity",
                "state": "MEASUREMENT_INVALID_BEFORE_SCORE",
            },
            {
                "term": "gap_or_nonfinite_track",
                "state": "MEASUREMENT_INVALID_BEFORE_SCORE",
            },
            {
                "term": "track_order",
                "state": "EXPLICIT_FROZEN_HYPOTHESIS_FAMILY",
            },
        ],
        "real_capability_admission": "NOT_EVALUATED_OPEN_TERMS",
        "scenarios": scenarios,
        "observation_access": {
            "network_requests": 0,
            "product_locators": 0,
            "headers": 0,
            "payload_bytes": 0,
            "values": 0,
        },
        "next_maximum_action": (
            "BOUNDED_RAW_GNSS_CAPABILITY_CONSIDERATION_ONLY_AFTER_REVIEW"
        ),
        "stop": "STOP_BEFORE_CAPABILITY_SEARCH_OR_OBSERVATION",
    }
    strict_json(result)
    for curve in surface.values():
        curve.fill(0.0)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-receipt", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    if args.write_receipt.exists():
        raise SystemExit("RECEIPT_ALREADY_EXISTS")
    receipt = build_receipt(root)
    args.write_receipt.write_text(strict_json(receipt, pretty=True) + "\n", encoding="ascii")
    print(
        strict_json(
            {
                "outcome": receipt["outcome"],
                "observation_access": receipt["observation_access"],
                "real_capability_admission": receipt["real_capability_admission"],
            }
        )
    )


if __name__ == "__main__":
    main()
