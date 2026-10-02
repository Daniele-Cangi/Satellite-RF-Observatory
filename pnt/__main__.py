"""CLI for offline diagnostics of a fixed GPS receiver."""

import argparse
import json
from pathlib import Path

from .fixed_site import analyze
from .benchmark import compare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    analysis = commands.add_parser('analyze', help='report code geometry, relative clock and data gaps')
    comparison = commands.add_parser('compare', help='compare original observations and software code ramps')
    for command in (analysis, comparison):
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
    args = parser.parse_args()
    references = {}
    for item in args.reference:
        name, separator, path = item.partition('=')
        if not separator or not name.strip() or not path or name in references:
            parser.error('references must be distinct NAME=PATH entries')
        references[name] = Path(path)
    if args.output.exists():
        parser.error('output already exists; choose a new report path')
    try:
        options = dict(start_s=args.start, stop_s=args.stop, local_ecef=args.local_ecef,
                       position_source=args.position_source)
        if args.command == 'compare':
            options.update(train_stop_s=args.train_stop, calibration_stop_s=args.calibration_stop,
                           amplitudes_m=args.amplitude if args.amplitude is not None else (2., 5., 10.),
                           proportion=args.quantile, minimum_training=args.minimum_training,
                           minimum_calibration=args.minimum_calibration, satellite=args.satellite,
                           direction_ecef=args.direction_ecef)
        function = compare if args.command == 'compare' else analyze
        report = function(args.local_rinex, references, args.navigation, args.day_gpst, **options)
        serialized = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + '\n'
        with args.output.open('x', encoding='utf-8', newline='\n') as destination:
            destination.write(serialized)
    except (ValueError, OSError) as error:
        parser.exit(2, f'PNT input/analysis error: {error}\n')
    summary = (report['original']['evaluation']['status_counts'] if args.command == 'compare' else
               report['coverage']['matched_status_counts'])
    print(f"{report['status']}: {summary}; {args.output}")


if __name__ == '__main__':
    main()
