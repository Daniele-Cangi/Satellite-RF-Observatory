"""Versioned, value-blind request plans for the supported historical GPS path."""
from copy import deepcopy
from datetime import date
import re

from .context import Context

PROFILE = 'gps-code-snapshot-v1'
POOL_PROFILE = 'gps-code-network-v1'
DEFAULT_FIT = ['ALGO00CAN', 'DRAO00CAN', 'STJO00CAN', 'YELL00CAN',
               'BOGT00COL', 'BRAZ00BRA', 'AREQ00PER']


def make_plan(target, date_gpst, fit_stations=None, withheld_station='GOLD00USA',
              prior_access='User-selected event. Prior exposure has not been independently established.'):
    context = Context(target, date_gpst)
    day = date.fromisoformat(date_gpst)
    if day < date(2022, 11, 27):
        raise ValueError('this product naming profile supports dates from GPS week 2238')
    names = list(DEFAULT_FIT if fit_stations is None else fit_stations)
    all_names = names + [withheld_station]
    if not 5 <= len(names) <= 8 or len(set(all_names)) != len(all_names):
        raise ValueError('need 5..8 distinct fit roots and one distinct held-out root')
    if any(not isinstance(n, str) or not re.fullmatch(r'[A-Z0-9]{9}', n) for n in all_names):
        raise ValueError('station IDs must be nine uppercase letters/digits')
    stamp = day.strftime('%Y%j')
    root = 'https://igs.bkg.bund.de/root_ftp/IGS/'
    return {
        'profile': PROFILE,
        'experiment': f'{target}_{stamp}_CONFIGURED_POSITION',
        'target': target, 'date_gpst': date_gpst,
        'fit_stations': names, 'withheld_station': withheld_station,
        'observation_base_url': f'{root}obs/{day.year}/{stamp[4:]}/',
        'observation_filename': '{station}_R_' + stamp + '0000_01D_30S_MO.crx.gz',
        'navigation_url': f'{root}BRDC/{day.year}/{stamp[4:]}/BRDM00DLR_S_{stamp}0000_01D_MN.rnx.gz',
        'oracle_url': f'{root}products/{context.gps_week}/IGS0OPSRAP_{stamp}0000_01D_15M_ORB.SP3.gz',
        'selection': {
            'rule': 'First chronological block of eleven normal 30-second epochs with target C1C/C2W and at least four non-target GPS codes at every declared station. Field presence only; no numeric target quality or orbit selection. Use all eleven; solve the central emitted event.',
            'support_epochs': 11, 'fit_epochs': 11, 'step_s': 30,
            'minimum_reference_count': 4,
        },
        'physical_change': 'A separately declared event tests transfer of the multi-root snapshot method. This profile adds no new observable and promises no reduction in uncertainty.',
        'prior_access': prior_access,
        'clock_calibration': 'C1C/C2W IF; healthy non-target GPS only, nearest toc within 7200 s, elevation >=10 deg, equal-weight clock mean, >=4 references. Exclude receiver clock fields and target navigation before numerical parsing. Check fixed terrestrial coordinates with non-target SPP; never fit them to target measurements.',
        'calibration_limits': {
            'max_reference_absolute_residual_m': 50, 'max_reference_rms_m': 20,
            'max_alternating_subset_clock_difference_m': 30,
            'max_ground_coordinate_check_m': 30,
        },
        'model': 'Nominal troposphere, relativistic reference clocks, Earth rotation during light travel. u=t_tag-P_IF/c, central median u0; four-node cubic and six-node quintic interpolation with bracketing and <=2 m control. Solve xyz+B using all four-root algebraic branches, without target orbit, radius or dynamics. Fit elevations >=5 deg; residuals <=100 m; full rank, branch, infinity and nonlinear-axis checks.',
        'uncertainty': {
            'code_sigma_floor_m': 20, 'common_reference_sigma_m': 5,
            'ground_coordinate_sigma_m': 5, 'per_root_systematic_envelope_m': 20,
            'nonlinear_margin_factor': 1.05,
            'rule': 'Increase the statistical floor for reference RMS/subset differences; differentiate code/tag/median-event transform and include clock, shared-reference and ground-coordinate covariance. All 2^N bias corners plus 64 deterministic interior samples, seed 2026250. Conditional radius = 1.05*(maximum statistical95 extent + maximum sampled bias displacement). Finite probes are not certified global bounds or population coverage.',
        },
        'confirmation': {
            'uncertainty_radius_limit_m': 10000, 'position_error_limit_m': 10000,
            'holdout_absolute_limit_m': 100,
            'holdout_band': '3 sigma with shared-reference cross-covariance plus fit-bias envelope and independent +/-20 m excluded-root bias; <=2 m interpolation control.',
            'oracle': 'Only after solution freeze and excluded receiver reveal. Nine nearest SP3 nodes at solved emission time; eight-node control <=10 m. Rotate fixed-u0 axes to emission axes. Allow 10 m oracle/interpolation/reference-point comparison. No fitted time or pose alignment.',
        },
        'stop': 'Exactly the declared target, date, roots and first structural block. No replacement products, alternate window or relaxed criterion. Missing transport/source/calibration/identifiability closes this request without an oracle. Excessive uncertainty permits the predeclared diagnostic reveal while primary status remains failed. An engineering exception stops the job without relabelling it scientific success; no automatic retry.',
        'claim': 'One receiver-labelled historical GPS position under target-state exclusion and conditional uncertainty. No velocity, autonomous identity, population coverage, universal service reliability or statistically disjoint oracle-data claim.',
    }


def validate_plan(plan):
    """Reject ignored settings and URL/path injection before acquisition."""
    if plan.get('profile') == POOL_PROFILE:
        expected = make_network_plan(plan['target'], plan['date_gpst'],
                                     plan['network']['candidate_stations'],
                                     plan['withheld_station'], plan['prior_access'])
    else:
        expected = make_plan(plan['target'], plan['date_gpst'], plan['fit_stations'],
                             plan['withheld_station'], plan['prior_access'])
    candidate = deepcopy(plan)
    if candidate != expected:
        changed = sorted(k for k in candidate.keys() | expected.keys()
                         if candidate.get(k) != expected.get(k))
        raise ValueError('unsupported or changed request profile fields: ' + ', '.join(changed))
    return expected


def make_network_plan(target, date_gpst, candidates, withheld_station='GOLD00USA',
                      prior_access='User-selected event; prior exposure must be declared.'):
    names = sorted(candidates)
    if not 7 <= len(names) <= 12 or len(set(names)) != len(names) or withheld_station in names:
        raise ValueError('need 7..12 distinct candidate stations and a separate fixed holdout')
    if any(not isinstance(n, str) or not re.fullmatch(r'[A-Z0-9]{9}', n) for n in names):
        raise ValueError('invalid candidate station ID')
    plan = make_plan(target, date_gpst, names[:7], withheld_station, prior_access)
    plan.update(profile=POOL_PROFILE, fit_stations=None,
                experiment=f"{target}_{date.fromisoformat(date_gpst).strftime('%Y%j')}_NETWORK_POSITION")
    plan['network'] = {
        'candidate_stations': names, 'fit_count': 7,
        'minimum_baseline_m': 2_000_000, 'minimum_latitude_span_deg': 20,
        'rule': 'At the earliest eleven-epoch window available at the fixed holdout, choose the first lexicographically sorted seven-station subset with continuous eligible fields, usable terrestrial header coordinates, >=2000 km maximum baseline and >=20 degrees geocentric latitude span. No fit-quality or target-orbit search. Stop at the first qualifying network/window.',
        'missing_sources': 'HTTP 404 and unsupported structural headers make that candidate unavailable. Other transport failures close this request as source unavailable. The holdout cannot be replaced. No alternate source filenames or products.',
    }
    plan['selection']['rule'] = plan['network']['rule']
    plan['physical_change'] = 'Replace mandatory overlap of a fixed network with a predeclared presence-only choice from a bounded terrestrial station pool. This may admit previously unsupported events; it adds no RF observable or guarantee of lower uncertainty.'
    plan['stop'] = 'Exactly this target/date/candidate pool/fixed holdout and the first declared network/window. No next subset/window after calibration, fit or uncertainty failure. The original uncertainty floors and confirmation criteria apply. Diagnostic reveal after excessive uncertainty is permitted, preserving failure. No automatic retry or replacement products.'
    return plan
