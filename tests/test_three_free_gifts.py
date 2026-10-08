import json
from pathlib import Path
import cv2
import pytest
from maalimbus.floor_gifts import observe,rank
from maalimbus.floor_gift_transaction import FloorGiftTransaction
from maalimbus.gift_vision import GiftCatalog
from maalimbus.policies import Team
from maalimbus.vision import Text

ROOT=Path(__file__).resolve().parents[1]
FRAME=ROOT/'evidence/runtime/window-20261008-100819/frame-0005.json'


def fixture():
    data=json.loads(FRAME.read_text())
    return [Text(r['text'],tuple(r['box']),r['score']) for r in data['ocr']],cv2.imread(str(FRAME.with_suffix('.png'))),GiftCatalog(ROOT/'assets/resource/base')


def read(records,image,catalog):
    return observe(records,(1920,1080),catalog,image=image,select_box=(1620,851,100,36))


def test_real_three_free_offer_has_no_trials_and_bounded_visible_benefit():
    offers,count=read(*fixture())
    assert count==dict(chosen=0,required=1)
    ranked=rank(offers,Team(2,frozenset({'Charge','Tremor'})),[])
    assert ranked[0]['title']=='Phantom Pain' and ranked[0]['visible_benefit']==15
    assert all(o.selection_source=='three_free_select_button' for o in offers)


@pytest.mark.parametrize('missing',['Phantom Pain','Refuse Gift','Select','Acquire E.G.O Gift'])
def test_missing_anchor_stops(missing):
    records,image,catalog=fixture()
    with pytest.raises(ValueError):read([r for r in records if r.text!=missing],image,catalog)


def test_bright_button_without_selection_outline_stops():
    records,image,catalog=fixture();image[851:887,1620:1720]=75
    with pytest.raises(ValueError):read(records,image,catalog)
    with pytest.raises(ValueError):read(records+[Text('Mounting Trials',(700,650,140,28),.99)],image,catalog)


def test_actual_selected_right_card_uses_visible_bottom_edge():
    path=ROOT/'evidence/runtime/window-20261008-101324/frame-0002.json'
    data=json.loads(path.read_text());records=[Text(r['text'],tuple(r['box']),r['score']) for r in data['ocr']]
    _,_,catalog=fixture();image=cv2.imread(str(path.with_suffix('.png')))
    offers,count=read(records,image,catalog)
    assert count==dict(chosen=1,required=1) and offers[2].title=='Phantom Pain'
    image[835:850,1180:1290]=0
    with pytest.raises(ValueError):read(records,image,catalog)


def test_unknown_gift_pick_never_completes_prior_receipt(tmp_path):
    offers,count=read(*fixture());tx=FloorGiftTransaction(tmp_path/'tx.json')
    tx.prepare('scope',offers,count,'offer')
    tx.intent('Phantom Pain',count,'intent')
    tx.observe_pick(offers,dict(chosen=1,required=1),'selection')
    tx.commit('commit');tx.receipt_intent('Phantom Pain','get')
    with pytest.raises(ValueError):tx.observe_receipt('GIFT_PICK',None,'unknown')
    assert tx.data['pending']['kind']=='receipt'
    tx.observe_receipt('GIFT_PICK',None,'proven-offer',next_free_offer=dict(count=count,
        source=offers[0].selection_source,offer=tx.signature(offers)))
    assert tx.data['completed'] and tx.data['pending'] is None
