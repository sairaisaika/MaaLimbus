"""Reconcile this retained refusal and confirmation, never send device input."""
import json,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from maalimbus.floor_gift_transaction import FloorGiftTransaction,refusal_confirm_target
from maalimbus.runner import unselected_reward_successor

def main():
    tx=FloorGiftTransaction(ROOT/'config/user-floor-gift-transaction.json')
    pending=tx.data['pending'];assert pending['kind']=='refuse_owned' and pending['confirm_sent']
    scope=json.loads((ROOT/'config/user-run-ledger.json').read_text())['active']['id']
    assert tx.data['scope']==scope
    inputs=[]
    for name,reason,key in (
        ('floor-five-owned-gift-refuse-live-20261008','refuse_proven_owned_single_free_gift','proof'),
        ('floor-five-owned-refusal-confirm-live-20261008','confirm_proven_owned_gift_refusal','confirm_proof')):
        result=json.loads((ROOT/f'build/{name}.json').read_text());step=result['steps'][-1]
        assert result['run_ledger']['run']==scope and result['clicks_sent']==step['clicks_sent']==1
        assert step['plan']['reason']==reason
        proof=Path(pending[key]);before=json.loads(proof.read_text())
        assert before['image_sha256']==step['observation']['image_sha256']
        assert hashlib.sha256(proof.with_suffix('.png').read_bytes()).hexdigest()==before['image_sha256']
        x,y,w,h=step['plan']['target'];px,py=step['click_point'];assert x<=px<x+w and y<=py<y+h
        if key=='confirm_proof':assert refusal_confirm_target(before)==step['plan']['target']
        inputs.append(dict(report=name,proof=str(proof),sha256=before['image_sha256']))
    report=json.loads((ROOT/'build/floor-five-after-owned-refusal-readonly-20261008.json').read_text())
    assert report['clicks_sent']==0 and report['run_ledger']['run']==scope
    assert report['observed']['page']=='REWARD_CARD'
    directories=sorted((ROOT/'evidence/runtime').glob('window-*'),key=lambda p:p.stat().st_mtime,reverse=True)
    matches=[]
    for directory in directories[:8]:
        path=directory/'frame-0001.json'
        if path.exists():
            data=json.loads(path.read_text())
            if data['image_sha256']==report['observed']['sha256']:matches.append((path,data))
    assert len(matches)==1
    path,data=matches[0]
    assert hashlib.sha256(path.with_suffix('.png').read_bytes()).hexdigest()==data['image_sha256']
    next_offer=unselected_reward_successor(data);assert next_offer
    tx.observe_refusal('REWARD_CARD',path,next_reward_offer=next_offer)
    output=ROOT/'build/owned-refusal-real-verification-20261008.json'
    output.write_text(json.dumps(dict(scope=scope,inputs=inputs,successor=str(path),
        successor_sha256=data['image_sha256'],device_input=False,refusal_completed=True,
        floor_clear_verified=False),indent=2)+'\n');print(output)

if __name__=='__main__':main()
