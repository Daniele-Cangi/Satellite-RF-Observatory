"""Structural availability and distinct phase-interval observable checks."""
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest

from research.kinematic.doppler import ALPHA, BETA, F1_HZ, F2_HZ
from research.kinematic.phase_rates import interval_matrix, predict_interval_rate, reference_phase_rates
from research.kinematic.physical_source_study import TAGS, evaluate, fixture_rows
from research.kinematic.physical_sources import inspect_header, neutral_delay_basis
from research.kinematic.receiver_time import C
from research.kinematic.reference_fixture import REFERENCES, TARGET, independent_code


@pytest.fixture
def data():
    return fixture_rows(), .01**2*np.eye(2*len(TAGS)*4)


def test_existing_header_is_not_a_doppler_or_qualification_claim():
    root = Path(__file__).resolve().parents[3]
    header = json.loads((root/'positioning/tests/fixtures/gold_header.json').read_text())['header']
    facts = inspect_header(header)
    assert facts['phase_difference_candidate']
    assert not facts['required_doppler_declared'] and not facts['real_rf_qualified']
    assert facts['missing_doppler_fields'] == ['D1C', 'D2W']
    assert inspect_header(None)['status'] == 'HEADER_UNAVAILABLE'
    damaged = deepcopy(header)
    damaged['SYS / # / OBS TYPES'] = ['G    2 L1C']
    with pytest.raises(ValueError):
        inspect_header(damaged)


def test_quantized_reference_phase_increments_match_independent_paths(data):
    rows, cov = data
    result = evaluate(rows, cov)
    path = np.array([[independent_code(t, i) for i in range(4)] for t in TAGS])
    expected = np.diff(path, axis=0)/np.diff(TAGS)[:, None]
    np.testing.assert_allclose(result['mean_phase_rate_m_s'], expected, atol=5e-5, rtol=0)
    assert result['status'] == 'REFERENCE_PHASE_RATE_AVAILABLE' and not result['real_rf_qualified']


def test_constant_band_ambiguities_cancel(data):
    rows, cov = data
    baseline = evaluate(rows, cov)
    for row in rows:
        if row['satellite'] in REFERENCES and row.get('epoch_flag') == 0:
            for name, delta in [('L1C', 3000), ('L2W', -5000)]:
                value = float(row['fields'][name][:14])+delta
                row['fields'][name] = f'{value:14.3f}0 '
    shifted = evaluate(rows, cov)
    np.testing.assert_allclose(shifted['mean_phase_rate_m_s'], baseline['mean_phase_rate_m_s'], atol=2e-9, rtol=0)


def test_difference_covariance_has_shared_endpoint_anticorrelation(data):
    rows, cov = data
    result = evaluate(rows, cov)
    expected_variance = 2*.01**2*((ALPHA*C/F1_HZ)**2+(BETA*C/F2_HZ)**2)/30**2
    out = result['covariance_rate']
    np.testing.assert_allclose(np.diag(out), expected_variance)
    assert out[0, 4] == pytest.approx(-expected_variance/2)
    assert out[0, 8] == 0 and out[0, 1] == 0


def test_common_ambiguity_noise_cancels_in_transformation(data):
    rows, cov = data
    nominal = evaluate(rows, cov)
    mode = np.tile([1., 0., 0., 0., 0., 0., 0., 0.], len(TAGS))
    correlated = evaluate(rows, cov+np.outer(mode, mode))
    np.testing.assert_allclose(correlated['covariance_rate'], nominal['covariance_rate'], atol=1e-16)


@pytest.mark.parametrize('kind', ['slip1', 'slip2', 'halfcycle', 'missing_phase', 'gap', 'reset', 'nonfinite'])
def test_reported_discontinuities_reject_entire_arc(data, kind):
    rows, cov = data
    row = rows[20]
    if kind == 'gap': del rows[20]
    elif kind == 'reset': row['epoch_flag'] = 1
    elif kind == 'missing_phase': del row['fields']['L2W']
    elif kind == 'nonfinite': row['fields']['L1C'] = f'{"nan":>14}0 '
    else:
        name = 'L2W' if kind == 'slip2' else 'L1C'
        row['fields'][name] = row['fields'][name][:14]+('2' if kind == 'halfcycle' else '1')+' '
    result = evaluate(rows, cov)
    assert result['status'] == 'REFERENCE_PHASE_WINDOW_REJECTED'
    assert 'mean_phase_rate_m_s' not in result


def test_target_and_future_payloads_not_decoded_or_hashed(data):
    rows, cov = data
    baseline = evaluate(rows, cov)
    rows[-2]['tag_s'] = object()
    rows[-2]['fields'] = object()
    rows[-1]['fields'] = object()
    changed = evaluate(rows, cov)
    assert baseline['admitted_phase_sha256'] == changed['admitted_phase_sha256']
    np.testing.assert_array_equal(baseline['mean_phase_rate_m_s'], changed['mean_phase_rate_m_s'])
    with pytest.raises(ValueError, match='non-target'):
        reference_phase_rates(rows, target=TARGET, references=(*REFERENCES[:3], TARGET), tags_s=TAGS, phase_covariance=cov)


def test_mean_rate_is_neither_end_nor_midpoint_instantaneous_rate():
    tags = np.array([0., 30., 60.])
    jerk = 1e-4
    path = (200.+10*tags+jerk*tags**3/6)[:, None]
    rate = predict_interval_rate(path, tags, 1)[:, 0]
    middle = (tags[1:]+tags[:-1])/2
    np.testing.assert_allclose(rate-(10+jerk*middle**2/2), jerk*30**2/24, atol=1e-12)
    assert np.max(abs(rate-(10+jerk*tags[1:]**2/2))) > .01


def test_neutral_covariance_is_shared_across_references_and_time(data):
    rows, cov = data
    e = np.array([15., 30., 50., 75.])[None, :]+(TAGS-TAGS[0])[:, None]*.01
    basis = neutral_delay_basis(TAGS, e)
    zin = np.diag([.05**2, 1e-4**2])
    raw = np.repeat(basis, 2, axis=0)*np.tile([F1_HZ/C, F2_HZ/C], len(basis))[:, None]
    result = evaluate(rows, cov+raw@zin@raw.T)
    nominal = evaluate(rows, cov)
    rate_basis = interval_matrix(TAGS, 4)@basis
    expected = rate_basis@zin@rate_basis.T
    np.testing.assert_allclose(result['covariance_rate']-nominal['covariance_rate'], expected, atol=1e-14)
    assert abs(expected[0, 1]) > 1e-9
    with pytest.raises(ValueError):
        neutral_delay_basis(TAGS, np.full((len(TAGS), 4), 9.))


@pytest.mark.parametrize('kind', ['duplicate', 'offgrid', 'covariance'])
def test_malformed_phase_input_rejected(data, kind):
    rows, cov = data
    if kind == 'duplicate': rows.append(rows[0])
    elif kind == 'offgrid': rows[0]['tag_s'] += .5
    else: cov[0, 0] = -1
    with pytest.raises(ValueError):
        evaluate(rows, cov)
