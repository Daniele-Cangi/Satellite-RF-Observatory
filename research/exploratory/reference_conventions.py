"""Reference-only ANTEX radial/yaw geometry and periodic clock relativity.

This is a partial convention alignment at SP3 nodes, never an estimator input.
"""
import argparse
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import numpy as np

from positioning.calibration import ALPHA, BETA, C, OMEGA, rotate_z, state_and_clock
from .reference_product_discrepancy import parse_extract
from .reference_ray_projection import run as raw_projection
from .reference_sensitivity import load_inputs


def label(line):
    return line[60:].strip()


def extract_antex(text, references, target):
    """Discard unselected blocks as text, before parsing any numeric metadata."""
    if target in references:
        raise ValueError('target in reference allowlist')
    lines = text.splitlines()
    if not lines or lines[0][:8].strip() != '1.4':
        raise ValueError('ANTEX 1.4 required')
    header_end = next(i for i, s in enumerate(lines) if label(s) == 'END OF HEADER')
    if not any(s.startswith('A') and label(s) == 'PCV TYPE / REFANT' for s in lines[:header_end]):
        raise ValueError('absolute antenna model required')
    output = [lines[0], next(s for s in lines[:header_end] if label(s) == 'PCV TYPE / REFANT'),
              ' '*60+'END OF HEADER']
    block = None
    for line in lines[header_end+1:]:
        if label(line) == 'START OF ANTENNA':
            if block is not None:
                raise ValueError('nested antenna block')
            block = []
        if block is not None:
            block.append(line)
        if label(line) == 'END OF ANTENNA':
            if block is None:
                raise ValueError('unmatched antenna end')
            identity = [s for s in block if label(s) == 'TYPE / SERIAL NO']
            if len(identity) != 1:
                raise ValueError('antenna identity required')
            if identity[0][20:40].strip() in references:
                output.extend(block)
            block = None
    if block is not None:
        raise ValueError('truncated antenna block')
    return '\n'.join(output)+'\n'


def epoch_tuple(line):
    fields = line[:60].split()
    if len(fields) != 6:
        raise ValueError('invalid antenna validity epoch')
    return tuple(int(x) for x in fields[:5])+(Decimal(fields[5]),)


def antenna_offsets(text, references, target, date, time_s, model):
    """Select uniquely valid G01/G02 offsets; ANTEX millimetres -> body XYZ m."""
    # Re-extraction must be identical: a tainted extract is rejected, not cleaned.
    if extract_antex(text, references, target) != text:
        raise ValueError('unselected data in antenna extract')
    year, month, day = map(int, date.split('-'))
    when = (year, month, day, int(time_s//3600), int(time_s%3600//60), Decimal(str(time_s%60)))
    selected = {}
    block = []
    for line in text.splitlines():
        if label(line) == 'START OF ANTENNA':
            block = []
        block.append(line)
        if label(line) != 'END OF ANTENNA':
            continue
        identity = next(s for s in block if label(s) == 'TYPE / SERIAL NO')
        sv = identity[20:40].strip()
        starts = [epoch_tuple(s) for s in block if label(s) == 'VALID FROM']
        ends = [epoch_tuple(s) for s in block if label(s) == 'VALID UNTIL']
        if len(starts) != 1 or len(ends) > 1:
            raise ValueError('invalid antenna validity interval')
        if when < starts[0] or (ends and when > ends[0]):
            continue
        if sv in selected:
            raise ValueError('ambiguous antenna assignment')
        codes = [s[:60].strip() for s in block if label(s) == 'SINEX CODE']
        if codes != [model]:
            raise ValueError('antenna model differs from SP3 PCV convention')
        frequency, offsets = None, {}
        for s in block:
            if label(s) == 'START OF FREQUENCY':
                frequency = s[:60].strip()
            elif label(s) == 'END OF FREQUENCY':
                frequency = None
            elif label(s) == 'NORTH / EAST / UP':
                if frequency in offsets or frequency is None:
                    raise ValueError('invalid frequency offset')
                value = np.array([float(v) for v in s[:60].split()])/1000.
                if value.shape != (3,) or not np.isfinite(value).all():
                    raise ValueError('invalid antenna offset')
                offsets[frequency] = value
        if not {'G01', 'G02'} <= offsets.keys():
            raise ValueError('dual-frequency GPS offsets required')
        selected[sv] = {'svn': identity[40:50].strip(), 'type': identity[:20].strip(),
                        'if_pco_body_m': (ALPHA*offsets['G01']+BETA*offsets['G02']).tolist()}
    if set(selected) != set(references):
        raise ValueError('missing valid reference antenna')
    return selected


def radial_yaw_geometry(station, precise, pco, tau):
    """Exact range envelope over every yaw, conditional on body Z = geocentric nadir.

    No nominal Sun/yaw model or attitude evidence is silently assumed. The
    envelope covers only transverse PCO yaw, not orbit, PCV, pitch/roll or noise.
    """
    station, precise, pco = [np.asarray(v, dtype=float) for v in (station, precise, pco)]
    if any(v.shape != (3,) or not np.isfinite(v).all() for v in (station, precise, pco)):
        raise ValueError('finite xyz vectors required')
    if np.linalg.norm(precise) == 0 or not np.isfinite(tau) or tau <= 0:
        raise ValueError('nonzero satellite and positive flight time required')
    p = rotate_z(precise, -OMEGA*tau)
    z = -p/np.linalg.norm(p)
    q = p+pco[2]*z-station
    radial_range = float(np.linalg.norm(q))
    axial = float(q@z)
    transverse = float(np.linalg.norm(q-axial*z))
    radius = float(np.linalg.norm(pco[:2]))
    return {'radial_pco_range_change_m': radial_range-float(np.linalg.norm(p-station)),
            'yaw_range_change_min_m': float(np.hypot(axial, transverse-radius))-radial_range,
            'yaw_range_change_max_m': float(np.hypot(axial, transverse+radius))-radial_range}


def node_velocity(epochs, sv, t, half_width):
    """Centered 900-s polynomial derivative, no gaps/extrapolation/flagged samples."""
    if half_width not in (3, 4):
        raise ValueError('use seven or nine nodes')
    nodes = np.arange(-half_width, half_width+1, dtype=float)
    positions = []
    for offset in nodes:
        sample = epochs.get(t+900.*offset, {}).get(sv)
        if sample is None or sample['status'] != 'AVAILABLE':
            raise ValueError('unavailable velocity stencil')
        positions.append(sample['xyz_m'])
    matrix = np.array([nodes**k for k in range(len(nodes))])
    rhs = np.zeros(len(nodes)); rhs[1] = 1.
    weights = np.linalg.solve(matrix, rhs)/900.
    return weights@np.asarray(positions)


def relativity_m(position, velocity):
    # r.(Omega cross r) == 0: the scalar is invariant to terrestrial rotation.
    position, velocity = [np.asarray(v, dtype=float) for v in (position, velocity)]
    if any(v.shape != (3,) or not np.isfinite(v).all() for v in (position, velocity)):
        raise ValueError('finite state required')
    return float(-2.*np.dot(position, velocity)/C)


def run(archive, products, antennas):
    products, antennas = Path(products), Path(antennas)
    result = raw_projection(archive, products/'reference_extract.txt', products/'receipt.json')
    admitted, context, nav, _ = load_inputs(archive)
    refs = result['references']
    text = (products/'reference_extract.txt').read_text(encoding='ascii')
    epochs = parse_extract(text, refs, context.target, context.date_gpst)
    models = {s.split('PCV:')[1].split()[0] for s in text.splitlines() if s.startswith('/*') and 'PCV:' in s}
    if len(models) != 1:
        raise ValueError('unique SP3 antenna model required')
    model = models.pop()
    content = (antennas/'reference_antenna.atx').read_bytes()
    receipt_bytes = (antennas/'receipt.json').read_bytes()
    receipt = json.loads(receipt_bytes)
    if (receipt['extract_sha256'] != hashlib.sha256(content).hexdigest()
            or receipt['references'] != refs or receipt['target_excluded'] != context.target
            or receipt['model'] != model):
        raise ValueError('antenna input differs from receipt')
    offsets = {t: antenna_offsets(content.decode('ascii'), refs, context.target, context.date_gpst, t, model)
               for t in result['emission_nodes_gpst_s']}
    for row in result['rows']:
        row['alignment_status'] = 'NOT_PROJECTED'
        if row['status'] != 'PROJECTED':
            continue
        t, sv = row['time_gpst_s'], row['reference']
        sample = epochs[t][sv]
        try:
            velocity9 = node_velocity(epochs, sv, t, 4)
            velocity7 = node_velocity(epochs, sv, t, 3)
        except ValueError:
            row['alignment_status'] = 'UNAVAILABLE_VELOCITY_STENCIL'
            continue
        record = min(nav[sv], key=lambda r: abs(t-(r.toc_gps-context.day).total_seconds()))
        age = t-(record.toc_gps-context.day).total_seconds()
        _, clock = state_and_clock(record, t, context)
        polynomial = record.af0_s+record.af1_s_s*age+record.af2_s_s2*age**2
        b_rel = C*(clock-polynomial)
        p_rel = relativity_m(sample['xyz_m'], velocity9)
        row.update(offsets[t][sv])
        row.update(radial_yaw_geometry(admitted['stations'][row['station']]['antenna_ecef_m'],
                                      sample['xyz_m'], row['if_pco_body_m'], row['baseline_vacuum_flight_time_s']))
        row['broadcast_periodic_relativity_m'] = b_rel
        row['precise_periodic_relativity_m'] = p_rel
        row['relativity_stencil_9_minus_7_m'] = p_rel-relativity_m(sample['xyz_m'], velocity7)
        row['relativity_model_change_m'] = -(b_rel-p_rel)
        row['radial_aligned_joint_m'] = (row['joint_range_difference_m']
                                        -row['radial_pco_range_change_m']+row['relativity_model_change_m'])
        row['yaw_joint_min_m'] = row['radial_aligned_joint_m']-row['yaw_range_change_max_m']
        row['yaw_joint_max_m'] = row['radial_aligned_joint_m']-row['yaw_range_change_min_m']
        row['alignment_status'] = 'PARTIALLY_ALIGNED'
    rows = [r for r in result['rows'] if r['alignment_status'] == 'PARTIALLY_ALIGNED']
    keys = ('joint_range_difference_m', 'radial_pco_range_change_m', 'relativity_model_change_m',
            'relativity_stencil_9_minus_7_m', 'radial_aligned_joint_m')
    result['alignment_rms_m'] = {k: float(np.sqrt(np.mean([r[k]**2 for r in rows]))) if rows else None for k in keys}
    result['max_yaw_range_excursion_m'] = max((max(abs(r['yaw_range_change_min_m']), abs(r['yaw_range_change_max_m'])) for r in rows), default=None)
    result['alignment_status_counts'] = dict(Counter(r['alignment_status'] for r in result['rows']))
    result['schema'] = 'reference-conventions-v1'
    result['scope'] = 'Partial radial antenna and periodic-relativity alignment at fixed SP3 nodes; yaw envelope is conditional on nadir pointing.'
    result['conventions']['clock'] = 'Broadcast polynomial + broadcast periodic relativity; SP3 field + -2*r.v/c^2 from nine centered orbit nodes'
    result['conventions']['antenna'] = f'{model} GPS L1/L2 ionosphere-free PCO; radial component applied; full-yaw transverse range envelope, nadir body Z assumed'
    result['conventions']['unresolved'] = ['actual satellite attitude including pitch/roll', 'code antenna response and PCV',
        'frame alignment', 'signal biases and clock datum', 'media, observation-time interpolation and nonlinear recalibration']
    result['conventions']['velocity_control'] = 'Nine versus seven centered nodes, 900 s spacing; numerical diagnostic, not physical error bound'
    # Existing summaries explicitly retain raw semantics; add separate aligned means.
    for group in result['station_epoch_projections']:
        subset = [r for r in rows if r['station'] == group['station'] and r['time_gpst_s'] == group['time_gpst_s']]
        group['alignment_status'] = 'PARTIALLY_ALIGNED' if len(subset) == len(group['references']) and len(subset) >= 4 else 'INCOMPLETE_ALIGNMENT'
        if group['alignment_status'] == 'PARTIALLY_ALIGNED':
            for key in ('radial_aligned_joint_m', 'yaw_joint_min_m', 'yaw_joint_max_m'):
                group['mean_'+key] = float(np.mean([r[key] for r in subset]))
    root = Path(__file__).resolve().parents[2]
    result['sources_sha256'][Path(__file__).relative_to(root).as_posix()] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result['input_sha256'].update(antenna_extract=hashlib.sha256(content).hexdigest(), antenna_receipt=hashlib.sha256(receipt_bytes).hexdigest())
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('archive', 'products', 'antennas', 'output'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.output.resolve().is_relative_to(args.archive.resolve()):
        parser.error('choose a new output outside the preserved archive')
    result = run(args.archive, args.products, args.antennas)
    with args.output.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write('\n')
