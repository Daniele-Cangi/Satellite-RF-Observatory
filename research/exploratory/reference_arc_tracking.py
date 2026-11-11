"""Replay causal phase arc decisions on exposed reference observations."""
from collections import Counter
import hashlib
import json
import subprocess

from . import integer_phase_feasibility as base
from research.kinematic import phase_continuity as continuity


def replay(reference):
    cohort = reference['cohorts']['day']
    plan = cohort['plan']
    allowed = set(plan['references'])
    if 'G12' in allowed or plan['target_excluded'] in allowed:
        raise ValueError('target in reference allowlist')
    if plan['step_s'] != continuity.STEP_S:
        raise ValueError('reference tracker expects 30 s samples')
    start = plan['start_gpst_s']
    stop = start + (plan['samples'] - 1)*continuity.STEP_S
    stations, decisions = {}, []
    for station in plan['stations']:
        item = cohort['stations'][station]
        header = base.header_status(item)
        stations[station] = header
        if header != 'SUPPORTED_RAW_SIGNALS':
            continue
        trackers = {}
        for row in item['rows']:
            satellite = row['reference']
            if satellite not in allowed:
                continue
            time_s = row['time_s']
            if time_s < start or time_s > stop:
                continue
            tracker = trackers.get(satellite)
            if tracker is None:
                tracker = trackers[satellite] = continuity.PhaseArcTracker()
            entry = {'station': station, 'reference': satellite, 'time_s': time_s,
                     'lli': row.get('lli')}
            if row['status'] != 'AVAILABLE' or row.get('lli') not in (
                    ['0','0'], ['0',' '], [' ','0'], [' ',' ']):
                entry['input_rejection'] = row.get('reasons') or ['STATUS_OR_LLI']
                entry.update(tracker.update(time_s))
            else:
                fields = row.get('fields')
                try:
                    mw = base.wide_lane(fields)
                    gf = (float(fields[2])*continuity.C/continuity.F1_HZ
                          - float(fields[3])*continuity.C/continuity.F2_HZ)
                except (TypeError, ValueError):
                    entry['input_rejection'] = ['INVALID_RAW_FIELDS']
                    entry.update(tracker.update(time_s))
                else:
                    entry.update(gf_m=gf, mw_cycles=mw)
                    entry.update(tracker.update(time_s, gf_m=gf, mw_cycles=mw))
            decisions.append(entry)

    counts = Counter(row['status'] for row in decisions)
    witnesses = Counter(
        'GF_AND_MW' if row['gf']['break'] and row['mw']['break']
        else 'GF_ONLY' if row['gf']['break'] else 'MW_ONLY'
        for row in decisions if row['status'] == 'ARC_BREAK'
    )
    return {'schema': 'reference-phase-arc-tracking-v1', 'stations': stations,
            'observation_count': len(decisions), 'statuses': dict(counts),
            'break_witnesses': dict(witnesses), 'decisions': decisions,
            'prospective_confirmation': False, 'integer_fix_admitted': False}


def run(input_path, output_path):
    if input_path.resolve() != base.REFERENCE.resolve():
        raise ValueError('use the retained reference-only extract')
    raw = input_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != base.EXPECTED[0]:
        raise ValueError('reference input hash mismatch')
    result = replay(json.loads(raw))
    sources = ['research/exploratory/reference_arc_tracking.py',
               'research/exploratory/real_phase.py',
               'research/exploratory/integer_phase_feasibility.py',
               'research/kinematic/phase_continuity.py',
               'research/kinematic/gnss_combinations.py',
               'research/kinematic/doppler.py', 'research/kinematic/receiver_time.py']
    result.update(input_sha256=digest, implementation_revision=subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=base.ROOT, text=True).strip(),
        source_sha256={name: hashlib.sha256((base.ROOT/name).read_bytes()).hexdigest()
                       for name in sources})
    base.write(output_path, result)
    return result
