"""Exposed reference code/carrier information; sparse data, existing header parsers.

No target observations or states. This is development, not a confirmation runner.
Static phase alignments/ambiguities are retained; only training offsets or
same-segment increments remove them. No phase repair or gap interpolation.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

import hatanaka
import numpy as np

from ..kinematic import phase_transform_header_audit as header
from ..kinematic.rinex_observations import _time
from ..kinematic.doppler import ALPHA, BETA, F1_HZ, F2_HZ
from ..kinematic.receiver_time import C

BASE = Path(__file__).parent
REQUIRED = ('C1C', 'C2W', 'L1C', 'L2W')
COHORTS = {
    'day': ('day_reference', 'day_reference_plan.json', 'day_reference_v1.json', 'day-reference-work'),
    'hour': ('hour_reference', 'hour_reference_plan.json', 'hour_reference_v2.json', 'hour-reference-work'),
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def parse_reference_fields(text, plan):
    """Decode only allowed reference fields in the declared exposed window.

    Unlike the fixed-grid bridge this extractor does not allocate a dense
    covariance for an entire day. Header interpretation is reused, not copied.
    RINEX 3.03 is supported only with unit legacy ambiguity-wavelength factors.
    """
    lines = text.splitlines()
    end = next((i for i, line in enumerate(lines) if line[60:80].strip() == 'END OF HEADER'), None)
    if end is None:
        raise ValueError('missing header end')
    headers, types = header._collect_headers(lines[:end+1])
    def one(name):
        values = headers.get(name, [])
        if len(values) != 1:
            raise ValueError('missing/duplicate '+name)
        return values[0]
    version = one('RINEX VERSION / TYPE')
    if version[:9].strip() not in ('3.03', '3.04', '3.05') or version[20] != 'O' or version[40] not in 'GM':
        raise ValueError('unsupported observation format')
    if float(one('INTERVAL')) != plan['step_s'] or one('TIME OF FIRST OBS')[48:51] != 'GPS':
        raise ValueError('interval/time system differs')
    if headers.get('RCV CLOCK OFFS APPL', ['0'])[0].strip() != '0':
        raise ValueError('applied receiver clock correction')
    gps = types.get('G', [])
    if not set(REQUIRED) <= set(gps):
        raise ValueError('required signal pair unavailable')
    scales = header._parse_scale_factors(headers.get('SYS / SCALE FACTOR', []), gps)
    shifts = header._parse_phase_shifts(headers.get('SYS / PHASE SHIFT', []))
    legacy = header._parse_legacy_wavelength(headers.get('WAVELENGTH FACT L1/2', []))
    if any(v != 1 for v in legacy['default_ambiguity_wavelength_divisor'].values()) or any(
            v != 1 for item in legacy['satellite_overrides'].values() for v in item.values()):
        raise ValueError('nonunit legacy wavelength factor unsupported')
    header._external_corrections(headers)
    refs = set(plan['references'])
    if plan['target_excluded'] in refs:
        raise ValueError('target in reference allowlist')
    first = _time(one('TIME OF FIRST OBS')[:43].split(), plan['date_gpst'], 0)
    start, stop = plan['start_gpst_s'], plan['start_gpst_s']+(plan['samples']-1)*plan['step_s']
    rows, previous, seen = [], None, set()
    i = end+1
    while i < len(lines):
        line = lines[i]; i += 1
        if not line.startswith('>'):
            raise ValueError('expected epoch record')
        fields = line[1:].split()
        if len(fields) not in (8, 9):
            raise ValueError('invalid epoch record')
        t = _time(fields[:6], plan['date_gpst'], 0)
        if t > stop:
            break
        flag, count = int(fields[6]), int(fields[7])
        if flag != 0:
            raise ValueError('event/header change in scanned prefix')
        if count < 0 or i+count > len(lines) or (previous is not None and t <= previous):
            raise ValueError('truncated/unordered observation block')
        if previous is None and t != first:
            raise ValueError('first epoch/header mismatch')
        previous = t
        block = lines[i:i+count]; i += count
        if t < start:
            continue
        if (t-start) % plan['step_s'] != 0:
            raise ValueError('off-grid observation')
        for record in block:
            sv = record[:3]
            if sv not in refs:
                continue  # Excluded target/unlisted payload never decoded.
            if (t, sv) in seen:
                raise ValueError('duplicate admitted reference')
            seen.add((t, sv))
            values, lli, reasons = [], [], []
            for name in REQUIRED:
                field = record[3+16*gps.index(name):3+16*(gps.index(name)+1)].ljust(16)
                try:
                    value = float(field[:14])/scales[name]
                except ValueError:
                    value = float('nan')
                if not np.isfinite(value) or value == 0 or (name.startswith('C') and value < 0):
                    reasons.append('MISSING_INVALID_'+name)
                values.append(float(value) if np.isfinite(value) else None)
                if name.startswith('L'):
                    lli.append(field[14])
                    if field[14] not in (' ', '0'):
                        reasons.append('LOSS_OF_LOCK_'+name)
            row = {'time_s': t, 'reference': sv, 'fields': values, 'lli': lli,
                   'status': 'AVAILABLE' if not reasons else 'REJECTED', 'reasons': reasons}
            if not reasons:
                c1, c2, l1, l2 = values
                row.update(code_m=ALPHA*c1+BETA*c2,
                           phase_m=ALPHA*C/F1_HZ*l1+BETA*C/F2_HZ*l2,
                           geometry_free_phase_m=C/F1_HZ*l1-C/F2_HZ*l2)
            rows.append(row)
    return {'version': version[:9].strip(), 'receiver': one('REC # / TYPE / VERS').strip(),
            'scales': scales, 'phase_shifts': shifts, 'legacy': legacy, 'rows': rows}


def extract(cache, output):
    """Reuse exact previously acquired bytes, retaining a reference-only extract."""
    result = {'schema': 'real-reference-phase-input-v1', 'cohorts': {}, 'target_values_decoded': False}
    for name, (folder, plan_file, report_file, work) in COHORTS.items():
        plan_bytes = (BASE/plan_file).read_bytes()
        receipt_bytes = (BASE/'inputs'/folder/'receipt.json').read_bytes()
        plan, receipt = json.loads(plan_bytes), json.loads(receipt_bytes)
        sources = receipt['observation_receipts']
        if isinstance(sources, list):
            sources = {r['station']: r for r in sources}
        cohort = {'plan': plan, 'plan_sha256': digest(plan_bytes), 'receipt_sha256': digest(receipt_bytes), 'stations': {}}
        for station in plan['stations']:
            source = sources[station]
            path = cache/work/source['url'].split('/')[-1]
            raw = path.read_bytes()
            if digest(raw) != source['sha256']:
                raise ValueError('cached observation hash mismatch: '+station)
            decoded = hatanaka.decompress(raw, strict=True)
            if digest(decoded) != source['decoded_sha256']:
                raise ValueError('decoded observation hash mismatch: '+station)
            try:
                parsed = parse_reference_fields(decoded.decode('ascii'), plan)
                cohort['stations'][station] = {'status': 'PARSED', 'source': source, **parsed}
            except ValueError as error:
                cohort['stations'][station] = {'status': 'UNSUPPORTED', 'source': source, 'reason': str(error), 'rows': []}
            print(name, station, cohort['stations'][station]['status'], flush=True)
        result['cohorts'][name] = cohort
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, separators=(',', ':'), allow_nan=False)+'\n', encoding='utf-8', newline='\n')
    return result


def moments(values):
    a = np.asarray(values, float)
    return {'count': len(a), 'mean': float(a.mean()) if len(a) else None,
            'rms': float(np.sqrt(np.mean(a*a))) if len(a) else None,
            'max_abs': float(abs(a).max()) if len(a) else None}


def correlation_pairs(intervals, field):
    """Descriptive paired correlations; no IID significance or attribution."""
    def summary(pairs):
        if len(pairs) < 10:
            return {'pairs': len(pairs), 'correlation': None}
        a = np.array(pairs)
        rho = float(np.corrcoef(a.T)[0, 1]) if np.all(a.std(axis=0) > 0) else None
        return {'pairs': len(pairs), 'correlation': rho}
    indexed = {(r['station'], r['reference'], r['time_s']): r[field]
               for r in intervals if field in r}
    links, cross = defaultdict(list), defaultdict(list)
    for (station, sv, t), value in indexed.items():
        if (station, sv, t-30) in indexed:
            links[(station, sv)].append((indexed[(station, sv, t-30)], value))
        for other in sorted({r['station'] for r in intervals}):
            if other > station and (other, sv, t) in indexed:
                cross[(station, other)].append((value, indexed[(other, sv, t)]))
    return {'lag_30s_by_link': [{'station': s, 'reference': sv, **summary(p)} for (s, sv), p in sorted(links.items())],
            'same_reference_between_receivers': [{'stations': list(k), **summary(p)} for k, p in sorted(cross.items())]}


def analyze(inputs):
    result = {'schema': 'real-reference-phase-information-v1', 'cohorts': {},
              'scope': 'Exposed diagnostic; common modes and absolute phase ambiguity unresolved. No physical covariance or target position qualification.'}
    for name, cohort in inputs['cohorts'].items():
        plan = cohort['plan']
        report = json.loads((BASE/'results'/COHORTS[name][2]).read_bytes())
        baseline = {(r['station'], r['time_s'], r['reference']): r for r in report['rows']}
        links = defaultdict(list); failures = Counter()
        for station, parsed in cohort['stations'].items():
            if parsed['status'] != 'PARSED':
                failures['UNSUPPORTED_STATION:'+parsed['reason']] += 1
            for r in parsed['rows']:
                key = station, r['time_s'], r['reference']
                if key not in baseline:
                    failures['OUTSIDE_BASELINE_MASK'] += 1
                    continue
                if r['status'] != 'AVAILABLE':
                    failures[r['status']] += 1
                    continue
                # Constant daily code bias translation is absorbed by train-only
                # offsets and cancels in increments, never fit on evaluation data.
                residual = baseline[key]['residual_m']
                links[(station, r['reference'])].append({**r, 'station': station,
                    'code_residual_m': residual, 'phase_residual_m': r['phase_m']-r['code_m']+residual,
                    'code_minus_carrier_m': r['code_m']-r['phase_m']})
        intervals, series, training = [], [], []
        for (station, sv), rows in sorted(links.items()):
            rows.sort(key=lambda r: r['time_s'])
            segment = 0
            for i, r in enumerate(rows):
                if i and r['time_s']-rows[i-1]['time_s'] != plan['step_s']:
                    segment += 1
                r['segment'] = segment
            train = [r for r in rows if r['time_s'] < plan['training_before_gpst_s']]
            if len(train) < 10:
                failures['INSUFFICIENT_TRAINING_LINK'] += 1
                continue
            # A training ambiguity must not cross a rejected/missing sample.
            train = [r for r in train if r['segment'] == train[-1]['segment']]
            offsets = {k: float(np.mean([r[k] for r in train])) for k in ['phase_residual_m', 'code_minus_carrier_m']}
            training.append({'station': station, 'reference': sv, 'count': len(train), 'offsets_m': offsets})
            for r in rows:
                if r['time_s'] >= plan['training_before_gpst_s']:
                    if r['segment'] != train[-1]['segment'] or len(train) < 10:
                        failures['LEVEL_WITHOUT_CONTIGUOUS_TRAINING'] += 1
                        continue
                    series.append({'station': station, 'reference': sv, 'time_s': r['time_s'],
                        'code_residual_m': r['code_residual_m'],
                        **{k: r[k]-v for k, v in offsets.items()}})
            for a, b in zip(rows, rows[1:]):
                if b['time_s']-a['time_s'] != plan['step_s']:
                    failures['UNBRIDGED_GAP'] += 1
                    continue
                if a['time_s'] < plan['training_before_gpst_s']:
                    continue
                intervals.append({'station': station, 'reference': sv, 'time_s': b['time_s'],
                    **{k: (b[k]-a[k])/plan['step_s'] for k in ['code_residual_m', 'phase_residual_m',
                       'code_minus_carrier_m', 'geometry_free_phase_m']}})
        blocks = defaultdict(list)
        for r in intervals:
            blocks[(r['station'], r['time_s'])].append(r)
        for block in blocks.values():
            if len(block) < 4:
                failures['INSUFFICIENT_COMMON_MODE_REFERENCES'] += 1
                continue
            for field in ['code_residual_m', 'phase_residual_m']:
                common = float(np.mean([r[field] for r in block]))
                for r in block:
                    r[field+'_common'] = common
                    r[field+'_differential'] = r[field]-common
                    r['common_reference_count'] = len(block)
        fields = ['code_residual_m', 'phase_residual_m', 'code_minus_carrier_m',
                  'code_residual_m_common', 'phase_residual_m_common',
                  'code_residual_m_differential', 'phase_residual_m_differential']
        result['cohorts'][name] = {'failures': dict(failures), 'training': training,
            'level_unit': 'm after train-only constant ambiguity removal', 'series': series,
            'interval_unit': 'm/s', 'intervals': intervals,
            'baseline_sha256': digest((BASE/'results'/COHORTS[name][2]).read_bytes()),
            'correlations': {f: correlation_pairs(intervals, f) for f in ['code_residual_m', 'phase_residual_m', 'phase_residual_m_differential']},
            'summary': {field: moments([r[field] for r in intervals if field in r]) for field in fields},
            'per_station': {s: {f: moments([r[f] for r in intervals if r['station']==s and f in r]) for f in fields} for s in plan['stations']}}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    data = extract(args.cache, args.inputs) if args.cache else json.loads(args.inputs.read_bytes())
    report = analyze(data)
    report['input_sha256'] = digest(args.inputs.read_bytes())
    report['source_sha256'] = digest(Path(__file__).read_bytes())
    args.output.write_text(json.dumps(report, separators=(',', ':'), allow_nan=False)+'\n', encoding='utf-8', newline='\n')
    for name, row in report['cohorts'].items():
        print(name, json.dumps(row['summary']), flush=True)
