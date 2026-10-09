import json
import copy

import pytest

from pnt import time_witness
from pnt.time_witness import compare_bracket_claim, compare_claim, utc_bracket_interval, utc_interval


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


def anchors(*, forward=MS, backward=97 * MS, rate_ppm=0):
    first = exchange(forward, backward=backward)
    second = exchange(backward, backward=forward)
    for field in ('send_monotonic_ns', 'receive_monotonic_ns'):
        second[field] += 2_000 * MS
    for field in ('server_receive_unix_ns', 'server_transmit_unix_ns'):
        second[field] += 2_000 * MS
    for record in (first, second):
        record['server'] = 'same-endpoint'
        for field in ('send_monotonic_ns', 'receive_monotonic_ns'):
            record[field] = 1000 + (record[field] - 1000) * (1000000 + rate_ppm) // 1000000
    return first, second


@pytest.mark.parametrize('forward,backward', [(MS, 97 * MS), (97 * MS, MS), (49 * MS, 49 * MS)])
@pytest.mark.parametrize('rate_ppm', [-100, 0, 100])
@pytest.mark.parametrize('offset,status', [(0, 'NOT_DISTINGUISHABLE'),
                                         (1000 * MS, 'INCONSISTENT_WITH_WITNESS'),
                                         (-1000 * MS, 'INCONSISTENT_WITH_WITNESS')])
def test_two_sided_bracket_covers_intermediate_epoch_with_asymmetry_and_rate(forward, backward, rate_ppm, offset, status):
    first, second = anchors(forward=forward, backward=backward, rate_ppm=rate_ppm)
    candidate = claim(1000 * MS, offset)
    counter = 1000 + 1000 * MS * (1000000 + rate_ppm) // 1000000
    candidate.update(start_monotonic_ns=counter - MS, end_monotonic_ns=counter + MS)
    options = dict(server_error_ns=MS, rate_error_ppm=100)
    assert compare_claim(first, candidate, **options)['status'] == 'INSUFFICIENT_EVIDENCE'
    assert compare_claim(second, candidate, **options)['status'] == 'INSUFFICIENT_EVIDENCE'
    result = compare_bracket_claim(first, second, candidate, max_span_ns=3_000 * MS, **options)
    assert result['status'] == status
    if offset:
        assert result['separation_ns'] > 800 * MS
    else:
        assert result['claim_minus_witness_ns'][0] <= 0 <= result['claim_minus_witness_ns'][1]
    assert result['witness_interval']['width_ns'] < 110 * MS


@pytest.mark.parametrize('event', [100 * MS, 100 * MS + 1, 1000 * MS, 2000 * MS - 1, 2000 * MS])
@pytest.mark.parametrize('biases', [(-MS, MS), (MS, -MS)])
def test_bracket_bounds_include_true_utc_at_edges_with_independent_server_errors(event, biases):
    first, second = anchors()
    for record, bias in zip((first, second), biases):
        record['server_receive_unix_ns'] += bias
        record['server_transmit_unix_ns'] += bias
        record['monotonic_resolution_ns'] = 100
    candidate = claim(event)
    result = compare_bracket_claim(first, second, candidate, server_error_ns=MS,
                                   rate_error_ppm=100, max_span_ns=2100 * MS)
    assert result['status'] == 'NOT_DISTINGUISHABLE'
    bounds = result['witness_interval']
    candidate['unix_ns'] = bounds['upper_unix_ns'] + 1
    assert compare_bracket_claim(first, second, candidate, server_error_ns=MS,
                                 rate_error_ppm=100, max_span_ns=2100 * MS)['separation_ns'] == 1


@pytest.mark.parametrize('change', ['capture', 'claim_capture', 'server', 'missing_server', 'auth',
                                  'before_first', 'after_last', 'overlap', 'span', 'processing',
                                  'step_forward', 'step_backward', 'bad_resolution', 'reversed_event',
                                  'bad_claim', 'missing_anchor', 'non_object'])
def test_unusable_brackets_fail_closed_without_a_receiver_fault(change):
    first, second = anchors()
    candidate = claim(1000 * MS)
    span = 3_000 * MS
    if change == 'capture':
        second['capture_id'] = 'another-process'
    elif change == 'claim_capture':
        candidate['capture_id'] = 'another-process'
    elif change == 'server':
        second['server'] = 'different-endpoint'
    elif change == 'missing_server':
        del first['server']
    elif change == 'auth':
        second['authentication'] = 'PLAIN_NTP'
    elif change == 'before_first':
        candidate['start_monotonic_ns'] = first['receive_monotonic_ns'] - 1
    elif change == 'after_last':
        candidate['end_monotonic_ns'] = second['send_monotonic_ns'] + 1
    elif change == 'overlap':
        second['send_monotonic_ns'] = first['receive_monotonic_ns'] - 1
    elif change == 'span':
        span = second['receive_monotonic_ns'] - first['send_monotonic_ns'] - 1
    elif change == 'processing':
        second['server_transmit_unix_ns'] += 1000 * MS
    elif change in ('step_forward', 'step_backward'):
        for field in ('server_receive_unix_ns', 'server_transmit_unix_ns'):
            second[field] += (1 if change == 'step_forward' else -1) * 1000 * MS
    elif change == 'bad_resolution':
        second['monotonic_resolution_ns'] = True
    elif change == 'reversed_event':
        candidate['end_monotonic_ns'] -= 1
    elif change == 'bad_claim':
        candidate['error_ns'] = -1
    elif change == 'missing_anchor':
        del second['server_receive_unix_ns']
    else:
        first = None
    result = compare_bracket_claim(first, second, candidate, server_error_ns=MS,
                                   rate_error_ppm=100, max_span_ns=span)
    assert result['status'] == 'INSUFFICIENT_EVIDENCE'
    assert 'separation_ns' not in result


@pytest.mark.parametrize('span', [0, -1, True, 1.0])
def test_bracket_span_is_a_positive_explicit_integer(span):
    first, second = anchors()
    with pytest.raises(ValueError):
        compare_bracket_claim(first, second, claim(1000 * MS), server_error_ns=MS,
                              rate_error_ppm=100, max_span_ns=span)


def test_packet_delay_widens_bracket_and_can_hide_a_shift():
    first, second = anchors()
    candidate = claim(1000 * MS, 300 * MS)
    for record in (first, second):
        record['send_monotonic_ns'] += 1000 * MS
        record['receive_monotonic_ns'] += 1000 * MS
    candidate['start_monotonic_ns'] += 1000 * MS
    candidate['end_monotonic_ns'] += 1000 * MS
    options = dict(server_error_ns=MS, rate_error_ppm=100, max_span_ns=3_000 * MS)
    original = compare_bracket_claim(first, second, candidate, **options)
    assert original['status'] == 'INCONSISTENT_WITH_WITNESS'
    delayed = copy.deepcopy((first, second))
    # Only causal send/receive uncertainty changes: server stamps stay intact.
    delayed[0]['send_monotonic_ns'] -= 400 * MS
    delayed[1]['send_monotonic_ns'] -= 400 * MS
    result = compare_bracket_claim(*delayed, candidate, **options)
    assert result['status'] == 'NOT_DISTINGUISHABLE'
    assert result['witness_interval']['width_ns'] > original['witness_interval']['width_ns']
    true_utc = UTC + 1000 * MS
    bounds = utc_bracket_interval(*delayed, event_start_ns=candidate['start_monotonic_ns'],
                                  event_end_ns=candidate['end_monotonic_ns'], **options)
    assert bounds['lower_unix_ns'] <= true_utc <= bounds['upper_unix_ns']
