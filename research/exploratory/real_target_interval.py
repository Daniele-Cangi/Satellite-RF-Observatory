"""Exploratory G12 real-RF interval fits under real_target_phase_access.json.

All target geometry comes from the RF code-only fit. This conditional adapter
does not establish an absolute error budget or new prospective confirmation.
"""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy.linalg import block_diag

from positioning.calibration import C, OMEGA, geodetic, rotate_z, troposphere
from . import vmf3_grid_model as meteo
from .real_phase import BASE, digest
from .real_target_phase import STATIONS
from ..kinematic.interval_fit import fit_intervals, interval_output
from ..kinematic.phase_rates import interval_matrix
from ..kinematic.receiver_time import predict
from ..kinematic.synthetic import native

TAGS = np.array([-60., -30., 0.])
CALIBRATION = 'CONDITIONAL_CLOCK_MODEL_ACCEPTED'


class TargetBelowMask(ValueError):
    def __init__(self, station, elevation):
        super().__init__(f'target below 10 degree elevation at {station}: {elevation:.3f} deg')
        self.station = station
        self.elevation = float(elevation)


def covariance(station_count):
    """Fixed, conditional weighting from the earlier interval transfer."""
    n, endpoints = station_count, len(TAGS)*station_count
    difference = interval_matrix(TAGS, n)
    raw = block_diag(400*np.eye(endpoints), .02**2*np.eye(endpoints),
                     np.kron(np.eye(n), np.diag([4., .01**2])), .25*np.eye(3*n))
    transform = block_diag(np.eye(endpoints), difference, np.eye(5*n))
    whole = transform@raw@transform.T
    indices = np.r_[np.arange(endpoints), np.arange(endpoints+len(difference), len(whole))]
    return whole, whole[np.ix_(indices, indices)]


def propagation(fit, tags, stations, station_names, times, weather, mjd_day):
    """VMF3 paths at RF-fitted target geometry; no target state product."""
    prediction = predict(fit['state'], tags, stations, fit['receiver_clocks'])
    delays = np.empty((len(tags), len(stations)))
    elevations = np.empty_like(delays)
    for i, tag in enumerate(tags):
        for j, station in enumerate(stations):
            transmit = prediction['transmit_s'][i, j]
            state = fit['state']
            satellite = state[:3]+transmit*state[3:6]+.5*transmit**2*state[6:9]
            rotated = rotate_z(satellite, -OMEGA*prediction['light_time_s'][i, j])
            _, elevation = troposphere(station, rotated)
            if elevation < 10.:
                raise TargetBelowMask(station_names[j], elevation)
            lat, lon, height, _ = geodetic(station)
            clock = fit['receiver_clocks'][j, 0]+tag*fit['receiver_clocks'][j, 1]
            mjd = mjd_day+(times[i]-clock/C-18.)/86400.
            mh, mw, dry, wet = weather.evaluate(mjd, math.degrees(lat), math.degrees(lon),
                                                 float(height), elevation)
            delays[i, j] = dry*mh+wet*mw
            elevations[i, j] = elevation
    return delays, elevations


def short_fit(fit):
    return {'status': fit['status'], 'state': fit['state'],
            'receiver_clocks': fit['receiver_clocks'], 'rank': fit['rank'],
            'scaled_condition': fit['scaled_condition'],
            'weighted_residual_cost': fit['weighted_residual_cost'],
            'conditional_residual_p': fit['conditional_residual_p'],
            'branch_failures': fit['branch_failures'],
            'branch_ambiguity': fit['branch_ambiguity'],
            'found_branches': fit['found_branches'],
            'fit_covariance_sha256': fit['fit_covariance_sha256']}


def fit_case(target, baseline, clocks, positions, start, weather, mjd_day, stations=STATIONS):
    times = [start, start+30, start+60, start+90]
    selected = {}
    for station in stations:
        if target['stations'][station]['status'] != 'PARSED':
            return {'status': 'UNSUPPORTED_STATION', 'station': station}
        rows = {r['time_s']: r for r in target['stations'][station]['rows']}
        for t in times:
            row = rows.get(t)
            if row is None or row['status'] != 'AVAILABLE':
                return {'status': 'INCOMPLETE_TARGET_WINDOW', 'station': station,
                        'time_s': t, 'reason': 'MISSING' if row is None else row['reasons']}
        selected[station] = [rows[t] for t in times]
    for station in stations:
        if baseline['calibrations'][station]['status'] != 'CALIBRATION_QUALIFIED':
            return {'status': 'REFERENCE_CODE_CALIBRATION_REJECTED', 'station': station}
        for t in times[1:3]:
            if clocks[station, t]['estimators']['median']['status'] != 'ESTIMATED':
                return {'status': 'REFERENCE_PHASE_CALIBRATION_REJECTED',
                        'station': station, 'time_s': t}
    station_xyz = np.array([positions[s][(start+60-36000)//30] for s in stations])
    code = np.array([[selected[s][i]['code_m'] for s in stations] for i in range(3)])
    phase = np.array([[selected[s][i]['phase_m'] for s in stations] for i in range(4)])
    rates = np.diff(phase[:3], axis=0)/30.
    clock_mean = np.array([[next(e['clock_m'] for e in baseline['calibrations'][s]['epochs']
                                if e['time_s'] == start+60),
                            np.mean([clocks[s, t]['estimators']['median']['rate_m_s']
                                     for t in times[1:3]])] for s in stations])
    whole_cov, code_cov = covariance(len(stations))
    provisional = fit_intervals(TAGS, station_xyz, code, rates, clock_mean, code_cov,
                                calibration_statuses=[CALIBRATION]*len(stations), include_phase=False)
    result = {'status': 'PROVISIONAL_CODE_ONLY', 'start_gpst_s': start,
              'provisional_code_fit': short_fit(provisional)}
    if provisional['status'] != 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED':
        result['status'] = 'PROVISIONAL_CODE_FIT_REJECTED'
        return result
    try:
        delays, elevations = propagation(provisional, TAGS, station_xyz, stations,
                                         times[:3], weather, mjd_day)
    except TargetBelowMask as error:
        result.update(status='TARGET_BELOW_ELEVATION_MASK', station=error.station,
                      elevation_deg=error.elevation)
        return result
    code_corrected = code-delays
    rates_corrected = rates-np.diff(delays, axis=0)/30.
    result['propagation_m'] = delays
    result['elevation_deg'] = elevations
    result['clock_prior'] = clock_mean
    result['fits'] = {}
    for name, use_phase, cov in (('code_only', False, code_cov),
                                 ('code_phase', True, whole_cov)):
        try:
            fitted = fit_intervals(TAGS, station_xyz, code_corrected, rates_corrected,
                                   clock_mean, cov, calibration_statuses=[CALIBRATION]*len(stations),
                                   include_phase=use_phase)
            compact = short_fit(fitted)
            if fitted['status'] == 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED':
                # A fitted state is frozen here, before withheld target RF is scored.
                predicted = []
                for j, station in enumerate(stations):
                    pair = interval_output(fitted['state'], 0., 30., station_xyz[j],
                                           fitted['receiver_clocks'][j])
                    predicted.append({'station': station, 'vacuum_code_m': float(pair[6]),
                                      'vacuum_phase_rate_m_s': float(pair[7])})
                compact['frozen_withheld_prediction'] = predicted
                compact['frozen_prediction_sha256'] = digest(json.dumps(native(predicted),
                                        separators=(',', ':')).encode())
                # Withheld propagation uses the same frozen RF state and clock.
                future_delays, future_elevations = propagation(fitted, np.array([0., 30.]),
                    station_xyz, stations, times[2:], weather, mjd_day)
                compact['withheld'] = []
                for j, station in enumerate(stations):
                    if future_elevations[1, j] < 10.:
                        raise ValueError('held-out elevation below mask')
                    observed = selected[station][3]
                    code_prediction = predicted[j]['vacuum_code_m']+future_delays[1, j]
                    rate_prediction = (predicted[j]['vacuum_phase_rate_m_s']
                                       +(future_delays[1, j]-future_delays[0, j])/30.)
                    phase_rate = (observed['phase_m']-selected[station][2]['phase_m'])/30.
                    compact['withheld'].append({'station': station,
                        'code_residual_m': observed['code_m']-code_prediction,
                        'phase_rate_residual_m_s': phase_rate-rate_prediction,
                        'elevation_deg': future_elevations[1, j]})
            result['fits'][name] = compact
        except ValueError as error:
            result['fits'][name] = {'status': 'FIT_OR_PREDICTION_FAILED', 'reason': str(error)}
    result['status'] = 'EVALUATED'
    return result


def run():
    target_bytes = (BASE/'inputs/real_phase/g12_target_phase.json').read_bytes()
    target = json.loads(target_bytes)
    access_bytes = (BASE/'real_target_phase_access.json').read_bytes()
    if target['access_sha256'] != digest(access_bytes) or target['target_state_accessed']:
        raise ValueError('target extract not bound to access record')
    baseline_bytes = (BASE/'results/day_reference_v1.json').read_bytes()
    baseline = json.loads(baseline_bytes)
    phase_bytes = (BASE/'results/reference_phase_clock_v1.json').read_bytes()
    phase = json.loads(phase_bytes)
    if phase['target_values_accessed'] or not baseline['calibration_complete'] or baseline['target_orbit_accessed']:
        raise ValueError('reference calibration boundary rejected')
    clock = {(r['station'], r['time_s']): r for r in phase['phase_clock_rates']}
    positions = json.loads((BASE/'inputs/day_reference/positions.json').read_bytes())
    weather = meteo.WeatherGrid(meteo.read_inputs()[0])
    mjd_day = (datetime(2026, 9, 5)-datetime(1858, 11, 17)).days
    cases = []
    for i in range(20):
        start = 37800+90*i
        try:
            case = fit_case(target, baseline, clock, positions, start, weather, mjd_day)
        except (ValueError, KeyError, IndexError) as error:
            case = {'status': 'CASE_FAILED', 'reason': str(error)}
        cases.append({'start_gpst_s': start, **case})
        print(i, cases[-1]['status'], flush=True)
    return native({'schema': 'exploratory-real-target-interval-v1',
        'claim': 'Actual G12 RF conditional interval fit, not prospective or physically qualified.',
        'target_orbit_accessed': False, 'physical_covariance_qualified': False,
        'historical_code_floor_m': 20.,
        'weight_scenario': {'code_sigma_m': 20., 'phase_endpoint_sigma_m': .02,
                            'reference_clock_offset_sigma_m': 2.,
                            'reference_clock_rate_sigma_m_s': .01,
                            'station_xyz_sigma_m': .5},
        'access_sha256': digest(access_bytes), 'target_input_sha256': digest(target_bytes),
        'baseline_sha256': digest(baseline_bytes), 'phase_clock_sha256': digest(phase_bytes),
        'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'status_counts': dict(Counter(c['status'] for c in cases)), 'cases': cases})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, separators=(',', ':'), allow_nan=False)+'\n',
                           encoding='utf-8', newline='\n')
