"""Read-only, byte-bound audit of paired CODE SP3 and terrestrial ERP headers.
No satellite record, clock value, Earth rotation value or RF observation is parsed.
Product declarations are not validation of physical accuracy or the entire model.
"""
import argparse
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'research/exploratory'
RECEIPT=BASE/'inputs/code_conventions/receipt.json'
RECEIPT_SHA='46e57b9fd4731d7608f6423f8635f180a76536be2eb5269f507b58bf40afa36c'


def checked(path,digest):
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('evidence hash differs: '+str(path))
    return raw


def sp3_header(lines,date):
    header=[]
    for line in lines:
        if line.startswith('* '):break
        if line.startswith(('P','V','EP','EV')):raise ValueError('state record before epoch')
        header.append(line.rstrip())
    else:raise ValueError('SP3 first epoch missing')
    if not header or not header[0].startswith('#dP'):raise ValueError('SP3-d position header required')
    first=header[0].split()
    actual=datetime(int(first[0][3:]),int(first[1]),int(first[2])).date().isoformat()
    if actual!=date or first[-3:]!=['IGc20','FIT','AIUB']:raise ValueError('SP3 date/frame/agency differs')
    stamp=datetime.fromisoformat(date).strftime('%Y-%j')
    if '/* Rapid GNSS orbits and clocks for year-day '+stamp not in header:
        raise ValueError('rapid product declaration missing')
    candidates=[s for s in header if s.startswith('/* PCV:')]
    if len(candidates)!=1:raise ValueError('one model declaration required')
    match=re.fullmatch(r'/\* PCV:(\S+)\s+OL/AL:(\S+)\s+(\S+)\s+([YN])([YN]) ORB:(CoN|CoM|CMB) CLK:(CoN|CoM|CMB|N/A)',candidates[0])
    if match is None:raise ValueError('unsupported model declaration')
    keys=('antenna_model','ocean_model','atmosphere_field','ocean_cmc_flag','atmosphere_cmc_flag','orbit_origin','clock_origin')
    return dict(zip(keys,match.groups()))|{'date':actual,'frame':'IGc20','raw_model_comment':candidates[0]}


def erp_header(raw,date):
    lines=raw.decode('ascii').splitlines()
    if len(lines)<6 or lines[0].strip()!='VERSION 2':raise ValueError('ERP version differs')
    match=re.fullmatch(r'CODE RAPID GNSS ERP INFORMATION FOR \(MIDDLE\) DAY (\d+), (\d{4})\s+.+',lines[1])
    expected=datetime.fromisoformat(date)
    if match is None or (int(match[1]),int(match[2]))!=(expected.timetuple().tm_yday,expected.year):
        raise ValueError('ERP family/day differs')
    models=[s for s in lines if s.startswith('NUTATION MODEL')]
    if len(models)!=1:raise ValueError('one ERP model declaration required')
    match=re.fullmatch(r'NUTATION MODEL\s*:\s*(\S+)\s+SUBDAILY POLE MODEL:\s*(\S+)\s*',models[0])
    if match is None:raise ValueError('ERP model declaration malformed')
    return {'date':date,'nutation_model':match[1],'subdaily_pole_model':match[2],
            'raw_title':lines[1],'raw_model_comment':models[0],
            'mean_pole_model_declared':False,'numeric_eop_values_parsed':False}


def decision(sp3,erp):
    aligned=(sp3['ocean_model']=='FES2014b' and sp3['ocean_cmc_flag']=='Y'
             and sp3['orbit_origin']=='CoN' and sp3['clock_origin']=='CoN')
    return {'ocean_cmc_product_declaration_resolved':aligned,
            'station_cmc_action':'retain CMC:NO local loading; do not add a geocenter translation' if aligned else 'unresolved; no automatic translation',
            'atmospheric_loading_absence_inferred':False,
            'mean_pole_realization_qualified':False,
            'instantaneous_code_eop_reconstructed':False,
            'subdaily_model_required':erp['subdaily_pole_model'],
            'whole_station_model_qualified':False}


def run():
    receipt=json.loads(checked(RECEIPT,RECEIPT_SHA))
    if receipt['schema']!='code-convention-evidence-v1':raise ValueError('receipt schema differs')
    hashes={RECEIPT.relative_to(ROOT).as_posix():RECEIPT_SHA};events=[]
    for tag in ('g14','g12'):
        path=f'research/exploratory/inputs/timed_reference_products/{tag}/receipt.json'
        digest=receipt['paired_receipt_sha256'][path]
        pair=json.loads(checked(ROOT/path,digest));hashes[path]=digest
        if pair['product_family']!='COD0OPSRAP' or pair['target_excluded']!=tag.upper():raise ValueError('paired identity differs')
        date=pair['date_gpst']
        orbit_path=Path(path).parent/'reference_orbit.txt';digest=pair['orbit']['extract_sha256']
        # Hash the restricted archive buffer once, then stop text parsing at its first epoch.
        sp3=sp3_header(io.StringIO(checked(ROOT/orbit_path,digest).decode('ascii')),date)
        hashes[orbit_path.as_posix()]=digest
        if sp3['antenna_model']!=pair['antenna_model'] or sp3['frame']!=pair['frame']:raise ValueError('paired model differs')
        er=receipt['erp_files'][tag];erp=erp_header(checked(ROOT/er['path'],er['sha256']),date)
        hashes[er['path']]=er['sha256']
        basename=datetime.fromisoformat(date).strftime('COD0OPSRAP_%Y%j0000_01D_01D_ERP.ERP.gz')
        if er['url'].rsplit('/',1)[-1]!=basename:raise ValueError('ERP filename differs')
        events.append({'event':tag,'paired_orbit_source':pair['orbit']['source_url'],
                       'paired_clock_source':pair['clock']['source_url'],'erp_source':er['url'],
                       'sp3':sp3,'erp':erp,'decision':decision(sp3,erp)})
    return {'schema':'code-convention-audit-v1','events':events,'input_sha256':hashes,
            'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'scope':'product declarations; not a numerical or physical calibration',
            'target_states_parsed':False,'rf_observations_parsed':False,'eop_values_parsed':False,
            'target_fit_performed':False,'previous_results_modified':False,'production_changed':False,
            'unresolved':['event-specific mean pole realization','DESAI2016 subdaily and other EOP terms',
                          'atmospheric loading declaration and local model','receiver/media response and physical covariance']}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path)
    args=parser.parse_args();result=run()
    with args.output.open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,indent=2);f.write('\n')
