from copy import deepcopy
import json
import math
from pathlib import Path
from urllib.error import HTTPError

import pytest

from positioning.acquisition import acquire, digest, write_json
from positioning.network import select_network, effective_plan, availability_report
from positioning.plans import DEFAULT_FIT, make_network_plan, validate_plan

POOL = DEFAULT_FIT + ['AMC400USA', 'PIE100USA', 'MKEA00USA']


def sample_structure(latitude, longitude, start=0, count=11):
    lat, lon = map(math.radians, (latitude, longitude))
    xyz = [6371000*math.cos(lat)*math.cos(lon),6371000*math.cos(lat)*math.sin(lon),6371000*math.sin(lat)]
    return {'header': {'APPROX POSITION XYZ': [' '.join(map(str,xyz))], 'ANTENNA: DELTA H/E/N':['0 0 0']},
            'epochs': [{'seconds_gpst':str(start+i*30),'eligible':True} for i in range(count)],
            'epoch_count':count,'target_code_epoch_count':count,'eligible_epoch_count':count,
            'gps_observation_types':['C1C','C2W']}


def setup():
    plan = make_network_plan('G14','2026-09-03',POOL)
    structures = {n:sample_structure(-35+i*9,-130+i*8) for i,n in enumerate(sorted(POOL))}
    structures['GOLD00USA'] = sample_structure(35,-117)
    return plan, structures


def test_selection_is_order_independent_and_ignores_target_values():
    plan, structures = setup()
    selected = select_network(plan,structures)
    assert selected['selected_seconds_gpst'][0] == '0'
    assert selected['fit_stations'] == sorted(POOL)[:7]
    poisoned = dict(reversed(list(deepcopy(structures).items())))
    for info in poisoned.values():
        info['target_position'] = [1e99,float('nan'),-1e99]
        for e in info['epochs']:
            e['pseudorange'] = 'POISONED_TARGET_VALUE'
    assert select_network(plan,poisoned) == selected
    report = availability_report(plan,{'structures':structures,'selection':selected})
    assert report['ready_for_calibration']


def test_gap_at_one_candidate_selects_declared_alternative_without_moving_holdout():
    plan, structures = setup()
    structures[sorted(POOL)[0]]['epochs'].pop(5)
    selected = select_network(plan,structures)
    assert selected['fit_stations'] == sorted(POOL)[1:8]
    structures['GOLD00USA']['epochs'].pop(5)
    assert select_network(plan,structures)['selected_seconds_gpst'] is None


def test_earliest_valid_window_wins_over_later_network():
    plan, structures = setup()
    for name in sorted(POOL)[:3]:
        structures[name] = sample_structure(40, -80, start=600)
    structures['GOLD00USA'] = sample_structure(35,-117,count=31)
    selected = select_network(plan, structures)
    assert selected['selected_seconds_gpst'][0] == '0'
    assert selected['fit_stations'] == sorted(POOL)[3:]


def test_colocated_roots_are_not_called_usable_and_roles_cannot_be_edited():
    plan, structures = setup()
    for name in POOL:
        structures[name] = sample_structure(35,-117)
    selected = select_network(plan,structures)
    assert selected['status'] == 'GROUND_APERTURE_NOT_QUALIFIED'
    plan, structures = setup()
    selected = select_network(plan,structures)
    selected['fit_stations'][-1] = 'GOLD00USA'
    with pytest.raises(ValueError,match='frozen rule'):
        effective_plan(plan,{'structures':structures,'selection':selected})
    plan['network']['minimum_latitude_span_deg'] = 0
    with pytest.raises(ValueError,match='unsupported'):
        validate_plan(plan)


def test_missing_or_nonfinite_antenna_metadata_cannot_admit_a_station():
    plan, structures = setup()
    del structures['GOLD00USA']['header']['ANTENNA: DELTA H/E/N']
    assert select_network(plan, structures)['status']=='WITHHELD_STATION_UNAVAILABLE'
    plan, structures = setup()
    for name in POOL:
        structures[name]['header']['ANTENNA: DELTA H/E/N']=['nan 0 0']
    assert select_network(plan, structures)['selected_seconds_gpst'] is None


def test_availability_never_downloads_navigation_or_parses_target_numbers(tmp_path,monkeypatch):
    plan, structures = setup()
    path=tmp_path/'plan.json'; run=tmp_path/'run'; write_json(path,plan)
    calls=[]
    def download(url,*args):
        assert '/obs/' in url
        assert (run/'plan_freeze.json').exists()
        name=url.rsplit('/',1)[-1][:9]; calls.append(name)
        raw=name.encode()
        import hashlib
        return raw,{'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'http_status':200}
    monkeypatch.setattr('positioning.acquisition.download',download)
    monkeypatch.setattr('positioning.acquisition.hatanaka.decompress',lambda raw,**kw:raw)
    monkeypatch.setattr('positioning.acquisition.scan_structure',lambda name,*args:structures[name])
    monkeypatch.setattr('positioning.acquisition.observation_window',lambda *args:pytest.fail('numeric access in availability'))
    report=acquire(path,run,availability_only=True)
    assert report['ready_for_calibration']
    assert len(calls)==11
    assert not (run/'estimation').exists()
    assert not (run/'oracle_request.json').exists()
    before=digest(run/'plan_freeze.json')
    assert acquire(path,run,availability_only=True)==report
    assert len(calls)==11
    assert digest(run/'plan_freeze.json')==before


def test_missing_candidates_are_explicit_but_holdout_cannot_be_replaced(tmp_path,monkeypatch):
    plan=make_network_plan('G14','2026-09-03',POOL)
    path=tmp_path/'plan.json';write_json(path,plan)
    def missing(url,*args):
        raise HTTPError(url,404,'not found',None,None)
    monkeypatch.setattr('positioning.acquisition.download',missing)
    result=acquire(path,tmp_path/'run',availability_only=True)
    report=json.loads((tmp_path/'run/availability.json').read_text())
    assert result['status']=='SOURCE_OR_MEASUREMENT_NOT_QUALIFIED'
    assert not report['ready_for_calibration']
    assert all(s['source_status']=='SOURCE_MISSING' for s in report['stations'])
    assert report['status']=='WITHHELD_STATION_UNAVAILABLE'


def test_admission_contains_only_selected_roots_and_no_withheld_target(tmp_path,monkeypatch):
    import gzip
    import hashlib
    plan, structures=setup()
    path=tmp_path/'plan.json';run=tmp_path/'run';write_json(path,plan)
    target_reads=[]
    def download(url,*args):
        raw=gzip.compress(b'references') if '/BRDC/' in url else url.rsplit('/',1)[-1][:9].encode()
        return raw,{'url':url,'sha256':hashlib.sha256(raw).hexdigest(),'http_status':200}
    monkeypatch.setattr('positioning.acquisition.download',download)
    monkeypatch.setattr('positioning.acquisition.hatanaka.decompress',lambda raw,**kw:raw)
    monkeypatch.setattr('positioning.acquisition.scan_structure',lambda name,*args:structures[name])
    monkeypatch.setattr('positioning.acquisition.strip_target_navigation',lambda text,target:'reference only')
    def observations(content,header,types,include_target,context):
        if include_target:
            target_reads.append(content)
        return [{'time_s':t,'if_code_m':{context.target:2e7} if include_target else {'G01':2e7}} for t in context.times]
    monkeypatch.setattr('positioning.acquisition.observation_window',observations)
    report=acquire(path,run,availability_only=True)
    assert not target_reads
    result=acquire(path,run)
    assert result['status']=='INPUTS_ADMITTED'
    admitted=json.loads((run/'estimation/admitted.json').read_text())
    assert admitted['fit_stations']==report['selected_fit_stations']
    assert set(admitted['stations'])==set(report['selected_fit_stations']+['GOLD00USA'])
    assert admitted['stations']['GOLD00USA']['target_if_codes_m'] is None
    assert target_reads==report['selected_fit_stations']


def test_failed_process_cannot_be_reported_completed_even_if_it_wrote_an_outcome(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from positioning.jobs import execute, dossier
    plan=make_network_plan('G14','2026-09-03',POOL)
    path=tmp_path/'plan.json';run=tmp_path/'run';write_json(path,plan)
    def child(*args,**kwargs):
        write_json(run/'outcome.json',{'status':'PARTIAL_RESULT','primary_pass':False})
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr('positioning.jobs.subprocess.run',child)
    assert execute(path,run)['state']=='FAILED'
    assert dossier(run)['status']=='ENGINEERING_FAILURE'
