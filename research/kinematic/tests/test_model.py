import numpy as np
import pytest

from positioning.errors import ScientificRejection
from research.kinematic.model import design,fit,forecast
from research.kinematic.synthetic import TRUTH,TIMES,receiver_positions,observations


@pytest.mark.parametrize('with_rate',[False,True])
def test_noiseless_recovery_and_unseen_time_receiver(with_rate):
    stations=receiver_positions()
    codes,rates,_,_=observations(TIMES,stations[:7])
    result=fit(TIMES,stations[:7],codes,rates=rates if with_rate else None)
    prediction=forecast(result,60,stations[7])
    truth_code,truth_rate,truth_position,truth_velocity=observations([60],stations[7:])
    assert np.linalg.norm(prediction['position_m']-truth_position[0])<.1
    assert np.linalg.norm(prediction['velocity_m_s']-truth_velocity[0])<.001
    assert abs(prediction['heldout_code_m']-truth_code[0,0])<.1
    assert abs(prediction['heldout_rate_m_s']-truth_rate[0,0])<.001
    assert result['rank']==11


def test_analytic_jacobian_and_rate_as_time_derivative():
    stations=receiver_positions()[:7]
    state=np.r_[TRUTH['position'],TRUTH['velocity'],TRUTH['acceleration'],75000.,12.]
    _,_,code_jac,rate_jac=design(state,[-120.,0.],stations)
    steps=[10.]*3+[.01]*3+[.0001]*3+[10.,.01]
    for index,step in enumerate(steps):
        delta=np.eye(11)[index]*step
        plus=design(state+delta,[-120.,0.],stations)
        minus=design(state-delta,[-120.,0.],stations)
        np.testing.assert_allclose((plus[0]-minus[0])/(2*step),code_jac[:,:,index],atol=5e-5,rtol=1e-5)
        np.testing.assert_allclose((plus[1]-minus[1])/(2*step),rate_jac[:,:,index],atol=1e-6,rtol=1e-5)
    at_time=design(state,[-.01,0.,.01],stations)
    np.testing.assert_allclose((at_time[0][2]-at_time[0][0])/.02,at_time[1][1],atol=1e-5)


def test_common_clock_shift_does_not_become_satellite_motion():
    stations=receiver_positions()[:7]
    codes,rates,_,_=observations(TIMES,stations)
    shifted=codes+1e6+17*TIMES[:,None]
    result=fit(TIMES,stations,shifted,rates=rates+17)
    np.testing.assert_allclose(result['state'][:3],TRUTH['position'],atol=.1)
    np.testing.assert_allclose(result['state'][3:6],TRUTH['velocity'],atol=.001)
    np.testing.assert_allclose(result['state'][9:],[1075000.,29.],atol=.1)


def test_acceleration_cannot_be_silently_absorbed_by_linear_motion():
    stations=receiver_positions()[:7]
    codes,rates,_,_=observations(TIMES,stations)
    result=fit(TIMES,stations,codes,rates=rates,quadratic=False)
    assert result['status']=='MODEL_REJECTED'


def test_receiver_count_does_not_rescue_degenerate_geometry():
    stations=np.repeat(receiver_positions()[:1],7,axis=0)
    codes,rates,_,_=observations(TIMES,stations)
    with pytest.raises((ValueError,ScientificRejection),match='rank deficient'):
        fit(TIMES,stations,codes,rates=rates)


def test_input_units_shapes_and_nonfinite_values_are_checked():
    stations=receiver_positions()[:7]
    codes,rates,_,_=observations(TIMES,stations)
    with pytest.raises(ValueError,match='noise scales'):
        fit(TIMES,stations,codes,rates=rates,rate_sigma_m_s=0)
    rates[0,0]=np.nan
    with pytest.raises(ValueError,match='rate observations'):
        fit(TIMES,stations,codes,rates=rates)
