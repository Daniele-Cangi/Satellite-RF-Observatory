"""CLI for offline diagnostics of a fixed GPS receiver."""

import argparse
import json
from pathlib import Path

from .fixed_site import analyze


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    command = commands.add_parser('analyze', help='report code geometry, relative clock and data gaps')
    command.add_argument('day_gpst')
    command.add_argument('local_rinex', type=Path)
    command.add_argument('navigation', type=Path, help='RINEX 2 GPS NAV, plain or gzip')
    command.add_argument('--reference', action='append', required=True, metavar='NAME=PATH')
    command.add_argument('--start', type=int, default=0, help='inclusive seconds of GPST day, 30-second grid')
    command.add_argument('--stop', type=int, default=86400, help='exclusive seconds of GPST day, 30-second grid')
    command.add_argument('--local-ecef', nargs=3, type=float, metavar=('X', 'Y', 'Z'))
    command.add_argument('--position-source', help='source of the explicit antenna ECEF coordinate')
    command.add_argument('--output', required=True, type=Path)
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
        report = analyze(args.local_rinex, references, args.navigation, args.day_gpst,
                         start_s=args.start, stop_s=args.stop, local_ecef=args.local_ecef,
                         position_source=args.position_source)
        serialized = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + '\n'
        with args.output.open('x', encoding='utf-8', newline='\n') as destination:
            destination.write(serialized)
    except (ValueError, OSError) as error:
        parser.exit(2, f'PNT input/analysis error: {error}\n')
    print(f"{report['status']}: {report['coverage']['matched_status_counts']}; {args.output}")


if __name__ == '__main__':
    main()
