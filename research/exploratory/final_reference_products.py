"""Strict paired CODE final adapter, separate from frozen rapid loaders."""
from datetime import timedelta
from pathlib import Path

from . import day_reference as baseline
from .day_reference_checked import RUNNER_SHA
from .prepare_final_reference_v2 import PLAN_SHA
from .erp_polar_bound import pinned, strict_json
from .hour_reference_v2 import source_bytes
from .precise_reference_model import PreciseReference, parse_orbit
from .final_reference_clock import parse_clock
from .reference_attitude_model import Attitude, AttitudeReference, parse_attitude
from .reference_code_bias import parse_bias, code_translation

BASE = Path(__file__).parent
INPUTS = BASE/'inputs/final_reference_v3'
RECEIPT_SHA = '3da32a6fc05325826bd45df394c0d1bbf9f8fe74537e819a43c2bce9c2ff332d'


def inputs():
    pinned(Path(baseline.__file__),RUNNER_SHA)
    choice = strict_json(pinned(BASE/'final_reference_plan_v2.json',PLAN_SHA))
    plan,ctx,observations,positions,prior_receipt = baseline.inputs()
    pinned(BASE/'day_reference_plan.json',choice['baseline_plan_sha256'])
    prior = strict_json(pinned(BASE/'results/day_reference_v1.json',choice['baseline_report_sha256']))
    if prior['plan'] != plan or not prior['calibration_complete'] or prior['receipt_sha256'] != baseline.RECEIPT_SHA:
        raise ValueError('baseline report is not the fixed complete cohort')
    receipt = strict_json(pinned(INPUTS/'receipt.json',RECEIPT_SHA))
    if receipt['failures'] or receipt['plan_sha256'] != PLAN_SHA or set(receipt['products']) != set(choice['files']):
        raise ValueError('incomplete final product family')
    for path,digest in receipt['sources_sha256'].items():
        source_bytes(baseline.frame.ROOT/path,digest)
    texts = {name[:-4]:pinned(INPUTS/name,digest).decode('ascii') for name,digest in receipt['files'].items()}
    if set(texts) != set(choice['files']):
        raise ValueError('incomplete final extracts')
    for kind,name in choice['files'].items():
        if receipt['products'][kind]['url'] != choice['source_base']+name:
            raise ValueError('wrong paired final source')
    return choice,plan,ctx,observations,positions,prior,receipt,texts


def products(choice,plan,ctx,texts):
    refs,target = plan['references'],ctx.target
    start,end = choice['window_gpst_s']
    # Existing guarded rapid loader validates the unchanged, pinned ANTEX inputs.
    rapid,_,_ = baseline.frame.guarded_products(ctx,refs,baseline.INPUTS/'timed',
                         BASE/'inputs/reference_biases/g12',BASE/'inputs/reference_antennas/g12')
    convention = 'PCV:IGS20_2425 OL/AL:FES2014b NONE YN ORB:CoN CLK:CoN'
    comments = [' '.join(line[2:].split()) for line in texts['orbit'].splitlines() if line.startswith('/*')]
    if convention not in comments or not any('Final GNSS orbits' in s for s in comments):
        raise ValueError('final orbit convention differs')
    if 'IAU2000R06' not in texts['erp'] or 'DESAI2016' not in texts['erp']:
        raise ValueError('Earth orientation convention differs')
    # ERP is convention evidence only. Keep the already fixed IERS-derived
    # station displacements; do not apply a second rotation to terrestrial SP3.
    orbits = parse_orbit(texts['orbit'],refs,target,ctx.date_gpst)
    clocks = parse_clock(texts['clock'],refs,target,ctx.date_gpst,start,end)
    records = parse_bias(texts['bias'],refs,target,'IGS20_2425')
    corrections = {(t,sv):code_translation(records,sv,ctx.day+timedelta(seconds=t),rapid.offsets[sv]['svn'])
                   for t in ctx.times for sv in refs}
    samples = parse_attitude(texts['attitude'],refs,target,ctx.date_gpst,start,end)
    if any(list(values) != list(range(start,end+1,30)) for values in samples.values()):
        raise ValueError('incomplete final attitude window')
    precise = PreciseReference(orbits,clocks,rapid.offsets,target)
    return AttitudeReference(precise,Attitude(samples,target)),corrections
