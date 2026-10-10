"""Native Android ZIP intake and presentation of the existing PNT engine.

No new verdict or replay algorithm. Originals stay in the ZIP; numerical results
are the existing gnss_time comparison, with explicit uncalibrated assumptions.
"""
from collections import Counter
import copy
import csv
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import zipfile

from .android_raw import inspect_android_raw_bytes
from .android_time import compare_android_time
from .gnss_time import _text
from .time_witness import _budgets, _integer

MAX_ARCHIVE_BYTES = 32 * 1024 * 1024
MAX_REPORT_BYTES = 32 * 1024 * 1024
MEMBER = re.compile(r'pnt-(clock|nts)-([a-zA-Z0-9-]{1,80})\.(txt|json)\Z')
REQUIRED_OPTIONS = {
    'server_error_ns', 'rate_error_ppm', 'budget_source',
    'monotonic_resolution_ns', 'counter_resolution_source', 'association_source',
    'gps_utc_offset_seconds', 'time_scale_source', 'utc_error_ns', 'utc_error_source',
}
OPTIONAL_OPTIONS = {'epoch_alignment_error_ns', 'epoch_alignment_source', 'bracket_span_ns'}
LEGACY_FIXED_PTB_VERSIONS = {'0.2.0', '0.3.0', '0.3.1', '0.4.0'}


def load_json(data):
    """Reject duplicate keys/nonfinite numbers rather than reinterpret options."""
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'duplicate JSON key: {key}')
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError(f'nonfinite JSON number: {value}')

    return json.loads(data, object_pairs_hook=object_pairs, parse_constant=invalid_constant)


def _options(options):
    if options is None:
        return
    if not isinstance(options, dict) or not REQUIRED_OPTIONS <= options.keys():
        raise ValueError('analysis options require all explicit budgets, resolution and sources')
    if options.keys() - REQUIRED_OPTIONS - OPTIONAL_OPTIONS:
        raise ValueError('unknown analysis option; no silently ignored parameters')
    _budgets(options['server_error_ns'], options['rate_error_ppm'])
    for name in ('monotonic_resolution_ns', 'utc_error_ns', 'gps_utc_offset_seconds'):
        _integer(options[name], name, 1 if name == 'monotonic_resolution_ns' else 0)
    if options['gps_utc_offset_seconds'] > 127:
        raise ValueError('gps_utc_offset_seconds exceeds the supported range')
    for name in REQUIRED_OPTIONS:
        if name.endswith('source'):
            _text(options[name], name)
    if any(options.get(k) is not None for k in ('epoch_alignment_error_ns', 'epoch_alignment_source')):
        _integer(options.get('epoch_alignment_error_ns'), 'epoch_alignment_error_ns', 0)
        _text(options.get('epoch_alignment_source'), 'epoch_alignment_source')
    if options.get('bracket_span_ns') is not None:
        _integer(options['bracket_span_ns'], 'bracket_span_ns', 1)


def _processor():
    """Ordinary Git provenance, not a seal or a scientific admission gate."""
    try:
        root = Path(__file__).resolve().parents[1]
        revision = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'],
                                           stderr=subprocess.DEVNULL, timeout=5).decode().strip()
        dirty = bool(subprocess.check_output(['git', '-C', str(root), 'status', '--porcelain'],
                                            stderr=subprocess.DEVNULL, timeout=5))
    except (OSError, subprocess.SubprocessError):
        revision, dirty = None, None
    return dict(command='python -m pnt android-session', source_revision=revision, working_tree_dirty=dirty)


def _source(name, data):
    return dict(name=name, size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def _comment_integer(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]+', value):
        raise ValueError('native terminal/event count must be a nonnegative integer')
    return int(value)


def _raw_terminal(raw, comments):
    terminals = [r for r in comments if r[:1] == ['Terminal']]
    if len(terminals) != 1 or len(terminals[0]) != 5:
        raise ValueError('Raw terminal missing or ambiguous; partial recording retained')
    _, reason, stop, event_count, row_count = terminals[0]
    _text(reason, 'Raw terminal reason')
    _comment_integer(stop)
    events = [r for r in comments if r[:1] == ['Event']]
    if (_comment_integer(event_count) != len(events)
            or _comment_integer(row_count) != raw['coverage']['status_counts']['raw_rows']):
        raise ValueError('Raw terminal accounting differs from retained events/Raw rows')
    actual = raw['source']['native_event_row_counts']
    declared_total = 0
    for index, event in enumerate(events, 1):
        if (len(event) < 5 or _comment_integer(event[1]) != index
                or _comment_integer(event[4]) != actual.get(str(index), 0)):
            raise ValueError('Raw event accounting differs from retained Raw rows')
        _comment_integer(event[2])
        _comment_integer(event[3])
        declared_total += _comment_integer(event[4])
    if declared_total != _comment_integer(row_count):
        raise ValueError('Raw event totals differ from terminal accounting')
    return reason


def _nts_schedule(witness):
    protocol = witness.get('protocol')
    if not isinstance(protocol, dict):
        raise ValueError('NTS declared protocol/schedule is missing')
    rounds = _integer(protocol.get('rounds'), 'NTS rounds', 1)
    if _integer(protocol.get('attempts_per_endpoint'), 'NTS attempts_per_endpoint', 1) != rounds:
        raise ValueError('NTS attempts_per_endpoint differs from rounds')
    if protocol.get('schedule') != 'ROUND_START_OFFSETS' or protocol.get('automatic_retries') is not False:
        raise ValueError('unsupported NTS schedule/retry declaration')
    endpoints = protocol.get('endpoints')
    source = 'protocol.endpoints'
    if endpoints is None:
        metadata = witness['capture_context'].get('metadata', {})
        version = metadata.get('Version') if isinstance(metadata, dict) else None
        if version not in LEGACY_FIXED_PTB_VERSIONS:
            raise ValueError('NTS endpoint set not declared; unknown legacy collector version')
        endpoints = ['ptbtime1.ptb.de', 'ptbtime2.ptb.de']
        source = f'legacy {version} fixed PTB endpoint declaration (trusted metadata, not attestation)'
    if (not isinstance(endpoints, list) or not 1 <= len(endpoints) <= 4
            or not all(isinstance(s, str) and s.strip() for s in endpoints)
            or len(set(endpoints)) != len(endpoints)):
        raise ValueError('invalid NTS endpoint declaration')
    interval = protocol.get('interval_ns')
    if interval is None:
        try:
            decimal = Decimal(str(protocol.get('interval_s'))) * 10**9
            if not decimal.is_finite() or decimal != decimal.to_integral_value():
                raise ValueError('NTS interval_s is not an exact integer nanosecond declaration')
            interval = int(decimal)
        except InvalidOperation as error:
            raise ValueError('invalid NTS interval declaration') from error
    _integer(interval, 'NTS interval_ns', 1)
    attempts = witness['attempts']
    planned = rounds * len(endpoints)
    if len(attempts) != planned or _integer(protocol.get('planned_attempts', planned), 'NTS planned_attempts', 1) != planned:
        raise ValueError('NTS slot accounting differs from the declared complete schedule')
    acquisition = witness['acquisition']
    start = _integer(acquisition.get('started_monotonic_ns'), 'NTS acquisition start', 0)
    end = _integer(acquisition.get('ended_monotonic_ns'), 'NTS acquisition end', start)
    previous_end, unattempted = start, False
    for index, attempt in enumerate(attempts):
        if (attempt.get('server') != endpoints[index % len(endpoints)]
                or type(attempt.get('round_index')) is not int or attempt['round_index'] != index // len(endpoints)
                or type(attempt.get('scheduled_round_start_monotonic_ns')) is not int
                or attempt['scheduled_round_start_monotonic_ns'] != start + index // len(endpoints) * interval
                or attempt['status'] not in {'AUTHENTICATED_EXCHANGE', 'WITNESS_UNAVAILABLE', 'NOT_ATTEMPTED'}):
            raise ValueError('NTS retained slot differs from its declared endpoint/round/schedule')
        if attempt['status'] == 'NOT_ATTEMPTED':
            unattempted = True
            if any(key in attempt for key in ('started_monotonic_ns', 'finished_monotonic_ns', 'exchange')):
                raise ValueError('NTS unattempted slot contains active attempt/exchange data')
        else:
            if unattempted:
                raise ValueError('NTS attempted slots must form a prefix before unattempted slots')
            attempt_start = _integer(attempt.get('started_monotonic_ns'), 'NTS attempt start', start)
            attempt_end = _integer(attempt.get('finished_monotonic_ns'), 'NTS attempt end', attempt_start)
            if attempt_start < max(previous_end, attempt['scheduled_round_start_monotonic_ns']):
                raise ValueError('NTS attempt precedes its schedule or the preceding attempt end')
            if attempt_end > end:
                raise ValueError('NTS attempt lies outside the declared acquisition window')
            previous_end = attempt_end
        if attempt['status'] == 'AUTHENTICATED_EXCHANGE':
            exchange = attempt.get('exchange')
            if (not isinstance(exchange, dict) or exchange.get('capture_id') != witness['capture_id']
                    or exchange.get('counter_clock') != 'CLOCK_BOOTTIME' or exchange.get('server') != attempt['server']):
                raise ValueError('NTS authenticated exchange differs from its retained slot/capture domain')
            sent = _integer(exchange.get('send_monotonic_ns'), 'NTS exchange send', attempt_start)
            received = _integer(exchange.get('receive_monotonic_ns'), 'NTS exchange receive', sent)
            if received > attempt_end:
                raise ValueError('NTS exchange lies outside its declared attempt/acquisition window')
    terminal = witness.get('terminal')
    totals = Counter(a['status'] for a in attempts)
    if not isinstance(terminal, dict) or terminal.get('reason') != acquisition['terminal_reason']:
        raise ValueError('NTS terminal accounting missing or inconsistent')
    if (_integer(terminal.get('counter_ns'), 'NTS terminal counter', 0) != end
            or _integer(terminal.get('authenticated_exchanges'), 'NTS authenticated total', 0) != totals['AUTHENTICATED_EXCHANGE']
            or _integer(terminal.get('unavailable_attempts'), 'NTS unavailable total', 0) != totals['WITNESS_UNAVAILABLE']):
        raise ValueError('NTS terminal accounting differs from retained attempt statuses')
    return source


def inspect_android_session(path, *, analysis_options=None):
    """Retain missing/partial/unusable captures; never invent a timing bound.

    Names are inspected and members read in memory. Nothing in the ZIP is
    extracted, executed, fetched or used as a filesystem destination.
    """
    _options(analysis_options)
    path = Path(path)
    with path.open('rb') as stream:
        archive = stream.read(MAX_ARCHIVE_BYTES + 1)
    if len(archive) > MAX_ARCHIVE_BYTES:
        raise ValueError('session ZIP exceeds the 32 MiB input limit')
    members = {}
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
            entries = zipped.infolist()
            if not 1 <= len(entries) <= 2 or sum(e.file_size for e in entries) > MAX_ARCHIVE_BYTES:
                raise ValueError('session requires one Raw member and optional NTS; 32 MiB total limit')
            for entry in entries:
                match = MEMBER.fullmatch(entry.filename)
                if (match is None or entry.filename in members or entry.flag_bits & 1
                        or (match[1], match[3]) not in (('clock', 'txt'), ('nts', 'json'))):
                    raise ValueError('invalid, duplicate or encrypted session member')
                with zipped.open(entry) as stream:
                    content = stream.read(MAX_ARCHIVE_BYTES + 1)
                if len(content) != entry.file_size or len(content) > MAX_ARCHIVE_BYTES:
                    raise ValueError('ZIP member size differs from its directory')
                members[entry.filename] = content
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError) as error:
        raise ValueError(f'invalid session ZIP: {error}') from error
    raw_names = [n for n in members if n.startswith('pnt-clock-')]
    if len(raw_names) != 1:
        raise ValueError('exactly one native Raw member is required')
    raw_name = raw_names[0]
    capture_id = MEMBER.fullmatch(raw_name)[2]
    nts_name = f'pnt-nts-{capture_id}.json'
    if set(members) - {raw_name, nts_name}:
        raise ValueError('Raw and NTS filenames identify different sessions')
    issues, raw, witness, comparison = [], None, None, None
    format_notes = []
    raw_terminal = None
    try:
        if members[raw_name].startswith(b'\x1f\x8b'):
            raise ValueError('native ZIP Raw must be plain UTF-8, without nested gzip expansion')
        raw = inspect_android_raw_bytes(members[raw_name], raw_name, allow_empty=True,
                                        expected_capture_id=capture_id)
        comments = [next(csv.reader([line[2:]])) for line in raw['source']['comments']]
        if [r for r in comments if r[:1] == ['Format']] != [['Format', 'pnt-android-clock-collector-v1']]:
            raise ValueError('native collector format marker is required')
        if [r for r in comments if r[:1] == ['CaptureId']] != [['CaptureId', capture_id]]:
            raise ValueError('Raw metadata differs from the filename capture ID')
        try:
            raw_terminal = _raw_terminal(raw, comments)
        except ValueError as error:
            issues.append(str(error))
        if not raw['coverage']['status_counts']['raw_rows']:
            issues.append('No Android Raw measurements; no GNSS time comparison')
    except (ValueError, UnicodeError, csv.Error, OSError) as error:
        raw = None
        issues.append(f'Raw intake failed: {error}')
    if nts_name not in members:
        issues.append('NTS original missing; no Internet time comparison')
    else:
        try:
            witness = load_json(members[nts_name])
            if (not isinstance(witness, dict) or witness.get('schema') != 'pnt-internet-time-v1'
                    or witness.get('capture_id') != capture_id):
                raise ValueError('NTS schema or capture ID differs from the Raw session')
            context = witness.get('capture_context', {})
            if (not isinstance(context, dict) or context.get('capture_id') != capture_id
                    or context.get('gnss_file') != raw_name or context.get('counter_clock') != 'CLOCK_BOOTTIME'
                    or context.get('gnss_acquired_by_this_command') is not True):
                raise ValueError('NTS native same-app capture context differs from the Raw session')
            attempts = witness.get('attempts')
            if not isinstance(attempts, list) or not all(isinstance(a, dict) for a in attempts):
                raise ValueError('NTS attempts must retain every slot as an object')
            if not all(isinstance(a.get('status'), str) and a['status'] for a in attempts):
                raise ValueError('NTS attempt status must be a nonempty string')
            if not isinstance(witness.get('assumptions'), dict):
                raise ValueError('NTS assumptions must retain the original unknown budgets')
            acquisition = witness.get('acquisition', {})
            if (not isinstance(acquisition, dict) or acquisition.get('state') != 'FINISHED'
                    or not isinstance(acquisition.get('terminal_reason'), str)):
                issues.append('NTS terminal missing; last partial checkpoint retained')
            else:
                try:
                    format_notes.append('NTS schedule bound by ' + _nts_schedule(witness))
                except ValueError as error:
                    issues.append(str(error))
        except (ValueError, UnicodeError, RecursionError) as error:
            witness = None
            issues.append(f'NTS intake failed: {error}')
    if analysis_options is None:
        issues.append('Timing comparison not run: explicit server/rate/UTC budgets, counter resolution '
                      'and external GPS-UTC conversion have not been supplied')
    elif not issues:
        # Derived analysis input, never overwrite the retained acquisition.
        prepared = copy.deepcopy(witness)
        prepared.setdefault('assumptions', {}).update(
            server_error_ns=analysis_options['server_error_ns'], rate_error_ppm=analysis_options['rate_error_ppm'],
            budget_source=analysis_options['budget_source'], calibrated=False)
        for attempt in prepared['attempts']:
            if isinstance(attempt.get('exchange'), dict):
                attempt['exchange']['monotonic_resolution_ns'] = analysis_options['monotonic_resolution_ns']
        options = {k: v for k, v in analysis_options.items()
                   if k not in {'server_error_ns', 'rate_error_ppm', 'budget_source',
                                'monotonic_resolution_ns', 'counter_resolution_source'}}
        try:
            comparison = compare_android_time(prepared, raw, **options)
        except (ValueError, KeyError, TypeError) as error:
            issues.append(f'Timing comparison not run: {error}')
    return dict(schema='pnt-android-session-report-v1', regime='EXPLORATORY_SESSION_REPORT',
                status=comparison['status'] if comparison else 'INSUFFICIENT_EVIDENCE',
                capture_id=capture_id, processor=_processor(),
                sources=dict(archive=_source(path.name, archive),
                             members=[_source(n, data) for n, data in sorted(members.items())]),
                intake=raw, witness_report=witness, comparison=comparison,
                analysis_options=copy.deepcopy(analysis_options), issues=issues,
                format_notes=format_notes,
                terminals=dict(raw=raw_terminal, nts=witness.get('acquisition') if witness else None),
                witness_status_counts=dict(sorted(Counter(a.get('status', 'MISSING_STATUS')
                    for a in witness['attempts']).items())) if witness else {},
                checks_not_performed=['RF_authenticity', 'position_accuracy', 'spoofing_attribution',
                                      'geometry', 'network_benefit', 'independent_budget_qualification'],
                limits=['Same-app session metadata and SHA-256 bind retained bytes, not RF origin or hardware attestation.',
                        'All supplied budgets remain explicit uncalibrated assumptions; receiver 68% estimates are not bounds.',
                        'PC analysis is trusted; phone import checks input identity, not the arithmetic or a server signature.',
                        'PTB endpoints share one authority; no independent quorum or ALLOW/BLOCK decision.'])
