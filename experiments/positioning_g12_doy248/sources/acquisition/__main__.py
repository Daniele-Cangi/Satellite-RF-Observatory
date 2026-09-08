"""Portable stage commands: python -m positioning acquire|estimate|verify."""
import argparse
import json
from pathlib import Path
import sys


def deny_network(event, args):
    if event.startswith('socket.') or event in ('subprocess.Popen','os.system'):
        raise PermissionError('estimation stage is offline; network/subprocess access denied')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='stage',required=True)
    a=commands.add_parser('acquire');a.add_argument('plan',type=Path);a.add_argument('run',type=Path)
    for name in ['estimate','verify']:
        p=commands.add_parser(name);p.add_argument('run',type=Path)
    args=parser.parse_args()
    if args.stage=='acquire':
        from .acquisition import acquire
        result=acquire(args.plan,args.run)
    elif args.stage=='estimate':
        from .estimation import estimate
        sys.addaudithook(deny_network)
        result=estimate(args.run)
    else:
        from .verification import verify
        result=verify(args.run)
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':
    main()
