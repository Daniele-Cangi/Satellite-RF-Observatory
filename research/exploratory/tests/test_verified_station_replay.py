import json
from pathlib import Path

import pytest

from research.exploratory import verified_station_replay as verified


@pytest.mark.parametrize('filename', ['admission_receipt.json', 'estimation/admitted.json'])
@pytest.mark.parametrize('poison', ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}', '{"x":1e999}'])
def test_archive_json_rejected_before_context_or_navigation(tmp_path, filename, poison):
    (tmp_path/'estimation').mkdir()
    (tmp_path/'admission_receipt.json').write_text('{}')
    (tmp_path/'estimation/admitted.json').write_text('{}')
    (tmp_path/filename).write_text(poison)
    # No navigation file exists: the JSON boundary must fail first.
    with pytest.raises(ValueError): verified.load_inputs(tmp_path)


@pytest.mark.parametrize('defect', ['reference_manifest', 'attitude_manifest', 'unit_direction'])
def test_complete_report_pins_reject_partial_provenance_and_unit_vector_substitution(monkeypatch, tmp_path, defect):
    paths = verified.paths('g14')
    key = 'attitude_report' if defect == 'attitude_manifest' else 'reference_report'
    report = json.loads(paths[key].read_bytes())
    if defect == 'unit_direction':
        # Still a valid unit vector; a norm-only check would accept this.
        report['reference_rows'][0]['los_enu'] = [1., 0., 0.]
    else:
        report['sources_sha256'] = {}
    altered = tmp_path/'altered.json'
    altered.write_text(json.dumps(report))
    paths[key] = altered
    monkeypatch.setattr(verified, 'paths', lambda tag: paths)
    with pytest.raises(ValueError, match='pinned input differs'): verified.verify('g14')


@pytest.mark.parametrize('tag', ['g14', 'g12'])
def test_complete_verified_replay_matches_frozen_receipt(tag):
    result = verified.verify(tag)
    saved = json.loads((verified.BASE/f'results/{tag}_verified_station_replay_v1.json').read_bytes())
    assert result == saved
    assert result['status'] == 'ALL_PINNED_RESULTS_REPRODUCED'
    assert result['station_count'] == 7 and result['reference_case_count'] == 8
    assert result['input_sha256'] == verified.PINS[tag]
