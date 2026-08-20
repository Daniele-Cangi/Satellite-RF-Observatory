"""Offline Cassini/DSS-26 one-way frequency compiler.

The compiler is deliberately scoped to the predeclared Cassini SAGR
development product.  It loads only the frozen pre-pass PREDICT SPK and its
time/station/Earth-orientation controls through SpiceyPy/CSPICE.  It has no
Horizons, Skyfield, reconstructed-orbit, RSR-payload, or ridge input.

The implemented central value includes geometric one-way light time and the
exact special-relativistic kinematic frequency factor in flat spacetime.
Terms not yet compiled are never silently assigned zero: they remain explicit
OPEN_TERM entries and make the result ineligible for a primary claim.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from hashlib import sha256
import importlib
import json
from math import isfinite, sqrt
from pathlib import Path
from typing import Final, Iterable, Iterator, Literal, Mapping, Protocol


SPEED_OF_LIGHT_M_S: Final = 299_792_458.0
COMPILER_VERSION: Final = "cassini-dss26-one-way-spiceypy-v1"
DEVELOPMENT_LIDVID: Final = (
    "urn:nasa:pds:cassini.rss.raw.sagr:data.rsr01:"
    "s11sags2005_157_1750nnnx26rd::1.0"
)
DEVELOPMENT_STATION: Final = "DSS-26"
SPACECRAFT: Final = "CASSINI"
INERTIAL_FRAME: Final = "J2000"
STATE_OBSERVER: Final = "SOLAR SYSTEM BARYCENTER"


class CassiniPredictionError(ValueError):
    """The product-specific one-way prediction is incomplete or inconsistent."""


class SpiceApi(Protocol):
    """Only the SpiceyPy/CSPICE entry points used by this compiler."""

    def furnsh(self, path: str) -> None: ...

    def kclear(self) -> None: ...

    def utc2et(self, utc: str) -> float: ...

    def et2utc(self, et: float, format: str, precision: int) -> str: ...

    def spkezr(
        self,
        target: str,
        et: float,
        frame: str,
        aberration_correction: str,
        observer: str,
    ) -> tuple[Iterable[float], float]: ...


@dataclass(frozen=True, slots=True)
class KernelSpec:
    name: str
    bytes: int
    sha256: str
    role: str
    independence: str


CASSINI_DSS26_KERNELS: Final = (
    KernelSpec(
        name="naif0012.tls",
        bytes=5_257,
        sha256="678e32bdb5a744117a467cd9601cd6b373f0e9bc9bbde1371d5eee39600a039b",
        role="UTC_TO_ET_TDB",
        independence="TIME_SCALE_CONTROL",
    ),
    KernelSpec(
        name="earth_720101_070426.bpc",
        bytes=8_603_648,
        sha256="1fa3670679bcd3d1978bea7653a34e68d1518f832124412c766faf454d77205e",
        role="HISTORICAL_EARTH_ORIENTATION",
        independence="EARTH_EOP_NOT_SPACECRAFT_RF_OUTCOME",
    ),
    KernelSpec(
        name="earthstns_itrf93_050714.bsp",
        bytes=38_912,
        sha256="371fb58d19dd757de7b31cac80b5e61d5eaa26dc3437a009eece1c47792cee5c",
        role="DSS26_STATION_STATE",
        independence="STATION_MODEL_CREATED_2005_PRE_PASS",
    ),
    KernelSpec(
        name="050426AP_SCPSE_05116_05216.bsp",
        bytes=3_832_832,
        sha256="065258e6982b10488604d97f02f9b5110d6b1e4760ff340211b50973ab8228f5",
        role="CASSINI_TRAJECTORY",
        independence="PREDICT_CREATED_2005_04_26_BEFORE_DEVELOPMENT_PASS",
    ),
)


CorrectionStatus = Literal["APPLIED", "BOUNDED", "OPEN_TERM"]


@dataclass(frozen=True, slots=True)
class FrequencyCorrectionTerm:
    """One declared correction downstream of the kinematic transfer."""

    name: str
    status: CorrectionStatus
    central_correction_hz: float | None
    absolute_bound_hz: float | None
    scope: str

    def validate(self) -> None:
        if not self.name or not self.scope:
            raise CassiniPredictionError("correction terms require name and scope")
        if self.status == "OPEN_TERM":
            if self.central_correction_hz is not None or self.absolute_bound_hz is not None:
                raise CassiniPredictionError("OPEN_TERM cannot carry an invented number")
            return
        if self.central_correction_hz is None or not isfinite(self.central_correction_hz):
            raise CassiniPredictionError("resolved correction requires a finite central value")
        if self.status == "BOUNDED":
            if self.absolute_bound_hz is None or not isfinite(self.absolute_bound_hz):
                raise CassiniPredictionError("BOUNDED correction requires a finite bound")
            if self.absolute_bound_hz < 0.0:
                raise CassiniPredictionError("frequency-correction bound must be non-negative")
        elif self.absolute_bound_hz is not None and (
            not isfinite(self.absolute_bound_hz) or self.absolute_bound_hz < 0.0
        ):
            raise CassiniPredictionError("APPLIED correction bound must be non-negative")


_REQUIRED_PROPAGATION_TERMS: Final = (
    "PROPER_TIME_AND_GRAVITATIONAL_FREQUENCY",
    "RELATIVISTIC_PROPAGATION_LIGHT_TIME",
    "EARTH_TROPOSPHERE",
    "EARTH_IONOSPHERE",
    "INTERPLANETARY_PLASMA",
    "STATION_HARDWARE_DELAY",
    "AVAILABLE_MEDIA_CALIBRATION",
)


def initial_open_terms() -> tuple[FrequencyCorrectionTerm, ...]:
    """The complete non-kinematic ledger for the first offline compiler."""

    scopes = {
        "PROPER_TIME_AND_GRAVITATIONAL_FREQUENCY": (
            "spacecraft/station proper-time and gravitational redshift"
        ),
        "RELATIVISTIC_PROPAGATION_LIGHT_TIME": "solar-system gravitational delay",
        "EARTH_TROPOSPHERE": "neutral-atmosphere path and frequency effect",
        "EARTH_IONOSPHERE": "dispersive terrestrial ionosphere",
        "INTERPLANETARY_PLASMA": "dispersive solar/interplanetary plasma",
        "STATION_HARDWARE_DELAY": "DSS receive-chain delay and its time derivative",
        "AVAILABLE_MEDIA_CALIBRATION": "applicable archived media calibration products",
    }
    return tuple(
        FrequencyCorrectionTerm(name, "OPEN_TERM", None, None, scopes[name])
        for name in _REQUIRED_PROPAGATION_TERMS
    )


@dataclass(frozen=True, slots=True)
class USOCarrierModel:
    """Declared rest-frame carrier plus pre-freeze calibration nuisance."""

    nominal_rest_frequency_hz: float
    calibration_reference_utc: str
    constant_offset_hz: float | None
    aging_rate_hz_s: float | None

    def validate(self) -> None:
        if not isfinite(self.nominal_rest_frequency_hz) or self.nominal_rest_frequency_hz <= 0.0:
            raise CassiniPredictionError("USO nominal rest frequency must be positive")
        if not self.calibration_reference_utc:
            raise CassiniPredictionError("USO calibration reference UTC is required")
        for value in (self.constant_offset_hz, self.aging_rate_hz_s):
            if value is not None and not isfinite(value):
                raise CassiniPredictionError("USO nuisance values must be finite")


@dataclass(frozen=True, slots=True)
class StateVector:
    position_m: tuple[float, float, float]
    velocity_m_s: tuple[float, float, float]

    def validate(self) -> None:
        values = (*self.position_m, *self.velocity_m_s)
        if not all(isfinite(value) for value in values):
            raise CassiniPredictionError("SPICE state vectors must be finite")
        if _norm(self.velocity_m_s) >= SPEED_OF_LIGHT_M_S:
            raise CassiniPredictionError("SPICE state-vector speed must be subluminal")


@dataclass(frozen=True, slots=True)
class OneWayEvent:
    receive_et_tdb_s: float
    transmit_et_tdb_s: float
    geometric_light_time_s: float
    geometric_range_m: float
    kinematic_frequency_factor: float


@dataclass(frozen=True, slots=True)
class OneWayPrediction:
    compiler_version: str
    development_lidvid: str
    receive_utc: str
    receive_et_tdb_s: float
    transmit_utc: str
    transmit_et_tdb_s: float
    station: str
    spacecraft: str
    geometric_light_time_s: float
    geometric_range_m: float
    nominal_rest_frequency_hz: float
    emitted_frequency_hz: float
    kinematic_frequency_factor: float
    kinematic_received_frequency_hz: float
    declared_correction_hz: float
    declared_correction_bound_hz: float
    received_sky_frequency_hz: float
    steering_only_received_sky_frequency_hz: float
    orbital_minus_steering_only_hz: float
    correction_terms: tuple[FrequencyCorrectionTerm, ...]
    kernel_lineage: tuple[dict[str, object], ...]
    transform_ledger: tuple[str, ...]
    claim_scope: str
    sky_prediction_terms_closed: bool
    primary_prediction_authorized: bool

    def as_json_object(self) -> dict[str, object]:
        return asdict(self)


def solve_one_way_event(
    receive_et_tdb_s: float,
    station_state,
    spacecraft_state,
    *,
    tolerance_s: float = 1e-9,
    maximum_iterations: int = 50,
) -> OneWayEvent:
    """Solve the geometric transmit epoch and exact flat-spacetime Doppler."""

    if not isfinite(receive_et_tdb_s):
        raise CassiniPredictionError("receive ET/TDB must be finite")
    if not isfinite(tolerance_s) or tolerance_s <= 0.0:
        raise CassiniPredictionError("light-time tolerance must be positive")
    if maximum_iterations < 1:
        raise CassiniPredictionError("light-time iteration count must be positive")

    station = _validated_state(station_state(receive_et_tdb_s))
    transmit = receive_et_tdb_s
    for _ in range(maximum_iterations):
        spacecraft = _validated_state(spacecraft_state(transmit))
        next_transmit = receive_et_tdb_s - _distance(
            spacecraft.position_m,
            station.position_m,
        ) / SPEED_OF_LIGHT_M_S
        if abs(next_transmit - transmit) <= tolerance_s:
            transmit = next_transmit
            break
        transmit = next_transmit
    else:
        raise CassiniPredictionError("one-way light-time solution did not converge")

    spacecraft = _validated_state(spacecraft_state(transmit))
    propagation = _unit_direction(spacecraft.position_m, station.position_m)
    distance = _distance(spacecraft.position_m, station.position_m)
    factor = _frequency_factor(
        spacecraft.velocity_m_s,
        station.velocity_m_s,
        propagation,
    )
    return OneWayEvent(
        receive_et_tdb_s=receive_et_tdb_s,
        transmit_et_tdb_s=transmit,
        geometric_light_time_s=receive_et_tdb_s - transmit,
        geometric_range_m=distance,
        kinematic_frequency_factor=factor,
    )


def compile_dss26_one_way(
    receive_utc: str,
    carrier: USOCarrierModel,
    kernel_paths: Mapping[str, Path],
    *,
    correction_terms: tuple[FrequencyCorrectionTerm, ...] | None = None,
    spice: SpiceApi | None = None,
) -> OneWayPrediction:
    """Compile one DSS-26 event without reading any RSR header or sample."""

    carrier.validate()
    api = spice if spice is not None else _import_spiceypy()
    terms = correction_terms if correction_terms is not None else initial_open_terms()
    _validate_correction_ledger(terms)
    with _loaded_frozen_kernels(api, kernel_paths) as lineage:
        receive_et = float(api.utc2et(receive_utc))
        reference_et = float(api.utc2et(carrier.calibration_reference_utc))
        event = solve_one_way_event(
            receive_et,
            _spice_state_provider(api, DEVELOPMENT_STATION),
            _spice_state_provider(api, SPACECRAFT),
        )
        emitted, uso_terms = _emitted_frequency(carrier, event.transmit_et_tdb_s, reference_et)
        all_terms = (*terms, *uso_terms)
        kinematic = emitted * event.kinematic_frequency_factor
        # USO offset/aging terms are already applied in the emitter rest frame
        # before the kinematic factor.  Only propagation/receive corrections
        # are additive here; counting the USO terms again would be causal
        # double application.
        central = sum(
            float(term.central_correction_hz)
            for term in terms
            if term.central_correction_hz is not None
        )
        bound = sum(
            float(term.absolute_bound_hz)
            for term in all_terms
            if term.absolute_bound_hz is not None
        )
        open_names = tuple(term.name for term in all_terms if term.status == "OPEN_TERM")
        prediction = OneWayPrediction(
            compiler_version=COMPILER_VERSION,
            development_lidvid=DEVELOPMENT_LIDVID,
            receive_utc=receive_utc,
            receive_et_tdb_s=receive_et,
            transmit_utc=api.et2utc(event.transmit_et_tdb_s, "ISOC", 6) + "Z",
            transmit_et_tdb_s=event.transmit_et_tdb_s,
            station=DEVELOPMENT_STATION,
            spacecraft=SPACECRAFT,
            geometric_light_time_s=event.geometric_light_time_s,
            geometric_range_m=event.geometric_range_m,
            nominal_rest_frequency_hz=carrier.nominal_rest_frequency_hz,
            emitted_frequency_hz=emitted,
            kinematic_frequency_factor=event.kinematic_frequency_factor,
            kinematic_received_frequency_hz=kinematic,
            declared_correction_hz=central,
            declared_correction_bound_hz=bound,
            received_sky_frequency_hz=kinematic + central,
            steering_only_received_sky_frequency_hz=emitted + central,
            orbital_minus_steering_only_hz=kinematic - emitted,
            correction_terms=all_terms,
            kernel_lineage=lineage,
            transform_ledger=(
                "RSR receive UTC --SpiceyPy/CSPICE LSK--> ET/TDB",
                "DSS-26 station SPK + historical Earth EOP --CSPICE--> J2000 SSB state",
                "receive ET/TDB --iterated geometric one-way light time--> transmit ET/TDB",
                "pre-pass PREDICT type-1 Cassini SPK --CSPICE--> transmit state",
                "transmit/receive states --exact SR kinematic factor--> received carrier",
                "declared USO rest carrier and calibration nuisance --> emitted carrier",
                "declared corrections/bounds/open terms --> received sky-frequency scope",
                "unit kinematic factor + identical controls --> steering-only sky null",
            ),
            claim_scope=(
                "ONE_WAY_KINEMATIC_SCREEN_ONLY_OPEN_TERMS=" + ",".join(open_names)
                if open_names
                else (
                    "ONE_WAY_SKY_FREQUENCY_WITH_DECLARED_ENVELOPE_"
                    "AWAITING_CONCRETE_RSR_TRANSFORM"
                )
            ),
            sky_prediction_terms_closed=not open_names,
            # This compiler never sees a concrete header, NCO continuity,
            # detector manifest, or final detectability result.  Those are
            # separate necessary conditions and cannot be inferred here.
            primary_prediction_authorized=False,
        )
    strict_json(prediction.as_json_object())
    return prediction


def compiler_manifest() -> dict[str, object]:
    return {
        "compiler_version": COMPILER_VERSION,
        "scope": "CASSINI_DSS26_DEVELOPMENT_ONE_WAY_OFFLINE",
        "development_lidvid": DEVELOPMENT_LIDVID,
        "runtime": "SpiceyPy/CSPICE required; lazy import; no fallback",
        "kernels": [asdict(spec) for spec in CASSINI_DSS26_KERNELS],
        "state_query": {
            "frame": INERTIAL_FRAME,
            "observer": STATE_OBSERVER,
            "aberration_correction": "NONE",
            "reason": "light time and frequency transfer are solved explicitly",
        },
        "implemented_terms": [
            "UTC_TO_ET_TDB",
            "HISTORICAL_EOP_STATION_STATE",
            "GEOMETRIC_ONE_WAY_LIGHT_TIME",
            "SPECIAL_RELATIVISTIC_KINEMATIC_TRANSFER",
            "DECLARED_USO_CARRIER_NUISANCE",
        ],
        "initial_open_terms": list(_REQUIRED_PROPAGATION_TERMS) + [
            "USO_REST_FREQUENCY_CALIBRATION",
            "USO_AGING",
        ],
        "forbidden_inputs": [
            "Horizons trajectory",
            "Skyfield trajectory",
            "reconstructed Cassini SPK",
            "RSR sample values",
            "signal ridge",
            "primary or reserve product information",
        ],
        "primary_policy": (
            "always false here; closing sky terms is necessary but concrete RSR "
            "transform and detectability are still required"
        ),
    }


def compiler_manifest_sha256() -> str:
    return sha256(strict_json(compiler_manifest()).encode("utf-8")).hexdigest()


def strict_json(value: object) -> str:
    return json.dumps(value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _import_spiceypy() -> SpiceApi:
    try:
        return importlib.import_module("spiceypy")  # type: ignore[return-value]
    except ModuleNotFoundError as error:
        raise CassiniPredictionError(
            "SpiceyPy/CSPICE is required; no Horizons or Skyfield fallback is permitted"
        ) from error


@contextmanager
def _loaded_frozen_kernels(
    spice: SpiceApi,
    paths: Mapping[str, Path],
) -> Iterator[tuple[dict[str, object], ...]]:
    expected_names = {spec.name for spec in CASSINI_DSS26_KERNELS}
    if set(paths) != expected_names:
        raise CassiniPredictionError("kernel path set differs from the frozen DSS-26 set")
    lineage: list[dict[str, object]] = []
    for spec in CASSINI_DSS26_KERNELS:
        path = Path(paths[spec.name])
        if not path.is_file() or path.stat().st_size != spec.bytes:
            raise CassiniPredictionError(f"kernel identity failed: {spec.name}")
        digest = _file_sha256(path)
        if digest != spec.sha256:
            raise CassiniPredictionError(f"kernel SHA-256 failed: {spec.name}")
        lineage.append(
            {
                "name": spec.name,
                "bytes": spec.bytes,
                "sha256": digest,
                "role": spec.role,
                "independence": spec.independence,
            }
        )
    spice.kclear()
    try:
        for spec in CASSINI_DSS26_KERNELS:
            spice.furnsh(str(paths[spec.name]))
        yield tuple(lineage)
    finally:
        spice.kclear()


def _spice_state_provider(spice: SpiceApi, target: str):
    def state(epoch_et_tdb_s: float) -> StateVector:
        vector, _ = spice.spkezr(
            target,
            epoch_et_tdb_s,
            INERTIAL_FRAME,
            "NONE",
            STATE_OBSERVER,
        )
        values = tuple(float(value) for value in vector)
        if len(values) != 6:
            raise CassiniPredictionError("CSPICE state must contain six values")
        return StateVector(
            position_m=tuple(value * 1_000.0 for value in values[:3]),  # type: ignore[arg-type]
            velocity_m_s=tuple(value * 1_000.0 for value in values[3:]),  # type: ignore[arg-type]
        )

    return state


def _emitted_frequency(
    carrier: USOCarrierModel,
    transmit_et_tdb_s: float,
    reference_et_tdb_s: float,
) -> tuple[float, tuple[FrequencyCorrectionTerm, ...]]:
    emitted = carrier.nominal_rest_frequency_hz
    terms: list[FrequencyCorrectionTerm] = []
    if carrier.constant_offset_hz is None:
        terms.append(
            FrequencyCorrectionTerm(
                "USO_REST_FREQUENCY_CALIBRATION",
                "OPEN_TERM",
                None,
                None,
                "constant offset from the declared rest-frame carrier",
            )
        )
    else:
        emitted += carrier.constant_offset_hz
        terms.append(
            FrequencyCorrectionTerm(
                "USO_REST_FREQUENCY_CALIBRATION",
                "APPLIED",
                carrier.constant_offset_hz,
                None,
                "declared constant rest-carrier calibration nuisance",
            )
        )
    if carrier.aging_rate_hz_s is None:
        terms.append(
            FrequencyCorrectionTerm(
                "USO_AGING",
                "OPEN_TERM",
                None,
                None,
                "Cassini USO aging over the development interval",
            )
        )
    else:
        aging = carrier.aging_rate_hz_s * (transmit_et_tdb_s - reference_et_tdb_s)
        emitted += aging
        terms.append(
            FrequencyCorrectionTerm(
                "USO_AGING",
                "APPLIED",
                aging,
                None,
                "declared affine USO aging nuisance at transmit epoch",
            )
        )
    for term in terms:
        term.validate()
    return emitted, tuple(terms)


def _validate_correction_ledger(terms: tuple[FrequencyCorrectionTerm, ...]) -> None:
    names = tuple(term.name for term in terms)
    if len(names) != len(set(names)):
        raise CassiniPredictionError("correction ledger contains duplicate terms")
    if set(names) != set(_REQUIRED_PROPAGATION_TERMS):
        raise CassiniPredictionError("correction ledger omits or adds a frozen physical term")
    for term in terms:
        term.validate()


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _frequency_factor(
    transmitter_velocity_m_s: tuple[float, float, float],
    receiver_velocity_m_s: tuple[float, float, float],
    propagation_direction: tuple[float, float, float],
) -> float:
    transmitter_beta = tuple(value / SPEED_OF_LIGHT_M_S for value in transmitter_velocity_m_s)
    receiver_beta = tuple(value / SPEED_OF_LIGHT_M_S for value in receiver_velocity_m_s)
    transmitter_gamma = 1.0 / sqrt(1.0 - _dot(transmitter_beta, transmitter_beta))
    receiver_gamma = 1.0 / sqrt(1.0 - _dot(receiver_beta, receiver_beta))
    numerator = receiver_gamma * (1.0 - _dot(propagation_direction, receiver_beta))
    denominator = transmitter_gamma * (1.0 - _dot(propagation_direction, transmitter_beta))
    factor = numerator / denominator
    if not isfinite(factor) or factor <= 0.0:
        raise CassiniPredictionError("one-way kinematic frequency factor is invalid")
    return factor


def _validated_state(state: StateVector) -> StateVector:
    state.validate()
    return state


def _distance(
    left: tuple[float, float, float],
    right: tuple[float, float, float],
) -> float:
    return _norm(tuple(r - l for l, r in zip(left, right)))


def _unit_direction(
    origin: tuple[float, float, float],
    destination: tuple[float, float, float],
) -> tuple[float, float, float]:
    delta = tuple(d - o for o, d in zip(origin, destination))
    length = _norm(delta)
    if length <= 0.0:
        raise CassiniPredictionError("link endpoints must not be colocated")
    return tuple(value / length for value in delta)  # type: ignore[return-value]


def _dot(
    left: tuple[float, float, float],
    right: tuple[float, float, float],
) -> float:
    return sum(l * r for l, r in zip(left, right))


def _norm(vector: tuple[float, float, float]) -> float:
    return sqrt(_dot(vector, vector))
