import io
import json
import pytest
from research.exploratory import code_convention_audit_v2 as audit
from research.exploratory.tests.test_code_conventions import HEADER


@pytest.mark.parametrize('epoch',['2026 9 4 0 0 0','2026 9 3 24 0 0','2026 9 3 0 60 0','2026 9 3 0 0 nan','2026 9 3 0 0 60','not an epoch'])
def test_first_epoch_rejected(epoch):
    text=HEADER.replace('*  2026 9 3 0 0 0','*  '+epoch)
    with pytest.raises(ValueError):audit.sp3_header(io.StringIO(text),'2026-09-03')


def test_first_epoch_validated_without_reading_body():
    def lines():
        yield from HEADER.splitlines()
        raise AssertionError('body entered')
    assert audit.sp3_header(lines(),'2026-09-03')['date']=='2026-09-03'


@pytest.mark.parametrize('raw',['{"x":1,"x":2}','{"x":NaN}','{"x":Infinity}','{"x":-Infinity}','{"x":1e999}'])
def test_strict_json_rejects_ambiguous_receipts(raw):
    with pytest.raises(ValueError):audit.strict_json(raw)


@pytest.mark.parametrize('key,old,new',[('orbit','2026246','2026248'),('clock','OPSRAP','OPSFIN'),('orbit','igs.bkg.bund.de','example.com')])
def test_paired_url_identity_rejected(key,old,new):
    pair=json.loads((audit.v1.BASE/'inputs/timed_reference_products/g14/receipt.json').read_bytes())
    pair[key]['source_url']=pair[key]['source_url'].replace(old,new)
    with pytest.raises(ValueError):audit.validate_urls(pair)


def test_v2_frozen_report_replays_and_keeps_findings():
    expected=json.loads((audit.v1.BASE/'results/code_convention_audit_v2.json').read_bytes())
    assert audit.run()==expected
    prior=json.loads((audit.v1.BASE/'results/code_convention_audit_v1.json').read_bytes())
    assert expected['events']==prior['events']


def test_report_binds_committed_execution_sources_and_inputs():
    import hashlib
    import subprocess
    report=json.loads((audit.v1.BASE/'results/code_convention_audit_v2.json').read_bytes())
    freeze='46a22ee'
    subprocess.run(['git','merge-base','--is-ancestor',freeze,'HEAD'],cwd=audit.v1.ROOT,check=True)
    for path,digest in (report['source_sha256']|report['input_sha256']).items():
        committed=subprocess.check_output(['git','show',freeze+':'+path],cwd=audit.v1.ROOT)
        assert hashlib.sha256(committed).hexdigest()==digest
        assert hashlib.sha256((audit.v1.ROOT/path).read_bytes()).hexdigest()==digest
