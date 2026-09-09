import hashlib
import json
import shutil
import pytest
from scripts.export_positioning_archive import ROOT, make_archive, export


def test_archive_preserves_failure_and_missing_measurements():
    data,_=make_archive()
    g12,g08,missing=data['events']
    assert not any(row['primaryPass'] for row in data['events'])
    assert g12['errorM']==pytest.approx(15.139240688)
    assert g12['radiusM']>g12['thresholdM']
    assert g08['radiusM']>21000
    assert missing['errorM'] is missing['radiusM'] is missing['ecefM'] is None
    assert missing['oracleUtc'] is None


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
