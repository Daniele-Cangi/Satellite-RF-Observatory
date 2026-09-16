"""Build original IERS HARDISP and freeze bounded fit-station OTL products.
Requires gfortran only for preparation; replay/estimation consumes pinned output.
Original IERS/Duncan Agnew software and complete license are in loading_reference.
"""
import argparse
from datetime import datetime,timedelta
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import numpy as np
from .ocean_pole_model import parse_blq
from .verified_station_replay import pinned_bytes

BASE=Path(__file__).parent
INPUTS=BASE/'inputs/ocean_loading'
SOURCE_SHA='cd1146e50dd383f35649d276466b6b98a62aa62932d7af454db00a130686ab42'
BLQ_RECEIPT_SHA='8af8406f224259d4c8e4101d1100aa4aad46b17cfa7f25c9d509af1e8360378a'
EXAMPLES_SHA='eea55eb3cd45b659512459a17561365c79ce4119eca644b8e7afe1c99f89d5eb'


def build(directory):
    compiler=shutil.which('gfortran')
    if compiler is None:raise RuntimeError('gfortran required to prepare ocean model products')
    manifest=json.loads(pinned_bytes(BASE/'loading_reference/sources.json',SOURCE_SHA))
    paths=[]
    for name,item in sorted(manifest.items()):
        path=BASE/'loading_reference'/name;pinned_bytes(path,item['sha256']);paths.append(str(path))
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
    exe=directory/('hardisp.exe' if __import__('os').name=='nt' else 'hardisp')
    subprocess.run([compiler,'-O2','-std=legacy','-o',str(exe)]+paths,check=True,capture_output=True)
    return exe,{'compiler':subprocess.check_output([compiler,'--version'],text=True).splitlines()[0],
                'compiler_flags':['-O2','-std=legacy'],'binary_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),
                'sources':{name:item['sha256'] for name,item in manifest.items()}}


def series(exe,utc,rows,count=11,step=30):
    args=[str(exe),str(utc.year),str(utc.month),str(utc.day),str(utc.hour),str(utc.minute),str(utc.second),str(count),str(step)]
    p=subprocess.run(args,input=rows,text=True,capture_output=True,check=True)
    values=np.array([[float(x) for x in line.split()] for line in p.stdout.splitlines()])
    if values.shape!=(count,3) or not np.all(np.isfinite(values)):raise ValueError('invalid HARDISP result')
    return values


def prepare(build_dir,output):
    output=Path(output)
    blq_receipt=json.loads(pinned_bytes(INPUTS/'blq_receipt.json',BLQ_RECEIPT_SHA))
    blq=pinned_bytes(INPUTS/'fit_stations.BLQ',blq_receipt['extract_sha256'])
    stations,bound=parse_blq(blq.decode('ascii'))
    examples=json.loads(pinned_bytes(INPUTS/'hardisp_examples.json',EXAMPLES_SHA))
    exe,build_info=build(build_dir)
    benchmarks=[]
    for name,example in examples.items():
        actual=series(exe,datetime(2009,6,25,1,10,45),example['six_lines'],24,3600)
        error=float(np.max(np.abs(actual-np.array(example['expected_usw_m']))))
        benchmarks.append({'station':name,'actual_usw_m':actual.tolist(),'published_usw_m':example['expected_usw_m'],
                           'max_abs_difference_m':error,'qualified_2_um':error<=2e-6})
    if not all(b['qualified_2_um'] for b in benchmarks):raise ValueError('HARDISP benchmark mismatch')
    events={}
    for tag,day,start,names in [('g14','2026-09-03',14100,['ALGO','BOGT','DRAO','MKEA','PIE1','STJO','YELL']),
                               ('g12','2026-09-05',37800,['ALGO','DRAO','STJO','YELL','BOGT','BRAZ','AREQ'])]:
        utc=datetime.fromisoformat(day)+timedelta(seconds=start-18)
        events[tag]={'date_gpst':day,'start_utc':utc.isoformat(),'times_gpst_s':list(range(start,start+301,30)),
                     'ocean_usw_m':{name:series(exe,utc,stations[name]['six_lines']).tolist() for name in names}}
    result={'schema':'hardisp-fit-products-v1','events':events,'benchmarks':benchmarks,
            'cmc_applied':False,'cmc_header_phase_free_norm_bound_m':bound,
            'output_resolution_m':1e-6,'target_states_accessed':False}
    payload=(json.dumps(result,indent=2,allow_nan=False)+'\n').encode('utf-8')
    receipt={'schema':'ocean-loading-products-v1','producer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             'model_sha256':hashlib.sha256((BASE/'ocean_pole_model.py').read_bytes()).hexdigest(),
             'source_receipt_sha256':SOURCE_SHA,'blq_receipt_sha256':BLQ_RECEIPT_SHA,'examples_sha256':EXAMPLES_SHA,
             'products_sha256':hashlib.sha256(payload).hexdigest(),'build':build_info,
             'convention':'Original HARDISP 342 harmonics, BLQ positive lags, UTC, output U/S/W metres, CMC:NO',
             'target_states_accessed':False}
    with (output/'hardisp_products.json').open('xb') as f:f.write(payload)
    with (output/'receipt.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(receipt,f,indent=2);f.write('\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('build_dir');p.add_argument('output')
    a=p.parse_args();prepare(a.build_dir,a.output)
