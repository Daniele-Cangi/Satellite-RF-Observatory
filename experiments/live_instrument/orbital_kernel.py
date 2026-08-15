"""Stateless orbital propagation for the Gate B experiment.

The public :func:`compute_orbital_state` function deliberately has no access to
the legacy configuration, database, Redis cache, network, or global observer.
Its result is therefore determined only by the four inputs supplied by the
caller: observer, orbital elements, event time, and optional carrier frequency.

Frame and sign conventions
--------------------------

``position_gcrs_km`` and ``velocity_gcrs_km_s`` are geocentric vectors in the
GCRS inertial frame returned by Skyfield.  Azimuth is degrees clockwise from
true north in ``[0, 360)``.  Elevation is geometric (no atmospheric
refraction).  ``range_rate_km_s`` is positive when geometric range is
increasing (the spacecraft is receding).  The optional one-way Doppler shift
uses the first-order convention ``-carrier * range_rate / c``; a receding
spacecraft therefore has a negative shift.

TLE and CelesTrak-style OMM/JSON element sets use SGP4/WGS-72.  Propagating far
outside an element set's epoch remains mathematically possible but does not
make the model physically trustworthy; freshness is an epistemic concern for
the caller rather than hidden policy in this physics kernel.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import isfinite, sqrt
from typing import Mapping, TypeAlias

from skyfield.api import EarthSatellite, load, wgs84


SPEED_OF_LIGHT_KM_S = 299_792.458


class OrbitalKernelError(ValueError):
    """Raised when inputs are invalid or SGP4 cannot produce a finite state."""


@dataclass(frozen=True, slots=True)
class Observer:
    """A WGS-84 observer location.

    ``latitude_deg`` must be in ``[-90, 90]``, ``longitude_deg`` in
    ``[-180, 180]``, and ``altitude_m`` is height above the WGS-84 ellipsoid.
    """

    latitude_deg: float
    longitude_deg: float
    altitude_m: float = 0.0


@dataclass(frozen=True, slots=True)
class TLEElements:
    """A two-line element set plus an optional human-readable object name."""

    line1: str
    line2: str
    name: str | None = None


OMMElements: TypeAlias = Mapping[str, object]
OrbitalElements: TypeAlias = TLEElements | OMMElements


@dataclass(frozen=True, slots=True)
class OrbitalState:
    """Geometric state of one spacecraft relative to one observer."""

    event_time: datetime
    position_gcrs_km: tuple[float, float, float]
    velocity_gcrs_km_s: tuple[float, float, float]
    azimuth_deg: float
    elevation_deg: float
    range_km: float
    range_rate_km_s: float
    carrier_hz: float | None
    doppler_shift_hz: float | None


def compute_orbital_state(
    observer: Observer,
    orbital_elements: OrbitalElements,
    event_time: datetime,
    carrier_hz: float | None = None,
) -> OrbitalState:
    """Propagate an element set and compute its observer-relative state.

    Args:
        observer: Arbitrary WGS-84 observer; no configured/default location is
            consulted.
        orbital_elements: Either :class:`TLEElements` or a mapping containing
            standard OMM field names, as returned by CelesTrak's OMM/JSON
            endpoint.  OMM numeric values may be strings or JSON numbers.
        event_time: A timezone-aware instant.  It is normalized to UTC in the
            returned state; naive datetimes are rejected to prevent a silent
            local-time interpretation.
        carrier_hz: Optional positive carrier frequency.  If omitted, Doppler
            is ``None`` rather than a fabricated zero.

    Returns:
        A new immutable :class:`OrbitalState`.

    Raises:
        OrbitalKernelError: For malformed inputs, an SGP4 propagation error, or
            a non-finite result.
    """

    _validate_observer(observer)
    event_time_utc = _normalize_event_time(event_time)
    carrier = _validate_carrier(carrier_hz)

    # Built-in timescale tables avoid both network access and mutable on-disk
    # cache state.  Keeping this local makes the kernel stateless and explicit.
    timescale = load.timescale(builtin=True)
    satellite = _build_satellite(orbital_elements, timescale)
    time = timescale.from_datetime(event_time_utc)
    observer_site = wgs84.latlon(
        observer.latitude_deg,
        observer.longitude_deg,
        elevation_m=observer.altitude_m,
    )

    try:
        geocentric = satellite.at(time)
        propagation_message = getattr(geocentric, "message", None)
        if propagation_message:
            raise OrbitalKernelError(f"SGP4 propagation failed: {propagation_message}")

        topocentric = (satellite - observer_site).at(time)
        elevation, azimuth, distance = topocentric.altaz()
        relative_position = tuple(float(value) for value in topocentric.position.km)
        relative_velocity = tuple(float(value) for value in topocentric.velocity.km_per_s)
        range_km = float(distance.km)
        range_rate_km_s = _radial_velocity(relative_position, relative_velocity)
        position = tuple(float(value) for value in geocentric.position.km)
        velocity = tuple(float(value) for value in geocentric.velocity.km_per_s)
    except OrbitalKernelError:
        raise
    except Exception as exc:
        raise OrbitalKernelError(f"orbital propagation failed: {exc}") from exc

    numeric_values = (
        *position,
        *velocity,
        float(azimuth.degrees),
        float(elevation.degrees),
        range_km,
        range_rate_km_s,
    )
    if not all(isfinite(value) for value in numeric_values):
        raise OrbitalKernelError("orbital propagation returned a non-finite state")

    doppler_shift_hz = (
        None
        if carrier is None
        else -(carrier * range_rate_km_s / SPEED_OF_LIGHT_KM_S)
    )
    return OrbitalState(
        event_time=event_time_utc,
        position_gcrs_km=position,
        velocity_gcrs_km_s=velocity,
        azimuth_deg=float(azimuth.degrees) % 360.0,
        elevation_deg=float(elevation.degrees),
        range_km=range_km,
        range_rate_km_s=range_rate_km_s,
        carrier_hz=carrier,
        doppler_shift_hz=doppler_shift_hz,
    )


def _build_satellite(orbital_elements: OrbitalElements, timescale) -> EarthSatellite:
    if isinstance(orbital_elements, TLEElements):
        if not orbital_elements.line1.strip() or not orbital_elements.line2.strip():
            raise OrbitalKernelError("both TLE lines must be non-empty")
        try:
            return EarthSatellite(
                orbital_elements.line1,
                orbital_elements.line2,
                orbital_elements.name,
                timescale,
            )
        except Exception as exc:
            raise OrbitalKernelError(f"invalid TLE elements: {exc}") from exc

    if not isinstance(orbital_elements, Mapping):
        raise OrbitalKernelError("orbital_elements must be TLEElements or an OMM mapping")

    required_omm_fields = {
        "OBJECT_ID",
        "EPOCH",
        "MEAN_MOTION",
        "ECCENTRICITY",
        "INCLINATION",
        "RA_OF_ASC_NODE",
        "ARG_OF_PERICENTER",
        "MEAN_ANOMALY",
        "EPHEMERIS_TYPE",
        "CLASSIFICATION_TYPE",
        "NORAD_CAT_ID",
        "ELEMENT_SET_NO",
        "REV_AT_EPOCH",
        "BSTAR",
        "MEAN_MOTION_DOT",
        "MEAN_MOTION_DDOT",
    }
    missing = sorted(required_omm_fields.difference(orbital_elements))
    if missing:
        raise OrbitalKernelError(f"OMM elements missing fields: {', '.join(missing)}")

    try:
        return EarthSatellite.from_omm(timescale, dict(orbital_elements))
    except Exception as exc:
        raise OrbitalKernelError(f"invalid OMM elements: {exc}") from exc


def _validate_observer(observer: Observer) -> None:
    if not isinstance(observer, Observer):
        raise OrbitalKernelError("observer must be an Observer")
    values = (observer.latitude_deg, observer.longitude_deg, observer.altitude_m)
    if not all(isfinite(value) for value in values):
        raise OrbitalKernelError("observer coordinates must be finite")
    if not -90.0 <= observer.latitude_deg <= 90.0:
        raise OrbitalKernelError("observer latitude must be in [-90, 90] degrees")
    if not -180.0 <= observer.longitude_deg <= 180.0:
        raise OrbitalKernelError("observer longitude must be in [-180, 180] degrees")


def _normalize_event_time(event_time: datetime) -> datetime:
    if not isinstance(event_time, datetime):
        raise OrbitalKernelError("event_time must be a datetime")
    if event_time.tzinfo is None or event_time.utcoffset() is None:
        raise OrbitalKernelError("event_time must be timezone-aware")
    return event_time.astimezone(timezone.utc)


def _validate_carrier(carrier_hz: float | None) -> float | None:
    if carrier_hz is None:
        return None
    try:
        carrier = float(carrier_hz)
    except (TypeError, ValueError) as exc:
        raise OrbitalKernelError("carrier_hz must be a finite positive number") from exc
    if not isfinite(carrier) or carrier <= 0.0:
        raise OrbitalKernelError("carrier_hz must be a finite positive number")
    return carrier


def _radial_velocity(
    relative_position_km: tuple[float, float, float],
    relative_velocity_km_s: tuple[float, float, float],
) -> float:
    range_km = sqrt(sum(component * component for component in relative_position_km))
    if range_km == 0.0:
        raise OrbitalKernelError("observer and satellite have zero geometric separation")
    return sum(
        position * velocity
        for position, velocity in zip(relative_position_km, relative_velocity_km_s)
    ) / range_km
