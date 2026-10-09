"""Repair a verified, untouched entry stub from explicit saved launch settings.

No device input. Does not erase pending inputs or infer authorization from a frame.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from maalimbus.grace_transaction import GraceTransaction
from maalimbus.grace_vision import available_starlight, observed_board
from maalimbus.vision import Text
from maalimbus.storage import read_json, write_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frame',type=Path,required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    frame=args.frame.resolve();frame.relative_to((ROOT/'evidence/runtime').resolve())
    png=frame.with_suffix('.png');record=read_json(frame)
    digest=hashlib.sha256(png.read_bytes()).hexdigest()
    if record.get('scene')!='STAR_GRACES' or digest!=record.get('image_sha256'):
        raise ValueError('Current STAR frame/hash required')
    ledger_path=ROOT/'config/user-run-ledger.json';ledger=read_json(ledger_path)
    active=ledger.get('active')
    if not active or active.get('phase')!='entered' or active.get('floors'):
        raise ValueError('Actual untouched entered run required')
    config_path=ROOT/'config/user-launch.json';settings=read_json(config_path)
    choices=[int(n) for n in settings['graces'].split(',') if n]
    budget=settings['grace_budget']
    records=[Text(t['text'],tuple(t['box']),t['score']) for t in record['ocr']]
    available=available_starlight(records,tuple(record['size']))
    import cv2
    board=observed_board(cv2.imread(str(png)),records,choices)
    if available is None or board is None or sum(board['costs'][n-1] for n in choices)>min(budget,available):
        raise ValueError('Current configured costs/balance/budget not proven')
    path=ROOT/'config/user-grace-transaction.json';transaction=GraceTransaction(path)
    original=path.read_bytes();ledger_hash=hashlib.sha256(ledger_path.read_bytes()).hexdigest()
    proof=dict(scope=active['id'],page='STAR_GRACES',frame=str(frame),frame_sha256=digest,
               configuration=str(config_path),configuration_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest())
    report=dict(scope=active['id'],team=active['team'],choices=choices,budget=budget,
                available=available,current_costs=board['costs'],proof=proof,
                original_transaction_sha256=hashlib.sha256(original).hexdigest(),
                ledger_sha256=ledger_hash,device_input=False,applied=False)
    if args.apply:
        backup=ROOT/'build'/('star-entry-stub-backup-'+uuid.uuid4().hex+'.json')
        backup.write_bytes(original)
        transaction.adopt_unspent_entry_settings(active['id'],choices,budget,available,proof)
        assert hashlib.sha256(ledger_path.read_bytes()).hexdigest()==ledger_hash
        report.update(applied=True,backup=str(backup),selected=transaction.data['selected'],spent=transaction.data['spent'])
    write_json(ROOT/'build/star-entry-settings-adoption.json',report)
    print(json.dumps(report))


if __name__=='__main__':main()
