import json
from pathlib import Path
import pytest
from positioning.acquisition import acquire, digest, snapshot_sources, source_hashes, write_json

ROOT=Path(__file__).resolve().parents[2]


def test_shorter_support_retains_emitted_event_for_varied_synthetic_curvature():
    from experiments.positioning_g12_doy248.support_design import audit
    result=audit()
    assert len(result['cases'])==18
    for case in result['cases']:
        assert max(case['difference_from_seven_samples_m'])<1e-6
        assert case['cubic_quintic_difference_m'][1]<2


def test_source_snapshot_preserves_bytes_and_refuses_a_changed_snapshot(tmp_path):
    hashes=snapshot_sources(tmp_path,'acquisition')
    assert hashes==source_hashes()
    for name, expected in hashes.items():
        assert digest(tmp_path/'sources/acquisition'/name)==expected
    path=tmp_path/'sources/acquisition/acquisition.py'
    path.write_bytes(path.read_bytes()+b'\n')
    with pytest.raises(ValueError,match='snapshot differs'):
        snapshot_sources(tmp_path,'acquisition')


def test_closed_acquisition_does_not_download_or_rewrite_evidence(tmp_path,monkeypatch):
    source=ROOT/'experiments/positioning_g12_doy250/plan.json'
    (tmp_path/'plan.json').write_bytes(source.read_bytes())
    write_json(tmp_path/'plan_freeze.json',{'plan_sha256':digest(source),'sources':{}})
    result={'status':'SOURCE_OR_MEASUREMENT_NOT_QUALIFIED','reason':'NO_COMMON_STRUCTURAL_WINDOW'}
    write_json(tmp_path/'outcome.json',result)
    before=digest(tmp_path/'outcome.json')
    monkeypatch.setattr('positioning.acquisition.download',lambda *args:pytest.fail('closed acquisition downloaded'))
    assert acquire(source,tmp_path)==result
    assert digest(tmp_path/'outcome.json')==before
    assert not (tmp_path/'raw_observations').exists()
