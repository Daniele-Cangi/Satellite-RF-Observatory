"""Real, already revealed G08 excerpts test engineering, never a new proof."""
import gzip
import hashlib
import json
from pathlib import Path
import pytest

from positioning.acquisition import write_json, digest
from positioning.estimation import estimate
from positioning.verification import verify, compare_oracle

FIXTURES=Path(__file__).parent/'fixtures'
ROOT=Path(__file__).resolve().parents[2]


def setup_regression(run):
    plan=json.loads((ROOT/'experiments/positioning_g12_doy250/plan.json').read_text())
    admitted=json.loads((FIXTURES/'g08_admitted.json').read_text())
    plan.update({'experiment':'PREVIOUSLY_REVEALED_G08_REGRESSION_ONLY','target':'G08','date_gpst':'2026-09-06','fit_stations':admitted['fit_stations'],'observation_filename':'{station}_fixture.rnx.gz','claim':'Engineering regression of already revealed data; no new blinded physical evidence.'})
    plan['selection'].update({'support_epochs':11,'fit_epochs':11,'step_s':30})
    plan['uncertainty']['nonlinear_margin_factor']=1.
    write_json(run/'plan.json',plan)
    write_json(run/'plan_freeze.json',{'plan_sha256':digest(run/'plan.json'),'freeze_utc':'engineering regression'})
    admitted['plan_sha256']=digest(run/'plan.json')
    write_json(run/'estimation/admitted.json',admitted)
    nav=run/'estimation/reference_only.rnx'
    nav.write_bytes(gzip.decompress((FIXTURES/'g08_reference_only.rnx.gz').read_bytes()))
    write_json(run/'admission_receipt.json',{'admitted_sha256':digest(run/'estimation/admitted.json'),'navigation_sha256':digest(nav)})
    raw=run/'raw_observations/GOLD00USA_fixture.rnx.gz';raw.parent.mkdir()
    raw.write_bytes((FIXTURES/'gold_g08_excerpt.rnx.gz').read_bytes())
    write_json(run/'structure.json',{'selection':{'selected_seconds_gpst':list(range(0,301,30))},'structures':{'GOLD00USA':json.loads((FIXTURES/'gold_header.json').read_text())},'receipts':[{'station':'GOLD00USA','sha256':digest(raw)}]})


def test_full_offline_calibration_freeze_and_reveal_regression(tmp_path,monkeypatch):
    setup_regression(tmp_path)
    # Estimation must not use the acquisition download capability.
    monkeypatch.setattr('positioning.acquisition.download',lambda *args:pytest.fail('network during estimation'))
    result=estimate(tmp_path)
    assert result['status']=='UNCERTAINTY_TOO_LARGE'
    assert result['total_95_outer_radius_m']==pytest.approx(21607.66024134,abs=.1)
    before=digest(tmp_path/'solution.json')
    def cached_oracle(url,limit):
        assert (tmp_path/'heldout_reveal.json').exists()
        assert (tmp_path/'solution_freeze.json').exists()
        data=gzip.compress((FIXTURES/'g08_oracle_excerpt.sp3').read_bytes())
        return data,{'url':url,'sha256':hashlib.sha256(data).hexdigest(),'access_utc':'offline regression of previously revealed oracle'}
    monkeypatch.setattr('positioning.verification.download',cached_oracle)
    outcome=verify(tmp_path)
    assert not outcome['primary_pass']
    assert outcome['comparison']['error_3d_m']==pytest.approx(188.705039,abs=.2)
    assert outcome['heldout']['residual_m']==pytest.approx(1.849238,abs=.01)
    assert digest(tmp_path/'solution.json')==before
    assert verify(tmp_path)==outcome
    with pytest.raises(ValueError,match='already frozen'):
        estimate(tmp_path)


def test_no_window_terminal_prevents_both_estimation_and_oracle(tmp_path,monkeypatch):
    terminal={'status':'SOURCE_OR_MEASUREMENT_NOT_QUALIFIED','reason':'NO_COMMON_STRUCTURAL_WINDOW','primary_pass':False,'oracle_accessed':False}
    write_json(tmp_path/'outcome.json',terminal)
    monkeypatch.setattr('positioning.verification.download',lambda *args:pytest.fail('closed event accessed oracle'))
    assert estimate(tmp_path)==terminal
    assert verify(tmp_path)==terminal
    assert not (tmp_path/'solution.json').exists()


def test_reveal_without_freeze_fails_before_download(tmp_path,monkeypatch):
    monkeypatch.setattr('positioning.verification.download',lambda *args:pytest.fail('premature oracle access'))
    with pytest.raises(ValueError,match='forbidden before'):
        verify(tmp_path)


def test_changed_admitted_input_rejected_before_calibration(tmp_path):
    setup_regression(tmp_path)
    path=tmp_path/'estimation/admitted.json';path.write_text(path.read_text()+' ')
    with pytest.raises(ValueError,match='input hash mismatch'):
        estimate(tmp_path)


def test_offline_stage_audit_denies_network_and_subprocess():
    from positioning.__main__ import deny_network
    for name in ['socket.connect','socket.getaddrinfo','subprocess.Popen','os.system']:
        with pytest.raises(PermissionError,match='offline'):
            deny_network(name,())


def test_oracle_never_extrapolates():
    with pytest.raises(ValueError,match='bracket'):
        compare_oracle((FIXTURES/'g08_oracle_excerpt.sp3').read_text(),'G08','2026-09-06',-1,[1,2,3],0)
