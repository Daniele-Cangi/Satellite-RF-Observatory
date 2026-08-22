"""Bounded metadata-only selection of a Cassini dual-root X/Ka pass.

The frozen source scope is the three official PDS4 SROC RSR collection
inventories. Five cross-complex sessions were selected before their labels
were inspected. Only a documented media-clear sub-window may enter geometry.

There is no network, RSR header, sample, amplitude, detector, or IQ input.
The five-second grid is a selection approximation, not a prospective grid.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import ceil, sqrt
from pathlib import Path
from typing import Final, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import cassini_dss14_header_evaluation as header_eval
from experiments.orbital_discriminability import cassini_dss26_one_way as one_way
from experiments.orbital_discriminability import cassini_sagr3_distributed_geometry as geometry


SELECTION_VERSION: Final = "cassini-sroc-dual-root-pass-selection-v1"
GRID_STEP_S: Final = 5.0
CALIBRATION_FRACTION: Final = 0.2
SCREENING_X_BAND_HZ: Final = 8_425_000_000.0
PLANNING_TIMING_BOUND_S: Final = 1e-6
OUTCOME_POSITIVE: Final = (
    "ONE_MEDIA_CLEAR_DUAL_ROOT_CANDIDATE_GEOMETRY_SCREEN_POSITIVE"
)
OUTCOME_NONE: Final = "NO_COMPLETE_DUAL_ROOT_PASS_FOUND"


class CassiniPassSelectionError(ValueError):
    """The frozen bounded selection or its geometry is inconsistent."""


@dataclass(frozen=True, slots=True)
class SourceSnapshot:
    role: str
    url: str
    bytes: int
    sha256: str


SOURCES: Final = (
    SourceSnapshot(
        "SROC_RSR01_COLLECTION_INVENTORY",
        "https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-sroc/data-rsr01/collection_sroc_rsr01.csv",
        122_992,
        "73d0a017c1db060a787ad96803f46cb85949806b371cf74ac95acc6ec14fd7d2",
    ),
    SourceSnapshot(
        "SROC_RSR02_COLLECTION_INVENTORY",
        "https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-sroc/data-rsr02/collection_sroc_rsr02.csv",
        1_230,
        "7f2e7d09e2e839b4c009172ccfff4c7c22b4368c96e69af7797ed9722ebd3e68",
    ),
    SourceSnapshot(
        "SROC_RSR16_COLLECTION_INVENTORY",
        "https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-sroc/data-rsr16/collection_sroc_rsr16.csv",
        73_636,
        "d5b84215078e9e784362ba64c2f1787985116d635d05c4276543ec5514db356a",
    ),
    SourceSnapshot(
        "SROC_PLANNING_TABLE",
        "https://atmos.nmsu.edu/data_and_services/atmospheres_data/Cassini/logs/8-Saturn_and_Saturn_Ring_Occultation_Planning.csv",
        25_835,
        "e0b22b90160f5c8d778d09fd397c246090fcad85bec9a7c7fdcac7a68c5f4eff",
    ),
)


@dataclass(frozen=True, slots=True)
class PredictKernel:
    name: str
    label_sha256: str
    product_creation_utc: str
    coverage_start_utc: str
    coverage_stop_utc: str
    product_version_type: str = "PREDICT"


@dataclass(frozen=True, slots=True)
class Candidate:
    candidate_id: str
    stations: tuple[str, str]
    complexes: tuple[str, str]
    uplink_path: str
    product_names: tuple[str, str, str, str]
    label_sha256: tuple[str, str, str, str]
    overlap_start_utc: str
    overlap_stop_utc: str
    overlap_seconds: int
    media_scope: str
    media_evidence: tuple[str, ...]
    geometry_start_utc: str | None
    geometry_stop_utc: str | None
    predict: PredictKernel


PREDICT_2005: Final = PredictKernel(
    "050426AP_SCPSE_05116_05216.bsp",
    "561cde58c09488576fbdfc32643c16b6a851ef29bf3bbb8cc049579752b3e9a6",
    "2005-04-26T11:10:12Z",
    "2005-04-26T11:04:46Z",
    "2005-08-04T00:00:00Z",
)
PREDICT_2008_139: Final = PredictKernel(
    "080514AP_SCPSE_08130_08153.bsp",
    "1a5ec267756653c75a32eec8d8a849091b7d661de0e7004e54fa2fe250d6d7f6",
    "2008-05-14T12:20:17Z",
    "2008-05-09T02:12:06Z",
    "2008-06-01T05:58:55Z",
)
PREDICT_2008_168: Final = PredictKernel(
    "080609AP_SCPSE_08161_08217.bsp",
    "4441286f245be809dbfa84735b6b30f0ec2cf70634a5c59f4a1a8ea45548f7bb",
    "2008-06-09T15:38:06Z",
    "2008-06-09T15:24:48Z",
    "2008-08-04T05:58:55Z",
)
PREDICT_2016: Final = PredictKernel(
    "160620AP_SCPSE_16172_16212.bsp",
    "114a9848b5d1b2685332e66008974f1fe3fb1daf99b77a6e6d21c236fbfd8a90",
    "2016-06-20T12:21:55Z",
    "2016-06-19T23:58:55Z",
    "2016-07-29T23:58:55Z",
)
PREDICT_2017: Final = PredictKernel(
    "170417AP_SCPSE_17062_17116.bsp",
    "4c3f3115aa4f1f53f134369d8ae0322904d2d940771c37fcbbc1f101a537f560",
    "2017-04-17T12:06:41Z",
    "2017-03-02T23:58:55Z",
    "2017-04-25T23:58:55Z",
)


CANDIDATES: Final = (
    Candidate(
        "SROC_2005_159_DSS25_DSS55",
        ("DSS-25", "DSS-55"),
        ("GOLDSTONE", "MADRID"),
        "ONE_WAY_NNN",
        (
            "s11sroe2005_159_1715nnnk25rd",
            "s11sroe2005_159_1715nnnx25rd",
            "s11sroe2005_159_1715nnnk55rd",
            "s11sroe2005_159_1715nnnx55rd",
        ),
        (
            "a785a4c803b4b66aaa5b585e98834e7141fdb9405c10eef8acab0165ecd371c4",
            "74ad0b7c1911ac7567843dd576263fc3e7aa19cda2b484cb78610fc7a4d76d5e",
            "8cbcea9512d103d2992738e98b5b5c72ce44f1888415436c0d5f39e555ec61c2",
            "fd135f96ca3f3d1e0d21aef09c3e50f13a624b42291977cfffa5abce0cd09cfe",
        ),
        "2005-06-08T17:15:01Z",
        "2005-06-08T20:44:59Z",
        12_598,
        "DOCUMENTED_POST_OCCULTATION_CLEAR_WINDOW",
        (
            "RSS_009RI_OCC004_PRIME 16:30-18:33 UTC",
            "Deadtime X-to-Earth 18:33-19:17 UTC",
            "frozen post-media window starts at 19:17 UTC",
        ),
        "2005-06-08T19:17:00Z",
        "2005-06-08T20:44:59Z",
        PREDICT_2005,
    ),
    Candidate(
        "SROC_2008_139_DSS25_DSS55",
        ("DSS-25", "DSS-55"),
        ("GOLDSTONE", "MADRID"),
        "ONE_WAY_NNN",
        (
            "s40saoe2008_139_0000nnnk25rd",
            "s40saoe2008_139_0000nnnx25rd",
            "s40saoe2008_139_0000nnnk55rd",
            "s40saoe2008_139_0000nnnx55rd",
        ),
        (
            "98446387728ebd0014b01cb81d71924d29750315b8ae1b7fc9f03a00a5e46fab",
            "a89252a27e8bf46b0907d6b61b9cc9fca502da1af415589683255d9d6ba6e6d1",
            "ae48d2a35a1246e23151cc52a5f90aa4dc0f09f95386f5e2af2bf4471aea6019",
            "f62d963b52f35bfbfcaaacde667052584fb53265326ddff77ca9e8b960a80740",
        ),
        "2008-05-18T00:00:00Z",
        "2008-05-18T01:06:32Z",
        3_992,
        "MEDIA_SCOPE_UNKNOWN",
        ("bounded planning-table snapshot has no matching 2008-139 activity",),
        None,
        None,
        PREDICT_2008_139,
    ),
    Candidate(
        "SROC_2008_168_DSS25_DSS34",
        ("DSS-25", "DSS-34"),
        ("GOLDSTONE", "CANBERRA"),
        "ONE_WAY_NNN",
        (
            "s41saoe2008_168_0600nnnk25rd",
            "s41saoe2008_168_0600nnnx25rd",
            "s41saoe2008_168_0600nnnk34rd",
            "s41saoe2008_168_0600nnnx34rd",
        ),
        (
            "1b9dc7a5a3e8faff502237d808f975dc01ca9948b29cada8116173d795461f77",
            "baeb1f704b1d318b4c980a0dfdc9a410e4e77a927f530a231d2f8417f200fab0",
            "de334fcc41ca6cb0280635e7c0df069f4260add44538c3e37073718abfc3d46c",
            "a7cdd1d26aa976e06018d9ce4875c1cd8b912767542b6a13e90e4aa81dfc1e15",
        ),
        "2008-06-16T06:00:00Z",
        "2008-06-16T06:54:59Z",
        3_299,
        "MEDIA_SCOPE_UNKNOWN",
        ("bounded planning-table snapshot has no matching 2008-168 activity",),
        None,
        None,
        PREDICT_2008_168,
    ),
    Candidate(
        "SROC_2016_182_DSS25_DSS35",
        ("DSS-25", "DSS-35"),
        ("GOLDSTONE", "CANBERRA"),
        "COHERENT_X_UPLINK_DSS14",
        (
            "s95saoe2016_182_0630x14k25rd",
            "s95saoe2016_182_0630x14x25rd",
            "s95saoe2016_182_0630x14k35rd",
            "s95saoe2016_182_0630x14x35rd",
        ),
        (
            "f3ff65eeb4ccdb3053e1dc210fd74ac1f852b907ea2e1a4728b6784d1abbcd09",
            "1d99403ae57f20fb02ccc252130925336e09c9c96ebc2c82335b3f723aa9fa83",
            "873a2d70007a307ea1380bb4d169bc9d9afdcb732b5d12bfd26fc0e6a9a1a696",
            "20f385645f43ba17977639d75de7c93b4279ea682c8eafad0ade343574945ed4",
        ),
        "2016-06-30T06:30:00Z",
        "2016-06-30T08:30:00Z",
        7_200,
        "FULL_OVERLAP_OCCULTATION_MEDIA",
        (
            "RSS_237SA_OCC002_PRIME 03:42-06:40 UTC",
            "RSS_237RI_OCC002_PIE 06:40-09:14 UTC",
        ),
        None,
        None,
        PREDICT_2016,
    ),
    Candidate(
        "SROC_2017_110_DSS26_DSS35",
        ("DSS-26", "DSS-35"),
        ("GOLDSTONE", "CANBERRA"),
        "COHERENT_X_UPLINK_DSS14",
        (
            "s99saoi2017_110_1230x14k26rd",
            "s99saoi2017_110_1230x14x26rd",
            "s99saoi2017_110_1230x14k35rd",
            "s99saoi2017_110_1230x14x35rd",
        ),
        (
            "3087f6824ca72404fd684828db975919a3e6395867f3edbb38a7147820e0b4c0",
            "357e209d2d5a95918ceb89925d3cb9de6ba34a36f44ef0a8c92436cccee08d62",
            "d809db7f704c8de122575e73302ba1f96a2ac545a3f6ab2e441531cb6d5e1e68",
            "65ebb99e27a434461a403fa5addddb36e189f990967dc498bd35685104c29adc",
        ),
        "2017-04-20T12:30:00Z",
        "2017-04-20T16:00:00Z",
        12_600,
        "OCCULTATION_THEN_DEADBAND",
        (
            "RSS_270SA_OCC001_PRIME 11:58-15:41 UTC",
            "deadband 15:41-16:01 UTC",
        ),
        None,
        None,
        PREDICT_2017,
    ),
)


def physical_condition_ledger() -> tuple[dict[str, object], ...]:
    """Every unresolved causal condition remains explicitly non-numeric."""

    rows = (
        ("FIRST_ORDER_PLASMA_EACH_ROOT", "OBSERVABLE_IN_PRINCIPLE", "simultaneous X/Ka; exact composite needs header carriers"),
        ("HIGHER_ORDER_PLASMA", "UNRESOLVED", "X/Ka does not cancel every dispersive term"),
        ("OCCULTATION_MEDIA", "CANDIDATE_SPECIFIC", "must be absent or bounded on exact holdout"),
        ("EARTH_TROPOSPHERE_DIFFERENTIAL", "UNRESOLVED", "station-local non-dispersive uncertainty"),
        ("RECEIVER_PROPER_TIME_GRAVITY_DIFFERENTIAL", "MODELED_CENTRAL_UNCERTAINTY_UNRESOLVED", "central value is not uncertainty"),
        ("RELATIVISTIC_PROPAGATION_REMAINDER", "UNRESOLVED", "requires predeclared uncertainty family"),
        ("EOP_AND_STATION_COORDINATES", "MODELED", "outcome-independent controls; propagate uncertainty"),
        ("USO_RETARDED_TIME_COUPLING", "UNRESOLVED", "different receive roots sample different transmit epochs"),
        ("X_KA_DIFFERENTIAL_HARDWARE", "UNRESOLVED", "two receive chains per root"),
        ("ADC_TIME_BINDING", "PLANNING_BOUND_ONLY", "1 microsecond screen; exact SFDU proof required"),
        ("NCO_DDC_TRANSITIONS", "UNKNOWN_UNTIL_HEADER_ONLY_AUDIT", "transition in holdout invalidates transform"),
        ("SAMPLE_RATE_FILTER_DECIMATION", "UNKNOWN_UNTIL_HEADER_ONLY_AUDIT", "collection is not resolution"),
        ("RSN_GAPS_X_KA_ALIGNMENT", "UNKNOWN_UNTIL_HEADER_ONLY_AUDIT", "labels do not prove continuity"),
        ("DETECTOR_SNR_CLIPPING", "UNKNOWN_UNTIL_MODEL_BLIND_DEVELOPMENT", "no IQ or amplitude accessed"),
        ("PREDICT_SPK_ORBIT_ERROR", "UNRESOLVED", "independent pre-pass orbit has no frozen covariance"),
        ("NULL_DEGENERACY", "EVALUATED_BY_SAME_PROJECTION", "affine and Saturn-center use same prefix/grid"),
        ("COMMON_TRANSMIT_EPOCH_MAPPING", "MODELED_SELECTION_ONLY", "receive roots map to distinct receive times on one transmit-time coordinate"),
        ("STATION_PHASE_CENTER_CABLE_DELAY", "UNRESOLVED", "root-specific non-dispersive delay and drift"),
        ("FREQUENCY_REFERENCE_STABILITY", "UNKNOWN_UNTIL_HEADER_ONLY_AUDIT", "cycle slips and reference changes may imitate curvature"),
        ("POLARIZATION_CHANNEL_MAPPING", "UNKNOWN_UNTIL_HEADER_ONLY_AUDIT", "band labels do not prove identical polarization or channel lineage"),
        ("FINITE_INTEGRATION_SPECTRAL_SMEARING", "UNKNOWN_UNTIL_DETECTOR_FREEZE", "header cadence and estimator window set the convolution kernel"),
        ("SOLAR_SYSTEM_EPHEMERIS_AND_CONSTANTS", "MODELED", "outcome-independent central model; uncertainty not yet propagated"),
        ("NUMERICAL_LIGHT_TIME_CONVERGENCE", "TESTABLE_SOFTWARE_BOUND", "solver tolerance must stay below the physical envelope"),
        ("OPEN_TERM_CORRELATION", "UNRESOLVED", "do not root-sum-square terms without documented independence"),
    )
    return tuple(
        {"condition": name, "state": state, "scope": scope, "numeric_substitution": None}
        for name, state, scope in rows
    )


def approximation_policy() -> dict[str, object]:
    """Return the frozen non-probabilistic treatment of unknown conditions."""

    return {
        "representation": "NON_PROBABILISTIC_CAUSAL_STATE_ENVELOPE",
        "states": [
            "OBSERVABLE",
            "MODELED",
            "BOUNDED",
            "UNRESOLVED",
        ],
        "combination": (
            "CORRELATED_INTERVAL_ENVELOPE_UNLESS_INDEPENDENCE_IS_DOCUMENTED"
        ),
        "prohibited": [
            "UNRESOLVED_AS_ZERO",
            "ROOT_SUM_SQUARE_WITHOUT_INDEPENDENCE",
            "POST_OUTCOME_BOUND_SELECTION",
            "UNJUSTIFIED_PROBABILITY_AMPLITUDES",
        ],
    }


def validate_frozen_selection() -> None:
    if len(CANDIDATES) != 5 or len({c.candidate_id for c in CANDIDATES}) != 5:
        raise CassiniPassSelectionError("the predeclared five-candidate set changed")
    for candidate in CANDIDATES:
        if len(candidate.product_names) != 4 or len(set(candidate.complexes)) != 2:
            raise CassiniPassSelectionError("candidate topology is not cross-complex")
        for station in candidate.stations:
            suffix = station[-2:]
            names = [name for name in candidate.product_names if name[-4:-2] == suffix]
            if len(names) != 2 or {name[-5] for name in names} != {"x", "k"}:
                raise CassiniPassSelectionError("each root requires exactly X and Ka")
        start = _utc(candidate.overlap_start_utc)
        stop = _utc(candidate.overlap_stop_utc)
        if int((stop - start).total_seconds()) != candidate.overlap_seconds:
            raise CassiniPassSelectionError("label intersection changed")
        predict = candidate.predict
        if predict.product_version_type != "PREDICT":
            raise CassiniPassSelectionError("trajectory is not PREDICT")
        if not (_utc(predict.product_creation_utc) < start):
            raise CassiniPassSelectionError("trajectory was not created before pass")
        if not (_utc(predict.coverage_start_utc) <= start <= _utc(predict.coverage_stop_utc)):
            raise CassiniPassSelectionError("trajectory does not cover pass")
    admitted = [c.candidate_id for c in CANDIDATES if c.geometry_start_utc]
    if admitted != ["SROC_2005_159_DSS25_DSS55"]:
        raise CassiniPassSelectionError("media admission changed")


def screen_media_clear_candidate(*, spice, kernel_paths: Mapping[str, Path]) -> dict[str, object]:
    """Screen the sole admitted 2005 sub-window on a five-second grid."""

    validate_frozen_selection()
    candidate = CANDIDATES[0]
    assert candidate.geometry_start_utc and candidate.geometry_stop_utc
    with header_eval._loaded_exact_kernels(
        spice, "HEADER_CANDIDATE_B", kernel_paths
    ) as lineage:
        cassini = one_way._spice_state_provider(spice, "CASSINI")
        saturn = one_way._spice_state_provider(spice, "SATURN BARYCENTER")
        earth = one_way._spice_state_provider(spice, "EARTH")
        left_station = one_way._spice_state_provider(spice, candidate.stations[0])
        right_station = one_way._spice_state_provider(spice, candidate.stations[1])
        start_et = float(spice.utc2et(candidate.geometry_start_utc))
        stop_et = float(spice.utc2et(candidate.geometry_stop_utc))
        common_start = max(
            one_way.solve_one_way_event(start_et, left_station, cassini).transmit_et_tdb_s,
            one_way.solve_one_way_event(start_et, right_station, cassini).transmit_et_tdb_s,
        )
        common_stop = min(
            one_way.solve_one_way_event(stop_et, left_station, cassini).transmit_et_tdb_s,
            one_way.solve_one_way_event(stop_et, right_station, cassini).transmit_et_tdb_s,
        )
        count = int((common_stop - common_start) // GRID_STEP_S) + 1
        grid = common_start + np.arange(count, dtype=np.float64) * GRID_STEP_S
        left_values, right_values, saturn_left, saturn_right = [], [], [], []
        left_el, right_el, receive_offsets = [], [], []
        timing_max = 0.0
        for transmit_et in grid:
            left = geometry.solve_forward_event(float(transmit_et), left_station, cassini, earth)
            right = geometry.solve_forward_event(float(transmit_et), right_station, cassini, earth)
            left_null = geometry.solve_forward_event(float(transmit_et), left_station, saturn, earth)
            right_null = geometry.solve_forward_event(float(transmit_et), right_station, saturn, earth)
            left_values.append(left.kinematic_frequency_factor)
            right_values.append(right.kinematic_frequency_factor)
            saturn_left.append(left_null.kinematic_frequency_factor)
            saturn_right.append(right_null.kinematic_frequency_factor)
            left_el.append(left.elevation_rad)
            right_el.append(right.elevation_rad)
            receive_offsets.append(right.receive_et_tdb_s - left.receive_et_tdb_s)
            for station, nominal in ((left_station, left), (right_station, right)):
                minus = geometry.solve_forward_event(float(transmit_et - PLANNING_TIMING_BOUND_S), station, cassini, earth)
                plus = geometry.solve_forward_event(float(transmit_et + PLANNING_TIMING_BOUND_S), station, cassini, earth)
                timing_max = max(
                    timing_max,
                    SCREENING_X_BAND_HZ * abs(minus.kinematic_frequency_factor - nominal.kinematic_frequency_factor),
                    SCREENING_X_BAND_HZ * abs(plus.kinematic_frequency_factor - nominal.kinematic_frequency_factor),
                )
        first_transmit_utc = spice.et2utc(float(grid[0]), "ISOC", 6) + "Z"
        last_transmit_utc = spice.et2utc(float(grid[-1]), "ISOC", 6) + "Z"
    orbital = SCREENING_X_BAND_HZ * (np.asarray(left_values) - np.asarray(right_values))
    saturn_curve = SCREENING_X_BAND_HZ * (np.asarray(saturn_left) - np.asarray(saturn_right))
    split = int(ceil(count * CALIBRATION_FRACTION))
    affine = _prefix_affine_metrics(orbital, split)
    saturn_null = _prefix_affine_metrics(orbital - saturn_curve, split)
    controlling = min(affine["peak_to_peak_hz"], saturn_null["peak_to_peak_hz"])
    left_deg = np.degrees(np.asarray(left_el))
    right_deg = np.degrees(np.asarray(right_el))
    joint_visible = bool(np.all(left_deg > 0.0) and np.all(right_deg > 0.0))
    result = {
        "candidate_id": candidate.candidate_id,
        "screening_grid": {
            "event_axis": "COMMON_CASSINI_TRANSMIT_ET_TDB",
            "step_s": GRID_STEP_S,
            "approximation_role": "SELECTION_ONLY_NOT_FINAL_SFDU_GRID",
            "records": count,
            "calibration_records": split,
            "holdout_records": count - split,
            "first_transmit_utc": first_transmit_utc,
            "last_transmit_utc": last_transmit_utc,
            "suffix_refit": "PROHIBITED",
        },
        "kernel_lineage": [
            {
                **entry,
                "role": (
                    "DSN_STATION_STATES_DSS25_DSS55"
                    if entry["role"] == "DSS14_STATION_STATE"
                    else entry["role"]
                ),
            }
            for entry in lineage
        ],
        "visibility": {
            "joint_visibility_required": True,
            "joint_visible": joint_visible,
            "dss25_elevation_deg": {"minimum": float(np.min(left_deg)), "maximum": float(np.max(left_deg))},
            "dss55_elevation_deg": {"minimum": float(np.min(right_deg)), "maximum": float(np.max(right_deg))},
        },
        "orbital_observable": {
            "definition": "8425e6 * (factor_DSS25 - factor_DSS55)",
            "raw_peak_to_peak_hz": float(np.ptp(orbital)),
            "raw_rms_hz": float(sqrt(float(np.mean(orbital * orbital)))),
            "receive_time_dss55_minus_dss25_s": {
                "minimum": float(np.min(receive_offsets)),
                "maximum": float(np.max(receive_offsets)),
            },
        },
        "nulls": {
            "prefix_affine": affine,
            "saturn_barycenter_geometry_destroying": saturn_null,
            "station_swap": "REMOVED_AS_SIGN_REDUNDANT",
        },
        "controlling_heldout_peak_to_peak_hz": controlling,
        "timing_envelope": {
            "per_stream_planning_bound_s": PLANNING_TIMING_BOUND_S,
            "method": "DIRECT_FORWARD_TRAJECTORY_AT_T_MINUS_AND_PLUS_BOUND",
            "maximum_one_stream_absolute_hz": timing_max,
            "two_stream_two_sided_hz": 2.0 * timing_max,
            "final_header_bound_still_required": True,
        },
        "screen_positive": bool(joint_visible and controlling > 2.0 * timing_max),
    }
    strict_json(result)
    return result


def build_receipt(geometry_screen: Mapping[str, object] | None) -> dict[str, object]:
    validate_frozen_selection()
    screen_positive = bool(
        geometry_screen and geometry_screen.get("screen_positive")
    )
    candidates = []
    for candidate in CANDIDATES:
        row = asdict(candidate)
        row["topology_state"] = (
            "CROSS_COMPLEX_DUAL_ROOT_X_KA_LABEL_QUALIFIED"
        )
        row["geometry_screen_state"] = (
            "EVALUATED"
            if candidate.geometry_start_utc and geometry_screen
            else "NOT_EVALUATED"
        )
        candidates.append(row)
    receipt = {
        "selection_version": SELECTION_VERSION,
        "selection_manifest_sha256": selection_manifest_sha256(),
        "outcome": OUTCOME_POSITIVE if screen_positive else OUTCOME_NONE,
        "scope": (
            "THREE_HASHED_SROC_RSR_COLLECTIONS_"
            "FIVE_PREDECLARED_SESSIONS_METADATA_ONLY"
        ),
        "source_snapshots": [asdict(source) for source in SOURCES],
        "inventory_filter": {
            "parsed_product_rows": 1_499,
            "same_day_dual_band_candidates": 43,
            "exact_start_cross_complex_dual_band_sessions": 16,
            "predeclared_label_shortlist": 5,
            "post_label_substitution": "PROHIBITED",
        },
        "candidates": candidates,
        "geometry_screen": (
            dict(geometry_screen) if geometry_screen else None
        ),
        "approximation_policy": approximation_policy(),
        "physical_condition_ledger": list(physical_condition_ledger()),
        "claim": {
            "authorized": [
                (
                    "five exact sessions have label-level X/Ka coverage "
                    "at two DSN complexes"
                ),
                "one has a documented post-occultation sub-window",
                "the selected trajectory is pre-pass PREDICT",
            ]
            + (
                ["the 2005 central geometry screen is positive"]
                if screen_positive
                else []
            ),
            "not_authorized": [
                "measurement validity",
                "plasma-corrected RF observable",
                "physical open-term closure",
                "orbital model preference",
                "satellite identity",
                "IQ access",
            ],
        },
        "access": {
            "rsr_header_bytes": 0,
            "rsr_iq_bytes": 0,
            "amplitude_values": 0,
        },
        "next_blocker": (
            "HEADER_ONLY_DSS25_DSS55_X_KA_QUALIFICATION_"
            "ON_2005_159_POST_MEDIA_WINDOW"
            if screen_positive
            else "NO_MEDIA_CLEAR_POSITIVE_GEOMETRY_CANDIDATE"
        ),
        "experiment_frozen": False,
    }
    strict_json(receipt)
    return receipt


def selection_manifest_sha256() -> str:
    manifest = {
        "selection_version": SELECTION_VERSION,
        "sources": [asdict(source) for source in SOURCES],
        "candidate_ids": [
            candidate.candidate_id for candidate in CANDIDATES
        ],
        "label_sha256": [
            digest
            for candidate in CANDIDATES
            for digest in candidate.label_sha256
        ],
        "predict_label_sha256": [
            candidate.predict.label_sha256 for candidate in CANDIDATES
        ],
        "grid_step_s": GRID_STEP_S,
        "calibration_fraction": CALIBRATION_FRACTION,
        "planning_timing_bound_s": PLANNING_TIMING_BOUND_S,
        "nulls": [
            "PREFIX_AFFINE",
            "SATURN_BARYCENTER_GEOMETRY_DESTROYING",
        ],
        "forbidden": [
            "RSR header access",
            "RSR payload access",
            "IQ decoding",
            "amplitude diagnostics",
            "post-label substitution",
            "suffix refit",
            "unresolved term set to zero",
        ],
        "approximation_policy": approximation_policy(),
        "physical_condition_ledger": list(physical_condition_ledger()),
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


def _prefix_affine_metrics(
    curve: Sequence[float], split: int
) -> dict[str, float]:
    values = np.asarray(curve, dtype=np.float64)
    if (
        values.ndim != 1
        or split < 2
        or values.size <= split
        or not np.all(np.isfinite(values))
    ):
        raise CassiniPassSelectionError(
            "invalid finite prefix/holdout curve"
        )
    elapsed = np.arange(values.size, dtype=np.float64) * GRID_STEP_S
    design = np.column_stack((np.ones(split), elapsed[:split]))
    coefficients, *_ = np.linalg.lstsq(
        design, values[:split], rcond=None
    )
    residual = values - (
        coefficients[0] + coefficients[1] * elapsed
    )
    heldout = residual[split:]
    return {
        "peak_to_peak_hz": float(np.ptp(heldout)),
        "rms_hz": float(
            sqrt(float(np.mean(heldout * heldout)))
        ),
        "maximum_absolute_hz": float(np.max(np.abs(heldout))),
        "prefix_rmse_hz": float(
            sqrt(float(np.mean(residual[:split] * residual[:split])))
        ),
    }


def _utc(text: str) -> datetime:
    value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise CassiniPassSelectionError("UTC must be timezone-aware")
    return value.astimezone(timezone.utc)

