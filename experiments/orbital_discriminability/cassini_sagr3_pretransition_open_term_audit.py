"""Differential physical-envelope audit for the frozen Cassini SAGR3 window.

Only exact-hash trajectory kernels and already frozen, outcome-independent
calibration metadata enter this module.  RSR headers, payloads, IQ, amplitude
and detector outputs are outside its input surface.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from math import sqrt
from pathlib import Path
from typing import Final, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import cassini_dss26_one_way as one_way
from experiments.orbital_discriminability import cassini_dss26_open_term_audit as prior
from experiments.orbital_discriminability import cassini_dss14_header_evaluation as header_eval
from experiments.orbital_discriminability import cassini_sagr3_distributed_geometry as geometry


AUDIT_VERSION: Final = "cassini-sagr3-pretransition-open-term-envelope-audit-v1"
RECEIPT_PATH: Final = Path(__file__).with_name(
    "CASSINI_SAGR3_TRANSITION_AUDIT_RECEIPT.json"
)
CONTROLLING_SEPARATION_HZ: Final = 0.07231370056321107
DETECTOR_BINS_REQUIRED: Final = 3.0
OUTCOME_BOUND_UNAVAILABLE: Final = "CASSINI_OPEN_TERM_BOUND_UNAVAILABLE"
OPEN_TERM_NAMES: Final = prior.OPEN_TERM_NAMES
PROVENANCE_INDEPENDENT: Final = prior.PROVENANCE_INDEPENDENT
PROVENANCE_UNKNOWN: Final = prior.PROVENANCE_UNKNOWN

SOURCES: Final = {
    "iers_proper_time": prior.SOURCES["iers_proper_time"],
    "iers_gravitational_delay": prior.SOURCES["iers_gravitational_delay"],
    "dsn_frequency_timing": prior.SOURCES["dsn_frequency_timing"],
    "dsn_media_interface": prior.SOURCES["dsn_media_interface"],
    "dsn_service_accuracy": "https://deepspace.jpl.nasa.gov/files/820-100-F1.pdf",
    "ion_product": (
        "https://atmos.nmsu.edu/pdsd/archive/data/co-s-rss-1-sagr3-v10/cors_0147/"
        "sagr3_ancillary/ion/s23sagf2006_244_2006_273.ion"
    ),
    "tro_product": (
        "https://atmos.nmsu.edu/pdsd/archive/data/co-s-rss-1-sagr3-v10/cors_0147/"
        "sagr3_ancillary/tro/s23sagf2006_244_2006_262.tro"
    ),
    "calibration_inventory": (
        "https://atmos.nmsu.edu/pdsd/archive/data/co-s-rss-1-sagr3-v10/"
        "cors_0147/calib/calinfo.txt"
    ),
    "jpl_gm": prior.SOURCES["jpl_gm"],
}

SOURCE_IDENTITIES: Final = {
    "dsn_media_interface": prior.SOURCE_IDENTITIES["dsn_media_interface"],
    "ion_product": {
        "bytes": 29_160,
        "sha256": "d643911892ee9a9d5b9f366e038d6705fd50769d9aa29c80f9192553c02c6aad",
    },
    "tro_product": {
        "bytes": 133_236,
        "sha256": "5a3b116405157715e094075d99c4cb28c2c289490bfa93901a427faf52378dcb",
    },
    "calibration_inventory": {
        "bytes": 1_996,
        "sha256": "afc3866c51a62292600bfb93c30372c60702be4353fbc70ec76a474c3160f3b3",
    },
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
        "2006-09-08T11:21:00Z",
        "2006-09-09T00:52:00Z",
        (
            1.0108,
            0.0558,
            2.1951,
            0.3994,
            -4.9116,
            4.9861,
            5.6071,
            -7.3999,
            -2.2253,
            2.9873,
        ),
        0.0154957,
    ),
    "DSS-65": IonModel(
        "C60",
        "2006-09-08T03:42:00Z",
        "2006-09-08T17:32:00Z",
        (
            1.0450,
            0.2476,
            0.6329,
            -1.3929,
            1.0502,
            6.7878,
            -1.9202,
            -6.5046,
            0.8621,
            1.3962,
        ),
        0.0234868,
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
        "2006-09-08T09:00:00.001000Z",
        "2006-09-08T15:00:00.000000Z",
        (
            -0.0796,
            -0.0233,
            0.0120,
            0.0686,
            -0.0215,
            -0.1134,
            0.0104,
            0.0796,
            -0.0013,
            -0.0193,
        ),
        (0.0014, 0.0013, 0.0005),
        0.0006464,
        0.0002454,
    ),
    "DSS-65": TroCorrection(
        "C60",
        "2006-09-08T09:00:00.001000Z",
        "2006-09-08T15:00:00.000000Z",
        (
            -0.0050,
            -0.0177,
            -0.0182,
            0.0348,
            0.0617,
            -0.0326,
            -0.0528,
            0.0097,
            0.0140,
        ),
        (-0.0070, -0.0023, -0.0011, 0.0006),
        0.0011061,
        0.0001421,
    ),
}


class CassiniSagr3OpenTermAuditError(ValueError):
    """The frozen differential audit inputs are inconsistent."""


def validate_transition_receipt(path: Path = RECEIPT_PATH) -> dict[str, object]:
    receipt = json.loads(Path(path).read_text(encoding="utf-8"))
    screen = receipt["pretransition_screen"]
    checks = (
        receipt["full_heldout_status"]
        == "BLOCKED_BY_UNMODELED_COORDINATE_TRANSITION_INSIDE_HELDOUT",
        receipt["transition_cause"] == "UNRESOLVED",
        screen["manifest_sha256"]
        == geometry.pretransition_screen_manifest_sha256(),
        screen["records"] == geometry.PRETRANSITION_RECORDS,
        screen["calibration_records"]
        == geometry.PRETRANSITION_CALIBRATION_RECORDS,
        screen["holdout_records"] == geometry.PRETRANSITION_HOLDOUT_RECORDS,
        screen["controlling_heldout_separation_hz_peak_to_peak"]
        == CONTROLLING_SEPARATION_HZ,
        screen["physical_admission"] is False,
        receipt["iq_accessed"] is False,
    )
    if not all(checks):
        raise CassiniSagr3OpenTermAuditError(
            "transition receipt no longer matches the frozen audit"
        )
    return receipt


def audit_open_terms(*, spice, kernel_paths: Mapping[str, Path]) -> dict[str, object]:
    receipt = validate_transition_receipt()
    compiled = _compile_differential_geometry(spice, kernel_paths)

    proper = _proper_time_gravity_differential(compiled)
    relativistic = _relativistic_delay_differential(compiled)
    ionosphere = _ionosphere_differential(compiled)
    tro_partial = _troposphere_correction_only_differential(compiled)
    media_partial = ionosphere + tro_partial

    proper_metrics = _projected_metrics(proper)
    relativistic_metrics = _projected_metrics(relativistic)
    ion_metrics = _projected_metrics(ionosphere)
    tro_partial_metrics = _projected_metrics(tro_partial)
    media_partial_metrics = _projected_metrics(media_partial)

    terms = [
        _term(
            OPEN_TERM_NAMES[0],
            PROVENANCE_INDEPENDENT,
            proper_metrics,
            "The common spacecraft/source contribution cancels structurally, but "
            "the IERS weak-field receiver-rate differential has no pass-specific "
            "hard truncation bound.",
        ),
        _term(
            OPEN_TERM_NAMES[1],
            PROVENANCE_INDEPENDENT,
            relativistic_metrics,
            "The outcome-independent Sun/Earth/Saturn central path model omits "
            "unbounded moving-body and higher-order differential terms.",
        ),
        _term(
            OPEN_TERM_NAMES[2],
            PROVENANCE_INDEPENDENT,
            None,
            "The TRO product supplies independent C10/C60 NUPART corrections, but "
            "the public frozen inputs do not contain the complete DSCC60 seasonal "
            "baseline or a deterministic residual/elevation-mapping bound.",
            partial_diagnostic=tro_partial_metrics,
        ),
        _term(
            OPEN_TERM_NAMES[3],
            PROVENANCE_INDEPENDENT,
            ion_metrics,
            "Applicable independent C10 and C60 line-of-sight models cover the grid, "
            "but FITSIG and DSN one-sigma accuracy are not deterministic residual-"
            "frequency bounds.",
        ),
        _term(
            OPEN_TERM_NAMES[4],
            PROVENANCE_UNKNOWN,
            None,
            "No applicable outcome-independent finite bound on the differential "
            "interplanetary-plasma gradient across the two Earth receive paths was found.",
        ),
        _term(
            OPEN_TERM_NAMES[5],
            PROVENANCE_UNKNOWN,
            None,
            "No pass-specific deterministic bound for differential DSS-25/DSS-65 "
            "receiver-chain frequency curvature was found.",
        ),
        _term(
            OPEN_TERM_NAMES[6],
            PROVENANCE_INDEPENDENT,
            None,
            "ION coverage is complete, but TRO remains a correction-only partial "
            "diagnostic and neither product supplies a hard residual bound.",
            role="NON_ADDITIVE_CONTROL_DO_NOT_DOUBLE_COUNT",
            partial_diagnostic=media_partial_metrics,
        ),
    ]

    timing = receipt["pretransition_screen"][
        "timing_envelope_two_stream_two_sided_hz"
    ]
    best_case = max(
        0.0,
        (CONTROLLING_SEPARATION_HZ - timing) / DETECTOR_BINS_REQUIRED,
    )
    unresolved = [term["name"] for term in terms]
    result = {
        "audit_version": AUDIT_VERSION,
        "audit_manifest_sha256": audit_manifest_sha256(),
        "scope": "SAGR3_PRETRANSITION_METADATA_ONLY_NO_RSR_OR_IQ_ACCESS",
        "authoritative_prior_outcome": receipt["outcome"],
        "controlling_comparison": (
            "DSS25_MINUS_DSS65_X_BAND_ORBITAL_VERSUS_SATURN_CENTER_"
            "AFTER_PREFIX_AFFINE_PROJECTION"
        ),
        "controlling_heldout_peak_to_peak_hz": CONTROLLING_SEPARATION_HZ,
        "grid": {
            "event_axis": "COMMON_CASSINI_TRANSMIT_ET_TDB",
            "records": geometry.PRETRANSITION_RECORDS,
            "calibration_records": geometry.PRETRANSITION_CALIBRATION_RECORDS,
            "holdout_records": geometry.PRETRANSITION_HOLDOUT_RECORDS,
            "first_transmit_utc": compiled["first_transmit_utc"],
            "last_transmit_utc": compiled["last_transmit_utc"],
            "suffix_refit": "PROHIBITED",
        },
        "source_identities": SOURCE_IDENTITIES,
        "sources": SOURCES,
        "kernel_lineage": compiled["kernel_lineage"],
        "outcome_conditioned_products_used": [],
        "structural_cancellation": {
            "topology_basis": "COHERENT_COMMON_SOURCE_FROZEN_IN_PARENT_HEADER_RECEIPT",
            "common_DSS14_uplink": "CANCELS_FROM_DSS25_MINUS_DSS65_AT_COMMON_TRANSMIT_EPOCH",
            "common_Cassini_transponder": "CANCELS_FROM_DSS25_MINUS_DSS65_AT_COMMON_TRANSMIT_EPOCH",
            "spacecraft_USO": "NOT_APPLICABLE_WITHIN_THE_FROZEN_COHERENT_TOPOLOGY",
            "remaining_terms": (
                "RECEIVER_RATE_PATH_MEDIA_AND_BRANCH_HARDWARE_DIFFERENTIALS"
            ),
        },
        "terms": terms,
        "timing_envelope_two_stream_two_sided_hz": timing,
        "conservative_combination": {
            "admitted_open_term_names": [],
            "admitted_open_term_peak_to_peak_hz": 0.0,
            "unresolved_open_term_names": unresolved,
            "combined_open_term_envelope_state": "UNAVAILABLE",
            "remaining_physical_margin_hz": None,
            "maximum_admissible_detector_resolution_hz": None,
            "detector_criterion": (
                "signature > 3 * R_f + timing_envelope + open_term_envelope"
            ),
            "best_case_upper_ceiling_if_every_unavailable_term_were_zero_hz": (
                best_case
            ),
            "best_case_ceiling_is_admission_requirement": False,
        },
        "outcome": OUTCOME_BOUND_UNAVAILABLE,
        "iq_access_authorized": False,
        "detector_implementation_authorized": False,
        "new_gate_created": False,
        "exact_remaining_blockers": [
            "DIFFERENTIAL_INTERPLANETARY_PLASMA_BOUND",
            "DIFFERENTIAL_RECEIVER_CHAIN_CURVATURE_BOUND",
            "COMPLETE_TROPOSPHERE_MODEL_AND_HARD_RESIDUAL_BOUND",
        ],
        "next_smallest_physical_step": (
            "CHANGE_OBSERVABLE_REVIEW_USING_THE_ALREADY_PREDECLARED_SIMULTANEOUS_"
            "DSS25_X_KA_WITNESS; DO_NOT_ACCESS_IQ_OR_IMPLEMENT_IT_YET"
        ),
    }
    strict_json(result)
    return result


def audit_manifest_sha256() -> str:
    manifest = {
        "audit_version": AUDIT_VERSION,
        "parent_manifest_sha256": geometry.pretransition_screen_manifest_sha256(),
        "controlling_separation_hz": CONTROLLING_SEPARATION_HZ,
        "records": geometry.PRETRANSITION_RECORDS,
        "calibration_records": geometry.PRETRANSITION_CALIBRATION_RECORDS,
        "open_terms": list(OPEN_TERM_NAMES),
        "ion_models": {key: asdict(value) for key, value in ION_MODELS.items()},
        "tro_corrections": {
            key: asdict(value) for key, value in TRO_CORRECTIONS.items()
        },
        "source_identities": SOURCE_IDENTITIES,
        "forbidden": [
            "RSR header access",
            "RSR payload access",
            "IQ decoding",
            "amplitude diagnostics",
            "detector implementation",
            "suffix refit",
            "FITSIG promoted to hard bound",
            "one-sigma accuracy promoted to hard bound",
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


def _compile_differential_geometry(
    spice, kernel_paths: Mapping[str, Path]
) -> dict[str, object]:
    products = {product.role: product for product in geometry.PRODUCTS}
    left_product = products["MEASUREMENT_X_DSS25"]
    right_product = products["MEASUREMENT_X_DSS65"]
    fields = {
        name: []
        for name in (
            "left_receive_et",
            "right_receive_et",
            "left_station",
            "right_station",
            "left_station_velocity",
            "right_station_velocity",
            "spacecraft",
            "spacecraft_velocity",
            "earth_transmit",
            "sun_transmit",
            "saturn_transmit",
            "earth_left_receive",
            "sun_left_receive",
            "saturn_left_receive",
            "earth_right_receive",
            "sun_right_receive",
            "saturn_right_receive",
            "left_elevation_rad",
            "right_elevation_rad",
        )
    }

    with header_eval._loaded_exact_kernels(
        spice, geometry.TRAJECTORY_ROLE, kernel_paths
    ) as lineage:
        cassini = one_way._spice_state_provider(spice, "CASSINI")
        earth = one_way._spice_state_provider(spice, "EARTH")
        sun = one_way._spice_state_provider(spice, "SUN")
        saturn = one_way._spice_state_provider(spice, "SATURN BARYCENTER")
        left_station = one_way._spice_state_provider(
            spice, left_product.receive_station
        )
        right_station = one_way._spice_state_provider(
            spice, right_product.receive_station
        )
        calibration_utc = sorted(
            {
                value
                for model in ION_MODELS.values()
                for value in (model.start_utc, model.end_utc)
            }
            | {
                value
                for correction in TRO_CORRECTIONS.values()
                for value in (correction.start_utc, correction.end_utc)
            }
        )
        calibration_et = {
            value: float(spice.utc2et(value)) for value in calibration_utc
        }
        left_start = one_way.solve_one_way_event(
            float(spice.utc2et(left_product.start_utc)), left_station, cassini
        ).transmit_et_tdb_s
        right_start = one_way.solve_one_way_event(
            float(spice.utc2et(right_product.start_utc)), right_station, cassini
        ).transmit_et_tdb_s
        first_transmit = max(left_start, right_start)
        transmit_grid = first_transmit + np.arange(
            geometry.PRETRANSITION_RECORDS, dtype=np.float64
        )

        for transmit_et in transmit_grid:
            spacecraft_state = cassini(float(transmit_et))
            earth_at_transmit = earth(float(transmit_et))
            sun_at_transmit = sun(float(transmit_et))
            saturn_at_transmit = saturn(float(transmit_et))
            left = geometry.solve_forward_event(
                float(transmit_et), left_station, cassini, earth
            )
            right = geometry.solve_forward_event(
                float(transmit_et), right_station, cassini, earth
            )
            left_state = left_station(left.receive_et_tdb_s)
            right_state = right_station(right.receive_et_tdb_s)
            values = {
                "left_receive_et": left.receive_et_tdb_s,
                "right_receive_et": right.receive_et_tdb_s,
                "left_station": left_state.position_m,
                "right_station": right_state.position_m,
                "left_station_velocity": left_state.velocity_m_s,
                "right_station_velocity": right_state.velocity_m_s,
                "spacecraft": spacecraft_state.position_m,
                "spacecraft_velocity": spacecraft_state.velocity_m_s,
                "earth_transmit": earth_at_transmit.position_m,
                "sun_transmit": sun_at_transmit.position_m,
                "saturn_transmit": saturn_at_transmit.position_m,
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

        first_utc = spice.et2utc(float(transmit_grid[0]), "ISOC", 6) + "Z"
        last_utc = spice.et2utc(float(transmit_grid[-1]), "ISOC", 6) + "Z"

    result = {
        name: np.asarray(values, dtype=np.float64)
        for name, values in fields.items()
    }
    result["transmit_et"] = transmit_grid
    result["first_transmit_utc"] = first_utc
    result["last_transmit_utc"] = last_utc
    result["kernel_lineage"] = [
        (
            {
                **item,
                "role": "DSN_STATION_STATES_DSS14_DSS25_DSS65",
            }
            if item["name"] == "earthstns_itrf93_050714.bsp"
            else item
        )
        for item in lineage
    ]
    result["calibration_et"] = calibration_et
    expected = validate_transition_receipt()["pretransition_screen"]
    if (
        first_utc != expected["first_transmit_utc"]
        or last_utc != expected["last_transmit_utc"]
    ):
        raise CassiniSagr3OpenTermAuditError(
            "compiled common-transmit grid changed"
        )
    return result


def _proper_time_gravity_differential(compiled) -> np.ndarray:
    left = _endpoint_clock_rate(compiled, "left")
    right = _endpoint_clock_rate(compiled, "right")
    return geometry.X_BAND_HZ * (left - right)


def _endpoint_clock_rate(compiled, side: str) -> np.ndarray:
    station = compiled[f"{side}_station"]
    station_velocity = compiled[f"{side}_station_velocity"]
    spacecraft = compiled["spacecraft"]
    spacecraft_velocity = compiled["spacecraft_velocity"]
    receive_potential = (
        prior.GM_SUN / _row_norm(station - compiled[f"sun_{side}_receive"])
        + prior.GM_EARTH / _row_norm(station - compiled[f"earth_{side}_receive"])
        + prior.GM_SATURN_SYSTEM
        / _row_norm(station - compiled[f"saturn_{side}_receive"])
    )
    transmit_potential = (
        prior.GM_SUN / _row_norm(spacecraft - compiled["sun_transmit"])
        + prior.GM_EARTH / _row_norm(spacecraft - compiled["earth_transmit"])
        + prior.GM_SATURN_SYSTEM
        / _row_norm(spacecraft - compiled["saturn_transmit"])
    )
    kinetic = 0.5 * (
        np.sum(station_velocity * station_velocity, axis=1)
        - np.sum(spacecraft_velocity * spacecraft_velocity, axis=1)
    )
    return (receive_potential - transmit_potential + kinetic) / (
        one_way.SPEED_OF_LIGHT_M_S**2
    )


def _relativistic_delay_differential(compiled) -> np.ndarray:
    left = _shapiro_delay(compiled, "left")
    right = _shapiro_delay(compiled, "right")
    return -geometry.X_BAND_HZ * np.gradient(
        left - right, geometry.GRID_STEP_S, edge_order=2
    )


def _shapiro_delay(compiled, side: str) -> np.ndarray:
    total = np.zeros(geometry.PRETRANSITION_RECORDS, dtype=np.float64)
    station = compiled[f"{side}_station"]
    spacecraft = compiled["spacecraft"]
    endpoint_range = _row_norm(spacecraft - station)
    for gm, name in (
        (prior.GM_SUN, "sun"),
        (prior.GM_EARTH, "earth"),
        (prior.GM_SATURN_SYSTEM, "saturn"),
    ):
        body = compiled[f"{name}_{side}_receive"]
        receiver_radius = _row_norm(station - body)
        transmitter_radius = _row_norm(spacecraft - body)
        numerator = receiver_radius + transmitter_radius + endpoint_range
        denominator = receiver_radius + transmitter_radius - endpoint_range
        if np.any(denominator <= 0.0):
            raise CassiniSagr3OpenTermAuditError(
                "invalid differential gravitational-delay geometry"
            )
        total += (
            2.0 * gm / one_way.SPEED_OF_LIGHT_M_S**3
        ) * np.log(numerator / denominator)
    return total


def _ionosphere_differential(compiled) -> np.ndarray:
    left = _ionosphere_delay(
        compiled,
        compiled["left_receive_et"],
        ION_MODELS["DSS-25"],
    )
    right = _ionosphere_delay(
        compiled,
        compiled["right_receive_et"],
        ION_MODELS["DSS-65"],
    )
    return (geometry.X_BAND_HZ / one_way.SPEED_OF_LIGHT_M_S) * np.gradient(
        left - right, geometry.GRID_STEP_S, edge_order=2
    )


def _ionosphere_delay(
    compiled, epochs: np.ndarray, model: IonModel
) -> np.ndarray:
    start = compiled["calibration_et"][model.start_utc]
    end = compiled["calibration_et"][model.end_utc]
    return _normalized_delay(
        epochs,
        start,
        end,
        model.coefficients_m_at_s_band,
    ) * (prior.S_BAND_ION_REFERENCE_HZ / geometry.X_BAND_HZ) ** 2


def _troposphere_correction_only_differential(compiled) -> np.ndarray:
    left = _troposphere_partial_delay(
        compiled,
        compiled["left_receive_et"],
        compiled["left_elevation_rad"],
        TRO_CORRECTIONS["DSS-25"],
    )
    right = _troposphere_partial_delay(
        compiled,
        compiled["right_receive_et"],
        compiled["right_elevation_rad"],
        TRO_CORRECTIONS["DSS-65"],
    )
    return -(geometry.X_BAND_HZ / one_way.SPEED_OF_LIGHT_M_S) * np.gradient(
        left - right, geometry.GRID_STEP_S, edge_order=2
    )


def _troposphere_partial_delay(
    compiled,
    epochs: np.ndarray,
    elevation_rad: np.ndarray,
    correction: TroCorrection,
) -> np.ndarray:
    start = compiled["calibration_et"][correction.start_utc]
    end = compiled["calibration_et"][correction.end_utc]
    wet = _normalized_delay(
        epochs, start, end, correction.wet_coefficients_m
    )
    dry = _normalized_delay(
        epochs, start, end, correction.dry_coefficients_m
    )
    if np.any(elevation_rad <= 0.0):
        raise CassiniSagr3OpenTermAuditError(
            "pre-transition track is below the geometric horizon"
        )
    return (wet + dry) / np.sin(elevation_rad)


def _normalized_delay(
    epochs: Sequence[float],
    start: float,
    end: float,
    coefficients: Sequence[float],
) -> np.ndarray:
    values = np.asarray(epochs, dtype=np.float64)
    if end <= start or values.min() < start or values.max() > end:
        raise CassiniSagr3OpenTermAuditError(
            "calibration model does not cover the exact receive grid"
        )
    x = 2.0 * (values - start) / (end - start) - 1.0
    result = np.zeros_like(x)
    for coefficient in reversed(coefficients):
        result = result * x + coefficient
    return result


def _projected_metrics(curve: Sequence[float]) -> dict[str, float]:
    metrics = geometry._prefix_affine_metrics(
        curve, geometry.PRETRANSITION_CALIBRATION_RECORDS
    )
    return {
        "peak_to_peak_hz": metrics["peak_to_peak_hz"],
        "rms_hz": metrics["rms_hz"],
        "maximum_absolute_hz": metrics["maximum_absolute_hz"],
        "calibration_prefix_rmse_hz": metrics["prefix_rmse_hz"],
    }


def _term(
    name: str,
    provenance: str,
    central_metrics: dict[str, float] | None,
    reason: str,
    *,
    role: str = "ADDITIVE_PHYSICAL_TERM",
    partial_diagnostic: dict[str, float] | None = None,
) -> dict[str, object]:
    if name not in OPEN_TERM_NAMES:
        raise CassiniSagr3OpenTermAuditError(
            "term is outside the frozen seven-entry ledger"
        )
    return {
        "name": name,
        "provenance": provenance,
        "central_model_heldout_non_affine": central_metrics,
        "partial_model_heldout_non_affine": partial_diagnostic,
        "central_or_partial_model_reduces_envelope": False,
        "bound_state": "UNAVAILABLE",
        "admitted_heldout_peak_to_peak_bound_hz": None,
        "admitted_heldout_rms_bound_hz": None,
        "combination_role": role,
        "reason": reason,
    }


def _row_norm(values: np.ndarray) -> np.ndarray:
    return np.linalg.norm(values, axis=1)
