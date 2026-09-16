"""Station-coordinate audit with descriptive RINEX marker names supported.

V1 results and implementation remain frozen; DOMES/point/day checks are unchanged.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np

from . import station_coordinates as legacy
from .station_coordinates import (sha, strict_json, parse_blocks, validate_reference_report,
    header_value, center_blocks, rms, extract_sinex, extract_header, ROOT)


def station_audit(name, header, blocks, day, times, admitted_arp):
    marker_name = header_value(header, 'MARKER NAME').strip()
    normalized = dict(header)
    normalized['MARKER NAME'] = [marker_name.split()[0] if marker_name else '']
    result = legacy.station_audit(name, normalized, blocks, day, times, admitted_arp)
    result['rinex_marker_name'] = marker_name
    return result


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
    sources = report['sources_sha256'] | {'research/exploratory/station_coordinates.py': sha(Path(legacy.__file__).read_bytes()),
        'research/exploratory/station_coordinates_v2.py': sha(Path(__file__).read_bytes())}
    return {'schema': 'station-coordinate-audit-v2', 'target_excluded': report['target_excluded'], 'date_gpst': day,
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
