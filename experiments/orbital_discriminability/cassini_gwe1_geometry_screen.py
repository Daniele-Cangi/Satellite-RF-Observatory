"""Metadata-only Cassini GWE1 two-way geometry route screen.

The screen is deliberately narrower than the closed SAGR3 distributed route.
It evaluates one DSS-25 receive root with three simultaneous coherent links
(X/X, X/Ka, Ka/Ka) and two same-path AWVR products.  It reads exact-hash SPICE
kernels only.  It has no RSR, path-delay table, header, sample, amplitude,
detector, or network input.

The purpose is not to admit an experiment.  It asks whether a pre-pass Cassini
PREDICT trajectory contains held-out two-way structure that survives both a
prefix-only affine null and a frozen rectilinear-spacecraft alternative.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from math import asin, floor, isfinite, sqrt
from pathlib import Path
from typing import Final, Iterator, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import cassini_dss26_one_way as one_way
from experiments.orbital_discriminability import (
    cassini_sagr3_distributed_geometry as light_time,
)


SCREEN_VERSION: Final = "cassini-gwe1-two-way-geometry-route-screen-v1"
GRID_STEP_S: Final = 10.0
CALIBRATION_FRACTION: Final = 0.2
NOMINAL_X_DOWNLINK_HZ: Final = 8_400_000_000.0
NOMINAL_KA_DOWNLINK_HZ: Final = 32_000_000_000.0
OUTCOME_POSITIVE: Final = "CASSINI_GWE1_GEOMETRY_ROUTE_POSITIVE"


class CassiniGweGeometryError(ValueError):
    """The bounded GWE metadata set or geometry screen is inconsistent."""


@dataclass(frozen=True, slots=True)
class KernelSpec:
    name: str
    bytes: int
    sha256: str
    url: str
    role: str
    independence: str


KERNELS: Final = (
    KernelSpec(
        "naif0012.tls",
        5_257,
        "678e32bdb5a744117a467cd9601cd6b373f0e9bc9bbde1371d5eee39600a039b",
        "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/lsk/naif0012.tls",
        "UTC_TO_ET_TDB",
        "TIME_SCALE_CONTROL",
    ),
    KernelSpec(
        "de405s.bsp",
        1_426_432,
        "0e3793cca287b75ce33bf6155a8fef912d1114de63b7cf39eded66afc08e8f98",
        (
            "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/"
            "a_old_versions/de405s.bsp"
        ),
        "PLANETARY_STATE_CHAIN",
        "PLANETARY_EPHEMERIS_NOT_TARGET_RF",
    ),
    KernelSpec(
        "earth_720101_070426.bpc",
        8_603_648,
        "1fa3670679bcd3d1978bea7653a34e68d1518f832124412c766faf454d77205e",
        (
            "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/"
            "a_old_versions/earth_720101_070426.bpc"
        ),
        "HISTORICAL_EARTH_ORIENTATION",
        "POST_PASS_EOP_INDEPENDENT_OF_TARGET_RF",
    ),
    KernelSpec(
        "earthstns_itrf93_050714.bsp",
        38_912,
        "371fb58d19dd757de7b31cac80b5e61d5eaa26dc3437a009eece1c47792cee5c",
        (
            "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/stations/"
            "a_old_versions/earthstns_itrf93_050714.bsp"
        ),
        "DSS25_STATION_STATE",
        "STATION_MODEL_INDEPENDENT_OF_TARGET_RF",
    ),
    KernelSpec(
        "010222A_SK_JP054_JP458.bsp",
        1_129_472,
        "63c10d2ca02fae980a7932bac0e8b6e1731ba1eaa8c86fd58738cfe31d5a020d",
        "https://naif.jpl.nasa.gov/pub/naif/CASSINI/kernels/spk/010222A_SK_JP054_JP458.bsp",
        "CASSINI_TRAJECTORY",
        (
            "PREDICT_CREATED_2001_02_22; PROPAGATED_ARC_THROUGH_2002_04_02; "
            "NO_RECONSTRUCTED_ARC; BEFORE_ALL_GWE1_SESSIONS"
        ),
    ),
)


@dataclass(frozen=True, slots=True)
class RsrProduct:
    role: str
    lidvid: str
    label_url: str
    label_bytes: int
    label_sha256: str
    data_file: str
    published_data_md5: str
    data_bytes: int
    records: int
    start_utc: str
    stop_utc: str
    uplink_band: str
    downlink_band: str


@dataclass(frozen=True, slots=True)
class PathDelayProduct:
    role: str
    lidvid: str
    label_url: str
    label_bytes: int
    label_sha256: str
    data_file: str
    published_data_md5: str
    data_bytes: int
    records: int
    start_utc: str
    stop_utc: str
    instrument: str


@dataclass(frozen=True, slots=True)
class Session:
    role: str
    day_of_year: int
    rsr_products: tuple[RsrProduct, RsrProduct, RsrProduct]
    path_delay_products: tuple[PathDelayProduct, PathDelayProduct]
    common_start_utc: str
    common_stop_utc: str


def _rsr(
    role: str,
    product: str,
    label_sha256: str,
    data_md5: str,
    data_bytes: int,
    records: int,
    start_utc: str,
    stop_utc: str,
    uplink: str,
    downlink: str,
) -> RsrProduct:
    return RsrProduct(
        role=role,
        lidvid=f"urn:nasa:pds:cassini.rss.raw.gwe:data.rsr01:{product}::1.0",
        label_url=(
            "https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-gwe/"
            f"data-rsr01/2001/{product}.xml"
        ),
        label_bytes=73_519,
        label_sha256=label_sha256,
        data_file=f"{product}.dat",
        published_data_md5=data_md5,
        data_bytes=data_bytes,
        records=records,
        start_utc=start_utc,
        stop_utc=stop_utc,
        uplink_band=uplink,
        downlink_band=downlink,
    )


def _pd(
    role: str,
    product: str,
    label_sha256: str,
    data_md5: str,
    data_bytes: int,
    records: int,
    start_utc: str,
    stop_utc: str,
    instrument: str,
) -> PathDelayProduct:
    collection = "pd1" if instrument.endswith("1") else "pd2"
    return PathDelayProduct(
        role=role,
        lidvid=(
            f"urn:nasa:pds:cassini.rss.raw.gwe:data.{collection}:" f"{product}::1.0"
        ),
        label_url=(
            "https://atmos.nmsu.edu/PDS/data/PDS4/cassini-rss-raw-gwe/"
            f"data-{collection}/2001/{product}.xml"
        ),
        label_bytes=22_269,
        label_sha256=label_sha256,
        data_file=f"{product}.tab",
        published_data_md5=data_md5,
        data_bytes=data_bytes,
        records=records,
        start_utc=start_utc,
        stop_utc=stop_utc,
        instrument=instrument,
    )


SESSIONS: Final = (
    Session(
        "DEVELOPMENT_CANDIDATE",
        331,
        (
            _rsr(
                "X_X",
                "c29eagw2001_331_0434x25x25rd",
                "b2ccea15c83d4d00992217fa9526acd004997388e9fb49b6edff988a7f00a70a",
                "9ae07f87145b92416db1ee499bf089d1",
                163_584_000,
                38_400,
                "2001-11-27T04:34:59Z",
                "2001-11-27T15:14:58Z",
                "X",
                "X",
            ),
            _rsr(
                "X_KA",
                "c29eagw2001_331_0435x25k25rd",
                "d5573514c935af7bd4a88af5ae1bacdefb1eb8187400ec22809b5f3af66f8865",
                "b24eb4dc30e75ae8a58feb51f6c8375d",
                163_515_840,
                38_384,
                "2001-11-27T04:35:15Z",
                "2001-11-27T15:14:58Z",
                "X",
                "KA",
            ),
            _rsr(
                "KA_KA",
                "c29eagw2001_331_0440k25k25rd",
                "378034bde245e335ddbb8c19be4d0141a4b56b9ab5bd8ec567299de1e0b9a0af",
                "d043653bc0e001a3d90b9a31169f9d18",
                162_288_960,
                38_096,
                "2001-11-27T04:40:03Z",
                "2001-11-27T15:14:58Z",
                "KA",
                "KA",
            ),
        ),
        (
            _pd(
                "AWVR_1",
                "c29eagw2001_331_0250_151525",
                "8a89a436c5e7df71dd0ac35949061fe1145cd498426429f5aee9f3239c356d2c",
                "cdcbcdbbd98dd216f6362e35fcce2963",
                137_949,
                1_858,
                "2001-11-27T02:51:00Z",
                "2001-11-27T15:13:48Z",
                "AWVR1",
            ),
            _pd(
                "AWVR_2",
                "c29eagw2001_331_0250_151525",
                "3272329b19d9794541d22a6d84c80b2802e1df15087f534cc549c9bd0f3010c5",
                "8f58ada66209320dd4cddcba94d71166",
                137_949,
                1_858,
                "2001-11-27T02:51:00Z",
                "2001-11-27T15:13:48Z",
                "AWVR2",
            ),
        ),
        "2001-11-27T04:40:03Z",
        "2001-11-27T15:13:48Z",
    ),
    Session(
        "RESERVE_CANDIDATE",
        342,
        (
            _rsr(
                "X_X",
                "c29eagw2001_342_0346x25x25rd",
                "88eb2909ffa430875dc92f7c363f4043406c6d0dd356e8e9d751abfdfd021aef",
                "d20439695c21f6a1aa8f5b8b334941d9",
                165_888_660,
                38_941,
                "2001-12-08T03:46:00Z",
                "2001-12-08T14:35:00Z",
                "X",
                "X",
            ),
            _rsr(
                "X_KA",
                "c29eagw2001_342_0346x25k25rd",
                "b0e0e7fd296e23078a26dd153b2694ade203a9e9487a7bb943197b9673e2e51e",
                "5704f42e8122181f3952651e9273309f",
                165_888_660,
                38_941,
                "2001-12-08T03:46:00Z",
                "2001-12-08T14:35:00Z",
                "X",
                "KA",
            ),
            _rsr(
                "KA_KA",
                "c29eagw2001_342_0352k25k25rd",
                "8b3f2896778e21dfb7018ba2c2ca03c6a9f82f876588246009385204293e1f68",
                "7b294f387b5cf715f4de97b8190605d3",
                164_103_720,
                38_522,
                "2001-12-08T03:52:58Z",
                "2001-12-08T14:34:59Z",
                "KA",
                "KA",
            ),
        ),
        (
            _pd(
                "AWVR_1",
                "c29eagw2001_342_0155_143525",
                "54c356a886b131b64a4c437635a853e5d335673f285117360b5b9b5a121a30a8",
                "5b1f0fe2aae2998ef4680e12b8ce583f",
                140_735,
                1_896,
                "2001-12-08T01:56:00Z",
                "2001-12-08T14:34:00Z",
                "AWVR1",
            ),
            _pd(
                "AWVR_2",
                "c29eagw2001_342_0155_143525",
                "8d5c4eb65677d9e7c46ad84c023975c62fc81ffbdd77b289e2d590334b1264bd",
                "59dadb2ad491a337d5cc231b779b0c2a",
                140_730,
                1_896,
                "2001-12-08T01:56:00Z",
                "2001-12-08T14:34:00Z",
                "AWVR2",
            ),
        ),
        "2001-12-08T03:52:58Z",
        "2001-12-08T14:34:00Z",
    ),
    Session(
        "PRIMARY_CANDIDATE",
        347,
        (
            _rsr(
                "X_X",
                "c29eagw2001_347_0321x25x25rd",
                "ad571dfb00dace6840dd3b4814286204b555577d54ef8055f26c21cce8b9f6e9",
                "083d842d30ad5dc141d17f7ecd1dc288",
                164_610_660,
                38_641,
                "2001-12-13T03:21:00Z",
                "2001-12-13T14:05:00Z",
                "X",
                "X",
            ),
            _rsr(
                "X_KA",
                "c29eagw2001_347_0321x25k25rd",
                "54a500886d89cfcff8f61d150e2b418d3563f684fe461938cab89687b7afa730",
                "29153a006ff717937b4a1ad258058d07",
                164_610_660,
                38_641,
                "2001-12-13T03:21:00Z",
                "2001-12-13T14:05:00Z",
                "X",
                "KA",
            ),
            _rsr(
                "KA_KA",
                "c29eagw2001_347_0324k25k25rd",
                "53624523b84ea565d900a346581891c04433e05600cf280bc0b1ac5871186a29",
                "fd29485ccb171aea1eed378a62e638cf",
                163_630_860,
                38_411,
                "2001-12-13T03:24:50Z",
                "2001-12-13T14:05:00Z",
                "KA",
                "KA",
            ),
        ),
        (
            _pd(
                "AWVR_1",
                "c29eagw2001_347_0135_140525",
                "3ad64eb97f15a907ab15e6997a46bc9912855d6a1dcd011689991620205181ff",
                "6a50b3800c751bdefd2d9cbfdfccf9c4",
                138_893,
                1_871,
                "2001-12-13T01:36:00Z",
                "2001-12-13T14:04:00Z",
                "AWVR1",
            ),
            _pd(
                "AWVR_2",
                "c29eagw2001_347_0135_140525",
                "d4c4a078d7458ed1187840e4d07feb42a387e67399e373a229385bb02ef4d2e5",
                "7cf56a7957e85a18e4faea6c990f6b37",
                138_893,
                1_871,
                "2001-12-13T01:36:00Z",
                "2001-12-13T14:04:00Z",
                "AWVR2",
            ),
        ),
        "2001-12-13T03:24:50Z",
        "2001-12-13T14:04:00Z",
    ),
)


@contextmanager
def _loaded_exact_kernels(
    spice, kernel_paths: Mapping[str, Path]
) -> Iterator[list[dict[str, object]]]:
    if set(kernel_paths) != {spec.name for spec in KERNELS}:
        raise CassiniGweGeometryError("kernel set does not match the frozen manifest")
    lineage: list[dict[str, object]] = []
    for spec in KERNELS:
        path = Path(kernel_paths[spec.name])
        if not path.is_file() or path.stat().st_size != spec.bytes:
            raise CassiniGweGeometryError(f"kernel identity failed: {spec.name}")
        digest = _file_sha256(path)
        if digest != spec.sha256:
            raise CassiniGweGeometryError(f"kernel SHA-256 failed: {spec.name}")
        lineage.append(asdict(spec))
    spice.kclear()
    try:
        for spec in KERNELS:
            spice.furnsh(str(kernel_paths[spec.name]))
        yield lineage
    finally:
        spice.kclear()


def _two_way_factor_and_elevation(
    receive_et: float, station_state, spacecraft_state, earth_state
) -> tuple[float, float]:
    epochs = light_time.solve_two_way_epochs(
        receive_et, station_state, station_state, spacecraft_state
    )
    station_tx = station_state(epochs.uplink_transmit_et_tdb_s)
    spacecraft = spacecraft_state(epochs.turnaround_et_tdb_s)
    station_rx = station_state(receive_et)
    earth_rx = earth_state(receive_et)
    uplink_factor = one_way._frequency_factor(
        station_tx.velocity_m_s,
        spacecraft.velocity_m_s,
        _unit(station_tx.position_m, spacecraft.position_m),
    )
    downlink_factor = one_way._frequency_factor(
        spacecraft.velocity_m_s,
        station_rx.velocity_m_s,
        _unit(spacecraft.position_m, station_rx.position_m),
    )
    line_of_sight = _unit(station_rx.position_m, spacecraft.position_m)
    zenith = _unit(earth_rx.position_m, station_rx.position_m)
    elevation = asin(np.clip(_dot(line_of_sight, zenith), -1.0, 1.0))
    return uplink_factor * downlink_factor, float(np.degrees(elevation))


def _rectilinear_state_provider(nominal_state, anchor_et: float):
    anchor = nominal_state(anchor_et)
    anchor.validate()

    def state(epoch_et: float) -> one_way.StateVector:
        elapsed = epoch_et - anchor_et
        return one_way.StateVector(
            position_m=tuple(
                position + velocity * elapsed
                for position, velocity in zip(anchor.position_m, anchor.velocity_m_s)
            ),
            velocity_m_s=anchor.velocity_m_s,
        )

    return state


def _prefix_affine_residual(
    values: Sequence[float], split: int, cadence_s: float
) -> tuple[np.ndarray, dict[str, float]]:
    curve = np.asarray(values, dtype=np.float64)
    if curve.ndim != 1 or curve.size <= split or split < 2:
        raise CassiniGweGeometryError("invalid prefix/holdout geometry")
    if not np.all(np.isfinite(curve)) or cadence_s <= 0.0:
        raise CassiniGweGeometryError("curve and cadence must be finite")
    elapsed = np.arange(curve.size, dtype=np.float64) * cadence_s
    design = np.column_stack((np.ones(split), elapsed[:split]))
    coefficients, *_ = np.linalg.lstsq(design, curve[:split], rcond=None)
    residual = curve - (coefficients[0] + coefficients[1] * elapsed)
    heldout = residual[split:]
    return residual, {
        "heldout_peak_to_peak": float(np.ptp(heldout)),
        "heldout_rms": float(sqrt(float(np.mean(heldout * heldout)))),
        "heldout_maximum_absolute": float(np.max(np.abs(heldout))),
        "prefix_rmse": float(sqrt(float(np.mean(residual[:split] * residual[:split])))),
    }


def _screen_session(
    spice, session: Session, grid_step_s: float = GRID_STEP_S
) -> dict[str, object]:
    if not isfinite(grid_step_s) or grid_step_s <= 0.0:
        raise CassiniGweGeometryError("grid step must be positive and finite")
    station = one_way._spice_state_provider(spice, "DSS-25")
    cassini = one_way._spice_state_provider(spice, "CASSINI")
    earth = one_way._spice_state_provider(spice, "EARTH")
    start_et = float(spice.utc2et(session.common_start_utc))
    stop_et = float(spice.utc2et(session.common_stop_utc))
    grid = np.arange(start_et, stop_et + 0.5 * grid_step_s, grid_step_s)
    split = max(2, int(floor(grid.size * CALIBRATION_FRACTION)))
    rectilinear = _rectilinear_state_provider(cassini, float(grid[split - 1]))
    orbital: list[float] = []
    null: list[float] = []
    elevations: list[float] = []
    for receive_et in grid:
        orbital_factor, elevation = _two_way_factor_and_elevation(
            float(receive_et), station, cassini, earth
        )
        null_factor, _ = _two_way_factor_and_elevation(
            float(receive_et), station, rectilinear, earth
        )
        orbital.append(orbital_factor - 1.0)
        null.append(null_factor - 1.0)
        elevations.append(elevation)

    orbital_residual, affine_metrics = _prefix_affine_residual(
        orbital, split, grid_step_s
    )
    null_residual, null_affine_metrics = _prefix_affine_residual(
        null, split, grid_step_s
    )
    heldout_difference = (orbital_residual - null_residual)[split:]
    geometry_metrics = {
        "heldout_peak_to_peak": float(np.ptp(heldout_difference)),
        "heldout_rms": float(
            sqrt(float(np.mean(heldout_difference * heldout_difference)))
        ),
        "heldout_maximum_absolute": float(np.max(np.abs(heldout_difference))),
    }
    scaled: dict[str, object] = {}
    for name, carrier in (
        ("NOMINAL_X_8P4_GHZ", NOMINAL_X_DOWNLINK_HZ),
        ("NOMINAL_KA_32_GHZ", NOMINAL_KA_DOWNLINK_HZ),
    ):
        scaled[name] = {
            "orbital_vs_affine_peak_to_peak_hz": affine_metrics["heldout_peak_to_peak"]
            * carrier,
            "orbital_vs_affine_rms_hz": affine_metrics["heldout_rms"] * carrier,
            "orbital_vs_rectilinear_peak_to_peak_hz": geometry_metrics[
                "heldout_peak_to_peak"
            ]
            * carrier,
            "orbital_vs_rectilinear_rms_hz": geometry_metrics["heldout_rms"] * carrier,
        }
    elevations_array = np.asarray(elevations)
    return {
        "role": session.role,
        "day_of_year": session.day_of_year,
        "receive_start_utc": session.common_start_utc,
        "receive_stop_utc": session.common_stop_utc,
        "records": int(grid.size),
        "grid_step_s": grid_step_s,
        "calibration_records": split,
        "calibration_stop_utc": spice.et2utc(float(grid[split - 1]), "ISOC", 3) + "Z",
        "holdout_start_utc": spice.et2utc(float(grid[split]), "ISOC", 3) + "Z",
        "visibility": {
            "required": True,
            "visible_on_complete_grid": bool(np.all(elevations_array > 0.0)),
            "minimum_elevation_deg": float(np.min(elevations_array)),
            "maximum_elevation_deg": float(np.max(elevations_array)),
        },
        "fractional_orbital_vs_affine": affine_metrics,
        "fractional_rectilinear_vs_affine": null_affine_metrics,
        "fractional_orbital_vs_rectilinear": geometry_metrics,
        "screening_carrier_scalings": scaled,
    }


def screen_gwe1_geometry(
    *, spice, kernel_paths: Mapping[str, Path]
) -> dict[str, object]:
    """Run the exact-hash metadata-only screen over the three bounded sessions."""

    with _loaded_exact_kernels(spice, kernel_paths) as lineage:
        screens = [_screen_session(spice, session) for session in SESSIONS]
    positive = all(
        screen["visibility"]["visible_on_complete_grid"]
        and screen["fractional_orbital_vs_rectilinear"]["heldout_peak_to_peak"] > 0.0
        for screen in screens
    )
    result = {
        "screen_version": SCREEN_VERSION,
        "screen_manifest_sha256": screen_manifest_sha256(),
        "physical_question": (
            "Does a pre-pass Cassini trajectory preserve non-affine two-way link "
            "structure against a frozen rectilinear-spacecraft alternative in an "
            "independent suffix at DSS-25?"
        ),
        "sessions": [
            {
                "role": session.role,
                "day_of_year": session.day_of_year,
                "rsr_products": [asdict(product) for product in session.rsr_products],
                "path_delay_products": [
                    asdict(product) for product in session.path_delay_products
                ],
                "common_interval_basis": (
                    "INTERSECTION_OF_THREE_RSR_LABELS_AND_TWO_PATH_DELAY_LABELS"
                ),
                "common_start_utc": session.common_start_utc,
                "common_stop_utc": session.common_stop_utc,
            }
            for session in SESSIONS
        ],
        "kernel_lineage": lineage,
        "coordinate": {
            "event_axis": "RSR_RECEIVE_ET_TDB",
            "central_model": (
                "DSS25_UPLINK_LIGHT_TIME_X_CASSINI_COHERENT_TURNAROUND_X_"
                "DSS25_DOWNLINK_LIGHT_TIME"
            ),
            "grid_step_s": GRID_STEP_S,
            "calibration_fraction": CALIBRATION_FRACTION,
            "exact_ramp_and_nco_applied": False,
            "carrier_scalings_are_screening_only": True,
        },
        "nulls": {
            "prefix_affine": (
                "CONSTANT_PLUS_LINEAR_FREQUENCY_FIT_ON_PREFIX_ONLY; NO_SUFFIX_REFIT"
            ),
            "rectilinear_spacecraft": (
                "CASSINI_POSITION_AND_VELOCITY_FROZEN_TO_INERTIAL_TANGENT_AT_"
                "PREFIX_END; SAME_TWO_WAY_SOLVER_AND_SEPARATE_PREFIX_AFFINE_FIT"
            ),
        },
        "screens": screens,
        "causal_topology": {
            "independent_receive_roots": ["DSS-25"],
            "simultaneous_link_coordinates": ["X/X", "X/Ka", "Ka/Ka"],
            "same_path_media_witnesses": ["AWVR1", "AWVR2"],
            "awvr_measurements_are_yet_qualified": False,
            "awvr_products_are_independent_orbital_roots": False,
            "claim_scope_if_later_admitted": (
                "SINGLE_STATION_TWO_WAY_ORBITAL_MODEL_VERSUS_FROZEN_NULLS; "
                "NOT_DISTRIBUTED_CONFIRMATION_AND_NOT_IDENTITY"
            ),
        },
        "screen_outcome": (
            OUTCOME_POSITIVE if positive else "CASSINI_GWE1_GEOMETRY_ROUTE_NONPOSITIVE"
        ),
        "physical_admission": False,
        "rsr_header_access_authorized": False,
        "path_delay_table_access_authorized": False,
        "iq_access_authorized": False,
        "detector_authorized": False,
        "exact_remaining_blockers": [
            "THREE_LINK_RSR_HEADER_CONTINUITY_AND_EXACT_RAMP_NCO_COORDINATE",
            "AWVR1_AWVR2_TABLE_CONTINUITY_FLAGS_AND_OUTCOME_INDEPENDENT_UNCERTAINTY",
            "BAND_SPECIFIC_RECEIVER_HARDWARE_DIFFERENTIAL_ENVELOPE",
            "EXACT_TWO_WAY_TURNAROUND_RATIOS_AND_RAMP_PROVENANCE",
            "RECORDED_BASEBAND_RECOMPUTATION_WITH_IDENTICAL_NULL_TRANSFORMS",
        ],
    }
    strict_json(result)
    return result


def screen_manifest_sha256() -> str:
    manifest = {
        "screen_version": SCREEN_VERSION,
        "sessions": [asdict(session) for session in SESSIONS],
        "kernels": [asdict(kernel) for kernel in KERNELS],
        "grid_step_s": GRID_STEP_S,
        "calibration_fraction": CALIBRATION_FRACTION,
        "nulls": ["PREFIX_AFFINE", "RECTILINEAR_SPACECRAFT_AT_PREFIX_END"],
        "forbidden": [
            "RSR header access",
            "RSR payload access",
            "path-delay table access",
            "IQ decoding",
            "amplitude diagnostics",
            "detector implementation",
            "suffix refit",
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


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _unit(
    origin: Sequence[float], destination: Sequence[float]
) -> tuple[float, float, float]:
    delta = np.asarray(destination, dtype=np.float64) - np.asarray(
        origin, dtype=np.float64
    )
    length = float(np.linalg.norm(delta))
    if not isfinite(length) or length <= 0.0:
        raise CassiniGweGeometryError("link endpoints must not be colocated")
    return tuple(float(value) for value in delta / length)


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    return float(
        np.dot(np.asarray(left, dtype=np.float64), np.asarray(right, dtype=np.float64))
    )
