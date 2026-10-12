import json
from pathlib import Path
from types import SimpleNamespace
import cv2
from maalimbus.floor_trial_vision import repair_levels
from maalimbus.floor_gifts import observe
from maalimbus.vision import Text
from maalimbus.gift_vision import GiftCatalog

ROOT=Path(__file__).resolve().parents[1]
FRAME=ROOT/'evidence/runtime/packaged-mirror-20261012-043307/frame-0001.json'


def test_selected_actual_badge_requires_independent_agreement():
    d=json.loads(FRAME.read_text()); records=[Text(t['text'],tuple(t['box']),t['score']) for t in d['ocr']]
    image=cv2.imread(str(FRAME.with_suffix('.png')))
    def native(*args):
        return SimpleNamespace(hit=True,filtered_results=[SimpleNamespace(text='+1',score=.99)])
    repaired,proof=repair_levels(native,image,records)
    offers,count=observe(repaired,d['size'],GiftCatalog(ROOT/'assets/resource/base'))
    assert count==dict(chosen=1,required=2) and offers[0].trial.level==1
    assert len(proof)==2
    calls=[]
    def conflicting(*args):
        calls.append(1)
        return SimpleNamespace(hit=True,filtered_results=[SimpleNamespace(text='+1' if len(calls)==1 else '+2',score=.99)])
    unchanged,_=repair_levels(conflicting,image,records)
    assert unchanged==records
    absent,_=repair_levels(native,image,[r for r in records if r.text!='Mounting Trials'])
    assert absent==[r for r in records if r.text!='Mounting Trials']


def test_real_sent_pick_can_reconcile_without_repeating_input(tmp_path):
    from maalimbus.floor_gift_transaction import FloorGiftTransaction
    catalog=GiftCatalog(ROOT/'assets/resource/base')
    before=ROOT/'evidence/runtime/packaged-mirror-20261012-042756/frame-0001.json'
    old=json.loads(before.read_text())
    offers,count=observe([Text(t['text'],tuple(t['box']),t['score']) for t in old['ocr']],old['size'],catalog)
    tx=FloorGiftTransaction(tmp_path/'tx.json');tx.prepare('scope',offers,count,before);tx.intent('Oracle',count,before)
    d=json.loads(FRAME.read_text());records=[Text(t['text'],tuple(t['box']),t['score']) for t in d['ocr']]
    repaired,_=repair_levels(lambda *args:SimpleNamespace(hit=True,filtered_results=[SimpleNamespace(text='+1',score=.99)]),
        cv2.imread(str(FRAME.with_suffix('.png'))),records)
    after,acount=observe(repaired,d['size'],catalog)
    import pytest
    raw=tx.path.read_bytes()
    with pytest.raises(ValueError):tx.recover_pick('other',after,acount,FRAME,catalog)
    assert tx.path.read_bytes()==raw
    tx.recover_pick('scope',after,acount,FRAME,catalog)
    assert tx.data['selected']==['Oracle'] and tx.data['pending'] is None
