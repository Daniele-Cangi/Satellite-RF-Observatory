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
    submit = commands.add_parser('submit')
    submit.add_argument('target')
    submit.add_argument('date_gpst')
    submit.add_argument('--prior-access', required=True)
    submit.add_argument('--implementation', required=True)
    submit.add_argument('--key', required=True)
    for name in ('work-once', 'request-status', 'cancel', 'reconcile'):
        command = commands.add_parser(name)
        command.add_argument('--queue', type=Path, required=True)
        if name != 'cancel':
            command.add_argument('--runs', type=Path, required=True)
        if name != 'work-once':
            command.add_argument('request_id')
            command.add_argument('--owner', required=True)
    submit.add_argument('--queue', type=Path, required=True)
    submit.add_argument('--owner', required=True)
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
    elif args.command == 'result':
        response = read_result(args.run_path)
    else:
        from .requests import RequestStore
        from .worker import reconcile, request_status, run_once, submit_request
        store = RequestStore(args.queue)
        if args.command == 'submit':
            response = submit_request(store, args.owner, args.key, {
                'target': args.target, 'date_gpst': args.date_gpst,
                'prior_access': args.prior_access, 'profile': 'gps-code-network-v1',
            }, args.implementation)
        elif args.command == 'work-once':
            response = run_once(store, args.runs)
        elif args.command == 'request-status':
            response = request_status(store, args.owner, args.request_id, args.runs)
        elif args.command == 'reconcile':
            response = reconcile(store, args.owner, args.request_id, args.runs)
        else:
            store.cancel(args.owner, args.request_id)
            response = store.get(args.owner, args.request_id)
    print(json.dumps(response, indent=2, ensure_ascii=False, allow_nan=False))
    if response.get('state') in ('FAILED', 'NEEDS_REVIEW'):
        return 1
    return 2 if response.get('status') in ('INVALID_REQUEST', 'UNSUPPORTED_REQUEST', 'DAY_NOT_COMPLETE',
                                         'PREVIOUSLY_ACCESSED_EVENT') else 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
