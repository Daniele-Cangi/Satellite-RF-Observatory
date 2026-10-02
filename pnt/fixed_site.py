"""One local recording plus external observations -> bounded offline diagnostics."""

from collections import Counter, defaultdict
from datetime import date
import hashlib
import math
from pathlib import Path

import hatanaka
import numpy as np

from positioning.calibration import ALPHA, BETA, antenna_position, reference_model
from research.exploratory.pnt_fixed_site_intake import station_header
from research.exploratory.pnt_observation_pairing import reference_codes
from .model import broadcast_navigation, day_context, fit_clock, nearest_record


MIN_SATELLITES = 4
MIN_ELEVATION_DEG = 10


def read_station(path, day, *, position=None, position_source=None):
    data = Path(path).read_bytes()
    content = hatanaka.decompress(data, strict=True).decode('ascii')
    identity = station_header(content)
    codes, counts = reference_codes(content, day)
    if position is None:
        header = defaultdict(list)
        for line in content.splitlines():
            header[line[60:80].strip()].append(line[:60])
            if line[60:80].strip() == 'END OF HEADER':
                break
        if any(len(header[key]) != 1 for key in ('APPROX POSITION XYZ', 'ANTENNA: DELTA H/E/N')):
            raise ValueError('one approximate XYZ and antenna H/E/N declaration required')
        approximate = identity['declared_approx_xyz_m']
        delta = [float(value) for value in header['ANTENNA: DELTA H/E/N'][0].split()]
        if (approximate is None or not 6e6 < np.linalg.norm(approximate) < 7e6 or
                len(delta) != 3 or not np.isfinite(delta).all()):
            raise ValueError('invalid terrestrial coordinate or antenna H/E/N')
        position = antenna_position(header)
        position_source = 'RINEX approximate XYZ + antenna H/E/N; not independently surveyed'
    else:
        if not isinstance(position_source, str) or not position_source.strip():
            raise ValueError('explicit antenna coordinate requires its source')
    position = np.asarray(position, dtype=float)
    if position.shape != (3,) or not np.isfinite(position).all() or not 6e6 < np.linalg.norm(position) < 7e6:
        raise ValueError('expected finite terrestrial antenna ECEF coordinate')
    return codes, position, {'file': Path(path).name,
                            'sha256': hashlib.sha256(data).hexdigest(), **identity,
                            'antenna_ecef_m': position.tolist(), 'position_source': position_source,
                            'code_status': counts}


def ionosphere_free(codes):
    return {sv: ALPHA * first + BETA * second for sv, (first, second) in codes.items()}


def evaluate_epoch(time_s, observations, positions, navigation, context):
    """Keep local coverage, matched comparisons and individual remote fits explicit."""
    admitted, excluded, records = {}, {}, {}
    for receiver, codes in observations.items():
        admitted[receiver], excluded[receiver] = {}, {}
        for sv, code in sorted(ionosphere_free(codes).items()):
            try:
                record = nearest_record(navigation, sv, time_s, context)
                _, elevation = reference_model(record, code, time_s, positions[receiver], 0.0, context)
                if not math.isfinite(elevation) or elevation < MIN_ELEVATION_DEG:
                    raise ValueError('BELOW_ELEVATION_MASK')
            except ValueError as error:
                excluded[receiver][sv] = str(error)
                continue
            admitted[receiver][sv] = code
            records[sv] = record

    def fit(receiver, satellites):
        if len(satellites) < MIN_SATELLITES:
            return {'status': 'INSUFFICIENT_EVIDENCE', 'satellites': sorted(satellites),
                    'reason': 'fewer than four admitted satellites'}
        try:
            values = {sv: admitted[receiver][sv] for sv in sorted(satellites)}
            model_records = {sv: records[sv] for sv in values}
            result = fit_clock(values, positions[receiver], model_records, time_s, context)
        except ValueError as error:
            return {'status': 'MODEL_FAILED', 'satellites': sorted(satellites), 'reason': str(error)}
        return {'status': 'EVALUATED', 'satellites': sorted(satellites), **result}

    standalone = {name: fit(name, set(codes)) for name, codes in admitted.items()}
    common = set.intersection(*(set(codes) for codes in admitted.values()))
    matched = {name: fit(name, common) for name in admitted}
    joint = {'status': 'INSUFFICIENT_EVIDENCE', 'satellites': sorted(common),
             'receiver_fits': matched}
    if len(common) >= MIN_SATELLITES:
        if all(result['status'] == 'EVALUATED' for result in matched.values()):
            reference_sv = min(common)
            local = matched['local']
            remote = {name: result for name, result in matched.items() if name != 'local'}
            differences = {}
            for name, result in remote.items():
                differences[name] = {
                    sv: (local['satellite_residuals_m'][sv] - local['satellite_residuals_m'][reference_sv]
                         - result['satellite_residuals_m'][sv] + result['satellite_residuals_m'][reference_sv])
                    for sv in sorted(common) if sv != reference_sv}
            # Reference clocks are GNSS-derived. Keeping each station and its
            # pairwise disagreement prevents cancellation in the mean hiding it.
            names = sorted(remote)
            disagreement = {
                first + '/' + second: {
                    'clock_difference_m': remote[first]['clock_m'] - remote[second]['clock_m'],
                    'max_absolute_satellite_difference_m': max(
                        abs(differences[first][sv] - differences[second][sv])
                        for sv in differences[first])}
                for index, first in enumerate(names) for second in names[index + 1:]}
            network_clock = float(np.mean([result['clock_m'] for result in remote.values()]))
            joint.update(status='EVALUATED', difference_reference_satellite=reference_sv,
                         model_double_difference_residuals_m=differences,
                         mean_double_difference_residuals_m={
                             sv: float(np.mean([values[sv] for values in differences.values()]))
                             for sv in sorted(common) if sv != reference_sv},
                         network_clock_m=network_clock,
                         local_minus_network_clock_m=local['clock_m'] - network_clock,
                         reference_disagreement=disagreement)
        else:
            joint['status'] = 'MODEL_FAILED'
    return {'gpst_s': time_s, 'source_code_satellites': {name: sorted(codes) for name, codes in observations.items()},
            'excluded_satellites': excluded, 'standalone_receiver_fits': standalone, 'matched': joint}


def validate_window(start_s, stop_s):
    if (not all(isinstance(value, int) and not isinstance(value, bool) for value in (start_s, stop_s))
            or not 0 <= start_s < stop_s <= 86400 or start_s % 30 or stop_s % 30):
        raise ValueError('window must be increasing 30-second GPST grid boundaries within one day')


def load_inputs(local_path, references, navigation_path, day_gpst, *,
                local_ecef=None, position_source=None):
    """Read/hash each original source once for analysis or a development comparison."""
    if (not isinstance(references, dict) or len(references) < 2 or
            any(not isinstance(name, str) or not name.strip() or name in ('local', 'navigation')
                for name in references)):
        raise ValueError('at least two named external receivers required; local/navigation are reserved')
    if local_ecef is None and position_source is not None:
        raise ValueError('coordinate source requires explicit local ECEF')
    day = date.fromisoformat(day_gpst)
    context = day_context(day)
    data, positions, sources = {}, {}, {}
    data['local'], positions['local'], sources['local'] = read_station(
        local_path, day, position=local_ecef, position_source=position_source)
    for name, path in sorted(references.items()):
        data[name], positions[name], sources[name] = read_station(path, day)
    markers = [item['marker_name'].strip().upper() for item in sources.values()]
    hashes = [item['sha256'] for item in sources.values()]
    if len(set(markers)) != len(markers) or len(set(hashes)) != len(hashes):
        raise ValueError('local and reference files must represent distinct receivers')
    nav_data = Path(navigation_path).read_bytes()
    nav, nav_counts = broadcast_navigation(nav_data)
    sources['navigation'] = {'file': Path(navigation_path).name,
                             'sha256': hashlib.sha256(nav_data).hexdigest(), 'record_status': nav_counts}
    return data, positions, nav, context, sources


def observation_epochs(data, start_s, stop_s):
    """Yield every requested grid epoch, including empty receiver observations."""
    by_epoch = {name: defaultdict(dict) for name in data}
    for name, rows in data.items():
        for (time_s, satellite), codes in rows.items():
            if start_s <= time_s < stop_s:
                by_epoch[name][time_s][satellite] = codes
    for time_s in range(start_s, stop_s, 30):
        yield time_s, {name: rows.get(time_s, {}) for name, rows in by_epoch.items()}


def analyze(local_path, references, navigation_path, day_gpst, *, start_s=0, stop_s=86400,
            local_ecef=None, position_source=None):
    validate_window(start_s, stop_s)
    data, positions, nav, context, sources = load_inputs(
        local_path, references, navigation_path, day_gpst,
        local_ecef=local_ecef, position_source=position_source)
    epochs = [evaluate_epoch(time_s, values, positions, nav, context)
              for time_s, values in observation_epochs(data, start_s, stop_s)]
    matched_counts = dict(sorted(Counter(epoch['matched']['status'] for epoch in epochs).items()))
    standalone_counts = {name: dict(sorted(Counter(epoch['standalone_receiver_fits'][name]['status']
                                                 for epoch in epochs).items())) for name in data}
    return {'schema': 'pnt-fixed-site-diagnostics-v1', 'day_gpst': context.day.date().isoformat(),
            'window_gpst_s': [start_s, stop_s], 'sources': sources,
            'status': 'DIAGNOSTICS_AVAILABLE' if matched_counts.get('EVALUATED', 0) else 'INSUFFICIENT_EVIDENCE',
            'coverage': {'expected_epochs': len(epochs), 'matched_status_counts': matched_counts,
                         'standalone_status_counts': standalone_counts},
            'model': {'observables': 'GPS ionosphere-free C1C/C2W',
                      'orbit': 'declared broadcast orbit/clock; nearest healthy toc within 7200 s; '
                               'absolute toe age within min(7200 s, half declared fit duration)',
                      'propagation': 'existing emission/reception, Earth rotation and simple troposphere model',
                      'clock': 'fixed-coordinate median code-minus-model; six iterations',
                      'minimum_satellites': MIN_SATELLITES, 'elevation_mask_deg': MIN_ELEVATION_DEG,
                      'epoch_grid_tolerance_s': 0.001,
                      'network': 'separate remote numerical fits, then arithmetic mean; common selection depends on all receivers'},
            'assessments': {'model_consistency': 'NOT_ASSESSED', 'network_detection_gain': 'NOT_ASSESSED',
                            'absolute_time': {'status': 'INSUFFICIENT_EVIDENCE',
                                              'reason': 'no independent clock witness supplied'}},
            'limits': [
                'Diagnostic residuals have no qualified uncertainty budget or detector threshold.',
                'Declared coordinates, inter-receiver code biases, propagation errors and source dependencies remain unqualified.',
                'Receiver GPST is not independent acquisition time; double differences cancel common clock offsets.',
                'Distinct markers/files do not prove independent clocks or providers; no RF authentication or attack attribution.',
                'Standalone fits can use different satellites; compare methods only through the identical matched set.',
            ], 'epochs': epochs}
