"""Fixed synthetic development experiment; no Internet or RF data acquisition."""
import argparse
import hashlib
import json
from pathlib import Path
import platform

import numpy as np
import scipy

from .model import fit, forecast

TRUTH = {'position':np.array([26e6,2e6,4e6]),'velocity':np.array([-250.,2300.,500.]),
         'acceleration':np.array([-.52,-.04,-.08]),'clock_m':75000.,'clock_rate_m_s':12.}
TIMES = np.arange(-300.,1.,30.)
LAT_LON = [(50,0),(-45,0),(0,60),(0,-55),(35,40),(-30,-35),(15,-10),(-10,45)]


def receiver_positions(clustered=False):
    angles = np.deg2rad(LAT_LON)
    if clustered:
        angles = angles*.025
    lat,lon = angles.T
    return 6371000*np.column_stack([np.cos(lat)*np.cos(lon),np.cos(lat)*np.sin(lon),np.sin(lat)])


def observations(times,stations,*,jerk=None,truth=None):
    """Independent generator, intentionally separate from the fitter's design."""
    truth = TRUTH if truth is None else truth
    jerk = np.zeros(3) if jerk is None else np.asarray(jerk)
    codes,rates,positions,velocities = [],[],[],[]
    for t in times:
        p = truth['position']+t*truth['velocity']+(t*t/2)*truth['acceleration']+(t**3/6)*jerk
        v = truth['velocity']+t*truth['acceleration']+(t*t/2)*jerk
        position_codes,position_rates = [],[]
        for station in stations:
            distance = np.sqrt(sum((float(p[j])-float(station[j]))**2 for j in range(3)))
            radial = sum((p[j]-station[j])*v[j] for j in range(3))/distance
            position_codes.append(distance+truth['clock_m']+t*truth['clock_rate_m_s'])
            position_rates.append(radial+truth['clock_rate_m_s'])
        codes.append(position_codes);rates.append(position_rates)
        positions.append(p);velocities.append(v)
    return tuple(np.array(values) for values in (codes,rates,positions,velocities))


def native(value):
    if isinstance(value,np.ndarray):return value.tolist()
    if isinstance(value,np.generic):return value.item()
    if isinstance(value,dict):return {k:native(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [native(v) for v in value]
    return value


def evaluate(seed,*,clustered=False,quadratic=True,jerk=None,bias=False,noiseless=False):
    stations = receiver_positions(clustered)
    codes,rates,_,_ = observations(TIMES,stations[:7],jerk=jerk)
    rng = np.random.default_rng(seed)
    if not noiseless:
        codes += rng.normal(0,20,codes.shape)
        rates += rng.normal(0,.05,rates.shape)
    if bias:
        codes += np.array([-20,20,-20,20,-20,20,0])[None,:]
        rates += np.array([-.05,.05,-.05,.05,-.05,.05,0])[None,:]
    rows = []
    for include_rate in (False,True):
        row = {'seed':seed,'variant':'code_and_range_rate' if include_rate else 'code_only'}
        try:
            result = fit(TIMES,stations[:7],codes,rates=rates if include_rate else None,quadratic=quadratic)
            row.update({k:v for k,v in result.items() if k not in ('state','covariance')})
            # Freeze predictions in memory before requesting any future/holdout
            # truth from the generator. This is synthetic, not a real blind seal.
            predictions = [forecast(result,t,stations[7]) for t in (0,30,60)]
            truth_codes,truth_rates,truth_positions,truth_velocities = observations([0,30,60],stations[7:],jerk=jerk)
            for i,prediction in enumerate(predictions):
                prediction.update(position_error_m=float(np.linalg.norm(prediction['position_m']-truth_positions[i])),
                                  velocity_error_m_s=float(np.linalg.norm(prediction['velocity_m_s']-truth_velocities[i])),
                                  heldout_code_error_m=prediction['heldout_code_m']-float(truth_codes[i,0]),
                                  heldout_rate_error_m_s=prediction['heldout_rate_m_s']-float(truth_rates[i,0]))
            row['forecasts'] = predictions
        except (ValueError,RuntimeError,np.linalg.LinAlgError) as error:
            row.update(status='FIT_UNAVAILABLE',reason=str(error))
        rows.append(row)
    return rows


def run():
    nominal = [row for seed in range(20260910,20260930) for row in evaluate(seed)]
    noiseless = evaluate(20260910,noiseless=True)
    stress = {
        'clustered_receivers':evaluate(20260910,clustered=True),
        'linear_model_on_accelerated_truth':evaluate(20260910,quadratic=False),
        'unmodelled_jerk':evaluate(20260910,jerk=[-5e-5,1e-4,3e-5]),
        'persistent_station_biases':evaluate(20260910,bias=True),
    }
    summaries = {}
    for variant in ('code_only','code_and_range_rate'):
        rows = [row for row in nominal if row['variant']==variant]
        finite = [row for row in rows if 'forecasts' in row]
        summaries[variant] = {'attempts':len(rows),'finite_fits':len(finite),
            'nominal_model_accepted':sum(row['status']=='NOMINAL_MODEL_ACCEPTED' for row in rows)}
        if finite:
            for key,field,index in [('median_position_error_60s_m','position_error_m',2),
                                    ('median_velocity_radius_0s_m_s','local_velocity_radius95_m_s',0),
                                    ('median_position_radius_60s_m','local_position_radius95_m',2)]:
                summaries[variant][key] = float(np.median([row['forecasts'][index][field] for row in finite]))
    code,joint = summaries['code_only'],summaries['code_and_range_rate']
    complete = code['finite_fits']==joint['finite_fits']==20
    criteria = {
        'all_nominal_fits_finite':complete,
        'noiseless_recovery':all('forecasts' in row and row['forecasts'][0]['position_error_m']<=.1 and row['forecasts'][0]['velocity_error_m_s']<=.001 for row in noiseless),
        'nominal_rank_full':all(row.get('rank')==11 for row in nominal),
        'velocity_radius_at_least_halved':complete and joint['median_velocity_radius_0s_m_s']<=.5*code['median_velocity_radius_0s_m_s'],
        'median_60s_error_not_worse':complete and joint['median_position_error_60s_m']<=code['median_position_error_60s_m'],
        'linear_mismatch_rejected':all(row['status']=='MODEL_REJECTED' for row in stress['linear_model_on_accelerated_truth']),
    }
    root = Path(__file__).resolve().parents[2]
    files = sorted(Path(__file__).parent.glob('*.py'))
    files += [root/'positioning'/name for name in ('solver.py','calibration.py','errors.py')]
    files += [root/'docs/SCIENTIFIC_ROADMAP.md']
    sources = {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    return native({'schema':'synthetic-kinematic-study-v1','scope':'Idealized development simulation only; no RF/Doppler integration, satellite proof or real uncertainty coverage.',
                   'noise_assumptions':{'independent_code_sigma_m':20,'independent_rate_sigma_m_s':.05},
                   'truth':TRUTH,'fit_times_s':TIMES,'station_lat_lon_deg':LAT_LON,
                   'sources_sha256':sources,'environment':{'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__},
                   'criteria':criteria,'nominal_criteria_pass':all(criteria.values()),
                   'summary':summaries,'noiseless':noiseless,'nominal':nominal,'stress':stress})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    report=run()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as handle:
        json.dump(report,handle,indent=2,allow_nan=False);handle.write('\n')
    print(json.dumps({'criteria':report['criteria'],'summary':report['summary']},indent=2))
