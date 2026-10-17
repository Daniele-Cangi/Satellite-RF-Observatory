"""Causal geometry-free continuity witnesses, never integer slip repairs.

The Navipedia example supplies the wavelength/sampling threshold and a ten
sample quadratic predictor. During warm-up use a first difference. These are
exploratory continuity assumptions, not calibrated detection probabilities:
ionosphere can trigger them and some dual-frequency slips are invisible.
Callers must exclude forbidden identities/times before supplying rows.
"""
import numpy as np

from .doppler import F1_HZ, F2_HZ
from .receiver_time import C

HISTORY = 10
STEP_S = 30.
MAX_GAP_S = 60.
SOURCE = 'https://gssc.esa.int/navipedia/index.php?title=Detector_based_in_carrier_phase_data:_The_geometry-free_combination'


def segment(rows):
    """Return copied rows with float-ambiguity segments split at witnesses.

    Requires ordered, finite, model-independent geometry-free phase metres.
    Original flag/mask/gap segments remain boundaries. A missing 30 s sample
    in a held-out training set permits a 60 s prediction with its own threshold;
    no values are interpolated. A detection resets history to the current row.
    """
    output, history, counters = [], {}, {}
    for row in rows:
        r = dict(row)
        key = r['station'], r['reference']
        t, value = float(r['time_s']), float(r['geometry_free_phase_m'])
        if not np.isfinite([t, value]).all():
            raise ValueError('finite geometry-free phase and time required')
        base = r.get('base_segment', r['segment'])
        previous = history.get(key, [])
        if previous and t <= previous[-1][0]:
            raise ValueError('ordered unique link epochs required')
        if previous and (base != previous[-1][2] or t-previous[-1][0] > MAX_GAP_S):
            previous = []
        assessment = {'method': 'NEW_SEGMENT', 'break': False}
        if previous:
            dt = t-previous[-1][0]
            threshold = 1.5*(C/F2_HZ-C/F1_HZ)*(1.-.5*np.exp(-dt/60.))
            prediction = previous[-1][1]
            method = 'FIRST_DIFFERENCE_WARMUP'
            if len(previous) >= HISTORY:
                x = np.array([(p[0]-t)/STEP_S for p in previous])
                y = np.array([p[1]-previous[-1][1] for p in previous])
                prediction += np.polynomial.polynomial.polyfit(x, y, 2)[0]
                method = 'QUADRATIC_PREVIOUS_TEN'
            innovation = value-prediction
            assessment = {'method': method, 'break': bool(abs(innovation) > threshold),
                'innovation_m': innovation, 'threshold_m': threshold, 'elapsed_s': dt,
                'raw_change_m': value-previous[-1][1]}
            if assessment['break']:
                previous = []
        if not previous:
            counters[key] = counters.get(key, 0)+1
        r.update(base_segment=base, segment=f'{base}/gf{counters[key]}',
                 continuity=assessment)
        previous.append((t, value, base))
        history[key] = previous[-HISTORY:]
        output.append(r)
    return output


def withheld_segment(row, training):
    """Assign an ambiguity using training identities/segments only, no held RF.

    Neighboring training samples straddling a detected boundary cannot identify
    which side contains the excluded epoch. Keep its code but no phase score.
    """
    base = row.get('base_segment', row['segment'])
    nearby = [r for r in training if r['station']==row['station'] and
              r['reference']==row['reference'] and r['base_segment']==base and
              abs(r['time_s']-row['time_s']) <= MAX_GAP_S]
    left = [r for r in nearby if r['time_s'] < row['time_s']]
    right = [r for r in nearby if r['time_s'] > row['time_s']]
    neighbors = ([max(left,key=lambda r:r['time_s'])] if left else []) + (
        [min(right,key=lambda r:r['time_s'])] if right else [])
    segments = {r['segment'] for r in neighbors}
    return next(iter(segments)) if len(segments)==1 else None
