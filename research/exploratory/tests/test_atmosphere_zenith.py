import math

import numpy as np
import pytest

from positioning.calibration import troposphere
from research.exploratory import atmosphere_zenith as study


@pytest.mark.parametrize('elevation', [10, 15, 30, 60, 90])
def test_legacy_mapping_matches_production(elevation):
    station = np.array([6378137.0, 0., 0.])
    angle = math.radians(elevation)
    satellite = station + 2e7 * np.array([math.sin(angle), math.cos(angle), 0.])
    delay, actual_elevation = troposphere(station, satellite)
    assert actual_elevation == pytest.approx(elevation)
    assert delay == pytest.approx(sum(study.simple_zenith(0)) * study.mapping(elevation))


@pytest.mark.parametrize('value', [float('nan'), float('inf'), 9, 91])
def test_mapping_invalid(value):
    with pytest.raises(ValueError):
        study.mapping(value)


@pytest.mark.parametrize('defect', ['duplicate', 'date', 'nan', 'columns', 'negative_wet'])
def test_weather_rejects_invalid(defect):
    row = 'ALGO 61286.00 .0012 .0005 2.3 .1 1000 20 15\n'
    data = {'duplicate': row + row, 'date': row.replace('61286', '61287'),
            'nan': row.replace('2.3', 'nan'), 'columns': row + 'BROKEN\n',
            'negative_wet': row.replace(' .1 ', ' -.1 ')}[defect]
    with pytest.raises(ValueError):
        study.parse_weather(data.encode(), 61286)


def test_column_units_and_missing_remain_explicit():
    data = study.parse_weather(b'ALGO 61286.25 .0012 .0005 2.3 .1234 1000 20 15\n', 61286)
    assert data[('ALGO', 61286.25)] == (2.3, .1234)
    assert ('ALGO', 61286) not in data
    assert study.simple_zenith(0) == (2.3, .1)
    assert study.simple_zenith(2000)[0] < 2.3
    assert study.mapping(90) == pytest.approx(1)


@pytest.mark.parametrize('data', [b'ALGO 91 0 0', b'ALGO 0 0 nan', b'ALGO 0 0 0\nALGO 0 0 0'])
def test_invalid_coordinates(data):
    with pytest.raises(ValueError):
        study.parse_coordinates(data)
