"""Replay the v2 station selection with the existing real-target interval fit."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path

from . import vmf3_grid_model as meteo
from .real_phase import BASE, digest
from .real_target_interval import fit_case
from ..kinematic.synthetic import native


def run():
    access_bytes = (BASE/'real_target_phase_access_v2.json').read_bytes()
    access = json.loads(access_bytes)
    target_bytes = (BASE/'inputs/real_phase/g12_target_phase_v2.json').read_bytes()
    target = json.loads(target_bytes)
    phase_bytes = (BASE/'results/reference_phase_clock_gps_only_v2.json').read_bytes()
    phase = json.loads(phase_bytes)
    baseline_bytes = (BASE/'results/day_reference_v1.json').read_bytes()
    baseline = json.loads(baseline_bytes)
    reference_bytes = (BASE/'inputs/real_phase/observations_gps_only_v2.json').read_bytes()
    if (target['access_sha256'] != digest(access_bytes) or target['target_state_accessed']
            or phase['target_values_accessed'] or phase['input_sha256'] != digest(reference_bytes)
            or not baseline['calibration_complete'] or baseline['target_orbit_accessed']):
        raise ValueError('v2 input/access/calibration boundary differs')
    stations = tuple(access['stations'])
    if (len(stations) != 5 or len(set(stations)) != 5 or 'STJO00CAN' in stations
            or 'BOGT00COL' not in stations):
        raise ValueError('v2 station selection differs')
    positions = json.loads((BASE/'inputs/day_reference/positions.json').read_bytes())
    clock = {(r['station'], r['time_s']): r for r in phase['phase_clock_rates']}
    weather = meteo.WeatherGrid(meteo.read_inputs()[0])
    mjd_day = (datetime(2026, 9, 5)-datetime(1858, 11, 17)).days
    cases = []
    for i in range(20):
        start = 37800+90*i
        try:
            case = fit_case(target, baseline, clock, positions, start, weather, mjd_day, stations)
        except (ValueError, KeyError, IndexError) as error:
            case = {'status': 'CASE_FAILED', 'reason': str(error)}
        cases.append({'start_gpst_s': start, **case})
        print(i, cases[-1]['status'], flush=True)
    return native({'schema': 'exploratory-real-target-interval-v2',
        'claim': 'Actual G12 RF conditional interval fits on a post-exposure exploratory redesign; no physical position bound.',
        'target_orbit_accessed': False, 'physical_covariance_qualified': False,
        'historical_code_floor_m': 20.,
        'stations': stations, 'access_sha256': digest(access_bytes),
        'target_input_sha256': digest(target_bytes), 'reference_input_sha256': digest(reference_bytes),
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
