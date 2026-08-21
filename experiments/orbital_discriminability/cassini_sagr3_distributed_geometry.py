"""Metadata-only distributed-geometry screen for the Cassini SAGR3 pass.

The bounded product set is fixed to simultaneous X/Ka reception at DSS-25 and
X reception at DSS-65.  This module accepts SPICE kernels only: it has no RSR,
header, sample, amplitude, detector, or network input.

The orbital observable is the X-band receiver differential evaluated on one
common spacecraft-transmit grid.  X/Ka at DSS-25 is retained only as a future
same-path dispersive witness; raw cross-band differencing is not promoted to
an orbital measurement because it cancels the common fractional Doppler.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from math import asin, ceil, floor, isfinite, sqrt
from pathlib import Path
from typing import Final, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import cassini_dss26_one_way as one_way
from experiments.orbital_discriminability import cassini_dss14_header_evaluation as header_eval


SCREEN_VERSION: Final = "cassini-sagr3-distributed-geometry-screen-v1"
TRAJECTORY_ROLE: Final = "HEADER_CANDIDATE_A"
X_BAND_HZ: Final = 8_425_000_000.0
KA_BAND_HZ: Final = 32_028_000_000.0
CALIBRATION_FRACTION: Final = 0.2
GRID_STEP_S: Final = 1.0
RSR_TIMING_BOUND_S: Final = 100e-9
DETECTOR_BINS_REQUIRED: Final = 3.0
OUTCOME_POSITIVE: Final = "CASSINI_DISTRIBUTED_GEOMETRY_SCREEN_POSITIVE"
PRETRANSITION_SCREEN_VERSION: Final = "cassini-sagr3-pretransition-geometry-screen-v1"
PRETRANSITION_RECORDS: Final = 10_651
PRETRANSITION_CALIBRATION_RECORDS: Final = 3_360
PRETRANSITION_HOLDOUT_RECORDS: Final = 7_291
PRETRANSITION_LAST_RECEIVE_UTC: Final = "2006-09-08T14:57:31Z"
PRETRANSITION_OUTCOME_POSITIVE: Final = "CASSINI_SAGR3_PRETRANSITION_GEOMETRY_SCREEN_POSITIVE"


class CassiniDistributedGeometryError(ValueError):
    """The bounded metadata set or geometric screen is inconsistent."""


@dataclass(frozen=True, slots=True)
class ProductSpec:
    role: str
    lidvid: str
    label_url: str
    label_bytes: int
    label_sha256: str
    data_file_name: str
    published_md5: str
    start_utc: str
    stop_utc: str
    records: int
    record_length_bytes: int
    uplink_band: str
    uplink_station: str
    downlink_band: str
    receive_station: str
    causal_role: str


PRODUCTS: Final = (
    ProductSpec(
        role="MEASUREMENT_X_DSS25",
        lidvid=(
            "urn:nasa:pds:cassini.rss.raw.sagr:data.rsr01:"
            "s23sags2006_251_1200x14x25rd::1.0"
        ),
        label_url=(
            "https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-sagr/"
            "data-rsr01/2006/s23sags2006_251_1200x14x25rd.xml"
        ),
        label_bytes=73_482,
        label_sha256="f83b5c6bb499b99ae0139ccc6c3d45b61b112a8d865490b09a193c20ebae51bc",
        data_file_name="s23sags2006_251_1200x14x25rd.dat",
        published_md5="2f62c3b792fd643124f1a7a7968eb549",
        start_utc="2006-09-08T12:00:01Z",
        stop_utc="2006-09-08T22:30:00Z",
        records=37_800,
        record_length_bytes=4_260,
        uplink_band="X",
        uplink_station="DSS-14",
        downlink_band="X",
        receive_station="DSS-25",
        causal_role="DISTRIBUTED_X_MEASUREMENT_LEFT_AND_DISPERSIVE_PAIR_MEMBER",
    ),
    ProductSpec(
        role="WITNESS_KA_DSS25",
        lidvid=(
            "urn:nasa:pds:cassini.rss.raw.sagr:data.rsr01:"
            "s23sags2006_251_1200x14k25rd::1.0"
        ),
        label_url=(
            "https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-sagr/"
            "data-rsr01/2006/s23sags2006_251_1200x14k25rd.xml"
        ),
        label_bytes=73_482,
        label_sha256="f8c0712750421d54bbb9d996bcb91e5bb0f844f928d94ba779366b21ba33fef0",
        data_file_name="s23sags2006_251_1200x14k25rd.dat",
        published_md5="e6bc1d5485d97c0069e7bd40d036b843",
        start_utc="2006-09-08T12:00:01Z",
        stop_utc="2006-09-08T22:30:00Z",
        records=37_800,
        record_length_bytes=4_260,
        uplink_band="X",
        uplink_station="DSS-14",
        downlink_band="KA",
        receive_station="DSS-25",
        causal_role="SAME_PATH_DISPERSIVE_WITNESS_NOT_AN_INDEPENDENT_OBSERVER",
    ),
    ProductSpec(
        role="MEASUREMENT_X_DSS65",
        lidvid=(
            "urn:nasa:pds:cassini.rss.raw.sagr:data.rsr01:"
            "s23sags2006_251_1200x14x65rd::1.0"
        ),
        label_url=(
            "https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-sagr/"
            "data-rsr01/2006/s23sags2006_251_1200x14x65rd.xml"
        ),
        label_bytes=73_509,
        label_sha256="5e6e7861dcc71552d4b7bebb07c63f03e2cc8968b7b3c0028ef0b3715f7a4419",
        data_file_name="s23sags2006_251_1200x14x65rd.dat",
        published_md5="34e11aaab5265be5a5ae33a99b7e5e67",
        start_utc="2006-09-08T12:00:01Z",
        stop_utc="2006-09-08T16:40:00Z",
        records=16_800,
        record_length_bytes=4_260,
        uplink_band="X",
        uplink_station="DSS-14",
        downlink_band="X",
        receive_station="DSS-65",
        causal_role="DISTRIBUTED_X_MEASUREMENT_RIGHT_INDEPENDENT_RECEIVE_ROOT",
    ),
)


@dataclass(frozen=True, slots=True)
class ForwardEvent:
    transmit_et_tdb_s: float
    receive_et_tdb_s: float
    geometric_light_time_s: float
    geometric_range_m: float
    kinematic_frequency_factor: float
    elevation_rad: float


@dataclass(frozen=True, slots=True)
class TwoWayEpochs:
    receive_et_tdb_s: float
    turnaround_et_tdb_s: float
    uplink_transmit_et_tdb_s: float
    downlink_light_time_s: float
    uplink_light_time_s: float


def solve_forward_event(
    transmit_et_tdb_s: float,
    station_state,
    transmitter_state,
    earth_state,
    *,
    tolerance_s: float = 1e-9,
    maximum_iterations: int = 50,
) -> ForwardEvent:
    """Solve receive epoch from a fixed transmit epoch and exact state functions."""

    if not isfinite(transmit_et_tdb_s):
        raise CassiniDistributedGeometryError("transmit ET/TDB must be finite")
    if not isfinite(tolerance_s) or tolerance_s <= 0.0:
        raise CassiniDistributedGeometryError("light-time tolerance must be positive")
    if maximum_iterations < 1:
        raise CassiniDistributedGeometryError("light-time iteration count must be positive")

    transmitter = transmitter_state(transmit_et_tdb_s)
    transmitter.validate()
    station = station_state(transmit_et_tdb_s)
    station.validate()
    light_time = _distance(transmitter.position_m, station.position_m) / one_way.SPEED_OF_LIGHT_M_S
    for _ in range(maximum_iterations):
        receive_et = transmit_et_tdb_s + light_time
        station = station_state(receive_et)
        station.validate()
        next_light_time = _distance(
            transmitter.position_m, station.position_m
        ) / one_way.SPEED_OF_LIGHT_M_S
        residual = abs(next_light_time - light_time)
        light_time = next_light_time
        if residual <= tolerance_s:
            break
    else:
        raise CassiniDistributedGeometryError(
            "forward one-way light-time solution did not converge"
        )

    receive_et = transmit_et_tdb_s + light_time
    station = station_state(receive_et)
    station.validate()
    earth = earth_state(receive_et)
    earth.validate()
    propagation = _unit_direction(transmitter.position_m, station.position_m)
    factor = one_way._frequency_factor(
        transmitter.velocity_m_s, station.velocity_m_s, propagation
    )
    line_to_spacecraft = _unit_direction(station.position_m, transmitter.position_m)
    zenith = _unit_direction(earth.position_m, station.position_m)
    elevation = asin(np.clip(_dot(line_to_spacecraft, zenith), -1.0, 1.0))
    return ForwardEvent(
        transmit_et_tdb_s=transmit_et_tdb_s,
        receive_et_tdb_s=receive_et,
        geometric_light_time_s=light_time,
        geometric_range_m=_distance(transmitter.position_m, station.position_m),
        kinematic_frequency_factor=factor,
        elevation_rad=float(elevation),
    )


def solve_two_way_epochs(
    receive_et_tdb_s: float,
    uplink_station_state,
    receive_station_state,
    spacecraft_state,
    *,
    tolerance_s: float = 1e-9,
    maximum_iterations: int = 50,
) -> TwoWayEpochs:
    """Map a receive epoch to the corresponding zero-delay two-way uplink epoch.

    The function performs geometry only.  It does not assert transponder lock,
    coherent mode, or that a particular ramp caused a receiver-coordinate
    transition.
    """

    if not isfinite(receive_et_tdb_s):
        raise CassiniDistributedGeometryError("receive ET/TDB must be finite")
    if not isfinite(tolerance_s) or tolerance_s <= 0.0:
        raise CassiniDistributedGeometryError("light-time tolerance must be positive")
    if maximum_iterations < 1:
        raise CassiniDistributedGeometryError("light-time iteration count must be positive")

    downlink = one_way.solve_one_way_event(
        receive_et_tdb_s, receive_station_state, spacecraft_state,
        tolerance_s=tolerance_s, maximum_iterations=maximum_iterations,
    )
    turnaround_et = downlink.transmit_et_tdb_s
    spacecraft = spacecraft_state(turnaround_et)
    spacecraft.validate()
    station = uplink_station_state(turnaround_et)
    station.validate()
    uplink_light_time = (
        _distance(station.position_m, spacecraft.position_m)
        / one_way.SPEED_OF_LIGHT_M_S
    )
    for _ in range(maximum_iterations):
        uplink_transmit_et = turnaround_et - uplink_light_time
        station = uplink_station_state(uplink_transmit_et)
        station.validate()
        next_light_time = (
            _distance(station.position_m, spacecraft.position_m)
            / one_way.SPEED_OF_LIGHT_M_S
        )
        residual = abs(next_light_time - uplink_light_time)
        uplink_light_time = next_light_time
        if residual <= tolerance_s:
            break
    else:
        raise CassiniDistributedGeometryError(
            "reverse uplink light-time solution did not converge"
        )

    return TwoWayEpochs(
        receive_et_tdb_s=receive_et_tdb_s,
        turnaround_et_tdb_s=turnaround_et,
        uplink_transmit_et_tdb_s=turnaround_et - uplink_light_time,
        downlink_light_time_s=downlink.geometric_light_time_s,
        uplink_light_time_s=uplink_light_time,
    )


def screen_distributed_geometry(
    *, spice, kernel_paths: Mapping[str, Path], _pretransition: bool = False
) -> dict[str, object]:
    """Evaluate the exact-hash trajectory without touching any RSR product."""

    products = {product.role: product for product in PRODUCTS}
    left_product = products["MEASUREMENT_X_DSS25"]
    right_product = products["MEASUREMENT_X_DSS65"]

    with header_eval._loaded_exact_kernels(
        spice, TRAJECTORY_ROLE, kernel_paths
    ) as lineage:
        cassini = one_way._spice_state_provider(spice, "CASSINI")
        saturn = one_way._spice_state_provider(spice, "SATURN BARYCENTER")
        earth = one_way._spice_state_provider(spice, "EARTH")
        left_station = one_way._spice_state_provider(spice, left_product.receive_station)
        right_station = one_way._spice_state_provider(spice, right_product.receive_station)

        left_start = one_way.solve_one_way_event(
            float(spice.utc2et(left_product.start_utc)), left_station, cassini
        ).transmit_et_tdb_s
        right_start = one_way.solve_one_way_event(
            float(spice.utc2et(right_product.start_utc)), right_station, cassini
        ).transmit_et_tdb_s
        left_stop = one_way.solve_one_way_event(
            float(spice.utc2et(left_product.stop_utc)), left_station, cassini
        ).transmit_et_tdb_s
        right_stop = one_way.solve_one_way_event(
            float(spice.utc2et(right_product.stop_utc)), right_station, cassini
        ).transmit_et_tdb_s
        common_start = max(left_start, right_start)
        common_stop = min(left_stop, right_stop)
        geometric_records = floor((common_stop - common_start) / GRID_STEP_S) + 1
        records = min(
            geometric_records,
            left_product.records,
            right_product.records,
        )
        if _pretransition:
            records = min(records, PRETRANSITION_RECORDS)
        if records < 10:
            raise CassiniDistributedGeometryError(
                "no useful common-transmit interval exists"
            )
        grid = common_start + np.arange(records, dtype=np.float64) * GRID_STEP_S
        first_transmit_utc = spice.et2utc(float(grid[0]), "ISOC", 6) + "Z"
        last_transmit_utc = spice.et2utc(float(grid[-1]), "ISOC", 6) + "Z"

        orbital_left: list[float] = []
        orbital_right: list[float] = []
        saturn_left: list[float] = []
        saturn_right: list[float] = []
        receive_offsets: list[float] = []
        left_elevation: list[float] = []
        right_elevation: list[float] = []
        timing_maximum = 0.0

        for transmit_et in grid:
            left = solve_forward_event(
                float(transmit_et), left_station, cassini, earth
            )
            right = solve_forward_event(
                float(transmit_et), right_station, cassini, earth
            )
            left_null = solve_forward_event(
                float(transmit_et), left_station, saturn, earth
            )
            right_null = solve_forward_event(
                float(transmit_et), right_station, saturn, earth
            )
            orbital_left.append(left.kinematic_frequency_factor)
            orbital_right.append(right.kinematic_frequency_factor)
            saturn_left.append(left_null.kinematic_frequency_factor)
            saturn_right.append(right_null.kinematic_frequency_factor)
            receive_offsets.append(right.receive_et_tdb_s - left.receive_et_tdb_s)
            left_elevation.append(left.elevation_rad)
            right_elevation.append(right.elevation_rad)

            for station, nominal in (
                (left_station, left.kinematic_frequency_factor),
                (right_station, right.kinematic_frequency_factor),
            ):
                minus = solve_forward_event(
                    float(transmit_et - RSR_TIMING_BOUND_S),
                    station,
                    cassini,
                    earth,
                ).kinematic_frequency_factor
                plus = solve_forward_event(
                    float(transmit_et + RSR_TIMING_BOUND_S),
                    station,
                    cassini,
                    earth,
                ).kinematic_frequency_factor
                timing_maximum = max(
                    timing_maximum,
                    X_BAND_HZ * abs(minus - nominal),
                    X_BAND_HZ * abs(plus - nominal),
                )

    orbital = X_BAND_HZ * (
        np.asarray(orbital_left) - np.asarray(orbital_right)
    )
    saturn_curve = X_BAND_HZ * (
        np.asarray(saturn_left) - np.asarray(saturn_right)
    )
    split = (
        PRETRANSITION_CALIBRATION_RECORDS
        if _pretransition
        else int(ceil(records * CALIBRATION_FRACTION))
    )
    affine_metrics = _prefix_affine_metrics(orbital, split)
    saturn_metrics = _prefix_affine_metrics(orbital - saturn_curve, split)
    controlling_separation = min(
        affine_metrics["peak_to_peak_hz"], saturn_metrics["peak_to_peak_hz"]
    )
    offsets = np.asarray(receive_offsets)
    left_el = np.degrees(np.asarray(left_elevation))
    right_el = np.degrees(np.asarray(right_elevation))
    joint_visible = bool(np.all(left_el > 0.0) and np.all(right_el > 0.0))
    timing_two_sided = 2.0 * timing_maximum
    best_case_resolution = max(
        0.0,
        (controlling_separation - timing_two_sided) / DETECTOR_BINS_REQUIRED,
    )
    result = {
        "screen_version": (
            PRETRANSITION_SCREEN_VERSION if _pretransition else SCREEN_VERSION
        ),
        "screen_manifest_sha256": (
            pretransition_screen_manifest_sha256()
            if _pretransition
            else screen_manifest_sha256()
        ),
        "scope": (
            "THREE_PREDECLARED_PDS_LABELS_EXACT_HASH_SPICE_AND_FROZEN_"
            "PRETRANSITION_WINDOW_ONLY"
            if _pretransition
            else "THREE_PREDECLARED_PDS_LABELS_AND_EXACT_HASH_SPICE_ONLY"
        ),
        "physical_question": (
            "Does observer-coupled Cassini downlink geometry leave a nonlinear "
            "DSS-25 minus DSS-65 X-band signature after prefix-only affine nuisance?"
        ),
        "products": [asdict(product) for product in PRODUCTS],
        "kernel_lineage": list(lineage),
        "coordinate": {
            "event_axis": "COMMON_CASSINI_TRANSMIT_ET_TDB",
            "data_transform_required": (
                "RESAMPLE_BOTH_RECEIVE_STREAMS_ONTO_THIS_FROZEN_AXIS; ALL_NULLS_"
                "RECEIVE_THE_SAME_RESAMPLING"
            ),
            "first_transmit_utc": first_transmit_utc,
            "last_transmit_utc": last_transmit_utc,
            "records": records,
            "cadence_s": GRID_STEP_S,
            "calibration_records": split,
            "holdout_records": records - split,
            "suffix_refit": "PROHIBITED",
            "receive_time_right_minus_left_s": {
                "minimum": float(np.min(offsets)),
                "maximum": float(np.max(offsets)),
                "peak_to_peak": float(np.ptp(offsets)),
            },
        },
        "visibility": {
            "joint_visibility_required": True,
            "joint_visible_on_complete_grid": joint_visible,
            "dss25_elevation_deg": {
                "minimum": float(np.min(left_el)),
                "maximum": float(np.max(left_el)),
            },
            "dss65_elevation_deg": {
                "minimum": float(np.min(right_el)),
                "maximum": float(np.max(right_el)),
            },
        },
        "orbital_observable": {
            "definition": (
                "8425e6 * (kinematic_factor_DSS25 - kinematic_factor_DSS65)"
            ),
            "raw_peak_to_peak_hz": float(np.ptp(orbital)),
            "raw_rms_hz": float(sqrt(float(np.mean(orbital * orbital)))),
        },
        "nulls": {
            "prefix_affine": affine_metrics,
            "saturn_barycenter_geometry_destroying": saturn_metrics,
            "station_swap": "REMOVED_AS_SIGN_REDUNDANT_UNDER_DIFFERENTIAL_SCORING",
        },
        "controlling_heldout_peak_to_peak_hz": controlling_separation,
        "timing_envelope": {
            "per_stream_event_time_bound_s": RSR_TIMING_BOUND_S,
            "method": "DIRECT_FORWARD_TRAJECTORY_AT_T_MINUS_AND_PLUS_BOUND",
            "maximum_one_stream_absolute_hz": timing_maximum,
            "two_stream_two_sided_hz": timing_two_sided,
        },
        "best_case_detector_resolution_ceiling_hz": best_case_resolution,
        "best_case_ceiling_is_admission_requirement": False,
        "same_path_witness": {
            "products": [
                "MEASUREMENT_X_DSS25",
                "WITNESS_KA_DSS25",
            ],
            "model": (
                "z_band(t) = g_common(t) + plasma(t) / f_band^2 + "
                "band_specific_hardware(t)"
            ),
            "raw_cross_band_difference_is_orbital_measurement": False,
            "permitted_role": (
                "Estimate dispersive structure and recover a common non-dispersive "
                "coordinate only after band-specific hardware is qualified"
            ),
        },
        "independence": {
            "independent_measurement_roots": ["DSS-25", "DSS-65"],
            "shared_upstream": [
                "DSS-14 X-band uplink",
                "Cassini transponder",
                "interplanetary downlink path before Earth-near divergence",
            ],
            "dss25_x_ka_pair_is_second_observer": False,
        },
        "screen_outcome": (
            (
                PRETRANSITION_OUTCOME_POSITIVE if _pretransition else OUTCOME_POSITIVE
            )
            if joint_visible and controlling_separation > timing_two_sided
            else "DISTRIBUTED_GEOMETRY_SCREEN_NONPOSITIVE"
        ),
        "physical_admission": False,
        "rsr_header_access_authorized": False,
        "iq_access_authorized": False,
        "detector_authorized": False,
        "exact_remaining_blocker": (
            "PRETRANSITION_PHYSICAL_CORRECTION_ENVELOPE"
            if _pretransition
            else (
                "PREDECLARED_THREE_PRODUCT_HEADER_ONLY_QUALIFICATION_OF_RSN_TIME_"
                "CONTINUITY_SAMPLE_MODE_NCO_AND_INDEPENDENT_RSR_HARDWARE"
            )
        ),
    }
    if _pretransition:
        result["coordinate"]["frozen_receive_stop_inclusive"] = (
            PRETRANSITION_LAST_RECEIVE_UTC
        )
        result["coordinate"]["excluded_coordinate_transition_utc"] = (
            "2006-09-08T14:57:32.000000Z"
        )
        result["coordinate"]["window_selection_basis"] = (
            "CONTROL_HEADER_TRANSITION_FROZEN_BEFORE_ANY_IQ_ACCESS"
        )
    strict_json(result)
    return result


def screen_pretransition_geometry(
    *, spice, kernel_paths: Mapping[str, Path]
) -> dict[str, object]:
    """Evaluate the fixed 10,651-record window ending before the transition."""

    return screen_distributed_geometry(
        spice=spice, kernel_paths=kernel_paths, _pretransition=True
    )


def decompose_common_and_dispersive(
    fractional_x: Sequence[float], fractional_ka: Sequence[float]
) -> tuple[np.ndarray, np.ndarray]:
    """Solve z(f)=g+p/f^2; hardware terms must be closed before use on RF."""

    x = np.asarray(fractional_x, dtype=np.float64)
    ka = np.asarray(fractional_ka, dtype=np.float64)
    if x.shape != ka.shape or not np.all(np.isfinite(x)) or not np.all(np.isfinite(ka)):
        raise CassiniDistributedGeometryError(
            "cross-band fractional arrays must be finite and shape-matched"
        )
    denominator = KA_BAND_HZ**2 - X_BAND_HZ**2
    common = (KA_BAND_HZ**2 * ka - X_BAND_HZ**2 * x) / denominator
    dispersive = (x - ka) / (1.0 / X_BAND_HZ**2 - 1.0 / KA_BAND_HZ**2)
    return common, dispersive


def screen_manifest_sha256() -> str:
    manifest = {
        "screen_version": SCREEN_VERSION,
        "products": [asdict(product) for product in PRODUCTS],
        "trajectory_role": TRAJECTORY_ROLE,
        "x_band_hz": X_BAND_HZ,
        "ka_band_hz": KA_BAND_HZ,
        "calibration_fraction": CALIBRATION_FRACTION,
        "grid_step_s": GRID_STEP_S,
        "timing_bound_s": RSR_TIMING_BOUND_S,
        "nulls": [
            "PREFIX_AFFINE",
            "SATURN_BARYCENTER_GEOMETRY_DESTROYING",
        ],
        "forbidden": [
            "RSR header access",
            "RSR payload access",
            "IQ decoding",
            "amplitude diagnostics",
            "detector implementation",
            "suffix refit",
            "null-specific resampling",
        ],
    }
    return sha256(strict_json(manifest).encode("ascii")).hexdigest()


def pretransition_screen_manifest_sha256() -> str:
    manifest = {
        "screen_version": PRETRANSITION_SCREEN_VERSION,
        "parent_screen_manifest_sha256": screen_manifest_sha256(),
        "products": [asdict(product) for product in PRODUCTS],
        "trajectory_role": TRAJECTORY_ROLE,
        "x_band_hz": X_BAND_HZ,
        "ka_band_hz": KA_BAND_HZ,
        "records": PRETRANSITION_RECORDS,
        "calibration_records": PRETRANSITION_CALIBRATION_RECORDS,
        "holdout_records": PRETRANSITION_HOLDOUT_RECORDS,
        "last_receive_utc_inclusive": PRETRANSITION_LAST_RECEIVE_UTC,
        "excluded_coordinate_transition_utc": "2006-09-08T14:57:32.000000Z",
        "window_selection_basis": (
            "CONTROL_HEADER_TRANSITION_FROZEN_BEFORE_ANY_IQ_ACCESS"
        ),
        "grid_step_s": GRID_STEP_S,
        "timing_bound_s": RSR_TIMING_BOUND_S,
        "nulls": [
            "PREFIX_AFFINE_WITH_ORIGINAL_3360_RECORD_PREFIX",
            "SATURN_BARYCENTER_GEOMETRY_DESTROYING",
        ],
        "forbidden": [
            "RSR payload access",
            "IQ decoding",
            "amplitude diagnostics",
            "detector implementation",
            "suffix refit",
            "post-transition samples",
            "null-specific resampling",
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


def _prefix_affine_metrics(curve: Sequence[float], split: int) -> dict[str, float]:
    values = np.asarray(curve, dtype=np.float64)
    if values.ndim != 1 or values.size <= split or split < 2:
        raise CassiniDistributedGeometryError("invalid prefix/holdout geometry")
    if not np.all(np.isfinite(values)):
        raise CassiniDistributedGeometryError("curve contains non-finite values")
    elapsed = np.arange(values.size, dtype=np.float64) * GRID_STEP_S
    design = np.column_stack((np.ones(split), elapsed[:split]))
    coefficients, *_ = np.linalg.lstsq(design, values[:split], rcond=None)
    residual = values - (coefficients[0] + coefficients[1] * elapsed)
    heldout = residual[split:]
    return {
        "peak_to_peak_hz": float(np.ptp(heldout)),
        "rms_hz": float(sqrt(float(np.mean(heldout * heldout)))),
        "maximum_absolute_hz": float(np.max(np.abs(heldout))),
        "prefix_rmse_hz": float(
            sqrt(float(np.mean(residual[:split] * residual[:split])))
        ),
    }


def _distance(left: Sequence[float], right: Sequence[float]) -> float:
    return sqrt(sum((float(r) - float(l)) ** 2 for l, r in zip(left, right)))


def _unit_direction(
    origin: Sequence[float], destination: Sequence[float]
) -> tuple[float, float, float]:
    delta = tuple(float(d) - float(o) for o, d in zip(origin, destination))
    length = sqrt(sum(value * value for value in delta))
    if length <= 0.0:
        raise CassiniDistributedGeometryError("link endpoints must not be colocated")
    return tuple(value / length for value in delta)  # type: ignore[return-value]


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(float(l) * float(r) for l, r in zip(left, right))
