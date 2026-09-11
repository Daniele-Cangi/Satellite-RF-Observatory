"""Predeclared station availability using field presence and terrestrial headers."""
from copy import deepcopy
from decimal import Decimal
from itertools import combinations
import math

from .qualification import select_window


def eligible_epochs(structure):
    return {Decimal(e['seconds_gpst']) for e in structure.get('epochs', []) if e['eligible']}


def ground_position(structure):
    try:
        values = list(map(float, structure['header']['APPROX POSITION XYZ'][0].split()))
        offsets = list(map(float, structure['header']['ANTENNA: DELTA H/E/N'][0].split()))
        if len(values) != 3 or not all(math.isfinite(v) for v in values):
            return None
        if len(offsets) != 3 or not all(math.isfinite(v) for v in offsets):
            return None
        if not 6_000_000 <= math.sqrt(sum(v*v for v in values)) <= 6_500_000:
            return None
        return values
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def aperture(positions):
    latitude = [math.degrees(math.atan2(p[2], math.hypot(p[0], p[1]))) for p in positions]
    baseline = max(math.dist(a, b) for a, b in combinations(positions, 2))
    return {'maximum_baseline_m': baseline, 'geocentric_latitude_span_deg': max(latitude)-min(latitude)}


def select_network(plan, structures):
    """Earliest qualifying window, then lexical seven-root subset; no target values."""
    if 'network' not in plan:
        selected = select_window(structures, plan['selection']['support_epochs'], plan['selection']['step_s'])
        selected['fit_stations'] = list(plan['fit_stations']) if selected['selected_seconds_gpst'] else None
        return selected
    policy = plan['network']
    names = policy['candidate_stations']
    withheld = plan['withheld_station']
    if set(structures) != set(names + [withheld]):
        raise ValueError('availability inventory differs from declared network')
    times = {n: eligible_epochs(structures[n]) for n in names + [withheld]}
    positions = {n: ground_position(structures[n]) for n in names}
    samples, step = plan['selection']['support_epochs'], plan['selection']['step_s']
    result = {'status': 'NO_COMMON_STRUCTURAL_WINDOW', 'selected_seconds_gpst': None,
              'fit_stations': None, 'withheld_station': withheld,
              'maximum_simultaneous_candidates_examined': 0, 'windows_with_seven_candidates': 0,
              'windows_rejected_by_ground_aperture': 0}
    if ground_position(structures[withheld]) is None:
        result['status'] = 'WITHHELD_STATION_UNAVAILABLE'
        return result
    for start in sorted(times[withheld]):
        window = {start + i*step for i in range(samples)}
        simultaneous = sum(start in times[n] for n in names)
        result['maximum_simultaneous_candidates_examined'] = max(result['maximum_simultaneous_candidates_examined'], simultaneous)
        if not window <= times[withheld]:
            continue
        candidates = [n for n in sorted(names) if positions[n] is not None and window <= times[n]]
        if len(candidates) < 7:
            continue
        result['windows_with_seven_candidates'] += 1
        for subset in combinations(candidates, 7):
            geometry = aperture([positions[n] for n in subset])
            if (geometry['maximum_baseline_m'] < policy['minimum_baseline_m'] or
                    geometry['geocentric_latitude_span_deg'] < policy['minimum_latitude_span_deg']):
                continue
            result.update(status='STRUCTURAL_NETWORK_AVAILABLE',
                          selected_seconds_gpst=[str(start+i*step) for i in range(samples)],
                          fit_stations=list(subset), ground_aperture=geometry)
            return result
        result['windows_rejected_by_ground_aperture'] += 1
    if result['windows_with_seven_candidates']:
        result['status'] = 'GROUND_APERTURE_NOT_QUALIFIED'
    return result


def effective_plan(plan, structure):
    """Resolve receiver roles again from the original frozen declaration."""
    if 'network' not in plan:
        return plan
    expected = select_network(plan, structure['structures'])
    if expected != structure['selection'] or expected['fit_stations'] is None:
        raise ValueError('selected network does not match the frozen rule')
    result = deepcopy(plan)
    result['fit_stations'] = expected['fit_stations']
    return result


def availability_report(plan, structure):
    selection = structure['selection']
    stations = []
    for name, info in sorted(structure['structures'].items()):
        times = sorted(eligible_epochs(info))
        longest = length = 0
        previous = None
        for time in times:
            length = length+1 if previous is not None and time-previous == plan['selection']['step_s'] else 1
            longest = max(longest, length)
            previous = time
        stations.append({'station': name, 'role': 'withheld' if name == plan['withheld_station'] else 'candidate',
                         'source_status': info.get('source_status', 'OBSERVATIONS_SCANNED'),
                         'source_reason': info.get('source_reason'), 'eligible_epochs': len(times),
                         'longest_consecutive_epochs': longest,
                         'ground_header_usable': ground_position(info) is not None})
    return {'schema': 'satellite-rf-availability-v1', 'target': plan['target'],
            'date_gpst': plan['date_gpst'], 'status': selection['status'],
            'ready_for_calibration': selection['selected_seconds_gpst'] is not None,
            'selected_fit_stations': selection.get('fit_stations'),
            'withheld_station': plan['withheld_station'],
            'selected_seconds_gpst': selection['selected_seconds_gpst'],
            'stations': stations,
            'scope': 'Field presence and terrestrial distribution only. Calibration, emitted-event alignment, identifiability, uncertainty and confirmation are not yet assessed.'}
