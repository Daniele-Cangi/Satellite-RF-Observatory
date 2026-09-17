import json
import math

import numpy as np
import pytest

from research.exploratory import vmf3_grid_model as model


@pytest.fixture(scope='module')
def weather():
    return model.WeatherGrid(model.read_inputs()[0])


def test_original_fortran_benchmarks(weather):
    report = json.loads((model.BASE/'results/vmf3_benchmark_v1.json').read_bytes())
    assert report['qualified_count'] == report['case_count'] == 88
    for case in report['cases']:
        assert weather.evaluate(*case['input']) == pytest.approx(case['original_mfh_mfw_zhd_zwd'], abs=1e-10, rel=0)


def test_height_transfer_identity_and_sign():
    dry, wet = model.height_delays(2.3, .2, np.array([100.]), 100., .5)
    assert dry == pytest.approx([2.3])
    assert wet == pytest.approx([.2])
    dry, wet = model.height_delays(2.3, .2, np.array([100.]), 1100., .5)
    assert 0 < dry[0] < 2.3
    assert wet == pytest.approx([.2*math.exp(-.5)])


def test_mapping_zenith_and_interpolation(weather):
    left = weather.evaluate(61286, 45.9558, -78.0714, 201.1, 90)
    right = weather.evaluate(61286.25, 45.9558, -78.0714, 201.1, 90)
    middle = weather.evaluate(61286.125, 45.9558, -78.0714, 201.1, 90)
    assert left[:2] == pytest.approx([1, 1], abs=1e-14)
    assert middle[2:] == pytest.approx((left[2:]+right[2:])/2, abs=1e-12)
    low = weather.evaluate(61286.125, 45.9558, -78.0714, 201.1, 10)
    assert np.all(low[:2] > 5)
    assert low[2:] == pytest.approx(middle[2:])


@pytest.mark.parametrize('index,value', [(0, 61285.99), (0, 61287), (1, 90), (2, 0), (3, 10000), (4, 4), (4, 91), (0, float('nan'))])
def test_unsupported_domain_rejected(weather, index, value):
    args = [61286.125, 45, -78, 200, 30]
    args[index] = value
    with pytest.raises(ValueError):
        weather.evaluate(*args)


@pytest.mark.parametrize('defect', ['epoch', 'units', 'coordinates', 'nan'])
def test_grid_contract_rejects_changes(defect):
    buffers, _ = model.read_inputs()
    key = '2026/VMF3_20260903.H00'
    old, new = {'epoch': (b'2026 09 03 00 00', b'2026 09 04 00 00'),
                'units': (b'1.e+00', b'1.e-03'),
                'coordinates': (b' 89.5    0.5', b' 88.5    0.5'),
                'nan': (b'0.00120849', b'       nan')}[defect]
    buffers[key] = buffers[key].replace(old, new, 1)
    with pytest.raises(ValueError):
        model.WeatherGrid(buffers)
