"""Terrestrial marker/ARP and phase-PCO audit; no code correction or target fit."""
import argparse
from collections import Counter
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path

import numpy as np

from positioning.calibration import antenna_position, geodetic
from .reference_attitude_model import strict_json
from .reference_residual_structure_v2 import center_blocks, rms

BLOCKS = ('SITE/ID', 'SITE/ANTENNA', 'SITE/ECCENTRICITY',
          'SITE/GPS_PHASE_CENTER', 'SOLUTION/EPOCHS', 'SOLUTION/ESTIMATE')
HEADER_LABELS = ('MARKER NAME', 'MARKER NUMBER', 'ANT # / TYPE',
                 'ANTENNA: DELTA H/E/N', 'APPROX POSITION XYZ', 'REC # / TYPE / VERS')
ROOT = Path(__file__).resolve().parents[2]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def extract_header(lines):
    """Stop at END OF HEADER, including for CRINEX; never decode observations."""
    result = {}
    for line in lines:
        label = line[60:80].strip()
        if label in HEADER_LABELS:
            result.setdefault(label, []).append(line[:60])
        if label == 'END OF HEADER':
            return result
    raise ValueError('missing END OF HEADER')


def extract_sinex(lines, stations):
    """Text allowlist: no satellite parameters or normal-equation numbers parsed."""
    codes = {name[:4] for name in stations}
    if len(codes) != len(stations):
        raise ValueError('ambiguous station short codes')
    kept = {key: [] for key in BLOCKS}
    block, header, footer = None, None, False
    for line in lines:
        line = line.rstrip('\r\n')
        if line.startswith('%=SNX'):
            if header is not None:
                raise ValueError('duplicate SINEX header')
            header = line
        elif line.startswith('%ENDSNX'):
            footer = True
        elif line.startswith('+'):
            if block is not None:
                raise ValueError('nested SINEX block')
            block = line[1:].strip()
        elif line.startswith('-'):
            if block != line[1:].strip():
                raise ValueError('SINEX block mismatch')
            block = None
        elif line.startswith(' ') and block in kept:
            if block == 'SITE/GPS_PHASE_CENTER':
                kept[block].append(line)
            elif block == 'SOLUTION/ESTIMATE':
                if line[7:13].strip() in ('STAX', 'STAY', 'STAZ') and line[14:18] in codes:
                    kept[block].append(line)
            elif line[1:5] in codes:
                kept[block].append(line)
    if header is None or not footer or block is not None:
        raise ValueError('incomplete SINEX')
    types = {line[42:62] for line in kept['SITE/ANTENNA']}
    kept['SITE/GPS_PHASE_CENTER'] = [s for s in kept['SITE/GPS_PHASE_CENTER'] if s[1:21] in types]
    result = [header, '* Restricted terrestrial extract; original parameter count is not an extract count.']
    for key in BLOCKS:
        result += ['+'+key, *kept[key], '-'+key]
    return '\n'.join([*result, '%ENDSNX', ''])


def parse_blocks(text):
    result, block = {}, None
    lines = text.splitlines()
    if not lines or not lines[0].startswith('%=SNX 2.01 COD ') or lines[-1] != '%ENDSNX':
        raise ValueError('expected complete CODE SINEX 2.01 extract')
    for line in lines[1:-1]:
        if line.startswith('*'):
            continue
        if line.startswith('+'):
            if block is not None:
                raise ValueError('nested extract block')
            block = line[1:]
            if block not in BLOCKS or block in result:
                raise ValueError('unexpected/duplicate terrestrial block')
            result[block] = []
        elif line.startswith('-'):
            if block != line[1:]:
                raise ValueError('block mismatch')
            block = None
        elif not line.startswith(' ') or block is None:
            raise ValueError('unexpected extract row')
        else:
            result[block].append(line)
    if block is not None or set(result) != set(BLOCKS):
        raise ValueError('incomplete extract')
    return result


def epoch(value):
    # This bounded reader rejects unknown/open epochs instead of inventing dates.
    yy, doy, seconds = map(int, value.split(':'))
    year = 2000+yy if yy < 80 else 1900+yy
    if not 1 <= doy <= (366 if year % 4 == 0 else 365) or not 0 <= seconds < 86400:
        raise ValueError('invalid SINEX epoch')
    return datetime(year, 1, 1)+timedelta(days=doy-1, seconds=seconds)


def numbers(text, count):
    values = np.array([float(s.replace('D', 'E')) for s in text.split()])
    if len(values) != count or not np.isfinite(values).all():
        raise ValueError('invalid finite numeric vector')
    return values


def basis(xyz):
    lat, lon, _, up = geodetic(xyz)
    east = np.array([-np.sin(lon), np.cos(lon), 0.])
    return np.array([east, np.cross(up, east), up])


def one(rows, description):
    if len(rows) != 1:
        raise ValueError('expected one '+description)
    return rows[0]


def header_value(header, key):
    return one(header[key], key)


def station_audit(name, header, blocks, day, times, admitted_arp):
    code = name[:4]
    marker_name = header_value(header, 'MARKER NAME').strip().upper()
    if marker_name not in (code, name):
        raise ValueError('marker identity mismatch')
    domes = header_value(header, 'MARKER NUMBER').strip()
    ident = one([s for s in blocks['SITE/ID'] if s[1:5] == code and s[9:18] == domes], 'DOMES-matched site')
    point = ident[6:8]
    start = datetime.fromisoformat(day)+timedelta(seconds=times[0])
    end = datetime.fromisoformat(day)+timedelta(seconds=times[-1])
    # The event lies strictly inside one solution day in either GPST or UTC.
    epochs = [s.split() for s in blocks['SOLUTION/EPOCHS'] if s[1:5] == code and s[6:8] == point]
    selected = one([v for v in epochs if epoch(v[4])+timedelta(seconds=18) < start and
                    end < epoch(v[5])-timedelta(seconds=18)], 'solution covering the whole window')
    sol = selected[2]
    def metadata(key):
        return one([s for s in blocks[key] if s[1:5] == code and s[6:8] == point and
                    s[9:13].strip() == sol and epoch(s[16:28]) <= start and end <= epoch(s[29:41])], key)
    antenna, eccentricity = metadata('SITE/ANTENNA'), metadata('SITE/ECCENTRICITY')
    rinex_antenna = header_value(header, 'ANT # / TYPE')[20:40]
    if antenna[42:62] != rinex_antenna:
        raise ValueError('antenna/radome mismatch')
    if eccentricity[42:45] != 'UNE':
        raise ValueError('this audit supports UNE eccentricity only')
    une = numbers(eccentricity[46:72], 3)
    hen = numbers(header_value(header, 'ANTENNA: DELTA H/E/N'), 3)
    marker = numbers(header_value(header, 'APPROX POSITION XYZ'), 3)
    arp = np.array(antenna_position(header))
    replay = float(np.linalg.norm(arp-np.array(admitted_arp)))
    if replay > 1e-7:
        raise ValueError('archived ARP differs from header reconstruction')
    coordinates, sigmas = [], []
    for axis in ('STAX', 'STAY', 'STAZ'):
        row = one([s.split() for s in blocks['SOLUTION/ESTIMATE'] if s[7:13].strip() == axis and
                   s[14:18] == code and s[19:21] == point and s[22:26].strip() == sol], axis)
        if row[5] != selected[6] or row[6] != 'm':
            raise ValueError('coordinate epoch/unit mismatch')
        value, sigma = numbers(' '.join(row[8:10]), 2)
        if sigma < 0:
            raise ValueError('negative formal sigma')
        coordinates.append(value)
        sigmas.append(sigma)
    sinex_marker = np.array(coordinates)
    sinex_arp = sinex_marker+basis(sinex_marker).T@une[[2, 1, 0]]
    pco = one([s for s in blocks['SITE/GPS_PHASE_CENTER'] if s[1:21] == rinex_antenna and
               s[22:27].strip() in (antenna[63:68].strip(), '-----')], 'phase-center model')
    offsets = numbers(pco[28:69], 6).reshape(2, 3)
    alpha = 1575.42**2/(1575.42**2-1227.60**2)
    phase_if = (alpha*offsets[0]+(1-alpha)*offsets[1])[[2, 1, 0]]
    delta = sinex_arp-arp
    return {'station': name, 'status': 'COMPARED', 'domes': domes, 'point': point.strip(), 'solution_id': sol,
            'solution_start': selected[4], 'solution_end': selected[5], 'coordinate_epoch': selected[6],
            'coordinate_epoch_minus_event_midpoint_s': (epoch(selected[6])-(start+(end-start)/2)).total_seconds(),
            'antenna_type_radome': rinex_antenna, 'rinex_serial': header_value(header, 'ANT # / TYPE')[:20].strip(),
            'sinex_serial': antenna[63:68].strip(), 'antenna_serial_independently_matched': False,
            'header_marker_ecef_m': marker.tolist(), 'sinex_marker_ecef_m': sinex_marker.tolist(),
            'marker_delta_norm_m': float(np.linalg.norm(sinex_marker-marker)),
            'header_eccentricity_enu_m': hen[[1, 2, 0]].tolist(), 'sinex_eccentricity_enu_m': une[[2, 1, 0]].tolist(),
            'eccentricity_difference_norm_m': float(np.linalg.norm(hen[[1, 2, 0]]-une[[2, 1, 0]])),
            'header_arp_ecef_m': arp.tolist(), 'sinex_arp_ecef_m': sinex_arp.tolist(),
            'arp_replay_norm_m': replay, 'arp_delta_enu_m': (basis(arp)@delta).tolist(),
            'arp_delta_norm_m': float(np.linalg.norm(delta)), 'sinex_formal_sigma_xyz_m': sigmas,
            'phase_pco_model': pco[70:80].strip(), 'phase_l1_pco_enu_m': offsets[0, [2, 1, 0]].tolist(),
            'phase_l2_pco_enu_m': offsets[1, [2, 1, 0]].tolist(), 'phase_if_pco_enu_m': phase_if.tolist(),
            'phase_if_pco_norm_m': float(np.linalg.norm(phase_if)), 'code_pco_qualified': False}


def validate_reference_report(report, admitted, day, times):
    names = admitted['fit_stations']
    context = admitted['context']
    expected_times = [context['start_s']+i*context['step_s'] for i in range(context['samples'])]
    if (report['schema'] != 'reference-residual-structure-v2' or report['date_gpst'] != day or
            day != context['date_gpst'] or report['target_excluded'] != context['target'] or times != expected_times or
            report['fit_stations'] != names or report['times_s'] != times or
            any(report.get(k) is not False for k in ('target_fit_performed', 'target_orbit_accessed',
                'new_confirmation', 'qualified_error_budget', 'applied_to_production_estimator'))):
        raise ValueError('reference report boundary differs')
    expected = {(name, obs['time_s'], sv) for name in names for obs in
                admitted['stations'][name]['reference_observations'] for sv in obs['if_code_m']}
    rows = report['reference_rows']+report['omitted_paths']
    keys = [(r['station'], r['time_s'], r['reference']) for r in rows]
    if len(keys) != len(set(keys)) or set(keys) != expected or report['observed_path_count'] != len(expected):
        raise ValueError('incomplete reference path accounting')
    if (report['evaluated_path_count'] != len(report['reference_rows']) or
            any(sv == context['target'] for _, _, sv in keys)):
        raise ValueError('invalid reference-only denominator')
    for row in report['reference_rows']:
        los = np.array(row['los_enu'])
        if los.shape != (3,) or not np.isfinite(los).all() or abs(np.linalg.norm(los)-1) > 1e-10:
            raise ValueError('invalid reference unit direction')
    for path, digest in report['sources_sha256'].items():
        source = (ROOT/path).resolve()
        if not source.is_relative_to(ROOT) or sha(source.read_bytes()) != digest:
            raise ValueError('reference source binding differs')


def run(directory, admitted_path, report_path):
    directory = Path(directory)
    payload = {name: (directory/name).read_bytes() for name in ('receipt.json', 'headers.json', 'station_sinex.txt')}
    receipt, headers = strict_json(payload['receipt.json']), strict_json(payload['headers.json'])
    for name in ('headers.json', 'station_sinex.txt'):
        if sha(payload[name]) != receipt['sha256'][name]:
            raise ValueError('station input hash mismatch')
    admitted_bytes, report_bytes = Path(admitted_path).read_bytes(), Path(report_path).read_bytes()
    admitted, report = strict_json(admitted_bytes), strict_json(report_bytes)
    if (receipt['schema'] != 'station-coordinate-receipt-v1' or headers['schema'] != 'station-header-extract-v1' or
            receipt['fit_stations'] != headers['fit_stations'] or receipt['fit_stations'] != admitted['fit_stations'] or
            receipt.get('satellite_parameters_parsed') is not False or headers.get('observation_numbers_parsed') is not False or
            report['input_sha256']['admitted.json'] != sha(admitted_bytes) or
            receipt['target_excluded'] != report['target_excluded']):
        raise ValueError('station input boundary differs')
    day, times = receipt['date_gpst'], report['times_s']
    validate_reference_report(report, admitted, day, times)
    blocks = parse_blocks(payload['station_sinex.txt'].decode('ascii'))
    stations = []
    for name in admitted['fit_stations']:
        try:
            result = station_audit(name, headers['headers'][name], blocks, day, times,
                                   admitted['stations'][name]['antenna_ecef_m'])
            rays = [r for r in report['reference_rows'] if r['station'] == name]
            # First-order *model range* change, not a corrected code residual.
            projection = np.array([-np.array(r['los_enu'])@result['arp_delta_enu_m'] for r in rays])
            centered = center_blocks(projection, rays)
            result.update(reference_ray_count=len(rays), range_change_rms_m=rms(projection),
                          centered_range_change_rms_m=rms(centered),
                          centered_range_change_max_abs_m=float(np.max(abs(centered))),
                          projections=[dict(time_s=r['time_s'], reference=r['reference'], range_change_m=float(v),
                                            centered_range_change_m=float(c)) for r, v, c in zip(rays, projection, centered, strict=True)])
        except (KeyError, ValueError) as error:
            result = {'station': name, 'status': 'NOT_COMPARABLE', 'reason': str(error)}
        stations.append(result)
    sources = report['sources_sha256'] | {'research/exploratory/station_coordinates.py': sha(Path(__file__).read_bytes())}
    return {'schema': 'station-coordinate-audit-v1', 'target_excluded': report['target_excluded'], 'date_gpst': day,
            'fit_stations': admitted['fit_stations'], 'station_count': len(stations),
            'status_counts': dict(Counter(s['status'] for s in stations)), 'stations': stations,
            'input_sha256': {name: sha(raw) for name, raw in payload.items()} |
                {'admitted.json': sha(admitted_bytes), 'reference_report': sha(report_bytes)}, 'sources_sha256': sources,
            'product_family': 'CODE final three-day SINEX, selected daily terrestrial solution; reference rays use CODE rapid',
            'frame_alignment': 'NOT_VERIFIED; antenna model name does not establish the terrestrial reference frame',
            'epoch_policy': 'Daily static solution at its reported epoch; no velocity, displacement/loading or tide correction applied',
            'phase_policy': 'L1/L2/IF phase PCO listed separately; no receiver code PCO/PCV or antenna orientation qualification',
            'projection_policy': 'First-order geometric response on frozen reference rays, centered per station/epoch; no recalibration',
            'formal_sigma_policy': 'Product formal component sigmas only; not coordinate accuracy or physical covariance',
            'target_fit_performed': False, 'target_orbit_accessed': False, 'new_confirmation': False,
            'qualified_error_budget': False, 'applied_to_production_estimator': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('directory', 'admitted', 'reference_report', 'output'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    result = run(args.directory, args.admitted, args.reference_report)
    with args.output.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write('\n')
