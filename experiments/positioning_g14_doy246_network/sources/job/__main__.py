"""Historical GPS requests, isolated stages and portable evidence dossiers."""
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
    p=commands.add_parser('plan');p.add_argument('target');p.add_argument('date_gpst');p.add_argument('output',type=Path)
    group=p.add_mutually_exclusive_group();group.add_argument('--fit',nargs='+');group.add_argument('--pool',nargs='+')
    p.add_argument('--withheld',default='GOLD00USA')
    p.add_argument('--prior-access',required=True)
    p=commands.add_parser('run');p.add_argument('plan',type=Path);p.add_argument('run',type=Path)
    for name in ('status','dossier'):
        p=commands.add_parser(name);p.add_argument('run',type=Path)
    a=commands.add_parser('acquire');a.add_argument('plan',type=Path);a.add_argument('run',type=Path)
    a=commands.add_parser('availability');a.add_argument('plan',type=Path);a.add_argument('run',type=Path)
    for name in ['estimate','verify']:
        p=commands.add_parser(name);p.add_argument('run',type=Path)
    args=parser.parse_args()
    if args.stage=='plan':
        from datetime import date, datetime, timezone
        from .plans import make_plan, make_network_plan
        from .acquisition import write_json
        if date.fromisoformat(args.date_gpst) >= datetime.now(timezone.utc).date():
            parser.error('choose a completed historical day; product availability is checked during acquisition')
        if args.pool:
            result=make_network_plan(args.target,args.date_gpst,args.pool,args.withheld,args.prior_access)
        else:
            result=make_plan(args.target,args.date_gpst,args.fit,args.withheld,args.prior_access)
        write_json(args.output,result,exclusive=True)
        result={'status':'PLAN_CREATED_NO_DATA_ACCESSED','path':str(args.output)}
    elif args.stage=='run':
        from .jobs import execute
        result=execute(args.plan,args.run)
    elif args.stage=='status':
        from .jobs import status
        result=status(args.run)
    elif args.stage=='dossier':
        from .jobs import dossier
        document=dossier(args.run)
        result={'status':document['status'],'path':str(args.run/'dossier.json')}
    else:
        result=run_stage(args.stage,args)
    print(json.dumps(result,indent=2),flush=True)
    if result.get('state')=='FAILED':
        raise SystemExit(1)


def run_stage(stage,args):
    from urllib.error import URLError
    from .qualification import QualificationError
    from .acquisition import write_json, utc_now
    from .errors import ScientificRejection
    try:
        return scientific_stage(stage,args)
    except (ScientificRejection, QualificationError, URLError, TimeoutError) as error:
        if isinstance(error,ScientificRejection):
            label=error.status
        elif isinstance(error,QualificationError):
            label='SOURCE_OR_MEASUREMENT_NOT_QUALIFIED'
        else:
            label='SOURCE_UNAVAILABLE'
        # Only known scientific/source failures become terminal scientific records.
        # Unexpected exceptions retain their traceback and fail the job instead.
        result={'status':label,'primary_pass':False,'stage':stage,'reason':str(error),
                'closed_utc':utc_now(),'oracle_access_attempted':(args.run/'oracle_request.json').exists(),
                'oracle_accessed':(args.run/'oracle_access.json').exists(),
                'heldout_revealed':(args.run/'heldout_reveal.json').exists()}
        write_json(args.run/'outcome.json',result,exclusive=True)
        return result


def scientific_stage(stage,args):
    if stage in ('acquire','availability'):
        from .acquisition import acquire
        return acquire(args.plan,args.run,availability_only=stage=='availability')
    elif stage=='estimate':
        from .estimation import estimate
        sys.addaudithook(deny_network)
        return estimate(args.run)
    else:
        from .verification import verify
        return verify(args.run)


if __name__=='__main__':
    main()
