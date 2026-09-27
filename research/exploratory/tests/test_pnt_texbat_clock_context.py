from datetime import datetime, timezone
import gzip
from types import SimpleNamespace

import numpy as np
import pytest

from research.exploratory import pnt_texbat_clock_context as study


# One NOAA composite BRDC 2012/258 GPS navigation record, retained as a small
# parser fixture; the daily source and its hash are identified in the report.
NAV_BLOCK = '\n'.join([
    ' 1 12  9 13 18  0  0.0 2.735313028100D-04 1.591615728100D-12 0.000000000000D+00',
    '    1.100000000000D+02 2.640625000000D+01 4.453042823370D-09 8.411232863100D-01',
    '    1.477077603340D-06 1.182511798110D-03 1.159496605400D-05 5.153647699360D+03',
    '    4.104000000000D+05 7.450580596920D-09-3.114169970390D+00 3.166496753690D-08',
    '    9.606273935530D-01 1.521562500000D+02 3.912028515120D-01-7.975689442220D-09',
    '    2.725113468220D-10 1.000000000000D+00 1.705000000000D+03 0.000000000000D+00',
    '    2.000000000000D+00 0.000000000000D+00 8.381903171540D-09 1.100000000000D+02',
    '    4.320000000000D+05',
])


def nav_source(block=NAV_BLOCK, *, version='     2.10           N: GPS NAV DATA'):
    text = f'{version:<60}RINEX VERSION / TYPE\n'
    text += f'{"":<60}END OF HEADER\n'
    text += block + '\n'
    return gzip.compress(text.encode('ascii'))


def test_rinex2_broadcast_reuses_record_parser_and_rejects_truncation():
    records, counts = study.broadcast_navigation(nav_source())
    record = records['G01'][0]
    assert counts == {'admitted_records': 1, 'source_records': 1}
    assert record.toc_gps == datetime(2012, 9, 13, 18, tzinfo=timezone.utc)
    assert record.gps_week == 1705
    assert record.sv_health == 0
    assert record.sqrt_a_m_sqrt == pytest.approx(5153.64769936)
    with pytest.raises(ValueError, match='truncated'):
        study.broadcast_navigation(nav_source('\n'.join(NAV_BLOCK.splitlines()[:-1])))
    with pytest.raises(ValueError, match='RINEX 2 GPS'):
        study.broadcast_navigation(nav_source(version='     3.04           N: GPS NAV DATA'))


def test_clock_fit_preserves_common_mode_and_satellite_spread(monkeypatch):
    models = {3: 20e6, 6: 21e6, 7: 22e6, 10: 23e6}
    residuals = {3: -1, 6: 0, 7: 0, 10: 2}
    def model(prn, code, time, station, clock, context):
        return models[prn], 45.0
    monkeypatch.setattr(study, 'reference_model', model)
    context = SimpleNamespace(sow_midnight=432000)
    records = {prn: prn for prn in models}
    clean = {prn: base + 100 + residuals[prn] for prn, base in models.items()}
    attacked = {prn: value + 200 for prn, value in clean.items()}
    first = study.fitted_clock(clean, np.zeros(3), records, 477930, context)
    second = study.fitted_clock(attacked, np.zeros(3), records, 477930, context)
    assert second['clock_m'] - first['clock_m'] == 200
    assert second['median_absolute_satellite_residual_m'] == first['median_absolute_satellite_residual_m']
    with pytest.raises(ValueError, match='incomplete common satellite set'):
        study.fitted_clock({3: clean[3]}, np.zeros(3), records, 477930, context)


def test_remote_change_affects_only_network_channel(monkeypatch):
    monkeypatch.setattr(study, 'chosen_records', lambda nav, prns, tow, context: {prn: prn for prn in prns})
    monkeypatch.setattr(study, 'fitted_clock',
                        lambda codes, position, records, tow, context:
                        {'clock_m': float(np.median(list(codes.values()))),
                         'median_absolute_satellite_residual_m': 0.0,
                         'max_absolute_satellite_residual_m': 0.0})
    paired = []
    for tow, phase, attack_shift, remote_shift in ((477930, 'preattack', 0, 0),
                                                    (477960, 'preattack', 0, 0),
                                                    (478050, 'time_push', 100, 50)):
        for prn in (3, 6, 7, 10):
            paired.append({'gpst_tow_s': tow, 'phase': phase, 'prn': prn,
                           'clean_m': 10, 'ds7_m': 10 + attack_shift,
                           'TXAU_m': remote_shift, 'SAM2_m': remote_shift})
    result = study.evaluate(paired, {}, {'TXAU': np.ones(3), 'SAM2': np.ones(3) * 2})
    late = result['epochs'][-1]
    assert late['centered_clock_m']['ds7']['local_only'] == 100
    assert late['centered_clock_m']['ds7']['local_minus_network'] == 50
    assert late['network_only_centered_clock_m'] == 50
    assert late['centered_clock_m']['cleanStatic']['local_only'] == 0
