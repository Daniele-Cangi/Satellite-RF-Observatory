import json

import pytest

from pnt import time_witness
from pnt.time_witness import compare_claim, utc_interval


UTC = 1700000000000000000
MS = 1000000


def exchange(forward=1 * MS, processing=2 * MS, backward=97 * MS):
    return dict(authentication='NTS_TLS13_AES_SIV_256', capture_id='same-process',
                send_monotonic_ns=1000, receive_monotonic_ns=1000 + forward + processing + backward,
                server_receive_unix_ns=UTC + forward, server_transmit_unix_ns=UTC + forward + processing,
                monotonic_resolution_ns=1)


def claim(event_ns, offset=0):
    return dict(capture_id='same-process', unix_ns=UTC + event_ns + offset, error_ns=0,
                start_monotonic_ns=1000 + event_ns, end_monotonic_ns=1000 + event_ns)


@pytest.mark.parametrize('forward,backward', [(1 * MS, 97 * MS), (97 * MS, 1 * MS), (49 * MS, 49 * MS)])
@pytest.mark.parametrize('rate_ppm', [-100, 0, 100])
def test_true_clock_remains_inside_bound_with_asymmetry_and_rate_error(forward, backward, rate_ppm):
    record = exchange(forward, backward=backward)
    event = forward + 2 * MS + backward
    record['receive_monotonic_ns'] = 1000 + event * (1000000 + rate_ppm) // 1000000
    candidate = claim(event)
    candidate['start_monotonic_ns'] = candidate['end_monotonic_ns'] = record['receive_monotonic_ns']
    result = compare_claim(record, candidate, server_error_ns=0, rate_error_ppm=100)
    assert result['status'] == 'NOT_DISTINGUISHABLE'
    lower, upper = result['claim_minus_witness_ns']
    assert lower <= 0 <= upper


def test_common_one_second_clock_shift_is_separated_but_small_shift_may_not_be():
    record = exchange()
    options = dict(server_error_ns=MS, rate_error_ppm=100)
    ordinary = compare_claim(record, claim(100 * MS), **options)
    small = compare_claim(record, claim(100 * MS, -MS), **options)
    shifted = compare_claim(record, claim(100 * MS, 1000 * MS), **options)
    assert ordinary['status'] == small['status'] == 'NOT_DISTINGUISHABLE'
    assert shifted['status'] == 'INCONSISTENT_WITH_WITNESS'
    assert shifted['separation_ns'] > 900 * MS
    # A delayed authenticated packet can hide a fault by widening uncertainty;
    # it cannot make the actual UTC falsely inconsistent within these assumptions.
    delayed = exchange(backward=2000 * MS)
    assert compare_claim(delayed, claim(2003 * MS), **options)['status'] == 'NOT_DISTINGUISHABLE'
    assert utc_interval(delayed, event_start_ns=delayed['receive_monotonic_ns'],
                        event_end_ns=delayed['receive_monotonic_ns'], **options)['width_ns'] > 2_000 * MS


def test_claim_uncertainty_and_exact_integer_boundary():
    record = exchange()
    options = dict(server_error_ns=0, rate_error_ppm=0)
    interval = utc_interval(record, event_start_ns=100001000, event_end_ns=100001000, **options)
    candidate = claim(100 * MS)
    candidate['unix_ns'] = interval['upper_unix_ns'] + 1
    assert compare_claim(record, candidate, **options)['separation_ns'] == 1
    candidate['error_ns'] = 1
    assert compare_claim(record, candidate, **options)['status'] == 'NOT_DISTINGUISHABLE'


def test_bracketed_event_inside_exchange_uses_its_own_time_not_receive_time():
    record = exchange()
    candidate = claim(50 * MS)
    candidate['start_monotonic_ns'] -= MS
    candidate['end_monotonic_ns'] += MS
    result = compare_claim(record, candidate, server_error_ns=0, rate_error_ppm=0)
    interval = result['witness_interval']
    assert interval['lower_unix_ns'] < candidate['unix_ns'] < interval['upper_unix_ns']
    assert interval['lower_unix_ns'] < UTC  # Backward delay permits an earlier event.
    assert result['status'] == 'NOT_DISTINGUISHABLE'


def test_retained_real_transport_report_replays_without_network():
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / 'research/exploratory/results/pnt_internet_time_v1.json'
    report = json.loads(path.read_text(encoding='utf-8'))
    options = {name: report['assumptions'][name] for name in ('server_error_ns', 'rate_error_ppm')}
    assert len(report['attempts']) == len(report['preliminary_transport_exchanges']) == 2
    for attempt in report['attempts']:
        assert compare_claim(attempt['exchange'], attempt['claim'], **options) == attempt['comparison']
        assert attempt['comparison']['status'] == 'INCONSISTENT_WITH_WITNESS'


@pytest.mark.parametrize('change', ['capture', 'stale', 'unauthenticated', 'negative_error', 'floating_timestamp', 'processing'])
def test_unqualified_or_misassociated_evidence_is_unavailable(change):
    record, candidate = exchange(), claim(100 * MS)
    if change == 'capture':
        candidate['capture_id'] = 'old-boot'
    elif change == 'stale':
        candidate['end_monotonic_ns'] += 1
    elif change == 'unauthenticated':
        record['authentication'] = 'PLAIN_NTP'
    elif change == 'negative_error':
        candidate['error_ns'] = -1
    elif change == 'floating_timestamp':
        candidate['unix_ns'] = float(candidate['unix_ns'])
    else:
        record['server_transmit_unix_ns'] += 2_000 * MS
    assert compare_claim(record, candidate, server_error_ns=MS, rate_error_ppm=100)['status'] == 'INSUFFICIENT_EVIDENCE'


def test_collection_retains_failure_does_not_retry_and_replays_comparison(monkeypatch):
    attempts = []

    def fake_probe(server, **kwargs):
        attempts.append(server)
        if server == 'unavailable':
            raise TimeoutError('test timeout')
        record = exchange()
        record.update(host_claim_unix_ns=UTC + 100 * MS, host_claim_error_ns=1,
                      claim_start_monotonic_ns=100001000, claim_end_monotonic_ns=100001000)
        return record

    monkeypatch.setattr(time_witness, 'probe', fake_probe)
    report = time_witness.collect(['unavailable', 'witness'], server_error_ns=MS,
                                 rate_error_ppm=100, budget_source='uncalibrated test assumption')
    assert attempts == ['unavailable', 'witness']
    restored = json.loads(json.dumps(report))
    assert restored['attempts'][0]['status'] == 'WITNESS_UNAVAILABLE'
    success = restored['attempts'][1]
    assert success['comparison'] == compare_claim(success['exchange'], success['claim'],
                                                 server_error_ns=MS, rate_error_ppm=100)
    assert restored['claim_source'] == 'HOST_WALL_CLOCK_NOT_GNSS'
    assert restored['assumptions']['calibrated'] is False


@pytest.mark.parametrize('budgets', [(-1, 100), (0, -1), (0, 1000000), (True, 100), (0, 0.1)])
def test_bad_assumptions_rejected_before_network_access(monkeypatch, budgets):
    monkeypatch.setattr(time_witness, 'probe', lambda *a, **k: pytest.fail('network accessed'))
    with pytest.raises(ValueError):
        time_witness.collect(['witness'], server_error_ns=budgets[0], rate_error_ppm=budgets[1], budget_source='test')


def test_cli_report_and_existing_output_guard(monkeypatch, tmp_path):
    from pnt.__main__ import main

    path = tmp_path / 'time.json'
    monkeypatch.setattr(time_witness, 'probe', lambda *a, **k: (_ for _ in ()).throw(TimeoutError()))
    monkeypatch.setattr('sys.argv', ['pnt', 'time-probe', '--server', 'witness', '--server-error-ns', '1000000',
                                   '--rate-error-ppm', '100', '--budget-source', 'test', '--output', str(path)])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    report = json.loads(path.read_text())
    assert report['attempts'][0]['status'] == 'WITNESS_UNAVAILABLE'
    original = path.read_bytes()
    with pytest.raises(SystemExit):
        main()
    assert path.read_bytes() == original
