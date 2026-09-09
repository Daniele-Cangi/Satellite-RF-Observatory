"""Bounded public-data acquisition and target-excluding estimator inputs."""
import gzip
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
import urllib.request
from urllib.error import HTTPError

import hatanaka

from .context import Context
from .qualification import scan_structure, QualificationError
from .network import select_network, availability_report, effective_plan
from .calibration import observation_window, antenna_position, strip_target_navigation


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, data, *, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x' if exclusive else 'w', encoding='utf-8') as handle:
        json.dump(data, handle, indent=2, allow_nan=False)


def source_hashes():
    return {p.name:digest(p) for p in sorted(Path(__file__).parent.glob('*.py'))}


def snapshot_sources(run, stage):
    """Keep byte-exact implementation alongside each stage's hash receipt."""
    destination = Path(run)/'sources'/stage
    destination.mkdir(parents=True, exist_ok=True)
    hashes = source_hashes()
    for name, expected in hashes.items():
        path = destination/name
        if path.exists():
            if digest(path) != expected:
                raise ValueError('stage source snapshot differs: '+stage+'/'+name)
        else:
            with path.open('xb') as handle:
                handle.write((Path(__file__).parent/name).read_bytes())
        if digest(path) != expected:
            raise ValueError('source changed while snapshotting: '+name)
    return hashes


def download(url, limit=50_000_000):
    if not url.startswith('https://igs.bkg.bund.de/root_ftp/'):
        raise ValueError('this bounded runner supports public BKG HTTPS inputs only')
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read(limit + 1)
        if len(data) > limit:
            raise ValueError('download exceeds declared bound')
        receipt = {'url':url,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(), 'access_utc':utc_now(),'http_status':response.status}
    return data, receipt


def acquire(plan_path, run_path, *, availability_only=False):
    run = Path(run_path)
    run.mkdir(parents=True, exist_ok=True)
    if (run/'solution_freeze.json').exists():
        raise ValueError('event already frozen; acquisition cannot overwrite it')
    plan_bytes = Path(plan_path).read_bytes()
    plan = json.loads(plan_bytes)
    if 'profile' in plan:
        from .plans import validate_plan
        validate_plan(plan)
    Context(plan['target'], plan['date_gpst'])
    if plan['calibration_limits'] != {'max_reference_absolute_residual_m':50,'max_reference_rms_m':20,'max_alternating_subset_clock_difference_m':30,'max_ground_coordinate_check_m':30}:
        raise ValueError('this version implements only the documented calibration thresholds')
    support_count = plan['selection']['support_epochs']
    fit_count = plan['selection']['fit_epochs']
    if not isinstance(support_count, int) or not isinstance(fit_count, int) or support_count % 2 != 1 or fit_count % 2 != 1 or not 7 <= fit_count <= support_count:
        raise ValueError('support and fit must be odd, with support >= fit >= 7')
    if plan['selection']['minimum_reference_count'] != 4:
        raise ValueError('this structural scanner implements four reference codes')
    candidates = plan['network']['candidate_stations'] if 'network' in plan else plan['fit_stations']
    names = candidates + [plan['withheld_station']]
    if len(set(names)) != len(names) or ('network' not in plan and not 5 <= len(candidates) <= 8):
        raise ValueError('need 5..8 distinct fit roots and one distinct held-out root')
    freeze = run/'plan_freeze.json'
    plan_sha = hashlib.sha256(plan_bytes).hexdigest()
    if freeze.exists():
        if json.loads(freeze.read_text())['plan_sha256'] != plan_sha:
            raise ValueError('plan differs from frozen plan')
        if (run/'outcome.json').exists():
            return json.loads((run/'outcome.json').read_text())
        if json.loads(freeze.read_text())['sources'] != source_hashes():
            raise ValueError('acquisition source changed since plan freeze')
        snapshot_sources(run, 'acquisition')
    else:
        (run/'plan.json').write_bytes(plan_bytes)
        frozen_sources = snapshot_sources(run, 'acquisition')
        write_json(freeze, {'plan_sha256':plan_sha,'freeze_utc':utc_now(),'sources':frozen_sources},exclusive=True)
    raw_dir = run/'raw_observations'
    raw_dir.mkdir(exist_ok=True)
    structures, receipts = {}, []
    for name in names:
        filename = plan['observation_filename'].format(station=name)
        path = raw_dir/filename
        receipt_path = raw_dir/(filename+'.json')
        if 'network' in plan and receipt_path.exists():
            cached = json.loads(receipt_path.read_text())
            if cached.get('http_status') == 404:
                receipts.append({'station':name, **cached})
                structures[name] = {'epochs':[], 'source_status':'SOURCE_MISSING', 'source_reason':'HTTP_404'}
                continue
        if path.exists():
            receipt = json.loads(receipt_path.read_text())
            if digest(path) != receipt['sha256']:
                raise ValueError('cached observation hash mismatch')
            raw = path.read_bytes()
        else:
            try:
                raw, receipt = download(plan['observation_base_url']+filename)
            except HTTPError as error:
                if 'network' not in plan or error.code != 404:
                    raise
                receipt = {'url':plan['observation_base_url']+filename, 'http_status':404, 'access_utc':utc_now()}
                write_json(receipt_path, receipt, exclusive=True)
                receipts.append({'station':name, **receipt})
                structures[name] = {'epochs':[], 'source_status':'SOURCE_MISSING', 'source_reason':'HTTP_404'}
                print(json.dumps({'station':name,'status':'SOURCE_MISSING'}),flush=True)
                continue
            path.write_bytes(raw)
            write_json(receipt_path,receipt,exclusive=True)
        # Full compressed receipt exists before the decoder sees the payload.
        decoded = hatanaka.decompress(raw,strict=True)
        receipts.append({'station':name,**receipt,'decoded_sha256':hashlib.sha256(decoded).hexdigest()})
        try:
            structure = scan_structure(decoded.decode('ascii'),plan['target'],plan['date_gpst'])
        except QualificationError as error:
            if 'network' not in plan:
                raise
            structures[name] = {'epochs':[], 'source_status':'STRUCTURE_UNSUPPORTED', 'source_reason':str(error)}
            continue
        structures[name] = structure
        print(json.dumps({'station':name,'epochs':structure['epoch_count'],'target_code_epochs':structure['target_code_epoch_count']}),flush=True)
    selection = select_network(plan, structures)
    structure_record = {'selection':selection,'structures':structures,'receipts':receipts,'sources':source_hashes()}
    write_json(run/'structure.json',structure_record)
    report = availability_report(plan, structure_record)
    report.update(plan_sha256=plan_sha, structure_sha256=digest(run/'structure.json'),
                  sources=source_hashes())
    write_json(run/'availability.json',report)
    if selection['selected_seconds_gpst'] is None:
        result={'experiment':plan['experiment'],'status':'SOURCE_OR_MEASUREMENT_NOT_QUALIFIED','reason':selection['status'],'primary_pass':False,'plan_sha256':plan_sha,'oracle_accessed':False}
        write_json(run/'outcome.json',result)
        return result
    if availability_only:
        return report
    plan = effective_plan(plan, structure_record)
    names = plan['fit_stations'] + [plan['withheld_station']]
    support = [int(float(v)) for v in selection['selected_seconds_gpst']]
    count = plan['selection']['fit_epochs']
    offset = (len(support)-count)//2
    context = Context(plan['target'],plan['date_gpst'],support[offset],count,plan['selection']['step_s'])
    admitted = {'plan_sha256':plan_sha,'context':context.__dict__,'fit_stations':plan['fit_stations'],'withheld_station':plan['withheld_station'],'stations':{},'observation_receipts':receipts}
    for name in names:
        info = structures[name]
        raw = raw_dir/plan['observation_filename'].format(station=name)
        if digest(raw)!=next(r['sha256'] for r in receipts if r['station']==name):
            raise ValueError('observation changed between structural scan and admission')
        content = hatanaka.decompress(raw.read_bytes(),strict=True).decode('ascii')
        reference_obs = observation_window(content,info['header'],info['gps_observation_types'],False,context)
        target_code = None
        if name in plan['fit_stations']:
            obs = observation_window(content,info['header'],info['gps_observation_types'],True,context)
            target_code = [o['if_code_m'][plan['target']] for o in obs]
        admitted['stations'][name]={'antenna_ecef_m':antenna_position(info['header']).tolist(),'reference_observations':reference_obs,'target_if_codes_m':target_code}
    estimation = run/'estimation'
    estimation.mkdir(exist_ok=True)
    nav_path = estimation/'reference_only.rnx'
    receipt_path = estimation/'navigation_receipt.json'
    if not nav_path.exists():
        data,receipt = download(plan['navigation_url'],20_000_000)
        sanitized = strip_target_navigation(gzip.decompress(data).decode('ascii'),plan['target']).encode('ascii')
        nav_path.write_bytes(sanitized)
        receipt.update({'reference_only_sha256':hashlib.sha256(sanitized).hexdigest(),'target_numerically_parsed':False,'raw_navigation_persisted':False})
        write_json(receipt_path,receipt,exclusive=True)
    else:
        receipt=json.loads(receipt_path.read_text())
        if digest(nav_path)!=receipt['reference_only_sha256']:
            raise ValueError('reference navigation hash mismatch')
    admitted['reference_navigation_sha256']=digest(nav_path)
    write_json(estimation/'admitted.json',admitted)
    write_json(run/'admission_receipt.json',{'admitted_sha256':digest(estimation/'admitted.json'),'navigation_sha256':digest(nav_path),'sources':source_hashes(),'admission_utc':utc_now(),'gold_target_numeric_access':False})
    result={'status':'INPUTS_ADMITTED','support_start_s':support[0],'window_start_s':context.start_s,'central_s':context.central_s,'fit_roots':len(plan['fit_stations'])}
    print(json.dumps(result),flush=True)
    return result
