"""Local entry point for request preparation and sealed verification results."""
import argparse
import json
from pathlib import Path
import sys

from .workflow import capabilities, prepare_request, read_result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('capabilities')
    prepare = commands.add_parser('prepare')
    prepare.add_argument('target')
    prepare.add_argument('date_gpst')
    prepare.add_argument('--prior-access', required=True)
    prepare.add_argument('--profile', default='gps-code-network-v1')
    prepare.add_argument('--plan-output', type=Path)
    result = commands.add_parser('result')
    result.add_argument('run_path', type=Path)
    args = parser.parse_args(argv)
    if args.command == 'capabilities':
        response = capabilities()
    elif args.command == 'prepare':
        response = prepare_request({key: getattr(args, key)
                                    for key in ('target', 'date_gpst', 'prior_access', 'profile')})
        if args.plan_output and response['plan'] is not None:
            # Exclusive creation preserves an existing declaration verbatim.
            with args.plan_output.open('x', encoding='utf-8', newline='\n') as handle:
                json.dump(response['plan'], handle, indent=2, ensure_ascii=False, allow_nan=False)
                handle.write('\n')
    else:
        response = read_result(args.run_path)
    print(json.dumps(response, indent=2, ensure_ascii=False, allow_nan=False))
    return 2 if response.get('status') in ('INVALID_REQUEST', 'UNSUPPORTED_REQUEST', 'DAY_NOT_COMPLETE') else 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
