"""Synthetic support audit only: no real target observations or ephemerides."""
import json
from itertools import product
import numpy as np
from positioning.calibration import C
from positioning.solver import interpolate_event


def audit():
    times = np.arange(-600., 601., 30.)
    roots = np.arange(7)
    stations = np.column_stack((np.full(7, 6371000.), 1000.*roots, -1000.*roots))
    clocks = np.broadcast_to((roots-3)[:, None]*25000., (7, 41))
    cases = []
    for speed, acceleration, amplitude in product((-3000., 0., 3000.), (-.5, 0., .5), (0., 1e6)):
        def curve(u):
            return 2e7+roots[:, None]*1.5e6+(speed+roots[:, None]*80.)*u+.5*acceleration*u*u+amplitude*np.sin(u/3000.+roots[:, None]*.2)
        tags = np.broadcast_to(times, clocks.shape).copy()
        for _ in range(8):
            codes = curve(tags)+clocks
            tags = times-codes/C
        codes = curve(tags)+clocks
        differences=[]; errors=[]; controls=[]; edge_margins=[]; results=[]
        for count in (7, 11, 41):
            offset=(41-count)//2
            window=slice(offset, offset+count)
            cubic=interpolate_event(codes[:,window],clocks[:,window],stations,times_s=times[window])
            results.append(cubic['z'])
            quintic=interpolate_event(codes[:,window],clocks[:,window],stations,u0=cubic['u0'],degree=5,times_s=times[window])
            expected=curve(np.full((7,1),cubic['u0']))[:,0]
            errors.append(float(max(abs(cubic['z']-expected))))
            controls.append(float(max(abs(cubic['z']-quintic['z']))))
            sample_tags=times[window]-codes[:,window]/C
            edge_margins.append(float(min(np.min(cubic['u0']-sample_tags[:,0]),np.min(sample_tags[:,-1]-cubic['u0']))))
            if count==7:
                baseline=cubic['z']
            differences.append(float(max(abs(cubic['z']-baseline))))
        assert max(differences)<1e-6
        cases.append({'speed_m_s':speed,'acceleration_m_s2':acceleration,'sine_amplitude_m':amplitude,'sample_counts':[7,11,41],'cubic_error_m':errors,'cubic_quintic_difference_m':controls,'difference_from_seven_samples_m':differences,'minimum_edge_margin_s':edge_margins,'difference_11_vs_41_m':float(max(abs(results[1]-results[2])))})
    return {'kind':'synthetic dependency audit, not target prediction or uncertainty validation','cases':cases,'maximum_11_vs_41_difference_m':max(c['difference_11_vs_41_m'] for c in cases),'maximum_11_sample_cubic_error_m':max(c['cubic_error_m'][1] for c in cases),'maximum_11_sample_control_difference_m':max(c['cubic_quintic_difference_m'][1] for c in cases),'rule':'Eleven samples spanning 300 seconds retain the six-node control and two additional epochs at each edge relative to seven samples. Actual monotonicity, bracketing and <=2 m control remain mandatory. No orbital radius, speed or dynamics constraint enters the real solver.'}


if __name__=='__main__':
    print(json.dumps(audit(), indent=2, allow_nan=False))
