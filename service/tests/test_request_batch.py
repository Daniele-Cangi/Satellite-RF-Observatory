"""Mixed local CLI requests through the real queue and staged job controller.

Scientific subprocesses are invented fixtures, not new RF confirmations.
"""
import json

from service.__main__ import main
from service.requests import RequestStore
from service.tests.test_worker import COMMIT, install_stages


def test_mixed_requests_complete_without_reexecution(tmp_path, monkeypatch, capsys):
    queue, runs = tmp_path / 'queue.sqlite', tmp_path / 'runs'
    common = ['--queue', str(queue)]

    def cli(*args):
        code = main(list(args))
        return code, json.loads(capsys.readouterr().out)

    cases = [('G15', 'unavailable', 'NOT_VERIFIABLE'),
             ('G16', 'software_error', 'EXECUTION_FAILED'),
             ('G17', 'synthetic_pass', 'VERIFIED_CONDITIONALLY'),
             ('G18', 'inconclusive', 'INCONCLUSIVE')]
    rows = []
    for target, kind, expected in cases:
        code, row = cli('submit', target, '2026-09-01', '--prior-access',
                        'Invented offline development batch; no RF acquisition.',
                        '--implementation', COMMIT, '--key', target,
                        '--owner', target, *common)
        assert code == 0 and row['state'] == 'QUEUED'
        rows.append((row, kind, expected, target))

    for row, kind, expected, owner in rows:
        calls = install_stages(monkeypatch, kind=kind)
        code, dispatched = cli('work-once', *common, '--runs', str(runs))
        assert dispatched['result']['status'] == expected
        assert code == (1 if kind == 'software_error' else 0)
        sealed = runs / row['id'] / 'result.json'
        before = sealed.read_bytes()
        # Optional missing diagnostics cannot hide or change any sealed verdict.
        for _ in range(2):
            _, status = cli('request-status', row['id'], '--owner', owner,
                            *common, '--runs', str(runs), '--diagnostic',
                            str(tmp_path / 'missing-report.json'))
            assert status['result']['status'] == expected
            assert status['result']['diagnostics']['reference_sensitivity']['status'] == 'UNAVAILABLE'
            assert sealed.read_bytes() == before
        assert calls == (['acquire', 'estimate', 'verify'] if kind == 'synthetic_pass'
                         else ['acquire', 'estimate'] if kind == 'inconclusive' else ['acquire'])

    assert cli('work-once', *common, '--runs', str(runs))[1]['state'] == 'NO_DISPATCH'
    store = RequestStore(queue)
    assert all(store.get(owner, row['id'])['state'] in ('COMPLETED', 'FAILED')
               for row, _, _, owner in rows)
