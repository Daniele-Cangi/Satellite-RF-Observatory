from copy import deepcopy
from datetime import datetime, timedelta
import json

import numpy as np
import pytest

from research.exploratory import station_frame_epoch as study


def test_psd_cumulative_log_exp_and_pre_quake_zero():
    terms = [{'epoch': '20:001:00000', 'model': 'LOG', 'axis': 'E', 'amplitude_m': .1, 'tau_years': 2.},
             {'epoch': '20:001:00000', 'model': 'EXP', 'axis': 'N', 'amplitude_m': -.2, 'tau_years': 1.},
             {'epoch': '21:001:00000', 'model': 'LOG', 'axis': 'E', 'amplitude_m': .3, 'tau_years': 1.}]
    start = datetime(2020, 1, 1)
    assert np.array_equal(study.psd_enu(terms, start-timedelta(seconds=1)), np.zeros(3))
    assert np.array_equal(study.psd_enu(terms, start), np.zeros(3))
    when = start+timedelta(seconds=study.YEAR_SECONDS*2)
    late_years = (when-datetime(2021, 1, 1)).total_seconds()/study.YEAR_SECONDS
    assert study.psd_enu(terms, when) == pytest.approx([.1*np.log(2)+.3*np.log1p(late_years), -.2*(1-np.exp(-2)), 0])


def test_coordinate_velocity_units_and_local_axes():
    xyz, vel = np.array([6378137.,0,0]), np.array([.01,.02,.03])
    when = datetime(2020,1,1)+timedelta(seconds=study.YEAR_SECONDS)
    assert study.marker_at(xyz, vel, [], when) == pytest.approx(xyz+vel, abs=1e-9)
    terms = [{'epoch': '20:001:00000', 'model': 'LOG', 'axis': 'E', 'amplitude_m': 1., 'tau_years': 1.}]
    assert study.marker_at(xyz, np.zeros(3), terms, when)-xyz == pytest.approx([0,np.log(2),0], abs=1e-9)
    assert study.arp(xyz, np.array([.2,.3,.1]))-xyz == pytest.approx([.1,.2,.3], abs=1e-9)


@pytest.mark.parametrize('defect', ['duplicate', 'missing_time', 'bad_tau', 'bad_unit', 'domes'])
def test_psd_pairing_rejects_invalid_models(defect):
    frame, _ = study.read_frame()
    text = frame['IGC20.PSD']
    line = next(s for s in text.splitlines() if 'ALOG_E' in s)
    if defect == 'duplicate': text = text.replace(line, line+'\n'+line)
    if defect == 'missing_time': text = '\n'.join(s for s in text.splitlines() if 'TLOG_E' not in s)
    if defect == 'bad_tau': text = text.replace('5.21643121260845e+00', '-5.21643121260845e+00')
    if defect == 'bad_unit': text = text.replace('73993 m ', '73993 y ')
    domes = '42202M004' if defect == 'domes' else '42202M005'
    with pytest.raises(ValueError): study.psd_terms(text, 'AREQ00PER', domes)


def test_catalog_matches_domes_not_first_station_row():
    frame, _ = study.read_frame()
    a, flag = study.catalog(frame['IGC20.CRD'], 'AREQ00PER', '42202M005')
    assert a[0] > 1942800 and flag == 'IGC20'
    with pytest.raises(ValueError, match='provenance'):
        study.catalog(frame['IGC20.CRD'], 'AREQ00PER', '42202M004')
    with pytest.raises(ValueError): study.catalog(frame['IGC20.CRD'], 'AREQ00PER', '99999M999')
    with pytest.raises(ValueError): study.catalog(frame['IGC20.CRD'].replace('IGc20_0','IGS20_0'), 'AREQ00PER', '42202M005')


def test_final_transport_anchors_exact_daily_coordinate_without_adding_psd_twice():
    frame, _ = study.read_frame()
    source = json.loads(study.verified.paths('g12')['station_report'].read_bytes())
    st = next(s for s in source['stations'] if s['station']=='AREQ00PER')
    model, info = study.station_model(st, frame, '2026-09-05', [37800.,38100.])
    t0 = study.epoch(st['coordinate_epoch'])
    seconds = (t0-datetime(2026,9,5)).total_seconds()
    assert model('final_transport', seconds) == pytest.approx(st['sinex_arp_ecef_m'], abs=1e-9)
    assert info['psd_terms']
    with pytest.raises(ValueError): model('unknown', seconds)


@pytest.mark.parametrize('tag', ['g14','g12'])
def test_report_replay_and_all_variants_accounting(tag):
    result = study.run(tag)
    saved = json.loads((study.verified.BASE/f'results/{tag}_station_frame_epoch_v1.json').read_bytes())
    # Nonlinear SPP finite differences have platform noise; calibrated residuals
    # and clocks remain separately constrained at sub-micrometre replay precision.
    for key in ('schema','case_count','status_counts','input_sha256','sources_sha256','omitted_paths'):
        assert result[key] == saved[key]
    for a,b in zip(result['station_models'],saved['station_models'],strict=True):
        study.verified.compare_tree(a,b)
    assert len(result['cases']) == 5
    for case,old in zip(result['cases'],saved['cases'],strict=True):
        assert case['mode'] == old['mode'] and case['status'] == old['status']
        assert case['evaluated_path_count']+len(result['omitted_paths']) == result['observed_path_count']
        assert case['pooled_reference_rms_m'] == pytest.approx(old['pooled_reference_rms_m'],abs=1e-7)
        for name,cal in case['calibrations'].items():
            previous=old['calibrations'][name]
            assert cal['status']==previous['status'] and len(cal['epochs'])==11
            assert cal['failures']==previous['failures']
            for e,p in zip(cal['epochs'],previous['epochs'],strict=True):
                assert e['time_s']==p['time_s'] and e['references']==p['references']
                assert e['residuals_m']==pytest.approx(p['residuals_m'],abs=1e-7)
                assert e['clock_m']==pytest.approx(p['clock_m'],abs=1e-7,rel=0)
                assert e['ground_fit_rank']==p['ground_fit_rank']==4
                assert e['ground_offset_xyz_m']==pytest.approx(p['ground_offset_xyz_m'],abs=.003)
    assert not result['target_fit_performed'] and not result['instantaneous_site_position_qualified']
