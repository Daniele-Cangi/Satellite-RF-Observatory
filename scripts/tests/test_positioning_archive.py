import hashlib
import json
import shutil
import pytest
from scripts.export_positioning_archive import ROOT, make_archive, export, validate_event, new_event, NEW_EVENTS


def test_archive_preserves_failure_and_missing_measurements():
    data,_=make_archive()
    g12,g08,missing,g13,g14=data['events']
    assert data['schemaVersion']==2
    assert [row['primaryPass'] for row in data['events']]==[False,False,False,False,True]
    assert g12['errorM']==pytest.approx(15.139240688)
    assert g12['radiusM']>g12['thresholdM']
    assert g08['radiusM']>21000
    assert missing['errorM'] is missing['radiusM'] is missing['ecefM'] is None
    assert missing['oracleUtc'] is None
    assert g13['errorM'] is g13['radiusM'] is g13['ecefM'] is g13['oracleUtc'] is None
    assert (g13['supportAvailable'],g13['supportRequired'])==(0,11)
    assert g14['errorM']==pytest.approx(31.016966131539373)
    assert g14['radiusM']==pytest.approx(5755.157155537385)
    assert g14['heldoutM']==pytest.approx(-0.8455900251865387)
    assert g14['fitStations']==['ALGO00CAN','BOGT00COL','DRAO00CAN','MKEA00USA','PIE100USA','STJO00CAN','YELL00CAN']
    assert len(g14['networkSelection']['candidateStations'])==10
    assert g14['sourceRevision']!=g13['sourceRevision']!=g12['sourceRevision']


def test_downloads_recover_original_bytes_and_match_published_hashes():
    data,bundles=make_archive()
    for event in data['events']:
        blob=bundles[event['id']]
        assert hashlib.sha256(blob).hexdigest()==event['dossierHash']
        for artifact in json.loads(blob)['files']:
            original=artifact['original_utf8'].encode('utf-8')
            assert original==(ROOT/artifact['path']).read_bytes()
            assert hashlib.sha256(original).hexdigest()==artifact['sha256']


def test_mutated_frozen_solution_cannot_be_exported(tmp_path):
    relative='experiments/positioning_g12_doy248'
    shutil.copytree(ROOT/relative,tmp_path/relative)
    path=tmp_path/relative/'solution.json'
    path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises(ValueError,match='solution hash mismatch'):
        make_archive(tmp_path)


def test_stale_published_numbers_fail_export_check(tmp_path):
    export(tmp_path)
    path=tmp_path/'app/results.json'
    value=json.loads(path.read_text(encoding='utf-8'))
    value['events'][0]['primaryPass']=True
    path.write_text(json.dumps(value),encoding='utf-8')
    with pytest.raises(ValueError,match='stale or modified'):
        export(tmp_path,check=True)


@pytest.mark.parametrize('field,value', [('radiusM',10001),('errorM',10001),('heldoutConfirmed',False),('heldoutM',101),('primaryPass',False)])
def test_success_requires_consistent_metrics(field,value):
    data,_=make_archive()
    row=dict(data['events'][-1]);row[field]=value
    with pytest.raises(ValueError):
        validate_event(row)


def test_structural_failure_cannot_acquire_a_position():
    data,_=make_archive()
    row=dict(data['events'][-2]);row['ecefM']=[0,0,0]
    with pytest.raises(ValueError,match='unqualified event'):
        validate_event(row)


@pytest.mark.parametrize('filename',['outcome.json','availability.json','solution.json'])
def test_new_frozen_evidence_mutation_is_rejected(tmp_path,filename):
    key,folder,revision=NEW_EVENTS[-1]
    shutil.copytree(ROOT/folder,tmp_path/folder)
    path=tmp_path/folder/filename
    path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises(ValueError,match='artifact hash mismatch'):
        new_event(tmp_path,key,folder,revision)
