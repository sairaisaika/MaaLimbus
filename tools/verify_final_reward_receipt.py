"""Reconcile actual acquired/pass receipts and independent HOME return, without input."""
import hashlib
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from maalimbus.storage import read_json,write_json,RunStore
from maalimbus.policies import Team
from maalimbus.vision import Text,find


def load_frame(path):
    path=Path(path)
    record=read_json(path)
    digest=hashlib.sha256(path.with_suffix('.png').read_bytes()).hexdigest()
    assert digest==record['image_sha256']
    return record,dict(frame=str(path),png_sha256=digest)


def gate(record,pattern,band):
    texts=[Text(t['text'],tuple(t['box']),t['score']) for t in record['ocr']]
    return len(find(texts,pattern,band,record['size'],.9))==1


def main():
    txpath=ROOT/'config/user-reward-claim-transaction.json'
    tx=read_json(txpath)
    assert tx['claim_sent'] and tx['confirm_sent'] and tx['receipt_ack_sent'] and tx['pass_ack_sent']
    assert not tx['completed'] and tx['reserved_modules']==6
    proofs=[]
    acquired,p=load_frame(tx['receipt_proof']);proofs.append(p)
    assert gate(acquired,r'^Rewards Acquired$',(.39,.30,.61,.39))
    assert gate(acquired,r'^250$',(.47,.48,.54,.56))
    bp,p=load_frame(tx['pass_receipt_proof']);proofs.append(p)
    assert gate(bp,r'^Pass Level Up$',(.40,.30,.61,.39))
    assert gate(bp,r'^Battle Pass XP$',(.39,.42,.57,.49))
    assert gate(bp,r'^81$',(.29,.45,.38,.57))
    homepath=ROOT/'evidence/runtime/window-20261008-172705/frame-0001.json'
    home,p=load_frame(homepath);proofs.append(p)
    assert home['scene']=='HOME'
    assert all(gate(home,pattern,band) for pattern,band in (
        (r'^Window$',(.60,.86,.69,.96)),(r'^Drive$',(.73,.86,.80,.96)),
        (r'^Sinners$',(.66,.86,.74,.96)),(r'^Inventory$',(.46,.90,.55,.97))))
    # Each existing input report belongs to this run and sent exactly one touch.
    for name in ('final-reward-authorized-claim-live','final-reward-authorized-confirm-live',
                 'final-reward-receipt-ack-live','final-pass-receipt-ack-live'):
        report=read_json(ROOT/f'build/{name}-20261008.json')
        assert report['run_ledger']['run']==tx['scope'] and report['clicks_sent']==1
        entry=report['steps'][0]
        assert entry['action']=='click'
        x,y,w,h=entry['target'];px,py=entry['click_point']
        assert x<=px<=x+w and y<=py<=y+h and 350<=entry['delay_ms']<=750
    ledgerpath=ROOT/'config/user-run-ledger.json'
    ledger=read_json(ledgerpath)
    assert ledger['active']['id']==tx['scope'] and ledger['active']['team']==2
    store=RunStore(ledgerpath,[Team(slot,frozenset()) for slot in ledger['team_slots']])
    store.record(tx['scope'],'real-reward-receipt-run','reward_received',tx['receipt_proof'])
    # HOME is a separately observed completed return, before choosing a new team.
    store.record(tx['scope'],'real-home-return-run','entry_returned',homepath)
    tx.update(completed=True,pending=None,reward_received=True,
              receipt_chain=proofs,home_return_proof=str(homepath),
              module_balance_delta_verified=False)
    write_json(txpath,tx)
    write_json(ROOT/'build/final-reward-real-verification-20261008.json',dict(
        scope=tx['scope'],team=2,proofs=proofs,payout_received=True,home_return_verified=True,
        saved_rotation=store.data['rotation'],next_saved_team=store.team_slot,
        next_team_visually_confirmed=False,reentry_verified=False,
        module_balance_delta_verified=False,game_input_sent=False))
    print('Actual acquired receipt, pass level81 and HOME return verified; saved next team',store.team_slot)


if __name__=='__main__':main()
