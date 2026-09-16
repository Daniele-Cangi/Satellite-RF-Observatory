"""Pinned, strict single-read verification of the two preserved exploratory audits.

Lower-level v1/v2 runners are frozen execution history. This is the active replay
boundary for the G14/G12 reports, not an importer for new scientific events.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np

from positioning.calibration import C, OMEGA, geodetic, rotate_z, parse_reference_navigation
from positioning.context import Context
from .reference_attitude import load_attitude
from .reference_attitude_model import AttitudeReference, guarded_products, strict_json
from .reference_code_bias import translate_observations
from .reference_residual_structure_v2 import MODELS, predict_block, describe, center_blocks, rms
from . import station_coordinates_v2 as station_model

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'research/exploratory'
INPUTS = BASE/'inputs'


def paths(tag):
    archive = ROOT/'experiments/positioning_g14_doy246_network' if tag == 'g14' else INPUTS/'g12_doy248'
    return {'admission_receipt': archive/'admission_receipt.json', 'admitted': archive/'estimation/admitted.json',
            'navigation': archive/'estimation/reference_only.rnx',
            'attitude_report': BASE/f'results/{tag}_reference_attitude_v1.json',
            'reference_report': BASE/f'results/{tag}_reference_residual_structure_v2.json',
            'station_report': BASE/f'results/{tag}_station_coordinates_v2.json',
            'station_receipt': INPUTS/f'station_coordinates/{tag}/receipt.json',
            'station_headers': INPUTS/f'station_coordinates/{tag}/headers.json',
            'station_sinex': INPUTS/f'station_coordinates/{tag}/station_sinex.txt'}


PINS = {'g14': {'admission_receipt': '18fa1a0a3fa5b87dbfb0c982b424c80a57a0b88d7df77926123b642de6258e45',
         'admitted': '043bf564eb38f69644fadd0ceff06cf7a63256ab828d97c38a04880a133b36a4',
         'navigation': '835bd418584f4a1d9aeaae2d2a65acde734906dd45c5c27ab3e8a2ba920837ba',
         'attitude_report': '5da66d272cb6dbaeaff8d513dfefc344f32588d764639c668805febd1fa9c096',
         'reference_report': '0ed708d96f506c996ebfe860acc83becfd8f82937666a740283c2257936bf9b6',
         'station_report': '2a145d52c8df1ea55fb2625f5b5c970f0c47a07155b0d41aae636dd43e44b9d2',
         'station_receipt': 'bcd92ac4e6e25c9709005e521682429ae4ae096fd327cbf62440e3375dc8a10d',
         'station_headers': '2d66a1a4c68e103cb2fd4fb5f5cddad5be890a1078cd41988d16647bf772817e',
         'station_sinex': 'e5541712120dbd1584122e47bd0cebb48604714bc14a0e5013737e0a1453863a'},
 'g12': {'admission_receipt': '1dce5c5f97cd9e6c6f450bdb1256a872bd0d600022052439d08c18717180f7bf',
         'admitted': '788fa50d4653ff13bcc842b2c9069cffc9423a7f8246a9a168c041bcd8d2e559',
         'navigation': '7419827eb29ff118f4b62e616887181cb027098aaefcc954abc6378a622b0ebd',
         'attitude_report': 'f373ef8869219ff04d8d66053d23611adc88ea91211d00eab9cf359e5e80f6a3',
         'reference_report': '5c5817f3dbe50643ef30ded2eace8a88a8e6290605c613d2a6e4e6b9c98d0af9',
         'station_report': '0b0952eb866f38fbdeb173b9fe2b33c4d5a8401d96ea80ab89999448d7ba3036',
         'station_receipt': '30439fe8934caab26e88661cbe9716a23a53bfa86128249aaa5f2d0e9c4093b7',
         'station_headers': '2ed20118620eb094ca1e037fcb1793e40910e5b1dc14be548f05e1c85dc71fe4',
         'station_sinex': 'ba6e8820710a2f955a209a9ac503ac6388503322f76e0531e2ca594305eb4572'}}


def pinned_bytes(path, expected):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('pinned input differs: '+Path(path).name)
    return raw


def load_inputs(archive):
    archive = Path(archive)
    receipt_raw = (archive/'admission_receipt.json').read_bytes()
    admitted_raw = (archive/'estimation/admitted.json').read_bytes()
    # Strictly parse the same bytes that will be hashed, before Context/numerics.
    receipt, admitted = strict_json(receipt_raw), strict_json(admitted_raw)
    tag = admitted['context']['target'].lower()
    expected = PINS[tag]
    if (hashlib.sha256(receipt_raw).hexdigest() != expected['admission_receipt'] or
            hashlib.sha256(admitted_raw).hexdigest() != expected['admitted']):
        raise ValueError('archive is not the pinned exposed event')
    nav_raw = pinned_bytes(archive/'estimation/reference_only.rnx', expected['navigation'])
    hashes = {'admitted.json': hashlib.sha256(admitted_raw).hexdigest(),
              'reference_only.rnx': hashlib.sha256(nav_raw).hexdigest()}
    if receipt['admitted_sha256'] != hashes['admitted.json'] or receipt['navigation_sha256'] != hashes['reference_only.rnx']:
        raise ValueError('archive receipt binding differs')
    context = Context(**admitted['context'])
    for station in admitted['stations'].values():
        if any(context.target in obs['if_code_m'] for obs in station['reference_observations']):
            raise ValueError('target contamination in reference data')
    return admitted, context, parse_reference_navigation(nav_raw.decode('ascii'), context.target), hashes


def prepare(archive, timed, biases, antennas, attitudes, prior_report):
    admitted, context, _, hashes = load_inputs(archive)
    names = admitted['fit_stations']
    refs = sorted({sv for name in names for obs in admitted['stations'][name]['reference_observations'] for sv in obs['if_code_m']})
    precise, corrections, products = guarded_products(context, refs, timed, biases, antennas)
    attitude, attitudes_hashes = load_attitude(attitudes, context, refs)
    provider = AttitudeReference(precise, attitude)
    prior_bytes = pinned_bytes(prior_report, PINS[context.target.lower()]['attitude_report'])
    prior = strict_json(prior_bytes)
    root = Path(__file__).resolve().parents[2]
    if (prior['schema'] != 'reference-attitude-v1' or prior['target'] != context.target or
            prior.get('date_gpst') != context.date_gpst or
            any(prior.get(k) is not False for k in ('target_orbit_accessed', 'target_attitude_parsed',
                'new_confirmation', 'qualified_error_budget', 'applied_to_production_estimator')) or
            prior['fit_stations'] != names or prior['references'] != refs or
            prior['input_sha256'] != hashes | products | attitudes_hashes):
        raise ValueError('prior report/input binding differs')
    for path, digest in prior['sources_sha256'].items():
        source = (root/path).resolve()
        if not source.is_relative_to(root) or hashlib.sha256(source.read_bytes()).hexdigest() != digest:
            raise ValueError('prior source binding differs')
    primary = [case for case in prior['cases'] if case['mode'] == 'full_pco_30s_attitude']
    if len(primary) != 1 or primary[0]['status'] != 'ESTIMATED':
        raise ValueError('one completed full-attitude calibration required')
    rows, omitted, max_replay = [], [], 0.
    for name in names:
        station = np.array(admitted['stations'][name]['antenna_ecef_m'])
        lat, lon, _, up = geodetic(station)
        east = np.array([-np.sin(lon), np.cos(lon), 0.])
        north = np.cross(up, east)
        basis = np.array([east, north, up])
        cal = primary[0]['calibration'][name]
        if cal['status'] != 'CALIBRATION_QUALIFIED' or [e['time_s'] for e in cal['epochs']] != list(context.times):
            raise ValueError('incomplete prior calibration')
        observations = translate_observations(admitted['stations'][name]['reference_observations'], corrections, context.target)
        if len(observations) != len(cal['epochs']):
            raise ValueError('observation/calibration lengths differ')
        for obs, epoch in zip(observations, cal['epochs'], strict=True):
            if obs['time_s'] != epoch['time_s'] or len(set(epoch['references'])) != len(epoch['references']) or len(epoch['references']) < 4:
                raise ValueError('invalid reference epoch')
            block, raw = [], []
            for sv, code in sorted(obs['if_code_m'].items()):
                row = {'station': name, 'time_s': obs['time_s'], 'reference': sv}
                if sv not in epoch['references']:
                    omitted.append(dict(row, status='NOT_IN_BROADCAST_REFERENCE_SET'))
                    continue
                clock = epoch['clock_m']
                predicted, elevation = provider.model(sv, code, obs['time_s'], station, clock)
                _, _, antenna, offset = provider.antenna_state(sv, code, obs['time_s'])
                ray = rotate_z(antenna, -OMEGA*(-clock/C-offset))-station
                los = ray/np.linalg.norm(ray)
                row.update(los_enu=(basis@los).tolist(), elevation_deg=elevation)
                raw.append(code-predicted)
                block.append(row)
            if len(block) != len(epoch['references']):
                raise ValueError('missing prior reference observation')
            residual = np.asarray(raw)-np.mean(raw)
            if len(epoch['references']) != len(epoch['residuals_m']):
                raise ValueError('reference/residual lengths differ')
            previous = dict(zip(epoch['references'], epoch['residuals_m'], strict=True))
            for row, value in zip(block, residual):
                max_replay = max(max_replay, abs(value-previous[row['reference']]))
                row['residual_m'] = float(value)
                rows.append(row)
    if max_replay > 1e-6:
        raise ValueError('reference residual replay differs')
    inputs = hashes | products | attitudes_hashes | {'prior_attitude_report': hashlib.sha256(prior_bytes).hexdigest()}
    return rows, omitted, context, names, refs, inputs, prior['sources_sha256'], max_replay


def recompute_reference(archive, timed, biases, antennas, attitudes, prior_report):
    rows, omitted, context, names, refs, inputs, prior_sources, replay = prepare(archive, timed, biases, antennas, attitudes, prior_report)
    times = list(context.times)
    if len(times) != 11:
        raise ValueError('this exploratory comparison requires eleven epochs')
    folds = [('forward', times[:5], times[5:]), ('reverse_control', times[-5:], times[:-5])]
    cases = []
    for fold, train_times, test_times in folds:
        training = [r for r in rows if r['time_s'] in train_times]
        testing = [r for r in rows if r['time_s'] in test_times]
        for model in MODELS:
            row = {'fold': fold, 'model': model, 'training_times_s': train_times, 'test_times_s': test_times}
            try:
                row.update(status='EVALUATED', **predict_block(training, testing, model))
            except Exception as error:
                row.update(status='ENGINEERING_FAILURE', reason=type(error).__name__+': '+str(error))
            cases.append(row)
    root = Path(__file__).resolve().parents[2]
    source = Path(__file__)
    sources = prior_sources | {source.relative_to(root).as_posix(): hashlib.sha256(source.read_bytes()).hexdigest()}
    return {'schema': 'reference-residual-structure-verified', 'target_excluded': context.target, 'date_gpst': context.date_gpst,
            'fit_stations': names, 'references': refs, 'times_s': times, 'input_sha256': inputs, 'sources_sha256': sources,
            'scope': 'Exploratory reference-contrast predictability over two halves of an exposed five-minute window.',
            'method': {'projection': 'Per station/epoch P = I - 11.T/n removes the fitted common clock coordinate.',
                'models': 'zero; common satellite constants; station ENU-direction coefficients; station/satellite constants',
                'fitting': 'Unweighted least squares of projected residuals and features; SVD rcond 1e-12; no target values',
                'testing': 'First five epochs to last six, then last five to first six; coefficients fit on training only',
                'interpretation': 'Coefficients are descriptive, not antenna calibration. Test residuals are clock-free contrasts, not absolute predictions.',
                'correlations': 'Pair means and sample/lag correlations use the whole window descriptively; no population inference.',
                'limitations': ['short window and limited direction change', 'clock-centering induces dependence',
                    'antenna, site coordinates, multipath and media are not causally separated',
                    'common reference modes and target/reference coupling remain unidentified']},
            'target_fit_performed': False, 'target_orbit_accessed': False, 'new_confirmation': False,
            'qualified_error_budget': False, 'applied_to_production_estimator': False,
            'reference_residual_replay_max_abs_m': replay,
            'observed_path_count': len(rows)+len(omitted), 'evaluated_path_count': len(rows),
            'omitted_paths': omitted, 'reference_rows': rows, 'descriptive': describe(rows, names, refs),
            'case_count': len(cases), 'status_counts': dict(Counter(c['status'] for c in cases)), 'cases': cases}


def compare_tree(actual, expected, key=None):
    """Complete numeric replay, with only dimensionless correlation tolerance wider."""
    if isinstance(expected, dict):
        if actual.keys() != expected.keys():
            raise ValueError('replay object keys differ')
        for name in expected:
            compare_tree(actual[name], expected[name], name)
    elif isinstance(expected, list):
        if len(actual) != len(expected):
            raise ValueError('replay list lengths differ')
        for a, b in zip(actual, expected, strict=True):
            compare_tree(a, b, key)
    elif isinstance(expected, float):
        tolerance = 1e-7 if key == 'pearson' else 1e-8
        if not np.isfinite(actual) or abs(actual-expected) > max(tolerance, 1e-10*abs(expected)):
            raise ValueError('numeric replay differs: '+str(key))
    elif actual != expected:
        raise ValueError('replay value differs: '+str(key))


def verify(tag):
    inputs = paths(tag)
    raw = {key: pinned_bytes(path, PINS[tag][key]) for key, path in inputs.items()}
    data = {key: strict_json(value) for key, value in raw.items() if inputs[key].suffix == '.json'}
    saved, admitted = data['reference_report'], data['admitted']
    actual = recompute_reference(inputs['admission_receipt'].parent,
        INPUTS/f'timed_reference_products/{tag}', INPUTS/f'reference_biases/{tag}',
        INPUTS/f'reference_antennas/{tag}', INPUTS/f'reference_attitudes/{tag}', inputs['attitude_report'])
    excluded = {'schema', 'sources_sha256'}
    compare_tree({k: v for k, v in actual.items() if k not in excluded},
                 {k: v for k, v in saved.items() if k not in excluded})
    station_model.validate_reference_report(saved, admitted, saved['date_gpst'], saved['times_s'])
    blocks = station_model.parse_blocks(raw['station_sinex'].decode('ascii'))
    stations = []
    for name in admitted['fit_stations']:
        result = station_model.station_audit(name, data['station_headers']['headers'][name], blocks,
            saved['date_gpst'], saved['times_s'], admitted['stations'][name]['antenna_ecef_m'])
        rays = [r for r in saved['reference_rows'] if r['station'] == name]
        projection = np.array([-np.array(r['los_enu'])@result['arp_delta_enu_m'] for r in rays])
        centered = center_blocks(projection, rays)
        result.update(reference_ray_count=len(rays), range_change_rms_m=rms(projection),
                      centered_range_change_rms_m=rms(centered),
                      centered_range_change_max_abs_m=float(np.max(abs(centered))),
                      projections=[dict(time_s=r['time_s'], reference=r['reference'], range_change_m=float(v),
                                        centered_range_change_m=float(c)) for r, v, c in zip(rays, projection, centered, strict=True)])
        stations.append(result)
    compare_tree(stations, data['station_report']['stations'])
    # This manifest comes from an exact pinned report, not a caller-supplied subset.
    sources = data['station_report']['sources_sha256']
    for path, digest in sources.items():
        source = (ROOT/path).resolve()
        if not source.is_relative_to(ROOT) or hashlib.sha256(source.read_bytes()).hexdigest() != digest:
            raise ValueError('pinned source differs')
    sources = sources | {'research/exploratory/verified_station_replay.py': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    return {'schema': 'verified-station-replay-v1', 'status': 'ALL_PINNED_RESULTS_REPRODUCED',
            'target_excluded': saved['target_excluded'], 'date_gpst': saved['date_gpst'],
            'input_sha256': {key: hashlib.sha256(value).hexdigest() for key, value in raw.items()},
            'sources_sha256': sources, 'reference_case_count': actual['case_count'],
            'reference_path_count': actual['evaluated_path_count'], 'station_count': len(stations),
            'target_fit_performed': False, 'target_orbit_accessed': False, 'new_confirmation': False,
            'qualified_error_budget': False, 'applied_to_production_estimator': False,
            'scope': 'Integrity repair and complete replay of pinned exposed evidence; no new physical result'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tag', choices=sorted(PINS))
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = verify(args.tag)
    with args.output.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write('\n')

