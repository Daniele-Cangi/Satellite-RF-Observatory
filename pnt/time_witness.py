"""Conditional UTC intervals from authenticated Internet time, without symmetry.

Replay recomputes arithmetic from a trusted collector's record; NTS is symmetric
authentication, not an independently verifiable signature on a saved report.
"""

import math
import uuid

from .nts import NTSError, probe


def _integer(value, name, minimum=None):
    if type(value) is not int or (minimum is not None and value < minimum):
        raise ValueError(f'{name} must be an integer' + (f' >= {minimum}' if minimum is not None else ''))
    return value


def _budgets(server_error_ns, rate_error_ppm):
    _integer(server_error_ns, 'server_error_ns', 0)
    _integer(rate_error_ppm, 'rate_error_ppm', 0)
    if rate_error_ppm >= 1000000:
        raise ValueError('rate_error_ppm must be below one million')


def _elapsed_bounds(delta, resolution, rate_error_ppm):
    """Outward integer bounds; rate budget holds throughout the elapsed time."""
    lower = max(0, delta - 2 * resolution) * 1000000 // (1000000 + rate_error_ppm)
    numerator = (delta + 2 * resolution) * 1000000
    denominator = 1000000 - rate_error_ppm
    return lower, (numerator + denominator - 1) // denominator


def utc_interval(exchange, *, event_start_ns, event_end_ns, server_error_ns, rate_error_ppm):
    """UTC bound for an event bracket wholly inside this exchange's capture.

    R,T are authenticated server receive/transmit UTC; s,r are monotonic
    send/receive bounds. For event [a,b], causality gives
    [T - upper_elapsed(r-a) - epsilon, R + upper_elapsed(b-s) + epsilon].
    An attacker delaying packets widens this interval, rather than inducing
    an unqualified point offset. Server accuracy and monotonic rate remain
    caller-declared assumptions. No holdover or cross-boot association.
    """
    _budgets(server_error_ns, rate_error_ppm)
    if exchange.get('authentication') != 'NTS_TLS13_AES_SIV_256':
        raise ValueError('an authenticated NTS exchange is required')
    s = _integer(exchange['send_monotonic_ns'], 'send_monotonic_ns', 0)
    r = _integer(exchange['receive_monotonic_ns'], 'receive_monotonic_ns', s)
    a = _integer(event_start_ns, 'event_start_ns', s)
    b = _integer(event_end_ns, 'event_end_ns', a)
    if b > r:
        raise ValueError('event is outside the captured exchange; no extrapolation')
    received = _integer(exchange['server_receive_unix_ns'], 'server_receive_unix_ns')
    transmitted = _integer(exchange['server_transmit_unix_ns'], 'server_transmit_unix_ns', received)
    resolution = _integer(exchange['monotonic_resolution_ns'], 'monotonic_resolution_ns', 1)

    def upper_elapsed(delta):
        # Each endpoint can be quantized by one counter resolution. Integer
        # arithmetic avoids loss of precision at modern Unix ns (~10**18).
        return _elapsed_bounds(delta, resolution, rate_error_ppm)[1]

    if transmitted - received > upper_elapsed(r - s) + 2 * server_error_ns:
        raise ValueError('server processing time exceeds the complete exchange')
    lower = transmitted - upper_elapsed(r - a) - server_error_ns - 1
    upper = received + upper_elapsed(b - s) + server_error_ns + 1
    if lower > upper:
        raise ValueError('inconsistent time interval')
    return dict(lower_unix_ns=lower, upper_unix_ns=upper, width_ns=upper - lower,
                event_start_monotonic_ns=a, event_end_monotonic_ns=b)


def utc_bracket_interval(before, after, *, event_start_ns, event_end_ns,
                         server_error_ns, rate_error_ppm, max_span_ns):
    """Bound an event between two same-endpoint exchanges, without symmetry.

    Propagate the causal UTC intervals at the earlier receive and later send
    using counter-rate bounds, then intersect their constraints. Server UTC
    bounds apply at both anchors; the rate budget holds across the entire span.
    No one-sided holdover or mixing
    endpoints; incompatible anchors are insufficient evidence, not a GNSS fault.
    """
    _budgets(server_error_ns, rate_error_ppm)
    _integer(max_span_ns, 'max_span_ns', 1)
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise ValueError('two authenticated exchange objects are required')
    capture_id, server = before.get('capture_id'), before.get('server')
    if not isinstance(capture_id, str) or not capture_id.strip() or after.get('capture_id') != capture_id:
        raise ValueError('bracket anchors do not share a capture domain')
    if not isinstance(server, str) or not server.strip() or after.get('server') != server:
        raise ValueError('bracket anchors must use the same configured NTS endpoint')
    r1 = _integer(before['receive_monotonic_ns'], 'earlier receive_monotonic_ns', 0)
    s2 = _integer(after['send_monotonic_ns'], 'later send_monotonic_ns', r1)
    a = _integer(event_start_ns, 'event_start_ns', r1)
    b = _integer(event_end_ns, 'event_end_ns', a)
    if b > s2:
        raise ValueError('event is not wholly between the two exchanges; no extrapolation')
    options = dict(server_error_ns=server_error_ns, rate_error_ppm=rate_error_ppm)
    first = utc_interval(before, event_start_ns=r1, event_end_ns=r1, **options)
    last = utc_interval(after, event_start_ns=s2, event_end_ns=s2, **options)
    if after['receive_monotonic_ns'] - before['send_monotonic_ns'] > max_span_ns:
        raise ValueError('complete bracket span exceeds max_span_ns')
    resolution = max(before['monotonic_resolution_ns'], after['monotonic_resolution_ns'])

    def elapsed(delta):
        return _elapsed_bounds(delta, resolution, rate_error_ppm)

    minimum, maximum = elapsed(s2 - r1)
    if (last['lower_unix_ns'] > first['upper_unix_ns'] + maximum
            or last['upper_unix_ns'] < first['lower_unix_ns'] + minimum):
        raise ValueError('bracket anchors contradict the declared UTC/counter budgets')
    lower = max(first['lower_unix_ns'] + elapsed(a - r1)[0],
                last['lower_unix_ns'] - elapsed(s2 - a)[1])
    upper = min(first['upper_unix_ns'] + elapsed(b - r1)[1],
                last['upper_unix_ns'] - elapsed(s2 - b)[0])
    if lower > upper:
        raise ValueError('inconsistent bracket time interval')
    return dict(lower_unix_ns=lower, upper_unix_ns=upper, width_ns=upper - lower,
                event_start_monotonic_ns=a, event_end_monotonic_ns=b)


def _compare_interval(interval, claim):
    utc = _integer(claim['unix_ns'], 'claim unix_ns')
    error = _integer(claim['error_ns'], 'claim error_ns', 0)
    # Signed interval for claimant minus witness UTC, including claim error.
    offset_lower = utc - error - interval['upper_unix_ns']
    offset_upper = utc + error - interval['lower_unix_ns']
    gap = max(0, offset_lower, -offset_upper)
    return dict(status='INCONSISTENT_WITH_WITNESS' if gap else 'NOT_DISTINGUISHABLE',
                conditional_on_declared_budgets=True, witness_interval=interval,
                claim_minus_witness_ns=[offset_lower, offset_upper], separation_ns=gap)


def compare_claim(exchange, claim, *, server_error_ns, rate_error_ppm):
    """Check a co-captured UTC claim. Overlap never authenticates GNSS or a fix."""
    _budgets(server_error_ns, rate_error_ppm)
    try:
        if not exchange.get('capture_id') or claim.get('capture_id') != exchange['capture_id']:
            raise ValueError('claim and exchange do not share a capture domain')
        interval = utc_interval(exchange, event_start_ns=claim['start_monotonic_ns'],
                                event_end_ns=claim['end_monotonic_ns'],
                                server_error_ns=server_error_ns, rate_error_ppm=rate_error_ppm)
        return _compare_interval(interval, claim)
    except (KeyError, ValueError) as error:
        return dict(status='INSUFFICIENT_EVIDENCE', reason=str(error))


def compare_bracket_claim(before, after, claim, *, server_error_ns, rate_error_ppm, max_span_ns):
    """Compare one claim with its two retained anchors; never choose anchors here."""
    _budgets(server_error_ns, rate_error_ppm)
    _integer(max_span_ns, 'max_span_ns', 1)
    try:
        if not all(isinstance(value, dict) for value in (before, after, claim)):
            raise ValueError('bracket anchors and claim must be objects')
        if not before.get('capture_id') or claim.get('capture_id') != before['capture_id']:
            raise ValueError('claim and bracket do not share a capture domain')
        interval = utc_bracket_interval(before, after,
                                        event_start_ns=claim['start_monotonic_ns'],
                                        event_end_ns=claim['end_monotonic_ns'],
                                        server_error_ns=server_error_ns, rate_error_ppm=rate_error_ppm,
                                        max_span_ns=max_span_ns)
        return _compare_interval(interval, claim)
    except (KeyError, ValueError) as error:
        return dict(status='INSUFFICIENT_EVIDENCE', reason=str(error))


def _new_report(servers, *, server_error_ns, rate_error_ppm, budget_source, timeout_s, ntp_era):
    """Shared report and validation for host probes and receiver co-capture."""
    _budgets(server_error_ns, rate_error_ppm)
    if not budget_source.strip() or not servers or len(set(servers)) != len(servers):
        raise ValueError('nonempty budget source and distinct explicit servers required')
    if not math.isfinite(timeout_s) or timeout_s <= 0 or type(ntp_era) is not int or ntp_era < 0:
        raise ValueError('positive finite timeout and nonnegative integer NTP era required')
    return dict(schema='pnt-internet-time-v1', regime='EXPLORATORY_TRANSPORT_QUALIFICATION',
                  status='CONDITIONAL_TIME_DIAGNOSTIC',
                  assumptions=dict(server_error_ns=server_error_ns, rate_error_ppm=rate_error_ppm,
                                   budget_source=budget_source, calibrated=False,
                                   trusted_collector_and_monotonic_counter=True,
                                   tls_calendar_bootstrap_required=True),
                  protocol=dict(timeout_s=timeout_s, ntp_era=ntp_era,
                                attempts_per_endpoint=1, automatic_retries=False),
                  claim_source='HOST_WALL_CLOCK_NOT_GNSS', attempts=[])


def _observe_attempt(attempt, *, server_error_ns, rate_error_ppm, timeout_s, ntp_era, capture_id=None):
    """Update an already retained attempt; never retry or replace a failure."""
    try:
        exchange = probe(attempt['server'], timeout_s=timeout_s, ntp_era=ntp_era)
    except ImportError:
        attempt['reason'] = 'MISSING_OPTIONAL_NTS_DEPENDENCIES'
        return
    except (NTSError, OSError) as error:
        attempt['reason'] = str(error) if isinstance(error, NTSError) else type(error).__name__
        return
    exchange['capture_id'] = capture_id if capture_id is not None else str(uuid.uuid4())
    claim = dict(capture_id=exchange['capture_id'], unix_ns=exchange['host_claim_unix_ns'],
                 error_ns=exchange['host_claim_error_ns'],
                 start_monotonic_ns=exchange['claim_start_monotonic_ns'],
                 end_monotonic_ns=exchange['claim_end_monotonic_ns'])
    attempt.update(status='AUTHENTICATED_EXCHANGE', exchange=exchange, claim=claim,
                   comparison=compare_claim(exchange, claim, server_error_ns=server_error_ns,
                                            rate_error_ppm=rate_error_ppm))


def collect(servers, *, server_error_ns, rate_error_ppm, budget_source, timeout_s=5.0, ntp_era=0):
    """Observe listed endpoints once, retaining every success and failure.

    Probe the host clock only. A GNSS adapter must independently establish its
    UTC scale, timestamp semantics and capture association before using this API.
    """
    report = _new_report(servers, server_error_ns=server_error_ns, rate_error_ppm=rate_error_ppm,
                         budget_source=budget_source, timeout_s=timeout_s, ntp_era=ntp_era)
    for server in servers:
        attempt = dict(server=server, status='WITNESS_UNAVAILABLE')
        report['attempts'].append(attempt)
        _observe_attempt(attempt, server_error_ns=server_error_ns, rate_error_ppm=rate_error_ppm,
                         timeout_s=timeout_s, ntp_era=ntp_era)
    return report
