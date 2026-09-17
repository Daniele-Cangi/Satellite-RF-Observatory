"""Native CODE 3.04 clocks; retain source headers, never relabel as rapid/2.00."""
import numpy as np
from .precise_reference_model import time_of

LABELS = ('RINEX VERSION / TYPE','PGM / RUN BY / DATE','COMMENT','TIME SYSTEM ID',
          'ANALYSIS CENTER','# OF CLK REF','ANALYSIS CLK REF','END OF HEADER',
          'SYS / PCVS APPLIED','SYS / DCBS APPLIED')


def header_field(line):
    # CODE retains some legacy padding alongside the 65-column 3.04 fields.
    # Only these explicit labels, starting at column 61..66, are recognized.
    for label in LABELS:
        if line.rstrip().endswith(label):
            start = len(line.rstrip())-len(label)
            if 60 <= start <= 65:
                return label,line[:start].strip()
    return None,None


def extract_clock(text, refs, target, day, start, end):
    if not refs or len(refs) != len(set(refs)) or target in refs or not 0 <= start < end < 86400:
        raise ValueError('invalid clock selection')
    lines = text.splitlines()
    if not lines or lines[0][:4] != '3.04' or lines[0][21] != 'C':
        raise ValueError('native RINEX clock 3.04 required')
    stops = [i for i,line in enumerate(lines) if header_field(line)[0]=='END OF HEADER']
    if len(stops) != 1:
        raise ValueError('one clock header required')
    stop = stops[0]
    selected = [line for line in lines[:stop+1] if header_field(line)[0] in LABELS
                and (header_field(line)[0] not in ('SYS / PCVS APPLIED','SYS / DCBS APPLIED') or line.startswith('G'))]
    for line in lines[stop+1:]:
        if not line.startswith('AS ') or line[3:12].strip() not in refs:
            continue
        fields = line.split()
        t = time_of(fields[2:8],day)
        if start <= t <= end:
            selected.append(line)
    return '\n'.join(selected)+'\n'


def parse_clock(text,refs,target,day,start,end):
    if extract_clock(text,refs,target,day,start,end) != text:
        raise ValueError('unadmitted clock data')
    fields = [header_field(line) for line in text.splitlines() if not line.startswith('AS ')]
    def values(label):
        return [value for key,value in fields if key == label]
    if values('TIME SYSTEM ID') != ['GPS'] or len(values('ANALYSIS CENTER')) != 1 or not values('ANALYSIS CENTER')[0].startswith('COD '):
        raise ValueError('GPS CODE clock required')
    pcv, bias = values('SYS / PCVS APPLIED'), values('SYS / DCBS APPLIED')
    if len(pcv) != 1 or pcv[0].split()[-1:] != ['IGS20_2425']:
        raise ValueError('clock antenna convention differs')
    if len(bias) != 1 or bias[0].split()[3:] != ['CODE.BIA','@','ftp.aiub.unibe.ch/CODE/']:
        raise ValueError('paired CODE.BIA convention required')
    if not any('consistent with phase and C1W/C2W code data' in s for s in values('COMMENT')):
        raise ValueError('explicit final signal convention required')
    result = {sv:{} for sv in refs}
    for line in text.splitlines():
        if not line.startswith('AS '):
            continue
        f = line.split()
        if len(f) < 9 or f[8] not in ('1','2') or len(f) != 9+int(f[8]):
            raise ValueError('only bias and optional sigma supported')
        sv,t = f[1],time_of(f[2:8],day)
        value = float(f[9].replace('D','E'))
        sigma = float(f[10].replace('D','E')) if len(f)==11 else None
        if not np.isfinite(value) or (sigma is not None and (not np.isfinite(sigma) or sigma < 0)):
            raise ValueError('invalid clock value')
        if t % 30 or (result[sv] and t <= max(result[sv])):
            raise ValueError('duplicate/unordered/off-grid clock')
        result[sv][t] = {'clock_s':value,'reported_sigma_s':sigma}
    expected = list(range(start,end+1,30))
    if any(list(samples) != expected for samples in result.values()):
        raise ValueError('incomplete native clock window')
    return result
