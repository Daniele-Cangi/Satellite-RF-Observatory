"""Offline physical-envelope audit for the frozen DRAO one-clutter proof.

The audit reads only committed model/proof artifacts.  It does not select an
observation product, open a header, decode a measurement, or score an orbit.
"""

from __future__ import annotations

from hashlib import sha256
import json
from math import ceil, isfinite, radians, sin
from pathlib import Path
from typing import Final, Mapping, Sequence


AUDIT_VERSION: Final = "drao-one-clutter-physical-envelope-audit-v1"
OUTCOME: Final = "DRAO_PHYSICAL_ENVELOPE_NOT_ADMITTED"
AUDIT_NAME: Final = "GNSS_DRAO_PHYSICAL_ENVELOPE_AUDIT.json"
REPORT_NAME: Final = "GNSS_DRAO_PHYSICAL_ENVELOPE_AUDIT.md"

PLAN_NAME: Final = "GNSS_DRAO_ONE_CLUTTER_PROSPECTIVE_PLAN.json"
PLAN_SHA256: Final = (
    "a26dcc8e2f2ef00c345d93f2e64132a2536349fcfe0790ba198ae50046e9bb58"
)
HISTORICAL_ENVELOPE_NAME: Final = "AMC_OBSERVER_PRIMARY_PREDICTIONS.json"
HISTORICAL_ENVELOPE_SHA256: Final = (
    "c9f7236f3cc221cb8485fe82f0a739e720ee3725f9dbf7c7fcc54c4167794155"
)

EXPECTED_PLAN_OUTCOME: Final = "DRAO_ONE_CLUTTER_PROSPECTIVE_PLAN_FROZEN"
GUARD_M: Final = 7_339.701234647398
MINIMUM_SHIFTED_ELEVATION_DEG: Final = 22.71848831204289
ZENITH_DELAY_INTERVAL_MAX_M: Final = 3.5
RAW_EPOCHS: Final = 139
CODE_WITNESS_COVERAGE: Final = 0.95


class DraoPhysicalEnvelopeError(ValueError):
    """A frozen authority or physical-envelope invariant changed."""


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


def _reject_nonfinite(token: str) -> object:
    raise DraoPhysicalEnvelopeError(f"NONFINITE_FROZEN_ARTIFACT:{token}")


def _load_exact(root: Path, name: str, expected_sha256: str) -> dict[str, object]:
    payload = (Path(root) / name).read_bytes()
    if sha256(payload).hexdigest() != expected_sha256:
        raise DraoPhysicalEnvelopeError(f"FROZEN_ARTIFACT_HASH_CHANGED:{name}")
    value = json.loads(payload, parse_constant=_reject_nonfinite)
    if not isinstance(value, dict):
        raise DraoPhysicalEnvelopeError(f"FROZEN_ARTIFACT_NOT_OBJECT:{name}")
    return value


def centered_peak_to_peak_bounds(
    per_track_peak_to_peak_m: Sequence[float],
) -> tuple[float, ...]:
    """Transfer per-track p-p bounds through six-track ensemble centering.

    For ``c_i = e_i - mean_j(e_j)``, subadditivity of peak-to-peak gives
    ``pp(c_i) <= pp(e_i) + mean_j(pp(e_j))``.  Prefix affine projection is
    linear and commutes with the per-epoch centering operator.
    """

    values = tuple(float(value) for value in per_track_peak_to_peak_m)
    if len(values) != 6 or any(not isfinite(value) or value < 0.0 for value in values):
        raise DraoPhysicalEnvelopeError("PER_TRACK_BOUND_VECTOR_INVALID")
    mean_bound = sum(values) / len(values)
    return tuple(value + mean_bound for value in values)


def uniform_centered_bound(per_track_peak_to_peak_m: float) -> float:
    return max(centered_peak_to_peak_bounds([per_track_peak_to_peak_m] * 6))


def troposphere_common_mode_bound_m(
    minimum_elevation_deg: float = MINIMUM_SHIFTED_ELEVATION_DEG,
    zenith_delay_max_m: float = ZENITH_DELAY_INTERVAL_MAX_M,
) -> float:
    if not (0.0 < minimum_elevation_deg <= 90.0):
        raise DraoPhysicalEnvelopeError("MINIMUM_ELEVATION_INVALID")
    if not isfinite(zenith_delay_max_m) or zenith_delay_max_m < 0.0:
        raise DraoPhysicalEnvelopeError("ZENITH_DELAY_BOUND_INVALID")
    per_track_peak_to_peak = zenith_delay_max_m / sin(
        radians(minimum_elevation_deg)
    )
    return uniform_centered_bound(per_track_peak_to_peak)


def maximum_missing_witness_epochs(
    total_epochs: int = RAW_EPOCHS,
    minimum_coverage: float = CODE_WITNESS_COVERAGE,
) -> int:
    if total_epochs <= 0 or not (0.0 <= minimum_coverage <= 1.0):
        raise DraoPhysicalEnvelopeError("WITNESS_COVERAGE_INVALID")
    return total_epochs - ceil(total_epochs * minimum_coverage)


def _historical_terms(value: Mapping[str, object]) -> dict[str, dict[str, object]]:
    physical = value.get("physical_envelope")
    if not isinstance(physical, Mapping):
        raise DraoPhysicalEnvelopeError("HISTORICAL_ENVELOPE_MISSING")
    rows = physical.get("terms")
    if not isinstance(rows, list):
        raise DraoPhysicalEnvelopeError("HISTORICAL_TERMS_INVALID")
    result = {
        str(row.get("term")): dict(row)
        for row in rows
        if isinstance(row, Mapping) and isinstance(row.get("term"), str)
    }
    required = {
        "BROADCAST_ORBIT_SV_ACCURACY",
        "ANTENNA_PCV_AND_PHASE_WINDUP",
        "MULTIPATH_AND_SIGNAL_SPECIFIC_HARDWARE",
        "SATELLITE_CLOCK_RETARDED_TIME_REMAINDER",
        "HIGHER_ORDER_IONOSPHERE",
        "RINEX_CARRIER_PHASE_QUANTIZATION",
        "STATION_C_DIFFERENTIAL_TROPOSPHERE",
    }
    if not required <= set(result):
        raise DraoPhysicalEnvelopeError("HISTORICAL_PRIMITIVE_SET_CHANGED")
    return result


def _conditional_historical_bound(
    terms: Mapping[str, Mapping[str, object]], *names: str
) -> float:
    return sum(float(terms[name]["heldout_peak_to_peak_bound_m"]) for name in names)


def build_audit(root: Path) -> dict[str, object]:
    root = Path(root)
    plan = _load_exact(root, PLAN_NAME, PLAN_SHA256)
    historical = _load_exact(
        root, HISTORICAL_ENVELOPE_NAME, HISTORICAL_ENVELOPE_SHA256
    )
    if plan.get("outcome") != EXPECTED_PLAN_OUTCOME:
        raise DraoPhysicalEnvelopeError("FROZEN_PLAN_OUTCOME_CHANGED")
    access = plan.get("artifact_access")
    if not isinstance(access, Mapping) or not access or set(access.values()) != {0}:
        raise DraoPhysicalEnvelopeError("PLAN_OBSERVATION_ACCESS_NOT_ZERO")
    admission = plan.get("pre_artifact_admission")
    if not isinstance(admission, Mapping):
        raise DraoPhysicalEnvelopeError("PLAN_ADMISSION_MISSING")
    if (
        float(admission.get("maximum_aggregate_effect_m", -1.0)) != GUARD_M
        or admission.get("artifact_selection_allowed_before_admission") is not False
        or admission.get("failure_terminal") != OUTCOME
    ):
        raise DraoPhysicalEnvelopeError("PLAN_PHYSICAL_BOUNDARY_CHANGED")
    historical_access = historical.get("observation_access")
    if not isinstance(historical_access, Mapping) or set(historical_access.values()) != {0}:
        raise DraoPhysicalEnvelopeError("HISTORICAL_SOURCE_USED_OBSERVATION")

    terms = _historical_terms(historical)
    troposphere_bound = troposphere_common_mode_bound_m()
    missing_code_epochs = maximum_missing_witness_epochs()
    if missing_code_epochs != 6:
        raise DraoPhysicalEnvelopeError("CODE_WITNESS_GAP_REGRESSION_CHANGED")

    conditional_orbit_clock = _conditional_historical_bound(
        terms,
        "BROADCAST_ORBIT_SV_ACCURACY",
        "SATELLITE_CLOCK_RETARDED_TIME_REMAINDER",
    )
    conditional_antenna = _conditional_historical_bound(
        terms, "ANTENNA_PCV_AND_PHASE_WINDUP"
    )
    conditional_higher_iono = _conditional_historical_bound(
        terms, "HIGHER_ORDER_IONOSPHERE"
    )
    conditional_hardware = _conditional_historical_bound(
        terms, "MULTIPATH_AND_SIGNAL_SPECIFIC_HARDWARE"
    )
    conditional_quantization = _conditional_historical_bound(
        terms, "RINEX_CARRIER_PHASE_QUANTIZATION"
    )

    term_rows = [
        {
            "term": "EVENT_TIME_DIRECT_TRAJECTORY_ENVELOPE",
            "state": "UNRESOLVED",
            "numeric_state": "UNAVAILABLE",
            "common_mode_heldout_peak_to_peak_bound_m": None,
            "reason": (
                "THE_COMMITTED_DRAO_RECEIPT_RETAINS_DIRECT_TIME_SHIFTED_"
                "VISIBILITY_BUT_NOT_THE_SIX_NOMINAL_AND_T_PLUS_MINUS_15_S_"
                "RANGE_CURVES_AFTER_PREFIX_AFFINE_PROJECTION"
            ),
            "forbidden_substitute": "LOCAL_SLOPE_TIMES_CLOCK_ERROR",
        },
        {
            "term": "BROADCAST_ORBIT_AND_CLOCK",
            "state": "UNRESOLVED",
            "numeric_state": "CONDITIONAL_HISTORICAL_ANALOGUE_ONLY",
            "common_mode_heldout_peak_to_peak_bound_m": None,
            "historical_two_track_analogue_m": conditional_orbit_clock,
            "reason": (
                "DOY231_SV_ACCURACY_AND_CLOCK_REMAINDER_FIELDS_WERE_NOT_"
                "RETAINED;_DOY221_AMC_VALUES_DO_NOT_ESTABLISH_A_DRAO_BOUND"
            ),
        },
        {
            "term": "DIFFERENTIAL_TROPOSPHERE",
            "state": "MODELED_CONSERVATIVE_INTERVAL",
            "numeric_state": "FINITE_CONSERVATIVE_BOUND",
            "common_mode_heldout_peak_to_peak_bound_m": troposphere_bound,
            "zenith_delay_interval_m": [0.0, ZENITH_DELAY_INTERVAL_MAX_M],
            "minimum_direct_time_shifted_elevation_deg": (
                MINIMUM_SHIFTED_ELEVATION_DEG
            ),
            "mapping": "ONE_OVER_SINE_THEN_SIX_TRACK_CENTERING",
        },
        {
            "term": "IONOSPHERE_FREE_AND_HIGHER_ORDER_REMAINDER",
            "state": "UNRESOLVED",
            "numeric_state": "CONDITIONAL_HISTORICAL_ANALOGUE_ONLY",
            "common_mode_heldout_peak_to_peak_bound_m": None,
            "conditional_higher_order_bound_m": conditional_higher_iono,
            "reason": (
                "THE_HIGHER_ORDER_INTERVAL_IS_TRANSFERABLE_ONLY_AFTER_THE_"
                "UNSELECTED_PRODUCT_PROVES_EXACT_L1C_L2W_SIGNAL_AND_SCALE_"
                "SEMANTICS"
            ),
        },
        {
            "term": "ANTENNA_PCV_AND_PHASE_WINDUP",
            "state": "UNRESOLVED",
            "numeric_state": "CONDITIONAL_HISTORICAL_ANALOGUE_ONLY",
            "common_mode_heldout_peak_to_peak_bound_m": None,
            "historical_two_track_analogue_m": conditional_antenna,
            "reason": (
                "THE_STATION LOG IDENTIFIES THE ANTENNA BUT THE FROZEN_"
                "AUTHORITY DOES_NOT_BIND_A_DRAO_PCV_CALIBRATION_OR_PHASE_"
                "WINDUP_IMPLEMENTATION"
            ),
        },
        {
            "term": "MULTIPATH_AND_SIGNAL_SPECIFIC_HARDWARE",
            "state": "UNRESOLVED",
            "numeric_state": "WITNESS_DOES_NOT_COVER_REQUIRED_WINDOW",
            "common_mode_heldout_peak_to_peak_bound_m": None,
            "conditional_bound_if_every_epoch_witnessed_m": conditional_hardware,
            "maximum_unwitnessed_epochs_per_track": missing_code_epochs,
            "reason": (
                "NINETY_FIVE_PERCENT_CODE_COVERAGE_PERMITS_UNBOUNDED_PHASE_"
                "ERROR_AT_SIX_EPOCHS;_NO_INTERPOLATION_OR_GAP_BRIDGING_IS_"
                "ALLOWED_AND_ONE_UNBOUNDED_EPOCH_CAN_DOMINATE_PEAK_TO_PEAK"
            ),
        },
        {
            "term": "RECEIVER_CLOCK_AND_IMPLEMENTATION",
            "state": "PARTIAL_EXACT_CANCELLATION_REMAINDER_UNRESOLVED",
            "numeric_state": "UNAVAILABLE",
            "common_mode_heldout_peak_to_peak_bound_m": None,
            "epoch_common_receiver_clock_contribution_m": 0.0,
            "reason": (
                "AN_ADDITIVE_EPOCH_COMMON_CLOCK_TERM_CANCELS_EXACTLY_UNDER_"
                "ENSEMBLE_CENTERING;_TRACK_SIGNAL_OR_CHANNEL_DEPENDENT_"
                "IMPLEMENTATION_ERROR_DOES_NOT_AND_HAS_NO_FROZEN_BOUND"
            ),
        },
        {
            "term": "RINEX_QUANTIZATION",
            "state": "UNRESOLVED",
            "numeric_state": "CONDITIONAL_HISTORICAL_ANALOGUE_ONLY",
            "common_mode_heldout_peak_to_peak_bound_m": None,
            "conditional_f14_3_bound_m": conditional_quantization,
            "reason": (
                "NO_DRAO_ARTIFACT_OR_SERIALIZATION_HAS_BEEN_SELECTED;_THE_"
                "F14_3_QUANTIZATION_MODEL_CANNOT_BE_ASSUMED_PRE_ARTIFACT"
            ),
        },
    ]
    expected = list(admission["terms_that_cannot_default_to_zero"])
    if [row["term"] for row in term_rows] != expected:
        raise DraoPhysicalEnvelopeError("AUDITED_TERM_ORDER_CHANGED")
    unresolved = [row["term"] for row in term_rows if row["state"] != "MODELED_CONSERVATIVE_INTERVAL"]

    result = {
        "schema": "gnss-drao-physical-envelope-audit-v1",
        "version": AUDIT_VERSION,
        "outcome": OUTCOME,
        "physical_question": (
            "CAN_OUTCOME_INDEPENDENT_DRAO_UNCERTAINTY_BOUNDS_BE_TRANSFERRED_"
            "THROUGH_THE_FROZEN_SIX_TRACK_COMMON_MODE_TO_FIT_INSIDE_THE_GUARD"
        ),
        "new_information": (
            "THE_FROZEN_DRAO_PROOF_CANNOT_INTERPRET_A_NEGATIVE_BECAUSE_"
            "SEVEN_REQUIRED_TERMS_REMAIN_UNBOUNDED_BEFORE_ARTIFACT_SELECTION"
        ),
        "authority": {
            PLAN_NAME: {
                "sha256": PLAN_SHA256,
                "outcome": EXPECTED_PLAN_OUTCOME,
                "role": "FROZEN_PROSPECTIVE_PROOF",
            },
            HISTORICAL_ENVELOPE_NAME: {
                "sha256": HISTORICAL_ENVELOPE_SHA256,
                "role": (
                    "PRIMITIVE_BOUND_PROVENANCE_ONLY_NOT_A_DRAO_ENVELOPE"
                ),
            },
            "audit_source_canonical_sha256": canonical_sha256(Path(__file__)),
        },
        "common_mode_topology": {
            "included_tracks_per_hypothesis": 6,
            "operator": "C=I-(1/6)11T",
            "prefix_projection_commutes_with_centering": True,
            "per_track_transfer_rule": (
                "PP(C_E_I)<=PP(E_I)+MEAN_J(PP(E_J))"
            ),
            "uniform_per_track_peak_to_peak_gain_upper_bound": 2.0,
            "epoch_common_additive_receiver_clock_cancels_exactly": True,
            "historical_pairwise_guard_reused_as_a_DRAO_model": False,
        },
        "terms": term_rows,
        "aggregate": {
            "numeric_state": "UNAVAILABLE",
            "common_mode_heldout_peak_to_peak_bound_m": None,
            "finite_partial_bound_m": troposphere_bound,
            "guard_m": GUARD_M,
            "comparison_to_guard": "NOT_EVALUABLE_WITH_UNRESOLVED_TERMS",
            "unresolved_terms": unresolved,
            "unresolved_terms_defaulted_to_zero": False,
            "admitted": False,
        },
        "failure_attribution": {
            "geometry_discriminability": "POSITIVE_AND_UNCHANGED",
            "physical_envelope": "NOT_CLOSED",
            "measurement_path": "NOT_EVALUATED",
            "observation_outcome": "NOT_EVALUATED",
            "artifact_selection_deadlock": (
                "THE_FROZEN_PRE_ARTIFACT_ORDER_REQUIRES_FORMAT_SIGNAL_AND_"
                "WITNESS_BOUNDS_THAT_CANNOT_BE_PROVED_BEFORE_SELECTING_A_"
                "PRODUCT"
            ),
        },
        "artifact_access": dict(access),
        "orbital_scores_produced": 0,
        "route_state": "CLOSED_BEFORE_DRAO_ARTIFACT_SELECTION",
        "next_change_of_abstraction": (
            "A_FUTURE_PROOF_MUST_FREEZE_DIRECT_SHIFTED_RANGE_ENVELOPES_AND_"
            "EITHER_REQUIRE_COMPLETE_SAME_PATH_WITNESS_COVERAGE_OR_SUPPLY_"
            "AN_INDEPENDENT_ALL_EPOCH_TRACK_ERROR_BOUND_BEFORE_PRIMARY"
        ),
        "new_gate": False,
        "stop": "STOP_WITHOUT_DRAO_LOCATOR_HEADER_PAYLOAD_VALUE_OR_SCORE",
    }
    strict_json(result)
    return result


def render_report(value: Mapping[str, object]) -> str:
    aggregate = value["aggregate"]
    terms = value["terms"]
    rows = []
    for term in terms:
        bound = term["common_mode_heldout_peak_to_peak_bound_m"]
        shown = "UNAVAILABLE" if bound is None else f"{float(bound):.9f} m"
        explanation = str(term.get("reason", term.get("mapping", ""))).replace(
            "_", " "
        )
        rows.append(
            f"| {term['term']} | {term['state']} | {shown} | {explanation} |"
        )
    return "\n".join(
        [
            "# DRAO physical-envelope audit",
            "",
            f"**{value['outcome']}**",
            "",
            "This audit used only the frozen prospective plan and historical model-only bound provenance. No DRAO product was selected or accessed and no orbital score was produced.",
            "",
            "## Common-mode topology",
            "",
            "For each six-track hypothesis, `c_i = e_i - mean_j(e_j)`. After the same prefix affine projection, `pp(c_i) <= pp(e_i) + mean_j(pp(e_j))`; a uniform per-track p-p bound therefore has gain at most two. A purely epoch-common receiver-clock term cancels exactly, but track-, signal- or channel-dependent implementation terms do not.",
            "",
            "## Term attribution",
            "",
            "| Term | State | active common-mode bound | Basis or refusal |",
            "|---|---|---:|---|",
            *rows,
            "",
            "## Decision",
            "",
            f"Only the conservative troposphere interval is active numerically (`{float(aggregate['finite_partial_bound_m']):.9f} m`). The aggregate is **UNAVAILABLE**, not zero or infinity encoded as a number. Seven terms remain unresolved, so it cannot be compared defensibly with the frozen `{float(aggregate['guard_m']):.9f} m` guard.",
            "",
            "The geometry remains positive and unchanged. The failure is physical-envelope closure before measurement admission, not a DRAO measurement failure and not evidence against the orbital hypothesis.",
            "",
            "The frozen route therefore closes before locator selection. A future proof would need to retain the direct `t ± 15 s` projected range envelopes and require complete same-path witness coverage (or an independent all-epoch track-error bound) before its primary is frozen.",
            "",
            "## Access boundary",
            "",
            "DRAO locators, headers, payload bytes, observation values and orbital scores: **0**.",
            "",
        ]
    )


def main() -> int:
    root = Path(__file__).resolve().parent
    value = build_audit(root)
    (root / AUDIT_NAME).write_text(
        strict_json(value, pretty=True) + "\n", encoding="utf-8", newline="\n"
    )
    (root / REPORT_NAME).write_text(
        render_report(value), encoding="utf-8", newline="\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
