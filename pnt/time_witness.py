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
        numerator = (delta + 2 * resolution) * 1000000
        denominator = 1000000 - rate_error_ppm
        return (numerator + denominator - 1) // denominator

    if transmitted - received > upper_elapsed(r - s) + 2 * server_error_ns:
        raise ValueError('server processing time exceeds the complete exchange')
    lower = transmitted - upper_elapsed(r - a) - server_error_ns - 1
    upper = received + upper_elapsed(b - s) + server_error_ns + 1
    if lower > upper:
        raise ValueError('inconsistent time interval')
    return dict(lower_unix_ns=lower, upper_unix_ns=upper, width_ns=upper - lower,
                event_start_monotonic_ns=a, event_end_monotonic_ns=b)


def compare_claim(exchange, claim, *, server_error_ns, rate_error_ppm):
    """Check a co-captured UTC claim. Overlap never authenticates GNSS or a fix."""
    _budgets(server_error_ns, rate_error_ppm)
    try:
        if not exchange.get('capture_id') or claim.get('capture_id') != exchange['capture_id']:
            raise ValueError('claim and exchange do not share a capture domain')
        interval = utc_interval(exchange, event_start_ns=claim['start_monotonic_ns'],
                                event_end_ns=claim['end_monotonic_ns'],
                                server_error_ns=server_error_ns, rate_error_ppm=rate_error_ppm)
        utc = _integer(claim['unix_ns'], 'claim unix_ns')
        error = _integer(claim['error_ns'], 'claim error_ns', 0)
    except (KeyError, ValueError) as error:
        return dict(status='INSUFFICIENT_EVIDENCE', reason=str(error))
    # Signed interval for claimant minus witness UTC, including claim error.
    offset_lower = utc - error - interval['upper_unix_ns']
    offset_upper = utc + error - interval['lower_unix_ns']
    gap = max(0, offset_lower, -offset_upper)
    return dict(status='INCONSISTENT_WITH_WITNESS' if gap else 'NOT_DISTINGUISHABLE',
                conditional_on_declared_budgets=True, witness_interval=interval,
                claim_minus_witness_ns=[offset_lower, offset_upper], separation_ns=gap)


def collect(servers, *, server_error_ns, rate_error_ppm, budget_source, timeout_s=5.0, ntp_era=0):
    """Observe listed endpoints once, retaining every success and failure.

    Probe the host clock only. A GNSS adapter must independently establish its
    UTC scale, timestamp semantics and capture association before using this API.
    """
    _budgets(server_error_ns, rate_error_ppm)
    if not budget_source.strip() or not servers or len(set(servers)) != len(servers):
        raise ValueError('nonempty budget source and distinct explicit servers required')
    if not math.isfinite(timeout_s) or timeout_s <= 0 or type(ntp_era) is not int or ntp_era < 0:
        raise ValueError('positive finite timeout and nonnegative integer NTP era required')
    report = dict(schema='pnt-internet-time-v1', regime='EXPLORATORY_TRANSPORT_QUALIFICATION',
                  status='CONDITIONAL_TIME_DIAGNOSTIC',
                  assumptions=dict(server_error_ns=server_error_ns, rate_error_ppm=rate_error_ppm,
                                   budget_source=budget_source, calibrated=False,
                                   trusted_collector_and_monotonic_counter=True,
                                   tls_calendar_bootstrap_required=True),
                  protocol=dict(timeout_s=timeout_s, ntp_era=ntp_era,
                                attempts_per_endpoint=1, automatic_retries=False),
                  claim_source='HOST_WALL_CLOCK_NOT_GNSS', attempts=[])
    for server in servers:
        attempt = dict(server=server, status='WITNESS_UNAVAILABLE')
        report['attempts'].append(attempt)
        try:
            exchange = probe(server, timeout_s=timeout_s, ntp_era=ntp_era)
        except ImportError:
            attempt['reason'] = 'MISSING_OPTIONAL_NTS_DEPENDENCIES'
            continue
        except (NTSError, OSError) as error:
            attempt['reason'] = str(error) if isinstance(error, NTSError) else type(error).__name__
            continue
        exchange['capture_id'] = str(uuid.uuid4())
        claim = dict(capture_id=exchange['capture_id'], unix_ns=exchange['host_claim_unix_ns'],
                     error_ns=exchange['host_claim_error_ns'],
                     start_monotonic_ns=exchange['claim_start_monotonic_ns'],
                     end_monotonic_ns=exchange['claim_end_monotonic_ns'])
        attempt.update(status='AUTHENTICATED_EXCHANGE', exchange=exchange, claim=claim,
                       comparison=compare_claim(exchange, claim, server_error_ns=server_error_ns,
                                                rate_error_ppm=rate_error_ppm))
    return report
