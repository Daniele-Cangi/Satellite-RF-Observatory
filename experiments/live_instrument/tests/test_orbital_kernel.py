"""Focused regression and invariant tests for the Gate B orbital kernel."""

from datetime import datetime, timedelta, timezone

import pytest

from experiments.live_instrument.orbital_kernel import (
    SPEED_OF_LIGHT_KM_S,
    Observer,
    OrbitalKernelError,
    TLEElements,
    compute_orbital_state,
)


ISS_TLE = TLEElements(
    name="ISS (ZARYA)",
    line1="1 25544U 98067A   19343.69339541  .00001764  00000-0  38792-4 0  9991",
    line2="2 25544  51.6439 211.2001 0007417  17.6667  85.6398 15.50103472202482",
)
ISS_OMM = {
    "OBJECT_NAME": "ISS (ZARYA)",
    "OBJECT_ID": "1998-067A",
    "EPOCH": "2019-12-09T16:38:29.363423",
    "MEAN_MOTION": 15.501034720000002,
    "ECCENTRICITY": 0.0007417,
    "INCLINATION": 51.6439,
    "RA_OF_ASC_NODE": 211.2001,
    "ARG_OF_PERICENTER": 17.6667,
    "MEAN_ANOMALY": 85.6398,
    "EPHEMERIS_TYPE": 0,
    "CLASSIFICATION_TYPE": "U",
    "NORAD_CAT_ID": 25544,
    "ELEMENT_SET_NO": 999,
    "REV_AT_EPOCH": 20248,
    "BSTAR": 3.8792e-05,
    "MEAN_MOTION_DOT": 1.764e-05,
    "MEAN_MOTION_DDOT": 0.0,
}
EPOCH = datetime(2019, 12, 9, 16, 38, 29, 363423, tzinfo=timezone.utc)
COPENHAGEN = Observer(latitude_deg=55.6761, longitude_deg=12.5683, altitude_m=20.0)


def test_known_iss_epoch_regression() -> None:
    """The published ISS element set produces a stable known-epoch snapshot."""

    state = compute_orbital_state(COPENHAGEN, ISS_TLE, EPOCH, carrier_hz=145_800_000.0)

    assert state.event_time == EPOCH
    assert state.position_gcrs_km == pytest.approx(
        (3467.75846, -2705.90341, 5169.20720), abs=0.00002
    )
    assert state.velocity_gcrs_km_s == pytest.approx(
        (5.8289313, 4.7763268, -1.3993070), abs=0.0000002
    )
    assert 0.0 <= state.azimuth_deg < 360.0
    assert -90.0 <= state.elevation_deg <= 90.0
    assert state.range_km > 0.0


def test_tle_and_equivalent_omm_json_agree() -> None:
    tle_state = compute_orbital_state(COPENHAGEN, ISS_TLE, EPOCH)
    omm_state = compute_orbital_state(COPENHAGEN, ISS_OMM, EPOCH)

    assert omm_state.position_gcrs_km == pytest.approx(tle_state.position_gcrs_km, abs=1e-5)
    assert omm_state.velocity_gcrs_km_s == pytest.approx(
        tle_state.velocity_gcrs_km_s, abs=1e-8
    )
    assert omm_state.range_km == pytest.approx(tle_state.range_km, abs=1e-5)
    assert omm_state.range_rate_km_s == pytest.approx(tle_state.range_rate_km_s, abs=1e-7)


def test_range_rate_matches_central_difference_and_doppler_convention() -> None:
    half_step = timedelta(milliseconds=50)
    before = compute_orbital_state(COPENHAGEN, ISS_TLE, EPOCH - half_step)
    state = compute_orbital_state(COPENHAGEN, ISS_TLE, EPOCH, carrier_hz=437_500_000.0)
    after = compute_orbital_state(COPENHAGEN, ISS_TLE, EPOCH + half_step)

    finite_difference_km_s = (after.range_km - before.range_km) / 0.1
    assert state.range_rate_km_s == pytest.approx(finite_difference_km_s, abs=1e-5)
    assert state.doppler_shift_hz == pytest.approx(
        -state.carrier_hz * state.range_rate_km_s / SPEED_OF_LIGHT_KM_S,
        abs=1e-12,
    )
    assert (state.doppler_shift_hz < 0.0) == (state.range_rate_km_s > 0.0)


def test_observer_changes_topocentric_not_geocentric_state() -> None:
    antipodal_observer = Observer(latitude_deg=-55.6761, longitude_deg=-167.4317)

    local = compute_orbital_state(COPENHAGEN, ISS_TLE, EPOCH)
    distant = compute_orbital_state(antipodal_observer, ISS_TLE, EPOCH)

    assert distant.position_gcrs_km == pytest.approx(local.position_gcrs_km, abs=1e-12)
    assert distant.velocity_gcrs_km_s == pytest.approx(local.velocity_gcrs_km_s, abs=1e-12)
    assert distant.range_km != pytest.approx(local.range_km, abs=1.0)
    assert distant.elevation_deg != pytest.approx(local.elevation_deg, abs=1.0)


def test_missing_carrier_is_unknown_not_zero_doppler() -> None:
    state = compute_orbital_state(COPENHAGEN, ISS_TLE, EPOCH)

    assert state.carrier_hz is None
    assert state.doppler_shift_hz is None


@pytest.mark.parametrize(
    ("observer", "event_time", "carrier_hz", "message"),
    [
        (Observer(91.0, 0.0), EPOCH, None, "latitude"),
        (COPENHAGEN, EPOCH.replace(tzinfo=None), None, "timezone-aware"),
        (COPENHAGEN, EPOCH, 0.0, "finite positive"),
    ],
)
def test_ambiguous_or_nonphysical_inputs_are_rejected(
    observer: Observer,
    event_time: datetime,
    carrier_hz: float | None,
    message: str,
) -> None:
    with pytest.raises(OrbitalKernelError, match=message):
        compute_orbital_state(observer, ISS_TLE, event_time, carrier_hz)


def test_incomplete_omm_is_rejected_before_propagation() -> None:
    with pytest.raises(OrbitalKernelError, match="OMM elements missing fields"):
        compute_orbital_state(COPENHAGEN, {"NORAD_CAT_ID": 25544}, EPOCH)
