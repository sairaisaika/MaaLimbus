"""One bounded GitHub check; cached retry deadline survives the next invocation."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from maalimbus.releases import ReleaseClient


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--proxy')
    args=parser.parse_args()
    result=ReleaseClient(ROOT/'config/user-update-state.json',proxy=args.proxy).check()
    release=result.pop('release',None)
    if release is not None: result['version']=release.get('tag_name')
    print(json.dumps(result,indent=2))


if __name__=='__main__': main()
