import json
from pathlib import Path
import cv2
import pytest
from maalimbus.floor_gifts import observe
from maalimbus.floor_gift_transaction import FloorGiftTransaction
from maalimbus.gift_vision import GiftCatalog
from maalimbus.vision import Text
from maalimbus.window import plan_step

ROOT=Path(__file__).resolve().parents[1]
FRAME=ROOT/'evidence/runtime/window-20261008-140541/frame-0290.json'

def offer(remove_owned=False):
    data=json.loads(FRAME.read_text())
    records=[Text(t['text'],tuple(t['box']),t['score']) for t in data['ocr']
             if not(remove_owned and t['text']=='Owned')]
    return observe(records,data['size'],GiftCatalog(ROOT/'assets/resource/base'),
        image=cv2.imread(str(FRAME.with_suffix('.png'))),select_box=(1620,851,100,36))

def test_actual_owned_label_and_absent_label():
    offers,count=offer()
    assert count==dict(chosen=0,required=1) and offers[0].owned
    assert not offer(True)[0][0].owned

def test_refusal_is_durable_and_unknown_cannot_repeat(tmp_path):
    offers,count=offer();tx=FloorGiftTransaction(tmp_path/'tx.json')
    tx.prepare('run',offers,count,FRAME);tx.refuse_owned(offers,count,FRAME)
    with pytest.raises(ValueError):tx.observe_refusal('UNKNOWN',FRAME)
    tx=FloorGiftTransaction(tx.path)
    assert tx.data['pending']['kind']=='refuse_owned'
    with pytest.raises(ValueError):tx.refuse_owned(offers,count,FRAME)
    tx.observe_refusal('MAP',FRAME,map_floor=5)
    assert tx.data['completed'] and not tx.data['receipts'] and not tx.data['selected']

def test_missing_owned_does_not_authorize_refusal(tmp_path):
    offers,count=offer(True);tx=FloorGiftTransaction(tmp_path/'tx.json')
    tx.prepare('run',offers,count,FRAME)
    with pytest.raises(ValueError):tx.refuse_owned(offers,count,FRAME)

@pytest.mark.parametrize('page,floor',[('MAP',None),('GIFT_GET',5),('GIFT_WARNING',5)])
def test_unproven_successor_preserves_pending(tmp_path,page,floor):
    offers,count=offer();tx=FloorGiftTransaction(tmp_path/'tx.json')
    tx.prepare('run',offers,count,FRAME);tx.refuse_owned(offers,count,FRAME)
    with pytest.raises(ValueError):tx.observe_refusal(page,FRAME,map_floor=floor)
    assert tx.data['pending'] and not tx.data['completed']

def test_planner_narrow_refusal_exception():
    box=[1348,851,152,34]
    plan=plan_step('GIFT_PICK',controls={'gift_pick.refuse_button':box},
        gift=dict(refuse_owned=True,refuse_target=box))
    assert plan['action']=='click' and plan['target']==box

def test_confirmation_requires_exact_question_and_both_controls(tmp_path):
    from maalimbus.floor_gift_transaction import refusal_confirm_target
    data=json.loads((ROOT/'evidence/runtime/window-20261008-144025/frame-0002.json').read_text())
    assert refusal_confirm_target(data)==[1114,722,112,34]
    for text in ('Continue without choosing an E.G.O Gift?','X Cancel','Confirm'):
        changed=dict(data,ocr=[t for t in data['ocr'] if t['text']!=text])
        assert refusal_confirm_target(changed) is None
    offers,count=offer();tx=FloorGiftTransaction(tmp_path/'tx.json')
    tx.prepare('run',offers,count,FRAME);tx.refuse_owned(offers,count,FRAME)
    tx.refusal_confirm_intent('run',FRAME)
    with pytest.raises(ValueError):FloorGiftTransaction(tx.path).refusal_confirm_intent('run',FRAME)
