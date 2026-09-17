"""Stricter metadata boundary; preserves the executed v1 audit and result."""
import argparse
from datetime import datetime
import hashlib
import io
import json
import math
from pathlib import Path
from urllib.parse import urlsplit
from . import code_convention_audit as v1


def strict_json(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('duplicate JSON key: '+key)
            result[key]=value
        return result
    def bad(value):raise ValueError('non-finite JSON constant: '+value)
    def finite(value):
        number=float(value)
        if not math.isfinite(number):raise ValueError('non-finite JSON number')
        return number
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad,parse_float=finite)


def sp3_header(lines,date):
    def validated():
        for line in lines:
            if line.startswith('* '):
                fields=line.split()
                if len(fields)!=7:raise ValueError('invalid first SP3 epoch')
                try:
                    year,month,day,hour,minute=map(int,fields[1:6])
                    second=float(fields[6])
                    epoch=datetime(year,month,day,hour,minute)
                except (ValueError,OverflowError) as e:raise ValueError('invalid first SP3 epoch') from e
                if epoch.date().isoformat()!=date or not 0<=second<60:
                    raise ValueError('first SP3 epoch outside declared day or invalid time')
                yield line
                return
            yield line
    return v1.sp3_header(validated(),date)


def validate_urls(pair):
    stamp=datetime.fromisoformat(pair['date_gpst']).strftime('%Y%j')
    for key,suffix in [('orbit','05M_ORB.SP3.gz'),('clock','30S_CLK.CLK.gz')]:
        expected='COD0OPSRAP_'+stamp+'0000_01D_'+suffix
        url=urlsplit(pair[key]['source_url'])
        if url.scheme!='https' or url.hostname!='igs.bkg.bund.de' or url.query or url.fragment or url.path.rsplit('/',1)[-1]!=expected:
            raise ValueError('paired '+key+' source identity differs')


def run():
    # Each buffer is rechecked against the immutable v1 digest before parsing.
    # Any mutation between this validation and v1 replay is rejected by v1 pins.
    receipt=strict_json(v1.checked(v1.RECEIPT,v1.RECEIPT_SHA))
    for tag in ('g14','g12'):
        path=f'research/exploratory/inputs/timed_reference_products/{tag}/receipt.json'
        pair=strict_json(v1.checked(v1.ROOT/path,receipt['paired_receipt_sha256'][path]))
        validate_urls(pair)
        orbit=v1.checked(v1.ROOT/Path(path).parent/'reference_orbit.txt',pair['orbit']['extract_sha256'])
        sp3_header(io.StringIO(orbit.decode('ascii')),pair['date_gpst'])
    result=v1.run()
    result['schema']='code-convention-audit-v2'
    result['source_sha256']={'research/exploratory/code_convention_audit.py':result['source_sha256'],
                             'research/exploratory/code_convention_audit_v2.py':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    result['additional_checks']=['strict JSON receipts','first SP3 epoch date/time','paired orbit/clock filename and source host']
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path)
    a=p.parse_args();result=run()
    with a.output.open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
