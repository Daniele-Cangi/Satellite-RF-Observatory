"""Compile original TU Wien grid routine and compare every predeclared case."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

import numpy as np

from positioning.calibration import geodetic
from . import vmf3_grid_model as model
from .erp_polar_bound import pinned, strict_json


def run(compiler, work):
    buffers, receipt = model.read_inputs()
    weather = model.WeatherGrid(buffers)
    work.mkdir(parents=True, exist_ok=True)
    for name, raw in buffers.items():
        if name.startswith('2026/') or name == 'orography_ell_1x1':
            path = work / name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(raw)
    executable = work / 'vmf3_benchmark.exe'
    command = [str(compiler), '-O2', '-ffree-line-length-none', '-fcheck=all',
               '-I'+str(model.INPUTS.resolve()), str((model.INPUTS/'driver.f90').resolve()), '-o', str(executable.resolve())]
    subprocess.run(command, cwd=work, check=True, capture_output=True, text=True)
    cases = []
    for tag, mjd, times in [('g14', 61286, (14100, 14400)), ('g12', 61288, (37800, 38100))]:
        name = f'results/{tag}_station_frame_epoch_v1.json'
        frame = strict_json(pinned(model.BASE/name, receipt['prior_sha256'][name]))
        for station in frame['station_models']:
            for index, t in ((0, times[0]), (-1, times[1])):
                lat, lon, h, _ = geodetic(station['positions']['final_transport'][index])
                for el in (10, 30, 90):
                    cases.append({'label': f'{tag}:{station["station"]}:{t}:{el}',
                                  'input': [mjd+(t-18)/86400, math.degrees(lat), math.degrees(lon), float(h), el]})
    # Grid centres, exact NWM times, southern latitude and altitude transport.
    for args in ([61286, 45.5, 281.5, 0, 10], [61286.25, -16.5, 288.5, 2500, 30],
                 [61288.25, 62.5, 245.5, 100, 90], [61288.5, 19.5, 204.5, 4000, 10]):
        cases.append({'label': 'grid_epoch_control', 'input': args})
    stdin = ''.join(' '.join(format(x, '.17g') for x in c['input'])+'\n' for c in cases)
    output = subprocess.run([str(executable.resolve()), str(work.resolve())], input=stdin,
                            capture_output=True, text=True, check=True, timeout=180)
    values = np.array([[float(x) for x in line.split()] for line in output.stdout.splitlines()])
    if values.shape != (len(cases), 4) or not np.isfinite(values).all():
        raise ValueError('incomplete original Fortran output')
    for case, reference in zip(cases, values, strict=True):
        actual = weather.evaluate(*case['input'])
        difference = float(np.max(np.abs(actual-reference)))
        case.update(original_mfh_mfw_zhd_zwd=reference.tolist(), python_mfh_mfw_zhd_zwd=actual.tolist(),
                    max_abs_difference=difference, qualified_1e_10=difference <= 1e-10)
    return {'schema': 'vmf3-benchmark-v1', 'cases': cases, 'case_count': len(cases),
            'qualified_count': sum(c['qualified_1e_10'] for c in cases),
            'source_sha256': {name: hashlib.sha256((model.BASE/name).read_bytes()).hexdigest()
                              for name in ('vmf3_grid_model.py', 'benchmark_vmf3.py', 'inputs/vmf3_grid/driver.f90')},
            'receipt_sha256': model.RECEIPT_SHA,
            'compiler_version': subprocess.check_output([str(compiler), '--version'], text=True).splitlines()[0],
            'scope': 'Numerical agreement with original gridded routine, not measured atmosphere accuracy'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('compiler', type=Path)
    parser.add_argument('work', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    report = run(args.compiler, args.work)
    with args.output.open('x', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(report['qualified_count'], '/', report['case_count'])
