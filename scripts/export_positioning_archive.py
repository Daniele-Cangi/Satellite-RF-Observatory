"""Export a read-only web archive from closed scientific receipts; never fit."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REVISION='7fcd71f9428c20202f98079955e8fac76aa0f6ad'
GITHUB=f'https://github.com/Daniele-Cangi/Satellite-RF-Observatory/tree/{REVISION}/'
FIT=['ALGO00CAN','DRAO00CAN','STJO00CAN','YELL00CAN','BOGT00COL']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def make_archive(root=ROOT):
    rows=[];bundles={}
    specifications=[('g12-2026-09-05','experiments/positioning_g12_doy248','G12','2026-09-05'),('g08-2026-09-06','experiments/gnss_inverse_positioning/event_2026249','G08','2026-09-06'),('g12-2026-09-07','experiments/positioning_g12_doy250','G12','2026-09-07')]
    for key,folder,target,date in specifications:
        base=root/folder
        filenames=['g08_protocol.json','g08_numerical_protocol.json','g08_solution_freeze.json','g08_oracle_reveal.json','g08_gold_reveal.json','frozen_solver_input.json'] if target=='G08' else ['plan.json','plan_freeze.json','outcome.json']
        if key=='g12-2026-09-05':
            filenames+=['solution.json','solution_freeze.json','heldout_reveal.json','input_inventory.json','publication.json']
        files=[{'path':folder+'/'+name,'sha256':sha((base/name).read_bytes()),'original_utf8':(base/name).read_bytes().decode('utf-8')} for name in filenames]
        result=load(base/('g08_oracle_reveal.json' if target=='G08' else 'outcome.json'))
        if result['status'] not in ('UNCERTAINTY_TOO_LARGE','SOURCE_OR_MEASUREMENT_NOT_QUALIFIED') or result['primary_pass'] is not False:
            raise ValueError('unreviewed outcome type: update export contract explicitly')
        row={'id':key,'target':target,'date':date,'status':result['status'],'primaryPass':False,'sourceUrl':GITHUB+folder,'fitStations':FIT+(['BRAZ00BRA','AREQ00PER'] if target=='G12' else []),'withheldStation':'GOLD00USA','errorM':None,'radiusM':None,'heldoutM':None,'heldoutConfirmed':False,'ecefM':None,'emissionS':None,'freezeUtc':None,'heldoutUtc':None,'oracleUtc':None,'solutionHash':None,'window':None,'supportAvailable':None,'supportRequired':None,'thresholdM':10000,'sources':[]}
        if target=='G08':
            row.update(errorM=result['error_3d_m'],radiusM=result['pre_oracle_total95_radius_m'],heldoutM=result['gold_reveal']['residual_m'],heldoutConfirmed=result['gold_reveal']['status']=='HELD_OUT_RECEIVER_CONFIRMED',ecefM=result['estimated_ecef_at_emission_m'],emissionS=result['emission_seconds_since_gpst_midnight'],freezeUtc=result['freeze_utc'],heldoutUtc=result['gold_reveal']['reveal_utc'],oracleUtc=result['oracle_access_utc'],solutionHash=result['solution_sha256'],window='00:00–00:05 GPST',sources=[{'label':'Orbita di confronto IGS','url':result['oracle_url']}])
            protocol=load(base/'g08_protocol.json')
            row['sources']=[{'label':station+' · osservazioni RF','url':protocol['base_url']+protocol['filename_pattern'].format(station=station)} for station in protocol['fit_stations']+[protocol['withheld_station']]]+row['sources']
        elif key=='g12-2026-09-05':
            solution=load(base/'solution.json');freeze=load(base/'solution_freeze.json')
            if sha((base/'solution.json').read_bytes())!=freeze['solution_sha256'] or freeze['solution_sha256']!=result['solution_sha256']:
                raise ValueError('frozen solution hash mismatch')
            if solution['target']!=target or solution['date_gpst']!=date:
                raise ValueError('frozen event identity mismatch')
            row.update(errorM=result['comparison']['error_3d_m'],radiusM=result['prospective_uncertainty_radius_m'],heldoutM=result['heldout']['residual_m'],heldoutConfirmed=result['heldout']['status']=='HELD_OUT_RECEIVER_CONFIRMED',ecefM=result['comparison']['estimated_ecef_at_emission_m'],emissionS=solution['emission_seconds_since_gpst_midnight'],freezeUtc=freeze['freeze_utc'],heldoutUtc=result['heldout']['reveal_utc'],oracleUtc=result['oracle_access']['access_utc'],solutionHash=freeze['solution_sha256'],window='10:30–10:35 GPST')
            row['sources']=[{'label':r['station']+' · osservazioni RF','url':r['url']} for r in load(base/'input_inventory.json')['receipts']]+[{'label':'Orbita di confronto IGS','url':result['oracle_access']['url']}]
        else:
            row.update(supportAvailable=result['longest_consecutive_support_epochs'],supportRequired=result['required_common_support_epochs'])
            row['sources']=[{'label':r['station']+' · osservazioni RF','url':r['url']} for r in result['observation_receipts']]
        if row['radiusM'] is not None and row['radiusM']<=row['thresholdM']:
            raise ValueError('uncertainty-failure label conflicts with numerical radius')
        if row['freezeUtc'] and not row['freezeUtc']<row['heldoutUtc']<row['oracleUtc']:
            raise ValueError('confirmation order is inconsistent')
        bundle={'schemaVersion':1,'event':dict(row),'scope':'Closed historical evidence dossier; original file bytes recoverable from UTF-8 strings. No raw RF payloads, current positions or new estimates are generated.','files':files}
        blob=(json.dumps(bundle,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8')
        row.update(dossierUrl=f'/evidence/{key}.json',dossierHash=sha(blob))
        rows.append(row);bundles[key]=blob
    return {'schemaVersion':1,'sourceRevision':REVISION,'events':rows},bundles


def export(destination,check=False):
    data,bundles=make_archive()
    files={destination/'app/results.json':(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8')}
    files.update({destination/f'public/evidence/{key}.json':blob for key,blob in bundles.items()})
    for path,blob in files.items():
        if check:
            if not path.exists() or path.read_bytes()!=blob:
                raise ValueError('stale or modified archive export: '+str(path))
        else:
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(blob)
    return len(files)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    print(f'{export(ROOT/"web",args.check)} archive files verified' if args.check else f'{export(ROOT/"web")} archive files generated')
