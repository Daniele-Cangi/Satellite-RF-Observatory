"""CLI for offline diagnostics of a fixed GPS receiver."""

import argparse
import json
from pathlib import Path

from .fixed_site import analyze
from .benchmark import compare
from .transfer import reference_transfer
from .navigation_witness import inspect_navigation
from .navigation_impact import compare_navigation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    analysis = commands.add_parser('analyze', help='report code geometry, relative clock and data gaps')
    comparison = commands.add_parser('compare', help='compare original observations and software code ramps')
    transfer = commands.add_parser('transfer', help='test training-only external residual prediction on later epochs')
    nav_check = commands.add_parser('navigation', help='compare local decoded navigation issues with external files')
    nav_check.add_argument('day_gpst')
    nav_check.add_argument('local_navigation', type=Path, help='local RINEX 2 GPS NAV or explicitly selected UBX')
    nav_check.add_argument('--local-format', choices=('rinex', 'ubx'), default='rinex')
    nav_check.add_argument('--recover-corrupt', action='store_true',
                           help='UBX only: exclude and count damaged packets instead of rejecting the file')
    nav_check.add_argument('--witness', dest='reference', action='append', required=True, metavar='NAME=PATH')
    nav_check.add_argument('--start', type=int, default=0)
    nav_check.add_argument('--stop', type=int, default=86400)
    nav_check.add_argument('--output', required=True, type=Path)
    nav_comparison = commands.add_parser('navigation-compare', help='compare paired OBS/NAV cases and local controls')
    nav_comparison.add_argument('day_gpst')
    nav_comparison.add_argument('local_rinex', type=Path)
    nav_comparison.add_argument('navigation', type=Path, help='original RINEX 2 GPS NAV')
    nav_comparison.add_argument('--case', nargs=3, action='append', required=True, metavar=('NAME', 'OBS', 'NAV'))
    nav_comparison.add_argument('--witness', dest='reference', action='append', required=True, metavar='NAME=PATH')
    for flag in ('start', 'calibration-stop', 'stop'):
        nav_comparison.add_argument('--' + flag, type=int, required=True)
    nav_comparison.add_argument('--quantile', type=float, default=.95)
    nav_comparison.add_argument('--minimum-calibration', type=int, default=20)
    nav_comparison.add_argument('--local-ecef', nargs=3, type=float, metavar=('X', 'Y', 'Z'))
    nav_comparison.add_argument('--position-source')
    nav_comparison.add_argument('--output', required=True, type=Path)
    for command in (analysis, comparison, transfer):
        command.add_argument('day_gpst')
        command.add_argument('local_rinex', type=Path)
        command.add_argument('navigation', type=Path, help='RINEX 2 GPS NAV, plain or gzip')
        command.add_argument('--reference', action='append', required=True, metavar='NAME=PATH')
        command.add_argument('--local-ecef', nargs=3, type=float, metavar=('X', 'Y', 'Z'))
        command.add_argument('--position-source', help='source of the explicit antenna ECEF coordinate')
        command.add_argument('--output', required=True, type=Path)
    analysis.add_argument('--start', type=int, default=0, help='inclusive GPST seconds, 30-second grid')
    analysis.add_argument('--stop', type=int, default=86400, help='exclusive GPST seconds, 30-second grid')
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
    references = {}
    for item in args.reference:
        name, separator, path = item.partition('=')
        if not separator or not name.strip() or not path or name in references:
            parser.error('references must be distinct NAME=PATH entries')
        references[name] = Path(path)
    if args.output.exists():
        parser.error('output already exists; choose a new report path')
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
            options.update(local_format=args.local_format, recover_corrupt=args.recover_corrupt)
            report = inspect_navigation(args.local_navigation, references, args.day_gpst, **options)
        elif args.command == 'navigation-compare':
            options.update(calibration_stop_s=args.calibration_stop, proportion=args.quantile,
                           minimum_calibration=args.minimum_calibration)
            report = compare_navigation(args.local_rinex, args.navigation, cases, references, args.day_gpst, **options)
        else:
            function = {'analyze': analyze, 'compare': compare, 'transfer': reference_transfer}[args.command]
            report = function(args.local_rinex, references, args.navigation, args.day_gpst, **options)
        serialized = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + '\n'
        with args.output.open('x', encoding='utf-8', newline='\n') as destination:
            destination.write(serialized)
    except (ValueError, OSError) as error:
        parser.exit(2, f'PNT input/analysis error: {error}\n')
    summary = (report['original']['evaluation']['status_counts'] if args.command == 'compare' else
               report['evaluation']['status_counts'] if args.command == 'transfer' else
               report['coverage']['status_counts'] if args.command == 'navigation' else
               {name: case['paired_evaluation']['status_counts'] for name, case in report['cases'].items()}
               if args.command == 'navigation-compare' else
               report['coverage']['matched_status_counts'])
    print(f"{report['status']}: {summary}; {args.output}")


if __name__ == '__main__':
    main()
