"""PNT diagnostics: offline GNSS analysis and read-only Internet time probes."""

import argparse
import hashlib
import json
from pathlib import Path

from .fixed_site import analyze
from .benchmark import compare
from .transfer import reference_transfer
from .navigation_witness import inspect_navigation
from .navigation_impact import compare_navigation
from .android_raw import inspect_android_raw
from .android_network import analyze_android


def write_report(report, output):
    serialized = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + '\n'
    with output.open('x', encoding='utf-8', newline='\n') as destination:
        destination.write(serialized)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    time_probe = commands.add_parser('time-probe', help='read-only NTS time witness; no GNSS authenticity verdict')
    time_capture = commands.add_parser('time-capture', help='co-capture UBX/TCP and NTS; conditional UTC diagnostic')
    for command in (time_probe, time_capture):
        command.add_argument('--server', action='append', required=True, help='explicit NTS-KE hostname')
        command.add_argument('--server-error-ns', type=int, required=True, help='declared server UTC error budget')
        command.add_argument('--rate-error-ppm', type=int, required=True, help='declared monotonic rate error budget')
        command.add_argument('--budget-source', required=True, help='provenance or explicit uncalibrated assumption')
        command.add_argument('--timeout', type=float, default=5.0, help='per-stage socket timeout, seconds')
        command.add_argument('--ntp-era', type=int, default=0, help='explicit era; 0 covers 1900-2036')
        command.add_argument('--output', required=True, type=Path)
    time_capture.add_argument('--receiver-host', required=True, help='explicit live UBX/TCP source; no file replay')
    time_capture.add_argument('--receiver-port', type=int, required=True)
    time_capture.add_argument('--receiver-source', required=True, help='receiver/forwarder configuration and provenance')
    time_capture.add_argument('--rounds', type=int, default=1, help='declared NTS sampling rounds; no automatic retries')
    time_capture.add_argument('--interval', type=float, default=1.0, help='seconds between scheduled round starts')
    time_capture.add_argument('--max-bytes', type=int, default=1048576, help='receiver byte retention limit')
    time_capture.add_argument('--epoch-age-min-ns', type=int, help='solution-to-userspace-receipt bound, host-counter ns')
    time_capture.add_argument('--epoch-age-max-ns', type=int)
    time_capture.add_argument('--epoch-age-source', help='independent qualification or explicit uncalibrated assumption')
    time_capture.add_argument('--utc-error-ns', type=int, required=True, help='declared receiver UTC error budget; not tAcc')
    time_capture.add_argument('--utc-error-source', required=True)
    time_compare = commands.add_parser('time-compare', help='compare captured UBX receiver UTC with NTS; offline replay')
    time_compare.add_argument('witness_report', type=Path, help='existing pnt-internet-time-v1 JSON')
    time_compare.add_argument('receiver_capture', type=Path, help='UTC packets and same-counter receipt/age bounds')
    time_compare.add_argument('--utc-error-ns', type=int, required=True, help='declared GNSS UTC error budget; not tAcc')
    time_compare.add_argument('--utc-error-source', required=True, help='independent qualification or explicit assumption')
    time_compare.add_argument('--output', required=True, type=Path)
    android = commands.add_parser('android-raw', help='normalize GPS L1/L5 Android Raw logs; no attack verdict')
    android.add_argument('local_log', type=Path, help='GNSS Logger text, plain or gzip')
    android.add_argument('--output', required=True, type=Path)
    android_analysis = commands.add_parser('android-analyze', help='GPS L1 Android/remote fixed-site geometry diagnostics')
    analysis = commands.add_parser('analyze', help='report code geometry, relative clock and data gaps')
    comparison = commands.add_parser('compare', help='compare original observations and software code ramps')
    transfer = commands.add_parser('transfer', help='test training-only external residual prediction on later epochs')
    nav_check = commands.add_parser('navigation', help='compare local decoded navigation issues with external files')
    nav_check.add_argument('day_gpst')
    nav_check.add_argument('local_navigation', type=Path, help='local RINEX 2/3 GPS NAV or explicitly selected UBX')
    nav_check.add_argument('--local-format', choices=('rinex', 'ubx'), default='rinex')
    nav_check.add_argument('--recover-corrupt', action='store_true',
                           help='UBX only: exclude and count damaged packets instead of rejecting the file')
    nav_check.add_argument('--qualify-lnav', action='store_true',
                           help='also test whether written intervals uniquely identify encodable GPS LNAV values')
    nav_check.add_argument('--witness', dest='reference', action='append', required=True, metavar='NAME=PATH')
    nav_check.add_argument('--start', type=int, default=0)
    nav_check.add_argument('--stop', type=int, default=86400)
    nav_check.add_argument('--output', required=True, type=Path)
    nav_comparison = commands.add_parser('navigation-compare', help='compare paired OBS/NAV cases and local controls')
    nav_comparison.add_argument('day_gpst')
    nav_comparison.add_argument('local_rinex', type=Path)
    nav_comparison.add_argument('navigation', type=Path, help='original RINEX 2/3 GPS NAV')
    nav_comparison.add_argument('--case', nargs=3, action='append', required=True, metavar=('NAME', 'OBS', 'NAV'))
    nav_comparison.add_argument('--witness', dest='reference', action='append', required=True, metavar='NAME=PATH')
    for flag in ('start', 'calibration-stop', 'stop'):
        nav_comparison.add_argument('--' + flag, type=int, required=True)
    nav_comparison.add_argument('--quantile', type=float, default=.95)
    nav_comparison.add_argument('--minimum-calibration', type=int, default=20)
    nav_comparison.add_argument('--local-ecef', nargs=3, type=float, metavar=('X', 'Y', 'Z'))
    nav_comparison.add_argument('--position-source')
    nav_comparison.add_argument('--output', required=True, type=Path)
    for command in (analysis, comparison, transfer, android_analysis):
        command.add_argument('day_gpst')
        command.add_argument('local_rinex', type=Path)
        command.add_argument('navigation', type=Path, help='RINEX 2/3 GPS NAV, plain or gzip')
        command.add_argument('--reference', action='append', required=True, metavar='NAME=PATH')
        command.add_argument('--local-ecef', nargs=3, type=float, metavar=('X', 'Y', 'Z'),
                             required=command is android_analysis)
        command.add_argument('--position-source', help='source of the explicit antenna ECEF coordinate',
                             required=command is android_analysis)
        command.add_argument('--output', required=True, type=Path)
    analysis.add_argument('--start', type=int, default=0, help='inclusive GPST seconds, 30-second grid')
    analysis.add_argument('--stop', type=int, default=86400, help='exclusive GPST seconds, 30-second grid')
    android_analysis.add_argument('--start', type=int, default=0)
    android_analysis.add_argument('--stop', type=int, default=86400)
    for flag in ('start', 'train-stop', 'calibration-stop', 'stop'):
        comparison.add_argument('--' + flag, type=int, required=True, help='chronological GPST grid boundary')
    comparison.add_argument('--amplitude', action='append', type=float, help='ramp endpoint in metres; default 2, 5, 10')
    comparison.add_argument('--quantile', type=float, default=.95)
    comparison.add_argument('--minimum-training', type=int, default=5)
    comparison.add_argument('--minimum-calibration', type=int, default=20)
    comparison.add_argument('--satellite', help='GPS PRN; default most supported in training, ties by PRN')
    comparison.add_argument('--direction-ecef', nargs=3, type=float, default=(1., 0., 0.), metavar=('X', 'Y', 'Z'))
    for flag in ('start', 'train-stop', 'stop'):
        transfer.add_argument('--' + flag, type=int, required=True, help='chronological GPST grid boundary')
    transfer.add_argument('--minimum-training', type=int, default=5)
    transfer.add_argument('--minimum-fit-epochs', type=int, default=20)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output already exists; choose a new report path')
    if args.command == 'time-compare':
        from .gnss_time import compare_receiver_capture

        try:
            witness_bytes = args.witness_report.read_bytes()
            capture_bytes = args.receiver_capture.read_bytes()
            report = compare_receiver_capture(json.loads(witness_bytes), json.loads(capture_bytes),
                                              utc_error_ns=args.utc_error_ns,
                                              utc_error_source=args.utc_error_source)
            report['sources'] = {
                name: dict(path=str(path), sha256=hashlib.sha256(content).hexdigest())
                for name, path, content in [('witness', args.witness_report, witness_bytes),
                                            ('receiver', args.receiver_capture, capture_bytes)]}
            write_report(report, args.output)
        except (ValueError, OSError) as error:
            parser.exit(2, f'PNT time input/output error: {error}\n')
        print(f"{report['status']}: {report['coverage']['comparison_status_counts']}; {args.output}")
        if report['status'] == 'INSUFFICIENT_EVIDENCE':
            parser.exit(2, 'No associated receiver UTC comparison; failures retained in report\n')
        return
    if args.command == 'time-capture':
        from .time_capture import collect_receiver_time

        try:
            report = collect_receiver_time(
                args.server, receiver_host=args.receiver_host, receiver_port=args.receiver_port,
                receiver_source=args.receiver_source, server_error_ns=args.server_error_ns,
                rate_error_ppm=args.rate_error_ppm, budget_source=args.budget_source,
                utc_error_ns=args.utc_error_ns, utc_error_source=args.utc_error_source,
                timeout_s=args.timeout, ntp_era=args.ntp_era, rounds=args.rounds,
                interval_s=args.interval, max_bytes=args.max_bytes,
                epoch_age_min_ns=args.epoch_age_min_ns, epoch_age_max_ns=args.epoch_age_max_ns,
                epoch_age_source=args.epoch_age_source)
            write_report(report, args.output)
        except (ValueError, OSError) as error:
            parser.exit(2, f'PNT time capture/output error: {error}\n')
        print(f"{report['status']}: {report['coverage']['comparison_status_counts']}; {args.output}")
        if report['acquisition']['interrupted']:
            parser.exit(130, 'Capture interrupted; retained data and attempt outcomes saved\n')
        if report['status'] == 'INSUFFICIENT_EVIDENCE':
            parser.exit(2, 'No associated receiver UTC comparison; capture and failures saved\n')
        return
    if args.command == 'time-probe':
        from .time_witness import collect

        try:
            report = collect(args.server, server_error_ns=args.server_error_ns,
                             rate_error_ppm=args.rate_error_ppm, budget_source=args.budget_source,
                             timeout_s=args.timeout, ntp_era=args.ntp_era)
            write_report(report, args.output)
        except (ValueError, OSError) as error:
            parser.exit(2, f'PNT time input/output error: {error}\n')
        count = sum(a['status'] == 'AUTHENTICATED_EXCHANGE' for a in report['attempts'])
        print(f"{count}/{len(report['attempts'])} authenticated exchanges; {args.output}")
        if not count:
            parser.exit(2, 'No authenticated time witness; failures retained in report\n')
        return
    if args.command == 'android-raw':
        try:
            report = inspect_android_raw(args.local_log)
            write_report(report, args.output)
        except (ValueError, OSError) as error:
            parser.exit(2, f'PNT input/analysis error: {error}\n')
        print(f"{report['status']}: {report['coverage']['status_counts']}; {args.output}")
        return
    references = {}
    for item in args.reference:
        name, separator, path = item.partition('=')
        if not separator or not name.strip() or not path or name in references:
            parser.error('references must be distinct NAME=PATH entries')
        references[name] = Path(path)
    cases = {}
    if args.command == 'navigation-compare':
        for name, observation, navigation in args.case:
            if not name.strip() or name == 'original' or name in cases:
                parser.error('cases require distinct nonempty names; original is reserved')
            cases[name] = (Path(observation), Path(navigation))
    try:
        options = dict(start_s=args.start, stop_s=args.stop)
        if args.command != 'navigation':
            options.update(local_ecef=args.local_ecef, position_source=args.position_source)
        if args.command == 'compare':
            options.update(train_stop_s=args.train_stop, calibration_stop_s=args.calibration_stop,
                           amplitudes_m=args.amplitude if args.amplitude is not None else (2., 5., 10.),
                           proportion=args.quantile, minimum_training=args.minimum_training,
                           minimum_calibration=args.minimum_calibration, satellite=args.satellite,
                           direction_ecef=args.direction_ecef)
        elif args.command == 'transfer':
            options.update(train_stop_s=args.train_stop, minimum_training=args.minimum_training,
                           minimum_fit_epochs=args.minimum_fit_epochs)
        if args.command == 'navigation':
            options.update(local_format=args.local_format, recover_corrupt=args.recover_corrupt,
                           qualify_lnav=args.qualify_lnav)
            report = inspect_navigation(args.local_navigation, references, args.day_gpst, **options)
        elif args.command == 'navigation-compare':
            options.update(calibration_stop_s=args.calibration_stop, proportion=args.quantile,
                           minimum_calibration=args.minimum_calibration)
            report = compare_navigation(args.local_rinex, args.navigation, cases, references, args.day_gpst, **options)
        else:
            function = {'analyze': analyze, 'android-analyze': analyze_android,
                        'compare': compare, 'transfer': reference_transfer}[args.command]
            report = function(args.local_rinex, references, args.navigation, args.day_gpst, **options)
        write_report(report, args.output)
    except (ValueError, OSError) as error:
        parser.exit(2, f'PNT input/analysis error: {error}\n')
    summary = (report['original']['evaluation']['status_counts'] if args.command == 'compare' else
               report['evaluation']['status_counts'] if args.command == 'transfer' else
               report['coverage']['status_counts'] if args.command == 'navigation' else
               {name: case['paired_evaluation']['status_counts'] for name, case in report['cases'].items()}
               if args.command == 'navigation-compare' else
               report['coverage']['matched_status_counts'])
    if args.command == 'navigation' and args.qualify_lnav:
        summary = {'written_decimal': summary, 'lnav_representation': report['lnav_representation']['status_counts']}
    print(f"{report['status']}: {summary}; {args.output}")


if __name__ == '__main__':
    main()
