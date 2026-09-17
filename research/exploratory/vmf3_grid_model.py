"""Bounded 1-degree VMF3 grid adapter; equations from TU Wien vmf3_grid.f90.

Full original products are pinned. Polar caps and longitude seam are deliberately
unsupported; all nine admitted sites lie strictly inside this interpolation domain.
"""
from datetime import datetime, timedelta
from functools import lru_cache
import gzip
import hashlib
import io
import math
from pathlib import Path
import re

import numpy as np

from .erp_polar_bound import pinned, strict_json

BASE = Path(__file__).parent
INPUTS = BASE / 'inputs/vmf3_grid'
RECEIPT_SHA = 'c10a99c31b2712619d09c112b2f8df4245f0fc189d6bcb6284d606b5b4f1098f'


def read_inputs():
    receipt = strict_json(pinned(INPUTS / 'receipt.json', RECEIPT_SHA))
    buffers = {}
    for name, item in receipt['sources'].items():
        if 'packed_file' in item:
            raw = gzip.decompress(pinned(INPUTS / item['packed_file'], item['packed_sha256']))
        else:
            raw = pinned(INPUTS / name, item['sha256'])
        if len(raw) != item['bytes'] or hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise ValueError('decompressed product differs')
        buffers[name] = raw
    return buffers, receipt


def coefficients(raw):
    text = raw.decode('utf-8')
    result = {}
    for kind in ('a', 'b'):
        for term in ('bh', 'bw', 'ch', 'cw'):
            name = kind + 'nm_' + term
            pattern = rf'data\({name}_temp\(i\),i=1,455\)\s*&\s*/(.*?)/'
            matches = re.findall(pattern, text, re.S)
            if len(matches) != 1:
                raise ValueError('missing or duplicate VMF3 harmonic table')
            values = [float(x.strip().replace('d', 'e')) for x in matches[0].replace('&', '').split(',')]
            array = np.array(values)
            if array.shape != (455,) or not np.isfinite(array).all():
                raise ValueError('invalid VMF3 harmonic coefficients')
            result[name] = array.reshape(91, 5)
    return result


def continued_fraction(a, b, c, sine):
    return (1 + a / (1 + b / (1 + c))) / (sine + a / (sine + b / (sine + c)))


def height_delays(zhd, zwd, grid_height, height, latitude):
    delta = height - grid_height
    factor = 1 - .0000226 * delta
    if np.any(factor <= 0):
        raise ValueError('invalid pressure height transfer')
    gravity = 1 - .00266 * math.cos(2 * latitude)
    dry = zhd * (gravity - .00000028 * grid_height) * factor ** 5.225 / (gravity - .00000028 * height)
    wet = zwd * np.exp(-delta / 2000)
    return dry, wet


class WeatherGrid:
    def __init__(self, buffers):
        self.coefficients = coefficients(buffers['vmf3_grid.f90'])
        self.height = np.loadtxt(io.BytesIO(buffers['orography_ell_1x1']))
        if self.height.shape != (64800,) or not np.isfinite(self.height).all():
            raise ValueError('invalid 1-degree orography')
        self.height = self.height.reshape(180, 360)
        expected_lat = np.repeat(np.arange(89.5, -90, -1), 360)
        expected_lon = np.tile(np.arange(.5, 360, 1), 180)
        self.grids = {}
        for name, raw in buffers.items():
            if not name.startswith('2026/VMF3_'):
                continue
            text = raw.decode('ascii')
            if '! Data_types:         VMF3 (lat lon ah aw zhd zwd)' not in text or '! Scale_factor:       1.e+00' not in text:
                raise ValueError('unsupported grid units/columns')
            matches = re.findall(r'^! Epoch:\s+(.+)$', text, re.M)
            if len(matches) != 1:
                raise ValueError('missing grid epoch')
            f = matches[0].split()
            if len(f) != 6 or float(f[5]) != 0 or int(f[4]) != 0:
                raise ValueError('unsupported grid epoch')
            dt = datetime(*map(int, f[:5]))
            if name != dt.strftime('2026/VMF3_%Y%m%d.H%H') or dt.hour not in (0, 6, 12, 18):
                raise ValueError('grid filename/UTC mismatch')
            mjd = (dt - datetime(1858, 11, 17)).total_seconds() / 86400
            data = np.loadtxt(io.StringIO(text), comments='!')
            if data.shape != (64800, 6) or not np.isfinite(data).all():
                raise ValueError('invalid complete grid')
            if not np.array_equal(data[:, 0], expected_lat) or not np.array_equal(data[:, 1], expected_lon):
                raise ValueError('grid order or coverage differs')
            if mjd in self.grids or np.any(data[:, 4] <= 0) or np.any(data[:, 5] < 0):
                raise ValueError('duplicate epoch or invalid zenith delay')
            self.grids[mjd] = data[:, 2:].reshape(180, 360, 4)
        if len(self.grids) != 4:
            raise ValueError('four fixed weather grids required')

    @lru_cache(maxsize=256)
    def harmonic_amplitudes(self, latitude_deg, longitude_deg):
        lat, lon = map(math.radians, (latitude_deg, longitude_deg))
        x, y, z = math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat)
        v, w = np.zeros((13, 13)), np.zeros((13, 13))
        v[0, 0], v[1, 0] = 1, z
        for n in range(2, 13):
            v[n, 0] = ((2*n-1)*z*v[n-1, 0] - (n-1)*v[n-2, 0])/n
        for m in range(1, 13):
            v[m, m] = (2*m-1)*(x*v[m-1, m-1] - y*w[m-1, m-1])
            w[m, m] = (2*m-1)*(x*w[m-1, m-1] + y*v[m-1, m-1])
            if m < 12:
                v[m+1, m], w[m+1, m] = (2*m+1)*z*v[m, m], (2*m+1)*z*w[m, m]
            for n in range(m+2, 13):
                v[n, m] = ((2*n-1)*z*v[n-1, m] - (n+m-1)*v[n-2, m])/(n-m)
                w[n, m] = ((2*n-1)*z*w[n-1, m] - (n+m-1)*w[n-2, m])/(n-m)
        vv = np.array([v[n, m] for n in range(13) for m in range(n+1)])
        ww = np.array([w[n, m] for n in range(13) for m in range(n+1)])
        return np.array([vv @ self.coefficients['anm_'+term] + ww @ self.coefficients['bnm_'+term]
                         for term in ('bh', 'bw', 'ch', 'cw')])

    def evaluate(self, mjd, latitude, longitude, height, elevation):
        """Return mfh, mfw, ZHD[m], ZWD[m]; angles in degrees, UTC MJD."""
        if not all(map(math.isfinite, (mjd, latitude, longitude, height, elevation))):
            raise ValueError('nonfinite atmosphere request')
        lon = longitude % 360
        if not (-89.5 < latitude < 89.5 and .5 <= lon < 359.5 and -500 <= height <= 9000 and 5 <= elevation <= 90):
            raise ValueError('outside bounded atmosphere domain')
        lo, hi = math.floor(mjd * 4) / 4, math.ceil(mjd * 4) / 4
        if lo not in self.grids or hi not in self.grids:
            raise ValueError('weather gap or extrapolation')
        i, j = math.floor(89.5-latitude), math.floor(lon-.5)
        u, v = 89.5-latitude-i, lon-.5-j
        weights = np.array([(1-u)*(1-v), (1-u)*v, u*(1-v), u*v])
        indices = [(i, j), (i, j+1), (i+1, j), (i+1, j+1)]
        fraction = 0 if lo == hi else (mjd-lo)/(hi-lo)
        weather = np.array([self.grids[lo][a, b]*(1-fraction) + self.grids[hi][a, b]*fraction for a, b in indices])
        grid_heights = np.array([self.height[a, b] for a, b in indices])
        dry, wet = height_delays(weather[:, 2], weather[:, 3], grid_heights, height, math.radians(latitude))
        dt = datetime(1858, 11, 17) + timedelta(days=mjd)
        doy = dt.timetuple().tm_yday + mjd - math.floor(mjd)
        phase = doy / 365.25 * 2 * math.pi
        seasonal = np.array([1, math.cos(phase), math.sin(phase), math.cos(2*phase), math.sin(2*phase)])
        bc = np.array([self.harmonic_amplitudes(89.5-a, .5+b) @ seasonal for a, b in indices])
        sine = math.sin(math.radians(elevation))
        mh = continued_fraction(weather[:, 0], bc[:, 0], bc[:, 2], sine)
        mw = continued_fraction(weather[:, 1], bc[:, 1], bc[:, 3], sine)
        mh += (1/sine - continued_fraction(2.53e-5, 5.49e-3, 1.14e-3, sine))*height/1000
        result = np.array([weights @ mh, weights @ mw, weights @ dry, weights @ wet])
        if not np.isfinite(result).all() or np.any(result < 0):
            raise ValueError('invalid atmospheric result')
        return result
