"""Paired development comparisons of local codes, NAV hypotheses and witnesses."""

from collections import Counter
from datetime import date
import math
from pathlib import Path

from research.exploratory.pnt_local_network import nearest_rank
from .fixed_site import admit_codes, observation_epochs, read_station, validate_window
from .model import day_context, fit_clock, indexed_broadcast_navigation
from .navigation_witness import compare_issue_records, group_issues, read_issues


SCORES = ('residual_spread_m', 'clock_step_m')
CONFLICTS = {'CONFLICTING_LOCAL_RECORDS', 'EXTERNAL_RECORD_CONFLICT'}


def evaluate_local(time_s, codes, position, navigation, indices, context):
    """Fit each case independently; support changes are compared, never hidden."""
    admitted, excluded, records = admit_codes(codes, position, navigation, time_s, context)
    result = {'gpst_s': time_s, 'satellites': sorted(admitted), 'excluded_satellites': excluded,
              'navigation_record_indices': {sv: indices[id(record)] for sv, record in records.items()}}
    if len(admitted) < 4:
        return dict(result, status='INSUFFICIENT_EVIDENCE')
    try:
        fitted = fit_clock(admitted, position, records, time_s, context)
    except ValueError as error:
        return dict(result, status='MODEL_FAILED', reason=str(error))
    residuals = fitted['satellite_residuals_m'].values()
    return dict(result, status='EVALUATED', **fitted,
                residual_spread_m=max(residuals) - min(residuals))


def score_controls(rows, thresholds):
    """Clock steps require consecutive successful grid epochs; never bridge a gap."""
    previous = None
    for row in rows:
        row['scores_m'] = {}
        if row['status'] == 'EVALUATED':
            row['scores_m']['residual_spread_m'] = row['residual_spread_m']
            if previous is not None and previous['status'] == 'EVALUATED':
                row['scores_m']['clock_step_m'] = abs(row['clock_m'] - previous['clock_m'])
        row['control_status'] = ('SCORED' if len(row['scores_m']) == len(SCORES) else
                                 'INSUFFICIENT_CLOCK_CONTINUITY' if row['scores_m'] else row['status'])
        row['exceedances'] = ({name: value > thresholds[name] for name, value in row['scores_m'].items()}
                              if thresholds is not None else {})
        row['local_exceedance'] = (any(row['exceedances'].values())
                                   if row['control_status'] == 'SCORED' and thresholds is not None else None)
        previous = row


def used_witness_outcome(row, comparisons):
    used = [comparisons[index] for index in row['navigation_record_indices'].values()]
    counts = dict(sorted(Counter(item['status'] for item in used).items()))
    # A positive match needs complete used-record coverage. Discordance may
    # coexist with missing coverage; the counts retain both. Conflicts take
    # precedence rather than selecting a preferred witness.
    if not used:
        status = 'INSUFFICIENT_EVIDENCE'
    elif any(item['status'] in CONFLICTS for item in used):
        status = 'RECORD_CONFLICT'
    elif counts.get('DIFFERENT_FROM_EXTERNAL'):
        status = 'DIFFERENT_FROM_EXTERNAL'
    elif counts.get('INSUFFICIENT_EVIDENCE'):
        status = 'INSUFFICIENT_EVIDENCE'
    else:
        status = 'COMPATIBLE_WITH_EXTERNAL'
    return {'status': status, 'used_record_status_counts': counts,
            'used_satellites': sorted(row['navigation_record_indices'])}


def summarize(rows):
    scored = [row for row in rows if row['local_exceedance'] is not None]
    return {'requested_epochs': len(rows), 'locally_scored_epochs': len(scored),
            'fit_status_counts': dict(sorted(Counter(row['status'] for row in rows).items())),
            'control_status_counts': dict(sorted(Counter(row['control_status'] for row in rows).items())),
            'local_exceedance_epochs': sum(row['local_exceedance'] for row in scored),
            'control_exceedances': {name: sum(row['exceedances'].get(name, False) for row in rows)
                                    for name in SCORES},
            'control_scored_epochs': {name: sum(name in row['exceedances'] for row in rows) for name in SCORES},
            'witness_status_counts': dict(sorted(Counter(row['witness']['status'] for row in rows).items()))}


def compare_navigation(local_path, original_navigation, cases, witnesses, day_gpst, *,
                       start_s, calibration_stop_s, stop_s, proportion=.95,
                       minimum_calibration=20, local_ecef=None, position_source=None):
    """Compare supplied OBS/NAV cases against an original-only calibration prefix.

    This does not generate RF, establish benign labels, or infer authenticity.
    Case observations may be the original file or a separately retained variant.
    """
    validate_window(start_s, calibration_stop_s)
    validate_window(calibration_stop_s, stop_s)
    if (not isinstance(minimum_calibration, int) or isinstance(minimum_calibration, bool) or
            minimum_calibration < 2 or not isinstance(proportion, (int, float)) or
            isinstance(proportion, bool) or not math.isfinite(proportion) or not 0 < proportion <= 1):
        raise ValueError('invalid calibration count or quantile')
    if (not isinstance(cases, dict) or not cases or
            any(not isinstance(name, str) or not name.strip() or name == 'original' for name in cases) or
            any(not isinstance(paths, (tuple, list)) or len(paths) != 2 for paths in cases.values())):
        raise ValueError('distinct named cases require (observation, navigation) paths; original is reserved')
    if (not isinstance(witnesses, dict) or not witnesses or
            any(not isinstance(name, str) or not name.strip() or name == 'local' for name in witnesses)):
        raise ValueError('at least one named navigation witness required; local is reserved')
    if local_ecef is None and position_source is not None:
        raise ValueError('coordinate source requires explicit local ECEF')
    day = date.fromisoformat(day_gpst)
    context = day_context(day)
    original_data, position, original_source = read_station(
        local_path, day, position=local_ecef, position_source=position_source)
    external, witness_sources = {}, {}
    for name, path in sorted(witnesses.items()):
        issues, witness_sources[name] = read_issues(path)
        external[name] = group_issues(issues)
    definitions = {'original': (local_path, original_navigation), **dict(sorted(cases.items()))}
    outputs = {}
    for name, (observation_path, nav_path) in definitions.items():
        if Path(observation_path).resolve() == Path(local_path).resolve():
            data, source = original_data, original_source
        else:
            data, _, source = read_station(observation_path, day, position=position,
                                           position_source=original_source['position_source'])
            if source['marker_name'].strip().upper() != original_source['marker_name'].strip().upper():
                raise ValueError('paired cases must declare the same receiver marker')
        issues, nav_source = read_issues(nav_path)
        comparisons = compare_issue_records(issues, external)
        navigation, nav_counts, indices = indexed_broadcast_navigation(Path(nav_path).read_bytes(), require_usable=False)
        nav_source['model_record_status'] = nav_counts
        rows = [evaluate_local(time_s, values['local'], position, navigation, indices, context)
                for time_s, values in observation_epochs({'local': data}, start_s, stop_s)]
        for row in rows:
            row['witness'] = used_witness_outcome(row, comparisons)
        score_controls(rows, None)
        outputs[name] = {'sources': {'observations': source, 'navigation': nav_source},
                         'navigation_comparison': comparisons,
                         'external_files_equal_to_local_navigation': [key for key in witness_sources
                             if witness_sources[key]['sha256'] == nav_source['sha256']], 'epochs': rows}
    calibration = [row for row in outputs['original']['epochs']
                   if row['gpst_s'] < calibration_stop_s and row['control_status'] == 'SCORED']
    thresholds = ({name: nearest_rank([row['scores_m'][name] for row in calibration], proportion)
                   for name in SCORES} if len(calibration) >= minimum_calibration else None)
    original_by_time = {row['gpst_s']: row for row in outputs['original']['epochs']}
    for name, case in outputs.items():
        rows = case['epochs']
        score_controls(rows, thresholds)
        for row in rows:
            base = original_by_time[row['gpst_s']]
            # Comparison support must agree also at the preceding epoch for
            # clock-step comparisons. Independent local diagnostics still stay.
            previous = original_by_time.get(row['gpst_s'] - 30)
            candidate_previous = rows[(row['gpst_s'] - start_s) // 30 - 1] if previous is not None else None
            same_support = row['satellites'] == base['satellites']
            if candidate_previous is not None:
                same_support &= candidate_previous['satellites'] == previous['satellites']
            comparable = (same_support and base['local_exceedance'] is not None and
                          row['local_exceedance'] is not None)
            row['paired_status'] = ('COMPARABLE' if comparable else
                                    'SUPPORT_CHANGED' if not same_support else 'INSUFFICIENT_CONTROLS')
            if comparable:
                row['clock_change_from_original_m'] = row['clock_m'] - base['clock_m']
                row['max_residual_change_from_original_m'] = max(
                    abs(row['satellite_residuals_m'][sv] - base['satellite_residuals_m'][sv])
                    for sv in row['satellites'])
        evaluation = [row for row in rows if row['gpst_s'] >= calibration_stop_s]
        paired = [row for row in evaluation if row['paired_status'] == 'COMPARABLE']
        case['calibration'] = summarize([row for row in rows if row['gpst_s'] < calibration_stop_s])
        case['evaluation'] = summarize(evaluation)
        case['paired_evaluation'] = {
            'status_counts': dict(sorted(Counter(row['paired_status'] for row in evaluation).items())),
            'comparable_epochs': len(paired),
            'original_local_exceedance_epochs': sum(original_by_time[row['gpst_s']]['local_exceedance']
                                                     for row in paired),
            'case_local_exceedance_epochs': sum(row['local_exceedance'] for row in paired),
            'witness_discordance_without_local_exceedance_epochs': sum(
                row['witness']['status'] == 'DIFFERENT_FROM_EXTERNAL' and not row['local_exceedance']
                for row in paired),
            'witness_status_counts': dict(sorted(Counter(row['witness']['status'] for row in paired).items()))}
    return {'schema': 'pnt-navigation-comparison-v1',
            'status': 'EXPLORATORY_COMPARISON' if thresholds is not None else 'INSUFFICIENT_CALIBRATION',
            'day_gpst': day_gpst, 'witness_sources': witness_sources,
            'parameters': {'boundaries_gpst_s': [start_s, calibration_stop_s, stop_s],
                           'calibration_quantile': proportion, 'minimum_calibration_epochs': minimum_calibration,
                           'qualified_original_calibration_epochs': len(calibration)},
            'thresholds_m': thresholds, 'cases': outputs,
            'model': {'observables': 'GPS ionosphere-free C1C/C2W',
                      'geometry': 'fixed original antenna ECEF; existing broadcast model and admission rules',
                      'controls': 'max-minus-min satellite residual; absolute 30-second fitted-clock step',
                      'thresholds': 'nearest-rank original-only calibration; strict >; no case/evaluation tuning',
                      'witness_selection': 'all RINEX records retained; epoch evidence bound to used source indices'},
            'assessments': {'recorded_RF_detection_gain': 'NOT_ASSESSED', 'RF_authenticity': 'NOT_ASSESSED',
                            'source_independence': 'NOT_QUALIFIED', 'absolute_time': 'INSUFFICIENT_EVIDENCE'},
            'limits': [
                'Supplied cases and original observations have no certified benign/attack labels; counts are not false-alarm rates.',
                'Software OBS/NAV changes do not simulate RF capture, tracking, C/N0, Doppler, PVT or hardware clocks.',
                'Passing these two local controls does not mean all reasonable local controls pass.',
                'Adjacent epochs and reused messages are correlated, not independent attack detections.',
                'Different fields provide discordant content, not RF origin, attack attribution or a validated time offset.',
                'Unchanged navigation content can accompany manipulated ranges; compatibility is never an allow verdict.',
                'Witness gaps/conflicts, changed satellite support and fit failures remain explicit; no nearest-issue witness fallback.',
                'Coordinates, propagation errors, serialized field precision, archive timing and source independence remain unqualified.',
            ]}
