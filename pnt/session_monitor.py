"""PC file-snapshot monitor of the existing conditional Android time engine.

No acquisition, upload, new detector, clock mapping or immutable alarm claim.
Every changed/error snapshot and every per-record revision stays in the output.
"""
import copy
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import time

from .__main__ import write_report
from .android_session import _inspect_android_members, _options, _read_native_files, _source
from .time_sensitivity import assess_time_sensitivity, _method_outcomes
from .time_witness import _integer


class AndroidSessionMonitor:
    """Observe one collector session; persistence is ordinary diagnostic output."""

    def __init__(self, raw_path, nts_path, output_directory, *, analysis_options=None,
                 local_counter_resolution_ns):
        _options(analysis_options)
        _integer(local_counter_resolution_ns, 'local_counter_resolution_ns', 1)
        self.raw_path, self.nts_path = Path(raw_path), Path(nts_path)
        self.options = copy.deepcopy(analysis_options)
        self.resolution = local_counter_resolution_ns
        self.output = Path(output_directory)
        self.output.mkdir(parents=True, exist_ok=False)
        write_report(dict(analysis_options=self.options, local_counter_resolution_ns=self.resolution,
            input_paths=[str(self.raw_path), str(self.nts_path)],
            scope='PC_FILE_SNAPSHOTS_ONLY; NOT_PHONE_ALERT_LATENCY_OR_RF_AUTHENTICATION'), self.output/'options.json')
        self.raw_previous, self.raw_closed, self.witness_previous = None, False, None
        self.previous_outcomes, self.last_fingerprint, self.last_update = {}, None, None
        self.last_input_fingerprint = None
        self.updates, self.finished = 0, False
        self.invalidation_reason = None

    def _history_issues(self, members, report):
        issues = []
        raw = members[self.raw_path.name]
        if self.raw_previous is not None and (not raw.startswith(self.raw_previous)
                or self.raw_closed and raw != self.raw_previous):
            issues.append('Raw recording changed/truncated instead of appending; prior snapshot retained')
        witness, previous = report['witness_report'], self.witness_previous
        if witness is not None and previous is not None and report['snapshot']['nts_schedule_valid']:
            if (witness.get('protocol') != previous['protocol']
                    or witness.get('capture_context') != previous['capture_context']
                    or witness['acquisition'].get('started_monotonic_ns') != previous['acquisition']['started_monotonic_ns']
                    or witness.get('assumptions') != previous['assumptions']):
                issues.append('NTS schedule/context/assumptions changed within the monitored session')
            current = witness['attempts']
            for index, attempt in enumerate(previous['attempts']):
                if 'finished_monotonic_ns' in attempt and (index >= len(current) or current[index] != attempt):
                    issues.append(f'Completed NTS slot {index} changed or disappeared; prior snapshot retained')
            if previous['acquisition']['state'] == 'FINISHED' and witness != previous:
                issues.append('Closed NTS recording changed or reopened')
        return issues

    def poll(self):
        """Publish changed input/error state; return None for identical polls."""
        if self.invalidation_reason:
            raise ValueError('monitor invalidated after a storage failure')
        try:
            return self._poll()
        except OSError as error:
            self.invalidate(f'Snapshot publication failed: {error}')
            raise

    def invalidate(self, reason):
        """Clear current results; finish durably records the failed admission.

        Previously published snapshots remain historical evidence. If storage
        also refuses the summary, the caller fails instead of returning success.
        """
        if self.finished:
            raise ValueError('monitor is closed')
        self.invalidation_reason = reason
        self.last_update, self.previous_outcomes = None, {}

    def _poll(self):
        if self.finished:
            raise ValueError('monitor is closed')
        started = time.monotonic_ns()
        members, report, outcomes, issues, read_end = {}, None, {}, [], None
        input_fingerprint = None
        try:
            members, capture_id = _read_native_files(self.raw_path, self.nts_path)
            read_end = time.monotonic_ns()
            input_fingerprint = tuple((name, hashlib.sha256(data).hexdigest()) for name, data in sorted(members.items()))
            if input_fingerprint == self.last_input_fingerprint:
                return None
            report = _inspect_android_members(members, capture_id, analysis_options=self.options,
                sources=dict(members=[_source(n, b) for n, b in sorted(members.items())]), allow_in_progress=True)
            history_issues = self._history_issues(members, report)
            issues = report['issues'] + history_issues
            if not issues and report['comparison'] is not None:
                # Zero control is the existing paired engine, without a challenge
                # or retrospective common/group selection for the live monitor.
                controls = assess_time_sensitivity(report['comparison'], [0],
                    local_counter_resolution_ns=self.resolution)
                methods = _method_outcomes(controls['offset_cases'][0], len(report['comparison']['records']))
                outcomes = {i: {method: values[i] for method, values in methods.items()}
                            for i in range(len(report['comparison']['records']))}
            if not history_issues:
                if report['snapshot']['raw_events_valid']:
                    self.raw_previous, self.raw_closed = members[self.raw_path.name], report['terminals']['raw'] is not None
                if report['snapshot']['nts_schedule_valid']:
                    self.witness_previous = copy.deepcopy(report['witness_report'])
        except (ValueError, OSError, UnicodeError, RecursionError) as error:
            if read_end is None:
                read_end = time.monotonic_ns()
            issues.append(f'Snapshot unavailable: {error}')
            outcomes = {}
        fingerprint = (tuple((name, hashlib.sha256(data).hexdigest()) for name, data in sorted(members.items())),
                       tuple(issues))
        if fingerprint == self.last_fingerprint:
            return None
        changes = []
        for index in sorted(self.previous_outcomes.keys() | outcomes.keys()):
            old, new = self.previous_outcomes.get(index), outcomes.get(index)
            if old != new:
                changes.append(dict(source_index=index, previous=old,
                    current=new or dict.fromkeys(('local', 'external', 'combined'), 'INSUFFICIENT_EVIDENCE')))
        analysed = time.monotonic_ns()
        next_update = self.updates + 1
        folder = self.output/f'update-{next_update:05d}'
        folder.mkdir()
        for name, data in members.items():
            with (folder/name).open('xb') as stream:
                stream.write(data)
        update = dict(schema='pnt-android-session-monitor-update-v1', regime='EXPLORATORY_FILE_SNAPSHOT_DIAGNOSTIC',
            update_index=next_update, status=report['status'] if report and not issues else 'INSUFFICIENT_EVIDENCE',
            session_complete=bool(report and not issues and report['snapshot']['session_complete']),
            capture_id=report['capture_id'] if report else None,
            processor=report['processor'] if report else None,
            source_members=[_source(n, b) for n, b in sorted(members.items())],
            issues=issues, revisions=changes, record_outcomes=outcomes,
            record_reasons={r['source_index']: r['reason'] for r in report['comparison']['records'] if 'reason' in r}
                if report and not issues and report['comparison'] is not None else {},
            witness_status_counts=report['witness_status_counts'] if report else {},
            snapshot=report['snapshot'] if report else None,
            timing=dict(counter_clock='PC_MONOTONIC', read_started_ns=started,
                        input_read_completed_ns=read_end, analysis_completed_ns=analysed),
            limits=['Uncalibrated declared assumptions; no RF authentication or ALLOW/BLOCK decision.',
                    'Per-record outcomes are revisable as new evidence arrives; no endpoint vote.',
                    'PC file observation/publishing is not phone callback-to-operator latency.'])
        write_report(update, folder/'result.json', durable=True)
        published = time.monotonic_ns()  # After the result file has been flushed.
        receipt = dict(update_index=next_update, result=f'{folder.name}/result.json',
            result_published_monotonic_ns=published, counter_clock='PC_MONOTONIC',
            input_read_ns=read_end-started, analysis_ns=analysed-read_end,
            result_publication_ns=published-analysed, total_pc_processing_ns=published-started,
            status=update['status'], session_complete=update['session_complete'], issues=len(issues), issue_messages=issues,
            revised_records=sum(c['previous'] is not None for c in changes),
            record_outcome_counts={m: dict(Counter(v[m] for v in outcomes.values())) for m in ('local', 'external', 'combined')})
        with (self.output/'updates.jsonl').open('a', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(receipt, sort_keys=True, allow_nan=False)+'\n')
            stream.flush()
            os.fsync(stream.fileno())
        self.last_fingerprint, self.previous_outcomes, self.last_update = fingerprint, outcomes, update
        self.last_input_fingerprint = input_fingerprint
        self.updates = next_update
        return receipt

    def finish(self, reason):
        if self.finished:
            raise ValueError('monitor is closed')
        self.finished = True
        summary = dict(schema='pnt-android-session-monitor-summary-v1', updates=self.updates, stop_reason=reason,
            status=self.last_update['status'] if self.last_update else 'INSUFFICIENT_EVIDENCE',
            session_complete=bool(self.last_update and self.last_update['session_complete']),
            last_result=f'update-{self.updates:05d}/result.json' if self.updates and not self.invalidation_reason else None,
            scope='PC_FILE_SNAPSHOTS_ONLY', phone_operator_alert_latency_measured=False,
            original_inputs_modified=False, calibrated=False)
        if self.invalidation_reason:
            summary.update(issues=[self.invalidation_reason],
                prior_result=f'update-{self.updates:05d}/result.json' if self.updates else None)
        write_report(summary, self.output/'summary.json', durable=True)
        return summary


def monitor_android_files(raw_path, nts_path, output_directory, *, analysis_options=None,
                          local_counter_resolution_ns, duration_s=60, poll_interval_s=.5, on_update=None):
    """Bounded foreground PC monitor; no background process or phone control."""
    for name, value in (('duration_s', duration_s), ('poll_interval_s', poll_interval_s)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f'{name} must be finite and positive')
    monitor = AndroidSessionMonitor(raw_path, nts_path, output_directory, analysis_options=analysis_options,
                                   local_counter_resolution_ns=local_counter_resolution_ns)
    deadline, reason = time.monotonic()+duration_s, 'DURATION_LIMIT'
    try:
        while True:
            receipt = monitor.poll()
            if receipt is not None:
                if on_update is not None:
                    on_update(receipt)
                if receipt['session_complete']:
                    reason = 'SESSION_TERMINALS_OBSERVED'
                    break
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(poll_interval_s, remaining))
    except KeyboardInterrupt:
        reason = 'USER_INTERRUPTED_MONITOR'
    except OSError:
        reason = 'PC_STORAGE_FAILED'
    return monitor.finish(reason)
