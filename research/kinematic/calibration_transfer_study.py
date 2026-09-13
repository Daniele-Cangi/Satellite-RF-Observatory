"""Deterministic, synthetic calibration-transfer counterexamples; no RF access."""
import hashlib
import json
from pathlib import Path

import numpy as np

from .calibration_transfer import operators, propagate, residual_blind_modes


def study():
    # Invented four-reference / eleven-endpoint clock-offset and drift model.
    tags = np.repeat(np.arange(-150., 151., 30.), 4)
    a = np.column_stack([np.ones(len(tags)), tags])
    # Rows are central code [m] and clock contribution to phase rate [m/s].
    op = operators(a, np.eye(2), np.eye(len(tags)))
    examples = []
    for name, coefficients, target_error in (
        ('reference_only_offset', [100., 0.], [0., 0.]),
        ('reference_only_drift', [0., .1], [0., 0.]),
        ('shared_receiver_offset_and_drift', [100., .1], [100., .1]),
    ):
        error = a@coefficients
        corrected = op['joint_to_target']@np.r_[error, target_error]
        examples.append({'case': name,
                         'reference_residual_max_m': float(np.max(np.abs(op['reference_residual']@error))),
                         'corrected_target_code_error_m': float(corrected[0]),
                         'corrected_target_phase_rate_error_m_s': float(corrected[1])})
    blind = residual_blind_modes(a, op['reference_to_target'])
    # The same marginal reference and target variances with different coupling.
    one = operators(np.ones((4, 1)), np.ones((1, 1)), np.eye(4))
    stochastic = []
    for correlation in (-1., 0., 1.):
        joint = np.eye(5)
        joint[:4, :4] += 9.*np.ones((4, 4))
        joint[4, 4] += 9.
        joint[:4, 4] = joint[4, :4] = 9.*correlation
        stochastic.append({'shared_mode_correlation': correlation,
            'corrected_target_variance_m2': float(propagate(one['joint_to_target'], joint)[0, 0]),
            'reference_residual_variance_m2': np.diag(propagate(one['reference_residual'], joint[:4, :4])).tolist()})
    root = Path(__file__).resolve().parents[2]
    sources = ['research/kinematic/calibration_transfer.py',
               'research/kinematic/calibration_transfer_study.py']
    return {'schema': 'calibration-transfer-synthetic-study-v1',
            'sources_sha256': {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in sources},
            'scope': 'Invented local linear observable errors; not real target errors, position errors or physical uncertainty bounds.',
            'real_rf_qualified': False, 'target_orbit_accessed': False,
            'design': {'references': 4, 'tags_s': sorted(set(tags)),
                       'weight_covariance': 'identity in code coordinates',
                       'stochastic_assumptions': '1 m independent noise per observation plus 3 m common reference/target marginal mode; correlation -1, 0, +1. Invented amplitudes.'},
            'deterministic_examples': examples,
            'blind_subspace_dimension': int(blind['reference_error_basis'].shape[1]),
            'blind_residual_max': float(np.max(np.abs(op['reference_residual']@blind['reference_error_basis']))),
            'stochastic_examples': stochastic,
            'conclusion': 'Reference residuals alone cannot bound clock-like reference errors; their target effect depends on shared/differential coupling.',
            'physical_amplitudes_established': False, 'population_coverage_established': False}


if __name__ == '__main__':
    print(json.dumps(study(), indent=2, allow_nan=False))
