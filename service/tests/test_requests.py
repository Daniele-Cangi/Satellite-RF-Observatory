from concurrent.futures import ThreadPoolExecutor
import pytest

from positioning.plans import make_plan
from service.requests import Conflict, QueueFull, RequestStore


@pytest.fixture
def declaration():
    return dict(plan=make_plan('G12','2026-09-05',prior_access='Previously revealed fixture, technical replay only.'),
                implementation='2ee7d0ab060f21e24d182968d4d94ea3ddcd17ca', purpose='historical_replay')


def test_duplicate_submit_and_restart_preserve_one_request(tmp_path,declaration):
    store=RequestStore(tmp_path/'queue.sqlite')
    row=store.submit('owner','key',**declaration)
    restarted=RequestStore(tmp_path/'queue.sqlite')
    assert restarted.submit('owner','key',**declaration)==row
    assert len(restarted.get('owner',row['id'])['events'])==1
    changed=dict(declaration,purpose='prospective_attempt')
    with pytest.raises(Conflict):
        store.submit('owner','key',**changed)


def test_owner_isolation_and_no_claim_secret_in_user_view(tmp_path,declaration):
    store=RequestStore(tmp_path/'queue.sqlite')
    row=store.submit('alice','key',**declaration)
    with pytest.raises(KeyError): store.get('bob',row['id'])
    with pytest.raises(KeyError): store.cancel('bob',row['id'])
    claim=store.claim()
    assert claim['lease_token'] not in str(store.get('alice',row['id']))
    assert 'lease_hash' not in store.get('alice',row['id'])


def test_competing_workers_claim_once(tmp_path,declaration):
    path=tmp_path/'queue.sqlite'
    store=RequestStore(path)
    store.submit('owner','one',**declaration)
    store.submit('owner','two',**declaration)
    def claim(_): return RequestStore(path).claim()
    with ThreadPoolExecutor(max_workers=4) as workers:
        claims=list(workers.map(claim,range(4)))
    assert sum(claim is not None for claim in claims)==1


def test_expired_worker_is_quarantined_and_cannot_finish(tmp_path,declaration,monkeypatch):
    now=[1000.0]
    # Equal timestamps must retain insertion order, not random UUID order.
    identifiers=iter(['ffffffff-ffff-4fff-8fff-ffffffffffff','00000000-0000-4000-8000-000000000000'])
    monkeypatch.setattr('service.requests.uuid.uuid4',lambda:next(identifiers))
    store=RequestStore(tmp_path/'queue.sqlite',clock=lambda:now[0])
    row=store.submit('owner','one',**declaration)
    store.submit('owner','two',**declaration)
    claim=store.claim(lease_seconds=10)
    assert claim['id']==row['id']
    now[0]+=11
    with pytest.raises(Conflict): store.heartbeat(row['id'],claim['lease_token'])
    with pytest.raises(Conflict): store.finish(row['id'],claim['lease_token'],state='COMPLETED',result_hash='a'*64)
    assert store.claim() is None
    assert store.get('owner',row['id'])['state']=='NEEDS_REVIEW'
    assert store.claim() is None


def test_finish_is_terminal_and_requires_owned_live_claim(tmp_path,declaration):
    store=RequestStore(tmp_path/'queue.sqlite')
    row=store.submit('owner','key',**declaration)
    claim=store.claim()
    with pytest.raises(Conflict): store.finish(row['id'],'wrong',state='COMPLETED',result_hash='b'*64)
    store.heartbeat(row['id'],claim['lease_token'])
    store.finish(row['id'],claim['lease_token'],state='COMPLETED',result_hash='b'*64)
    assert store.get('owner',row['id'])['result_hash']=='b'*64
    assert store.claim() is None
    assert store.submit('owner','key',**declaration)['state']=='COMPLETED'
    with pytest.raises(Conflict): store.finish(row['id'],claim['lease_token'],state='FAILED',result_hash='c'*64)


def test_quotas_and_queued_cancellation(tmp_path,declaration):
    store=RequestStore(tmp_path/'queue.sqlite',capacity=2,per_owner=1)
    row=store.submit('alice','one',**declaration)
    with pytest.raises(QueueFull): store.submit('alice','two',**declaration)
    store.submit('bob','one',**declaration)
    with pytest.raises(QueueFull): store.submit('charlie','one',**declaration)
    store.cancel('alice',row['id']); store.cancel('alice',row['id'])
    row=store.submit('alice','two',**declaration)
    claim=store.claim()
    owner='alice' if claim['id']==row['id'] else 'bob'
    with pytest.raises(Conflict): store.cancel(owner,claim['id'])


def test_arbitrary_source_and_unpinned_implementation_rejected(tmp_path,declaration):
    store=RequestStore(tmp_path/'queue.sqlite')
    with pytest.raises(ValueError): store.submit('owner','one',**dict(declaration,implementation='main'))
    declaration['plan']['oracle_url']='https://example.com/unapproved'
    with pytest.raises(ValueError): store.submit('owner','two',**declaration)
