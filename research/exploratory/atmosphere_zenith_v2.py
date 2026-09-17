"""Meteorological zenith model sensitivity, not VMF3 slant delay or RF replay."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from positioning.calibration import geodetic
from research.exploratory.erp_polar_bound import pinned, strict_json

BASE = Path(__file__).parent
RECEIPT_SHA = '5604eb9482a1a2a9e51e10f65d9c09fe8b83233dcc62d69f399ed73e5dda3689'
STATIONS = ('ALGO', 'BOGT', 'DRAO', 'MKEA', 'PIE1', 'STJO', 'YELL', 'BRAZ', 'AREQ')
ELEVATIONS = (10, 15, 30, 60, 90)


def parse_coordinates(raw):
    result = {}
    for line in raw.decode('ascii').splitlines():
        f = line.split()
        if not f:
            continue
        if len(f) < 4 or f[0] in result:
            raise ValueError('invalid or duplicate coordinate row')
        lat, lon, height = map(float, f[1:4])
        if not all(map(math.isfinite, (lat, lon, height))) or not -90 <= lat <= 90 or not -180 <= lon <= 180 or not -500 <= height <= 9000:
            raise ValueError('invalid coordinates')
        result[f[0]] = (lat, lon, height)
    return result


def parse_weather(raw, mjd):
    result = {}
    for line in raw.decode('ascii').splitlines():
        f = line.split()
        if not f:
            continue
        if len(f) != 9:
            raise ValueError('expected nine VMF3 columns')
        values = tuple(map(float, f[1:]))
        if not all(map(math.isfinite, values)):
            raise ValueError('nonfinite meteorology')
        epoch, ah, aw, zhd, zwd, pressure, temperature, vapor = values
        key = (f[0], epoch)
        if epoch not in [mjd + i / 4 for i in range(4)] or key in result:
            raise ValueError('unexpected or duplicate UTC epoch')
        # Mapping coefficients are finite but unused; do not impose a positivity rule.
        if not (0 < zhd < 4 and 0 <= zwd < 2 and 0 < pressure < 1200 and -100 < temperature < 100 and 0 <= vapor < 150):
            raise ValueError('invalid meteorological value')
        result[key] = (zhd, zwd)
    return result


def simple_zenith(height):
    if not math.isfinite(height) or not -500 <= height <= 9000:
        raise ValueError('invalid height')
    return 2.3 * math.exp(-.000116 * height), .1


def mapping(elevation):
    if not math.isfinite(elevation) or not 10 <= elevation <= 90:
        raise ValueError('elevation outside diagnostic domain')
    return 1.001 / math.sqrt(.002001 + math.sin(math.radians(elevation)) ** 2)


def run():
    receipt_path = BASE / 'inputs/atmosphere/receipt.json'
    receipt = strict_json(pinned(receipt_path, RECEIPT_SHA))
    hashes = {'inputs/atmosphere/receipt.json': RECEIPT_SHA}
    inputs = {}
    for name, source in receipt['sources'].items():
        path = 'inputs/atmosphere/' + name
        inputs[name] = pinned(BASE / path, source['sha256'])
        if len(inputs[name]) != source['bytes']:
            raise ValueError('source length differs')
        hashes[path] = source['sha256']
    local = {}
    for name, digest in receipt['local_sha256'].items():
        local[name] = pinned(BASE / name, digest)
        hashes[name] = digest
    coordinates = parse_coordinates(inputs['gnss.ell'])
    rows = []
    alignment = []
    for tag, day, mjd in [('g14', 246, 61286), ('g12', 248, 61288)]:
        weather = parse_weather(inputs[f'2026{day}.vmf3_g'], mjd)
        frame = strict_json(local[f'results/{tag}_station_frame_epoch_v1.json'])
        for model in frame['station_models']:
            root = model['station'][:4]
            if root not in coordinates:
                alignment.append({'event': tag, 'station': root, 'status': 'missing_coordinates'})
                continue
            lat, lon, height, _ = geodetic(model['positions']['final_transport'][0])
            plat, plon, ph = coordinates[root]
            alignment.append({'event': tag, 'station': root, 'status': 'coordinate_comparison_only',
                              'admitted_domes': model['domes'], 'provider_domes_identity_qualified': False,
                              'latitude_difference_deg': plat - math.degrees(lat),
                              'longitude_difference_deg': (plon - math.degrees(lon) + 180) % 360 - 180,
                              'provider_minus_admitted_height_m': ph - float(height)})
        for station in STATIONS:
            for hour in (0, 6, 12, 18):
                row = {'event': tag, 'station': station, 'mjd_utc': mjd + hour / 24, 'hour_utc': hour}
                value = weather.get((station, row['mjd_utc']))
                if station not in coordinates or value is None:
                    row['status'] = 'missing_coordinates' if station not in coordinates else 'missing_weather'
                else:
                    height = coordinates[station][2]
                    dry, wet = simple_zenith(height)
                    zhd, zwd = value
                    delta = zhd + zwd - dry - wet
                    row.update(status='compared_at_provider_height', provider_height_m=height,
                               zhd_m=zhd, zwd_m=zwd, simple_zhd_m=dry, simple_zwd_m=wet,
                               dry_difference_m=zhd-dry, wet_difference_m=zwd-wet,
                               zenith_difference_m=delta,
                               common_mapping_difference_m={str(e): delta * mapping(e) for e in ELEVATIONS})
                rows.append(row)
    return {'schema': 'atmosphere-zenith-sensitivity-v2',
            'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'input_sha256': hashes, 'fixed_station_roots': list(STATIONS),
            'expected_rows': 72, 'rows': rows, 'coordinate_alignment': alignment,
            'status_counts': {s: sum(r['status'] == s for r in rows) for s in sorted({r['status'] for r in rows})},
            'scope': 'Four UTC weather epochs per day, 00-18h; common legacy mapping sensitivity only. No interpolation, height transport, VMF3 mapping or RF fit.',
            'physical_error_bound': False, 'target_orbit_accessed': False,
            'new_confirmation': False, 'applied_to_production_estimator': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    report = run()
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + '\n')
