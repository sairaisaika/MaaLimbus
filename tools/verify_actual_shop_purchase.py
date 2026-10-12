"""Read-only audit of the two installed GUI runs that settle Devil's Share."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from maalimbus.storage import read_json,write_json
from maalimbus.shop_transaction import ShopTransaction,_verify,_coins,_shelf,_notice
from maalimbus.shop_vision import matching_purchase_question
tx=ShopTransaction(ROOT/'config/user-shop-f855ac82c2b1429aae9c747a122213b8.json')
receipt=[r for r in tx.data['bought'] if r['name']=="Devil's Share"]
assert len(receipt)==1;receipt=receipt[0]
before,btexts,bsize=_verify(receipt['before']);after,atexts,asize=_verify(receipt['successor'])
question,qtexts,qsize=_verify(receipt['question'])
assert receipt['price']==144 and _coins(btexts,bsize)==2707 and _coins(atexts,asize)==2563
assert matching_purchase_question(qtexts,"Devil's Share",144,qsize,coins=2707)
own=[r for r in _shelf(atexts,asize) if r['name']=="Devil's Share"]
assert len(own)==1 and own[0].get('purchased')
notice=receipt['overlay_acknowledgement'];nrecord,ntexts,nsize=_verify(notice['frame'])
assert _notice(ntexts,nrecord)['target']==notice['target']
first=ROOT/'dist/MaaLimbus/evidence/runtime/pi-20261012-173651/events.jsonl'
resume=ROOT/'dist/MaaLimbus/evidence/runtime/pi-20261012-174217/events.jsonl'
events=lambda path:[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
a,b=events(first),events(resume)
purchase_reason='confirming_the_purchase_the_shop_asked_about'
get_reason='the_gift_get_notice_is_cleared_with_its_own_confirm'
assert sum(e.get('event')=='window_intent' and e.get('reason')==purchase_reason for e in a)==1
assert sum(e.get('event')=='window_intent' and e.get('reason')==get_reason for e in a)==1
assert not any(e.get('event')=='window_intent' and e.get('reason') in (purchase_reason,get_reason) for e in b)
assert any(e.get('event')=='shop_receipt_verified' and e.get('kind')=='purchase' for e in b)
write_json(ROOT/'build/actual-shop-purchase-real-verification.json',dict(passed=True,
    scope=tx.data['scope'],gift="Devil's Share",price=144,coins_before=2707,coins_after=2563,
    purchased_badge_verified=True,gui_start_executed=True,purchase_inputs=1,get_inputs=1,
    resumed_paid_inputs=0,purchase_receipt_completed=True,proofs=dict(before=receipt['before'],
    question=receipt['question'],notice=notice['frame'],successor=receipt['successor']),
    full_five_floor_clear=False,device_input=False))
print('passed: actual GUI purchase/GET/shelf chain; no audit input')
