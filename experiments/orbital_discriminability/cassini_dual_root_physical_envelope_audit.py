"""Offline physical-envelope closure attempt for the frozen 2005 X/Ka path.

The input surface is deliberately smaller than the preceding exact compiler:
one frozen receipt plus exact-hash SPICE kernels.  There is no header, RSR,
sample, amplitude, detector, or network input.  Central physical models are
kept separate from uncertainty bounds and cannot reduce the envelope.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from math import sqrt
from pathlib import Path
from typing import Final, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import (
    cassini_dss14_header_evaluation as header_eval,
)
from experiments.orbital_discriminability import cassini_dss26_one_way as one_way
from experiments.orbital_discriminability import (
    cassini_dss26_open_term_audit as prior,
)
from experiments.orbital_discriminability import cassini_dual_root_headers as headers
from experiments.orbital_discriminability import (
    cassini_dual_root_xka_compiler as compiler,
)
from experiments.orbital_discriminability import (
    cassini_sagr3_distributed_geometry as forward,
)


AUDIT_VERSION: Final = "cassini-sroc-2005-dual-root-physical-envelope-audit-v1"
PARENT_RECEIPT_PATH: Final = Path(__file__).with_name(
    "CASSINI_DUAL_ROOT_XKA_COMPILER_RECEIPT.json"
)
PARENT_RECEIPT_SHA256: Final = (
    "942549a05d37d0926af9a5d65b7891c4c998134a9eb2254c28406982134ec1f8"
)
OUTCOME_CLOSED: Final = "CASSINI_DUAL_ROOT_2005_CLOSED_WITHOUT_IQ"
CONTROLLING_SEPARATION_HZ: Final = 0.2995923735627999
TIMING_ENVELOPE_HZ: Final = 2.04165223073319e-05
GRID_RECORDS: Final = 5_279
CALIBRATION_RECORDS: Final = 1_056
DETECTOR_BINS_REQUIRED: Final = 3.0
PROVENANCE_INDEPENDENT: Final = "INDEPENDENT_OF_TARGET_RF"
PROVENANCE_UNKNOWN: Final = "UNKNOWN"

SOURCES: Final = {
    "iers_proper_time": prior.SOURCES["iers_proper_time"],
    "iers_gravitational_delay": prior.SOURCES["iers_gravitational_delay"],
    "dsn_frequency_timing": prior.SOURCES["dsn_frequency_timing"],
    "dsn_media_interface": prior.SOURCES["dsn_media_interface"],
    "ion_product": compiler.MEDIA_PRODUCTS["ION"],
    "tro_product": compiler.MEDIA_PRODUCTS["TRO"],
    "jpl_gm": prior.SOURCES["jpl_gm"],
}


@dataclass(frozen=True, slots=True)
class IonModel:
    complex_id: str
    start_utc: str
    end_utc: str
    coefficients_m_at_s_band: tuple[float, ...]
    fitsig_m: float


ION_MODELS: Final = {
    "DSS-25": IonModel(
        "C10",
        "2005-06-08T15:28:00Z",
        "2005-06-09T05:33:00Z",
        (1.3258, -0.1266, 1.5215, -1.1927, -4.2652, 4.8422,
         12.3600, -6.3820, -7.9323, 3.0490),
        0.0178356,
    ),
    "DSS-55": IonModel(
        "C60",
        "2005-06-08T07:45:00Z",
        "2005-06-08T22:17:00Z",
        (1.6509, 1.1352, 0.1803, -7.3149, 9.0497, 19.0474,
         -8.4904, -20.3378, 1.0796, 7.5935),
        0.0291035,
    ),
}


@dataclass(frozen=True, slots=True)
class TroCorrection:
    complex_id: str
    start_utc: str
    end_utc: str
    wet_coefficients_m: tuple[float, ...]
    dry_coefficients_m: tuple[float, ...]
    wet_fitsig_m: float
    dry_fitsig_m: float


TRO_CORRECTIONS: Final = {
    "DSS-25": TroCorrection(
        "C10",
        "2005-06-08T18:00:00.001000Z",
        "2005-06-09T06:00:00.000000Z",
        (-0.0038, 0.0053, 0.0355, 0.0738, -0.1001,
         -0.1777, 0.0683, 0.1621, -0.0136, -0.0505),
        (0.0019, 0.0008, 0.0071, -0.0102, -0.0038,
         0.0142, 0.0006, -0.0058),
        0.0011639,
        0.0002242,
    ),
    "DSS-55": TroCorrection(
        "C60",
        "2005-06-08T18:00:00.001000Z",
        "2005-06-09T06:00:00.000000Z",
        (-0.0575, -0.0010, 0.0479, 0.0599, -0.1182,
         -0.2163, 0.1257, 0.2207, -0.0466, -0.0702),
        (-0.0045, 0.0054, -0.0027, -0.0055, 0.0015, 0.0021),
        0.0014777,
        0.0001534,
    ),
}


class CassiniDualRootEnvelopeError(ValueError):
    """Frozen authority or physical-envelope inputs are inconsistent."""


def validate_parent_receipt(path: Path = PARENT_RECEIPT_PATH) -> dict[str, object]:
    raw = Path(path).read_bytes()
    if sha256(raw).hexdigest() != PARENT_RECEIPT_SHA256:
        raise CassiniDualRootEnvelopeError("frozen parent receipt hash changed")
    receipt = json.loads(
        raw,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
    )
    geometry = receipt["geometry_and_nulls"]
    checks = (
        receipt["outcome"] == compiler.OUTCOME_BLOCKED,
        geometry["records"] == GRID_RECORDS,
        geometry["calibration_records"] == CALIBRATION_RECORDS,
        geometry["controlling_heldout_peak_to_peak_hz"]
        == CONTROLLING_SEPARATION_HZ,
        geometry["timing_envelope"]["four_stream_weighted_hz"]
        == TIMING_ENVELOPE_HZ,
        geometry["joint_visibility"] is True,
        geometry["rf_or_plasma_observed"] is False,
        receipt["access"]["iq_bytes_accessed"] == 0,
    )
    if not all(checks):
        raise CassiniDualRootEnvelopeError(
            "parent receipt no longer matches the frozen physical question"
        )
    return receipt


def audit_physical_envelope(*, spice, kernel_paths: Mapping[str, Path]) -> dict[str, object]:
    parent = validate_parent_receipt()
    compiled = _compile_exact_geometry(spice, kernel_paths)
    proper = _projected_metrics(_proper_time_gravity_differential(compiled))
    relativistic = _projected_metrics(_relativistic_delay_differential(compiled))
    tro_partial = _projected_metrics(_troposphere_partial_differential(compiled))
    ion_partial = _projected_metrics(_ionosphere_x_band_differential(compiled))

    terms = [
        _unresolved_term(
            compiler.OPEN_TERM_NAMES[0],
            "MODELED_CENTRAL_UNCERTAINTY_UNRESOLVED",
            PROVENANCE_INDEPENDENT,
            proper,
            "The weak-field receiver-rate differential is evaluated on the exact "
            "grid, but the frozen sources provide no pass-specific truncation and "
            "input-uncertainty family. Its central value is not its uncertainty.",
        ),
        _unresolved_term(
            compiler.OPEN_TERM_NAMES[1],
            "MODELED_CENTRAL_UNCERTAINTY_UNRESOLVED",
            PROVENANCE_INDEPENDENT,
            relativistic,
            "The static Sun/Earth/Saturn differential is evaluated, but moving-body "
            "and higher-order path remainders have no frozen deterministic bound.",
        ),
        _unresolved_term(
            compiler.OPEN_TERM_NAMES[2],
            "PARTIAL_MODEL_UNRESOLVED",
            PROVENANCE_INDEPENDENT,
            None,
            "Applicable C10/C60 NUPART corrections cover the grid, but the complete "
            "slant baseline, mapping uncertainty and deterministic residual bound "
            "are absent.",
            partial=tro_partial,
        ),
        _unresolved_term(
            compiler.OPEN_TERM_NAMES[3],
            "FIRST_ORDER_STRUCTURALLY_CANCELLED_MEASUREMENT_NOT_EVALUATED",
            PROVENANCE_INDEPENDENT,
            None,
            "The frozen X/Ka weights cancel an ideal first-order 1/f^2 term at both "
            "roots. The independent X-band calibration diagnostic does not measure "
            "the future RF coordinate and higher-order terms remain unbounded.",
            partial=ion_partial,
        ),
        _unresolved_term(
            compiler.OPEN_TERM_NAMES[4],
            "FIRST_ORDER_STRUCTURALLY_CANCELLED_MEASUREMENT_NOT_EVALUATED",
            PROVENANCE_UNKNOWN,
            None,
            "First-order cold-plasma algebra is shared with the ionospheric term; "
            "no outcome-independent finite higher-order/scintillation family is frozen.",
        ),
        _unresolved_term(
            compiler.OPEN_TERM_NAMES[5],
            "UNRESOLVED",
            PROVENANCE_UNKNOWN,
            None,
            "Header continuity constrains only the digital steering description. "
            "Cross-band/root reference curvature, cables, analog path and unknown FIR "
            "phase/group delay have no product-specific deterministic bound.",
            partial=_header_continuity_diagnostic(parent),
        ),
        _unresolved_term(
            compiler.OPEN_TERM_NAMES[6],
            "PARTIAL_CALIBRATION_UNRESOLVED",
            PROVENANCE_INDEPENDENT,
            None,
            "ION and TRO coverage is outcome-independent, but FITSIG is not a hard "
            "frequency bound and the partial controls may not be double counted.",
            role="NON_ADDITIVE_CONTROL_DO_NOT_DOUBLE_COUNT",
            partial=_combined_partial_diagnostic(tro_partial, ion_partial),
        ),
    ]

    unresolved = [term["name"] for term in terms]
    optimistic = max(
        0.0,
        (CONTROLLING_SEPARATION_HZ - TIMING_ENVELOPE_HZ)
        / DETECTOR_BINS_REQUIRED,
    )
    result = {
        "audit_version": AUDIT_VERSION,
        "audit_manifest_sha256": audit_manifest_sha256(),
        "scope": "FROZEN_RECEIPT_AND_EXACT_HASH_KERNELS_ONLY_NO_HEADER_OR_IQ_ACCESS",
        "authoritative_parent_outcome": parent["outcome"],
        "physical_question": (
            "CAN_EVERY_NONDISPERSIVE_AND_HARDWARE_FAMILY_BE_BOUNDED_BELOW_"
            "THE_FROZEN_ORBITAL_VERSUS_SATURN_CENTER_SEPARATION"
        ),
        "grid": {
            "event_axis": "COMMON_CASSINI_TRANSMIT_ET_TDB",
            "records": GRID_RECORDS,
            "calibration_records": CALIBRATION_RECORDS,
            "holdout_records": GRID_RECORDS - CALIBRATION_RECORDS,
            "first_transmit_utc": compiled["first_transmit_utc"],
            "last_transmit_utc": compiled["last_transmit_utc"],
            "joint_visibility": compiled["joint_visibility"],
            "suffix_refit": "PROHIBITED",
        },
        "frozen_comparison": {
            "coordinate": "DSS25_XKA_DISPERSIVE_FREE_MINUS_DSS55_XKA_DISPERSIVE_FREE",
            "null": "SATURN_BARYCENTER_GEOMETRY_DESTROYING",
            "heldout_peak_to_peak_hz": CONTROLLING_SEPARATION_HZ,
            "timing_envelope_hz": TIMING_ENVELOPE_HZ,
            "changed": False,
        },
        "kernel_lineage": compiled["kernel_lineage"],
        "sources": SOURCES,
        "terms": terms,
        "causal_state_semantics": {
            "representation": "NON_PROBABILISTIC_CAUSAL_STATE_ENVELOPE",
            "states": ["OBSERVABLE", "MODELED", "BOUNDED", "UNRESOLVED"],
            "central_model_is_uncertainty": False,
            "unresolved_is_zero": False,
            "root_sum_square_used": False,
            "combination_if_all_bounded": "CORRELATED_MINKOWSKI_SUM",
        },
        "conservative_combination": {
            "admitted_open_term_names": [],
            "admitted_open_term_peak_to_peak_hz": 0.0,
            "unresolved_open_term_names": unresolved,
            "combined_open_term_envelope_state": "UNAVAILABLE",
            "remaining_physical_margin_hz": None,
            "maximum_admissible_detector_resolution_hz": None,
            "optimistic_zero_open_term_detector_ceiling_hz": optimistic,
            "optimistic_ceiling_is_an_admission_requirement": False,
        },
        "closure_attribution": {
            "model": "CENTRAL_CURVES_EVALUATED_NOT_FALSIFIED",
            "model_to_prediction": "FROZEN_COORDINATE_AND_NULL_UNCHANGED",
            "observational_capacity": "NOT_TESTED_NO_IQ",
            "feature_extraction": "NOT_IMPLEMENTED",
            "physical_hypothesis": "NOT_TESTED",
            "blocking_cut": (
                "NO_OUTCOME_INDEPENDENT_BOUND_FOR_RECEIVER_HARDWARE_AND_"
                "NONDISPERSIVE_RESIDUAL_FAMILIES"
            ),
        },
        "outcome": OUTCOME_CLOSED,
        "maximum_authorized_claim": (
            "EXACT_GEOMETRY_AND_CENTRAL_PHYSICAL_DIAGNOSTICS_ONLY;"
            "NO_RF_OR_ORBITAL_MEASUREMENT"
        ),
        "iq_access_authorized": False,
        "detector_implementation_authorized": False,
        "header_accessed": False,
        "iq_bytes_accessed": 0,
        "new_gate_created": False,
        "next_action": (
            "ABANDON_THIS_2005_VERTICAL;SELECT_A_FUTURE_PHYSICAL_PATH_WITH_"
            "OUTCOME_INDEPENDENT_HARDWARE_AND_NONDISPERSIVE_CONTROLS"
        ),
    }
    strict_json(result)
    return result


def audit_manifest_sha256() -> str:
    manifest = {
        "audit_version": AUDIT_VERSION,
        "parent_receipt_sha256": PARENT_RECEIPT_SHA256,
        "controlling_separation_hz": CONTROLLING_SEPARATION_HZ,
        "timing_envelope_hz": TIMING_ENVELOPE_HZ,
        "grid_records": GRID_RECORDS,
        "calibration_records": CALIBRATION_RECORDS,
        "ion_models": {name: asdict(model) for name, model in ION_MODELS.items()},
        "tro_corrections": {
            name: asdict(model) for name, model in TRO_CORRECTIONS.items()
        },
        "projection": "SAME_PREFIX_AFFINE_NO_SUFFIX_REFIT",
        "null": "SAME_SATURN_BARYCENTER_GEOMETRY_DESTROYING_NULL",
        "forbidden": [
            "network access",
            "header access",
            "RSR or IQ access",
            "amplitude or detector input",
            "central model promoted to uncertainty",
            "FITSIG promoted to deterministic bound",
            "unresolved term set to zero",
            "root-sum-square combination",
            "null or threshold change",
        ],
    }
    return sha256(strict_json(manifest).encode("ascii")).hexdigest()


def strict_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _compile_exact_geometry(spice, kernel_paths: Mapping[str, Path]) -> dict[str, object]:
    fields = {
        name: []
        for name in (
            "left_receive_et", "right_receive_et", "left_station",
            "right_station", "left_station_velocity", "right_station_velocity",
            "spacecraft", "spacecraft_velocity", "earth_transmit", "sun_transmit",
            "saturn_transmit", "earth_left_receive", "sun_left_receive",
            "saturn_left_receive", "earth_right_receive", "sun_right_receive",
            "saturn_right_receive", "left_elevation_rad", "right_elevation_rad",
        )
    }
    with header_eval._loaded_exact_kernels(
        spice, compiler.TRAJECTORY_ROLE, kernel_paths
    ) as lineage:
        cassini = one_way._spice_state_provider(spice, "CASSINI")
        earth = one_way._spice_state_provider(spice, "EARTH")
        sun = one_way._spice_state_provider(spice, "SUN")
        saturn = one_way._spice_state_provider(spice, "SATURN BARYCENTER")
        left_station = one_way._spice_state_provider(spice, "DSS-25")
        right_station = one_way._spice_state_provider(spice, "DSS-55")
        first_receive = (
            float(spice.utc2et(headers.FROZEN_WINDOW_START_UTC))
            + compiler.REPRESENTATIVE_SAMPLE_OFFSET_S
        )
        last_receive = (
            float(spice.utc2et(headers.FROZEN_WINDOW_STOP_UTC))
            + compiler.REPRESENTATIVE_SAMPLE_OFFSET_S
        )
        common_start = max(
            one_way.solve_one_way_event(first_receive, left_station, cassini).transmit_et_tdb_s,
            one_way.solve_one_way_event(first_receive, right_station, cassini).transmit_et_tdb_s,
        )
        common_stop = min(
            one_way.solve_one_way_event(last_receive, left_station, cassini).transmit_et_tdb_s,
            one_way.solve_one_way_event(last_receive, right_station, cassini).transmit_et_tdb_s,
        )
        count = int(np.floor(common_stop - common_start)) + 1
        if count != GRID_RECORDS:
            raise CassiniDualRootEnvelopeError("exact common grid record count changed")
        transmit = common_start + np.arange(count, dtype=np.float64)
        calibration_utc = sorted(
            {value for model in ION_MODELS.values() for value in (model.start_utc, model.end_utc)}
            | {value for model in TRO_CORRECTIONS.values() for value in (model.start_utc, model.end_utc)}
        )
        calibration_et = {value: float(spice.utc2et(value)) for value in calibration_utc}
        for epoch in transmit:
            spacecraft = cassini(float(epoch))
            earth_tx = earth(float(epoch))
            sun_tx = sun(float(epoch))
            saturn_tx = saturn(float(epoch))
            left = forward.solve_forward_event(float(epoch), left_station, cassini, earth)
            right = forward.solve_forward_event(float(epoch), right_station, cassini, earth)
            left_state = left_station(left.receive_et_tdb_s)
            right_state = right_station(right.receive_et_tdb_s)
            values = {
                "left_receive_et": left.receive_et_tdb_s,
                "right_receive_et": right.receive_et_tdb_s,
                "left_station": left_state.position_m,
                "right_station": right_state.position_m,
                "left_station_velocity": left_state.velocity_m_s,
                "right_station_velocity": right_state.velocity_m_s,
                "spacecraft": spacecraft.position_m,
                "spacecraft_velocity": spacecraft.velocity_m_s,
                "earth_transmit": earth_tx.position_m,
                "sun_transmit": sun_tx.position_m,
                "saturn_transmit": saturn_tx.position_m,
                "earth_left_receive": earth(left.receive_et_tdb_s).position_m,
                "sun_left_receive": sun(left.receive_et_tdb_s).position_m,
                "saturn_left_receive": saturn(left.receive_et_tdb_s).position_m,
                "earth_right_receive": earth(right.receive_et_tdb_s).position_m,
                "sun_right_receive": sun(right.receive_et_tdb_s).position_m,
                "saturn_right_receive": saturn(right.receive_et_tdb_s).position_m,
                "left_elevation_rad": left.elevation_rad,
                "right_elevation_rad": right.elevation_rad,
            }
            for name, value in values.items():
                fields[name].append(value)
        first_utc = spice.et2utc(float(transmit[0]), "ISOC", 6) + "Z"
        last_utc = spice.et2utc(float(transmit[-1]), "ISOC", 6) + "Z"

    parent_geometry = validate_parent_receipt()["geometry_and_nulls"]
    if (
        first_utc != parent_geometry["first_transmit_utc"]
        or last_utc != parent_geometry["last_transmit_utc"]
    ):
        raise CassiniDualRootEnvelopeError("exact common-transmit grid changed")
    result = {name: np.asarray(values, dtype=np.float64) for name, values in fields.items()}
    result["transmit_et"] = transmit
    result["first_transmit_utc"] = first_utc
    result["last_transmit_utc"] = last_utc
    result["joint_visibility"] = bool(
        np.all(result["left_elevation_rad"] > 0.0)
        and np.all(result["right_elevation_rad"] > 0.0)
    )
    result["calibration_et"] = calibration_et
    result["kernel_lineage"] = [
        ({**item, "role": "DSN_STATION_STATES_DSS25_DSS55"}
         if item["name"] == "earthstns_itrf93_050714.bsp" else item)
        for item in lineage
    ]
    return result


def _proper_time_gravity_differential(compiled) -> np.ndarray:
    left = _endpoint_clock_rate(compiled, "left")
    right = _endpoint_clock_rate(compiled, "right")
    return compiler.REFERENCE_X_HZ * (left - right)


def _endpoint_clock_rate(compiled, side: str) -> np.ndarray:
    station = compiled[f"{side}_station"]
    velocity = compiled[f"{side}_station_velocity"]
    spacecraft = compiled["spacecraft"]
    spacecraft_velocity = compiled["spacecraft_velocity"]
    receive_potential = (
        prior.GM_SUN / _row_norm(station - compiled[f"sun_{side}_receive"])
        + prior.GM_EARTH / _row_norm(station - compiled[f"earth_{side}_receive"])
        + prior.GM_SATURN_SYSTEM / _row_norm(station - compiled[f"saturn_{side}_receive"])
    )
    transmit_potential = (
        prior.GM_SUN / _row_norm(spacecraft - compiled["sun_transmit"])
        + prior.GM_EARTH / _row_norm(spacecraft - compiled["earth_transmit"])
        + prior.GM_SATURN_SYSTEM / _row_norm(spacecraft - compiled["saturn_transmit"])
    )
    kinetic = 0.5 * (
        np.sum(velocity * velocity, axis=1)
        - np.sum(spacecraft_velocity * spacecraft_velocity, axis=1)
    )
    return (receive_potential - transmit_potential + kinetic) / one_way.SPEED_OF_LIGHT_M_S**2


def _relativistic_delay_differential(compiled) -> np.ndarray:
    left = _shapiro_delay(compiled, "left")
    right = _shapiro_delay(compiled, "right")
    return -compiler.REFERENCE_X_HZ * np.gradient(left - right, 1.0, edge_order=2)


def _shapiro_delay(compiled, side: str) -> np.ndarray:
    total = np.zeros(GRID_RECORDS, dtype=np.float64)
    station = compiled[f"{side}_station"]
    spacecraft = compiled["spacecraft"]
    endpoint_range = _row_norm(spacecraft - station)
    for gm, body_name in (
        (prior.GM_SUN, "sun"),
        (prior.GM_EARTH, "earth"),
        (prior.GM_SATURN_SYSTEM, "saturn"),
    ):
        body = compiled[f"{body_name}_{side}_receive"]
        receiver_radius = _row_norm(station - body)
        transmitter_radius = _row_norm(spacecraft - body)
        denominator = receiver_radius + transmitter_radius - endpoint_range
        if np.any(denominator <= 0.0):
            raise CassiniDualRootEnvelopeError("invalid Shapiro geometry")
        total += (2.0 * gm / one_way.SPEED_OF_LIGHT_M_S**3) * np.log(
            (receiver_radius + transmitter_radius + endpoint_range) / denominator
        )
    return total


def _ionosphere_x_band_differential(compiled) -> np.ndarray:
    left = _calibration_delay(compiled, "left", ION_MODELS["DSS-25"])
    right = _calibration_delay(compiled, "right", ION_MODELS["DSS-55"])
    scale = (prior.S_BAND_ION_REFERENCE_HZ / compiler.REFERENCE_X_HZ) ** 2
    return (compiler.REFERENCE_X_HZ / one_way.SPEED_OF_LIGHT_M_S) * np.gradient(
        scale * (left - right), 1.0, edge_order=2
    )


def _troposphere_partial_differential(compiled) -> np.ndarray:
    values = []
    for side, station in (("left", "DSS-25"), ("right", "DSS-55")):
        model = TRO_CORRECTIONS[station]
        wet = _calibration_delay(compiled, side, model, coefficients=model.wet_coefficients_m)
        dry = _calibration_delay(compiled, side, model, coefficients=model.dry_coefficients_m)
        elevation = compiled[f"{side}_elevation_rad"]
        if np.any(elevation <= 0.0):
            raise CassiniDualRootEnvelopeError("frozen track is below horizon")
        values.append((wet + dry) / np.sin(elevation))
    return -(compiler.REFERENCE_X_HZ / one_way.SPEED_OF_LIGHT_M_S) * np.gradient(
        values[0] - values[1], 1.0, edge_order=2
    )


def _calibration_delay(compiled, side: str, model, *, coefficients=None) -> np.ndarray:
    epochs = compiled[f"{side}_receive_et"]
    start = compiled["calibration_et"][model.start_utc]
    end = compiled["calibration_et"][model.end_utc]
    if epochs.min() < start or epochs.max() > end or end <= start:
        raise CassiniDualRootEnvelopeError("calibration does not cover receive grid")
    x = 2.0 * (epochs - start) / (end - start) - 1.0
    selected = model.coefficients_m_at_s_band if coefficients is None else coefficients
    result = np.zeros_like(x)
    for coefficient in reversed(selected):
        result = result * x + coefficient
    return result


def _projected_metrics(curve: Sequence[float]) -> dict[str, float]:
    values = np.asarray(curve, dtype=np.float64)
    if values.shape != (GRID_RECORDS,) or not np.all(np.isfinite(values)):
        raise CassiniDualRootEnvelopeError("physical curve is not finite on exact grid")
    elapsed = np.arange(GRID_RECORDS, dtype=np.float64)
    design = np.column_stack(
        (np.ones(CALIBRATION_RECORDS), elapsed[:CALIBRATION_RECORDS])
    )
    coefficients, *_ = np.linalg.lstsq(
        design, values[:CALIBRATION_RECORDS], rcond=None
    )
    residual = values - (coefficients[0] + coefficients[1] * elapsed)
    heldout = residual[CALIBRATION_RECORDS:]
    return {
        "peak_to_peak_hz": float(np.ptp(heldout)),
        "rms_hz": float(sqrt(float(np.mean(heldout * heldout)))),
        "maximum_absolute_hz": float(np.max(np.abs(heldout))),
        "calibration_prefix_rmse_hz": float(
            sqrt(float(np.mean(residual[:CALIBRATION_RECORDS] ** 2)))
        ),
    }


def _header_continuity_diagnostic(parent) -> dict[str, object]:
    weights = parent["geometry_and_nulls"]["composition_weights"]
    residuals = {
        "DSS25_X": 9.5367431640625e-7,
        "DSS25_KA": 3.814697265625e-6,
        "DSS55_X": 9.5367431640625e-7,
        "DSS55_KA": 3.814697265625e-6,
    }
    upper = 0.0
    for role, residual in residuals.items():
        magnitude = max(abs(weights[role]["minimum"]), abs(weights[role]["maximum"]))
        upper += magnitude * residual
    return {
        "maximum_adjacent_transform_boundary_residual_hz": residuals,
        "weighted_sum_hz": upper,
        "semantics": "DESCRIPTIVE_DIGITAL_CONTINUITY_NOT_END_TO_END_HARDWARE_BOUND",
    }


def _combined_partial_diagnostic(*metrics) -> dict[str, object]:
    return {
        "components": list(metrics),
        "combination": "DESCRIPTIVE_ONLY_NOT_AN_ENVELOPE",
    }


def _unresolved_term(
    name: str,
    state: str,
    provenance: str,
    central: dict[str, float] | None,
    reason: str,
    *,
    role: str = "ADDITIVE_PHYSICAL_TERM",
    partial: dict[str, object] | None = None,
) -> dict[str, object]:
    if name not in compiler.OPEN_TERM_NAMES:
        raise CassiniDualRootEnvelopeError("term outside frozen ledger")
    return {
        "name": name,
        "state": state,
        "provenance": provenance,
        "central_model_heldout_non_affine": central,
        "partial_diagnostic": partial,
        "central_or_partial_model_reduces_envelope": False,
        "bound_state": "UNAVAILABLE",
        "admitted_heldout_peak_to_peak_bound_hz": None,
        "admitted_heldout_rms_bound_hz": None,
        "combination_role": role,
        "reason": reason,
    }


def _row_norm(values: np.ndarray) -> np.ndarray:
    return np.linalg.norm(values, axis=1)


if __name__ == "__main__":
    raise SystemExit(
        "Import audit_physical_envelope and pass SpiceyPy plus exact-hash local kernels"
    )
