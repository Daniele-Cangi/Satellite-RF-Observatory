"""CODE satellite C1C -> C1W translation on exposed reference observations.

An isolated bias-only development trial, not full precise-product calibration.
"""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import numpy as np

from positioning.calibration import ALPHA, BETA, C, calibrate_station
from positioning.errors import ScientificRejection
from .reference_conventions import antenna_offsets
from .reference_sensitivity import load_inputs, fit_variant

SIGNALS = ('C1C', 'C1W', 'C2W')
MARKER = '* REFERENCE-ONLY EXTRACT; source header count is not the extract count'


def selected_line(line, references):
    return (line[1:5].strip() == 'OSB' and line[11:14] in references
            and not line[15:24].strip() and line[25:29].strip() in SIGNALS
            and not line[30:34].strip())


def extract_bias(text, references, target):
    """Select by text identity before numeric conversion, including target bias."""
    if target in references:
        raise ValueError('target in reference allowlist')
    lines = text.splitlines()
    if not lines or not lines[0].startswith('%=BIA 1.00 ') or lines[-1].strip() != '%=ENDBIA':
        raise ValueError('complete Bias-SINEX 1.00 required')
    kept, block = [lines[0], MARKER], None
    counts = Counter()
    allowed = {'FILE/REFERENCE', 'BIAS/DESCRIPTION', 'BIAS/SOLUTION'}
    for line in lines[1:-1]:
        if line.startswith('+'):
            if block is not None:
                raise ValueError('nested bias block')
            block = line[1:].strip()
            counts[block] += 1
            if block in allowed:
                kept.append(line)
        elif line.startswith('-'):
            if line[1:].strip() != block:
                raise ValueError('unmatched bias block')
            if block in allowed:
                kept.append(line)
            block = None
        elif block == 'BIAS/SOLUTION':
            if selected_line(line, references):
                kept.append(line)
        elif block in allowed:
            kept.append(line)
    if block is not None or any(counts[name] != 1 for name in allowed):
        raise ValueError('missing or duplicated bias block')
    return '\n'.join(kept+['%=ENDBIA'])+'\n'


def parse_epoch(value):
    year, day, seconds = map(int, value.split(':'))
    if not (1 <= day <= 366 and 0 <= seconds < 86400):
        raise ValueError('invalid bias epoch')
    # tzinfo is the same calendar carrier as Context.day, not a GPST->UTC conversion.
    result = datetime(year, 1, 1, tzinfo=timezone.utc)+timedelta(days=day-1, seconds=seconds)
    if result.year != year:
        raise ValueError('invalid day of year')
    return result


def parse_bias(text, references, target, model):
    if extract_bias(text, references, target) != text:
        raise ValueError('unselected data in bias extract')
    description, records, block = {}, [], None
    for line in text.splitlines():
        if line.startswith('+'):
            block = line[1:].strip()
        elif line.startswith('-'):
            block = None
        elif block == 'BIAS/DESCRIPTION' and not line.startswith('*'):
            parts = line.split()
            if parts:
                description.setdefault(parts[0], []).append(parts[1:])
        elif block == 'BIAS/SOLUTION' and line.strip() and not line.startswith('*'):
            if not selected_line(line, references) or line[65:69].strip() != 'ns':
                raise ValueError('unsupported bias record or unit')
            if line[103:].strip():
                raise ValueError('bias slope unsupported')
            start, end = parse_epoch(line[35:49]), parse_epoch(line[50:64])
            value, sigma = float(line[70:91]), float(line[92:103])
            if start >= end or not np.isfinite([value, sigma]).all() or sigma < 0:
                raise ValueError('invalid bias value or interval')
            records.append({'reference': line[11:14], 'svn': line[6:10], 'signal': line[25:29].strip(),
                            'start': start, 'end': end, 'value_ns': value, 'reported_std_ns': sigma})
    for key, expected in {'TIME_SYSTEM': ['G'], 'BIAS_MODE': ['ABSOLUTE'], 'APC_MODEL': [model]}.items():
        if description.get(key) != [expected]:
            raise ValueError('incompatible bias convention: '+key)
    clocks = [value for value in description.get('SATELLITE_CLOCK_REFERENCE_OBSERVABLES', []) if value[0] == 'G']
    if clocks != [['G', 'C1W', 'C2W']]:
        raise ValueError('GPS clock must reference C1W/C2W')
    return records


def code_translation(records, reference, when, svn):
    chosen = {}
    for signal in SIGNALS:
        candidates = [r for r in records if r['reference'] == reference and r['signal'] == signal
                      and r['start'] <= when < r['end']]
        if len(candidates) != 1 or candidates[0]['svn'] != svn:
            raise ValueError('missing, overlapping or wrong-SVN bias: '+reference+' '+signal)
        chosen[signal] = candidates[0]
    dsb = chosen['C1W']['value_ns']-chosen['C1C']['value_ns']
    # Difference cancels a common pseudo-absolute OSB datum. Do not directly
    # subtract CODE OSBs from observations used with another center's clocks.
    return {'dsb_c1w_minus_c1c_ns': dsb, 'if_code_change_m': ALPHA*C*1e-9*dsb,
            'clock_reference_if_closure_m': C*1e-9*(ALPHA*chosen['C1W']['value_ns']+BETA*chosen['C2W']['value_ns']),
            'osb_ns': {s: chosen[s]['value_ns'] for s in SIGNALS},
            'product_reported_std_ns': {s: chosen[s]['reported_std_ns'] for s in SIGNALS},
            'svn': svn}


def translate_observations(observations, corrections, target):
    result = []
    for obs in observations:
        codes = {}
        for sv, value in obs['if_code_m'].items():
            if sv == target:
                raise ValueError('target code in reference translation')
            correction = corrections[(obs['time_s'], sv)]['if_code_change_m']
            if not np.isfinite([value, correction]).all():
                raise ValueError('nonfinite code translation')
            codes[sv] = value+correction
        result.append(dict(obs, if_code_m=codes))
    return result


def run(archive, biases, antennas):
    biases, antennas = Path(biases), Path(antennas)
    admitted, context, nav, hashes = load_inputs(archive)
    names = admitted['fit_stations']
    # Include every observed reference, even one without usable navigation.
    refs = sorted({sv for name in names for obs in admitted['stations'][name]['reference_observations']
                   for sv in obs['if_code_m']})
    buffers = {'bias_extract': (biases/'reference_bias.bia').read_bytes(),
               'bias_receipt': (biases/'receipt.json').read_bytes(),
               'antenna_extract': (antennas/'reference_antenna.atx').read_bytes(),
               'antenna_receipt': (antennas/'receipt.json').read_bytes()}
    for kind in ('bias', 'antenna'):
        receipt = json.loads(buffers[kind+'_receipt'])
        if (receipt['extract_sha256'] != hashlib.sha256(buffers[kind+'_extract']).hexdigest()
                or receipt['references'] != refs or receipt['target_excluded'] != context.target
                or receipt['model'] != 'IGS20_2425'):
            raise ValueError(kind+' input differs from receipt or reference set')
    records = parse_bias(buffers['bias_extract'].decode('ascii'), refs, context.target, 'IGS20_2425')
    corrections = {}
    for t in context.times:
        offsets = antenna_offsets(buffers['antenna_extract'].decode('ascii'), refs, context.target,
                                  context.date_gpst, t, 'IGS20_2425')
        for sv in refs:
            corrections[t, sv] = code_translation(records, sv, context.day+timedelta(seconds=t), offsets[sv]['svn'])
    cases, baseline = [], None
    for mode in ('baseline', 'satellite_code_translation'):
        calibration = {}
        row = {'mode': mode}
        try:
            for name in names:
                station = admitted['stations'][name]
                observations = station['reference_observations']
                if mode != 'baseline':
                    observations = translate_observations(observations, corrections, context.target)
                calibration[name] = calibrate_station(observations, np.array(station['antenna_ecef_m']), nav, context)
            row['calibration'] = calibration
            row.update(fit_variant(admitted, context, calibration))
        except ScientificRejection as error:
            row.update(status='FIT_REJECTED', reason=str(error), calibration=calibration)
        except Exception as error:
            row.update(status='ENGINEERING_FAILURE', reason=type(error).__name__+': '+str(error), calibration=calibration)
        if mode == 'baseline':
            baseline = row
        elif baseline['status'] == row['status'] == 'ESTIMATED':
            if baseline['u0_relative_s'] != row['u0_relative_s']:
                row['comparison_status'] = 'FRAME_TAG_CHANGED'
            else:
                delta = np.array(row['xyz_m'])-baseline['xyz_m']
                row.update(comparison_status='COMPARABLE', delta_xyz_m=delta.tolist(),
                           displacement_from_baseline_m=float(np.linalg.norm(delta)),
                           delta_B_m=row['B_m']-baseline['B_m'])
        cases.append(row)
    changes = []
    for name in names:
        old = {e['time_s']: e for e in cases[0]['calibration'].get(name, {}).get('epochs', [])}
        new = {e['time_s']: e for e in cases[1]['calibration'].get(name, {}).get('epochs', [])}
        for t in context.times:
            entry = {'station': name, 'time_s': t, 'status': 'MISSING_CALIBRATION_EPOCH'}
            if t in old and t in new:
                expected = float(np.mean([corrections[t, sv]['if_code_change_m'] for sv in old[t]['references']]))
                actual = new[t]['clock_m']-old[t]['clock_m']
                entry.update(status='COMPARED', selection_changed=old[t]['references'] != new[t]['references'],
                             clock_change_m=actual, frozen_geometry_mean_code_change_m=expected,
                             nonlinear_minus_frozen_m=actual-expected)
            changes.append(entry)
    root = Path(__file__).resolve().parents[2]
    sources = [Path(__file__), Path(__file__).with_name('reference_sensitivity.py'),
               Path(__file__).with_name('reference_conventions.py'),
               Path(__file__).with_name('reference_product_discrepancy.py'),
               Path(__file__).with_name('reference_ray_projection.py')]
    sources += [root/'positioning'/name for name in ('calibration.py', 'navigation.py', 'context.py', 'solver.py', 'errors.py')]
    return {'schema': 'reference-code-bias-v1', 'target': context.target, 'date_gpst': context.date_gpst,
            'fit_stations': names, 'references': refs, 'input_sha256': hashes | {
                key: hashlib.sha256(value).hexdigest() for key, value in buffers.items()},
            'sources_sha256': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
            'scope': 'Satellite DSB-only exploratory recalibration and inverse fit on exposed archived data; no joint precise orbit/clock substitution.',
            'conventions': {'input_codes': 'alpha*C1C + beta*C2W',
                'translation': 'add alpha*c*1e-9*(OSB_C1W-OSB_C1C) to reference IF codes only',
                'clock_reference': 'C1W/C2W; common CODE OSB datum cancels in DSB',
                'reference_geometry': 'unchanged broadcast model and historical calibration gates',
                'target_codes': 'unchanged; no target bias or orbit read',
                'weights': 'unchanged equal 20 m; no new prospective uncertainty',
                'unresolved': ['receiver-dependent signal response', 'bias product errors and covariance',
                    'cross-center clock datum and full orbit/clock alignment', 'actual attitude, frame/media, observation-time precise products']},
            'product_sigmas_used_as_uncertainty': False, 'qualified_error_budget': False,
            'applied_to_production_estimator': False, 'target_orbit_accessed': False,
            'target_bias_parsed': False, 'new_confirmation': False,
            'translations': [{'time_s': t, 'reference': sv, **value} for (t, sv), value in corrections.items()],
            'case_count': len(cases), 'status_counts': dict(Counter(row['status'] for row in cases)),
            'cases': cases, 'station_epoch_changes': changes}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('archive', 'biases', 'antennas', 'output'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.output.resolve().is_relative_to(args.archive.resolve()):
        parser.error('choose a new output outside the preserved archive')
    result = run(args.archive, args.biases, args.antennas)
    with args.output.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write('\n')
