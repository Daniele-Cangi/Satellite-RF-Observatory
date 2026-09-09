"""Read frozen evidence and covariance only; never reconstruct a closed event."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scripts.export_positioning_archive import ROOT, make_archive


def report():
    archive,_=make_archive()
    rows=[]
    for event in archive['events']:
        row={key:event[key] for key in ('id','status','errorM','radiusM','sourceRevision','solutionHash')}
        row['local_uncertainty_diagnosis']=None
        folders={'g12-2026-09-05':'positioning_g12_doy248','g14-2026-09-03':'positioning_g14_doy246_network'}
        if event['id'] in folders:
            path=ROOT/'experiments'/folders[event['id']]/'solution.json'
            raw=path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=event['solutionHash']:
                raise ValueError('frozen solution changed')
            solution=json.loads(raw)
            covariance=np.array(solution['fit']['covariance'])[:3,:3]
            eigenvalues,eigenvectors=np.linalg.eigh(covariance)
            radial=np.array(solution['xyz_m']);radial=radial/np.linalg.norm(radial)
            uncertainty=solution['uncertainty']
            row['local_uncertainty_diagnosis']={
                'statistical_extent_m':uncertainty['statistical_95_radius_m'],
                'sampled_bias_displacement_m':uncertainty['bias_displacement_max_m'],
                'margin':uncertainty['margin'],
                'local_principal_1sigma_m':np.sqrt(eigenvalues).tolist(),
                'weakest_axis_geocentric_alignment':float(abs(eigenvectors[:,-1]@radial)),
                'local_axis_ratio':float(np.sqrt(eigenvalues[-1]/eigenvalues[0])),
                'effective_code_sigma_m':solution['effective_code_sigma_m'],
            }
        elif event['id']=='g08-2026-09-06':
            row['diagnostic_note']='Frozen web evidence contains no full solution covariance; no reconstruction or invented decomposition.'
        else:
            row['diagnostic_note']='No position was estimated; no numerical position covariance exists.'
        rows.append(row)
    return {'schema':'frozen-position-diagnosis-v1',
            'scope':'Read-only development diagnosis of already revealed events; heterogeneous protocols, no success-rate or causal error-source attribution.',
            'events':rows}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path)
    args=parser.parse_args();document=report()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as handle:
        json.dump(document,handle,indent=2,allow_nan=False);handle.write('\n')
    print(json.dumps(document,indent=2))
