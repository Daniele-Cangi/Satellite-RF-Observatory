"""Native Android ZIP intake and presentation of the existing PNT engine.

No new verdict or replay algorithm. Originals stay in the ZIP; numerical results
are the existing gnss_time comparison, with explicit uncalibrated assumptions.
"""
from collections import Counter
import copy
import csv
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
        terminals = [r for r in comments if r[:1] == ['Terminal']]
        if len(terminals) == 1 and len(terminals[0]) == 5:
            raw_terminal = terminals[0][1]
        else:
            issues.append('Raw terminal missing or ambiguous; partial recording retained')
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
                terminals=dict(raw=raw_terminal, nts=witness.get('acquisition') if witness else None),
                witness_status_counts=dict(sorted(Counter(a.get('status', 'MISSING_STATUS')
                    for a in witness['attempts']).items())) if witness else {},
                checks_not_performed=['RF_authenticity', 'position_accuracy', 'spoofing_attribution',
                                      'geometry', 'network_benefit', 'independent_budget_qualification'],
                limits=['Same-app session metadata and SHA-256 bind retained bytes, not RF origin or hardware attestation.',
                        'All supplied budgets remain explicit uncalibrated assumptions; receiver 68% estimates are not bounds.',
                        'PC analysis is trusted; phone import checks input identity, not the arithmetic or a server signature.',
                        'PTB endpoints share one authority; no independent quorum or ALLOW/BLOCK decision.'])
