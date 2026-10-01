"""One bounded GitHub check; cached retry deadline survives the next invocation."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from maalimbus.releases import ReleaseClient
from maalimbus.update_stage import stage_release, StageError


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proxy')
    parser.add_argument('--stage', action='store_true', help='Stage and validate a Windows update; do not install')
    parser.add_argument('--timeout', type=int, default=120)
    args=parser.parse_args()
    result=ReleaseClient(ROOT/'config/user-update-state.json',proxy=args.proxy).check()
    release=result.pop('release',None)
    if release is not None: result['version']=release.get('tag_name')
    if args.stage:
        if release is None or result['status'] not in ('available','cached'):
            result['stage']={'status':'deferred','installed':False,'retry_at':result['retry_at']}
        else:
            try:
                result['stage']=stage_release(release, ROOT/'build/updates', proxy=args.proxy,
                    timeout=args.timeout, cache=ROOT/'config/user-update-state.json')
            except StageError:
                result['stage']={'status':'failed','reason':'release_assets_invalid','installed':False}
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
