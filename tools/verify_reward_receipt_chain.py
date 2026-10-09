"""Audit a scoped reward receipt chain without controller input or state writes."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from maalimbus.reward_receipt_audit import verify
from maalimbus.storage import read_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--transaction',type=Path,required=True)
    parser.add_argument('--home',type=Path,required=True)
    for action in ('claim','confirm','receipt','pass'):
        parser.add_argument('--'+action+'-report',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    # Never overwrite transaction, input evidence, or any other private settings.
    output=args.output.resolve()
    if not output.is_relative_to((ROOT/'build').resolve()) or output.is_symlink():
        raise ValueError('Audit output must stay in the build directory')
    before=args.transaction.read_bytes()
    transaction=read_json(args.transaction)
    protected=[args.transaction,args.home,args.home.with_suffix('.png')]
    protected += [getattr(args,action+'_report') for action in ('claim','confirm','receipt','pass')]
    for key in ('claim_proof','confirm_proof','receipt_proof','pass_receipt_proof'):
        path=Path(transaction[key]);protected.extend((path,path.with_suffix('.png')))
    if output in {path.resolve() for path in protected}:
        raise ValueError('Audit cannot overwrite its source evidence')
    proof=verify(transaction,args.home,
        {action:read_json(getattr(args,action+'_report')) for action in ('claim','confirm','receipt','pass')})
    if before!=args.transaction.read_bytes():
        raise ValueError('Transaction changed during read-only audit')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(passed=True,output=str(output),state_written=False,game_input=False)))


if __name__=='__main__':main()
