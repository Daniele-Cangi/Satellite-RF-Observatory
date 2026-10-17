"""IF code/phase, GF phase and MW from the same four raw RF channels.

All raw channels are metres, ordered P1/P2/phase1/phase2. The invertible
transform creates no observations or independent information. A free
ionosphere at every link epoch profiles out GF; retain the marginal IF/MW
covariance, never its covariance conditioned on a supposedly exact GF.
"""
import numpy as np

from .doppler import ALPHA, BETA, F1_HZ, F2_HZ
from .receiver_time import C, cholesky_covariance
from .phase_rates import interval_matrix

RETAINED = [0, 1, 3]


def transform():
    f1,f2 = F1_HZ,F2_HZ
    return np.array([[ALPHA,BETA,0.,0.], [0.,0.,ALPHA,BETA],
        [0.,0.,1.,-1.], [-f1/(f1+f2),-f2/(f1+f2),f1/(f1-f2),-f2/(f1-f2)]])


def values(fields, *, code1_change_m=0.):
    """RINEX P1/P2 metres and L1/L2 cycles, after caller identity admission."""
    raw = np.asarray(fields,float)*np.array([1.,1.,C/F1_HZ,C/F2_HZ])
    if raw.shape!=(4,) or not np.isfinite(raw).all() or not np.isfinite(code1_change_m):
        raise ValueError('four finite admitted code/phase fields required')
    raw[0] += code1_change_m
    return transform()@raw


def covariance(raw_covariance):
    cholesky_covariance(raw_covariance,4)
    t = transform()
    result = t@np.asarray(raw_covariance,float)@t.T
    return (result+result.T)/2


def assumed_endpoint_covariance(*, code_correlation=0., code_sigma_m=20., phase_sigma_m=.02):
    """Explicit equal-band weighting scenario preserving historical IF sigmas.

    Neither equal band variances nor correlation is inferred from IF floors or
    residuals. Distinct raw covariance scenarios can have identical IF floors.
    Endpoint, station and link independence remain unqualified assumptions.
    """
    if (not np.isfinite([code_correlation,code_sigma_m,phase_sigma_m]).all()
            or abs(code_correlation)>=1 or min(code_sigma_m,phase_sigma_m)<=0):
        raise ValueError('positive IF scales and strict code correlation required')
    c = np.zeros((4,4))
    factor = ALPHA**2+BETA**2
    c[:2,:2] = code_sigma_m**2/(factor+2*ALPHA*BETA*code_correlation)*np.array(
        [[1.,code_correlation],[code_correlation,1.]])
    c[2:,2:] = phase_sigma_m**2/factor*np.eye(2)
    return c


def rf_covariance(tags, station_count, raw_covariance):
    """Joint covariance of IF code, IF rates, MW rates; epoch/site ordering.

    Removing free GF/ionosphere uses a principal submatrix, equivalent to
    profiling its unconstrained level in the four-channel likelihood.
    """
    own = covariance(raw_covariance)[np.ix_(RETAINED,RETAINED)]
    n = station_count
    count = len(tags)*n
    difference = interval_matrix(tags,n)
    select = [np.kron(np.eye(count),np.eye(3)[i:i+1]) for i in range(3)]
    mapping = np.vstack([select[0],difference@select[1],difference@select[2]])
    result = mapping@np.kron(np.eye(count),own)@mapping.T
    return (result+result.T)/2
