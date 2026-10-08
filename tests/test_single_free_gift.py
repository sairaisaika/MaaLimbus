import json
from pathlib import Path

import cv2
import pytest

from maalimbus.floor_gifts import observe, rank
from maalimbus.floor_gift_transaction import FloorGiftTransaction
from maalimbus.gift_vision import GiftCatalog
from maalimbus.policies import Team
from maalimbus.vision import Text

ROOT = Path(__file__).resolve().parents[1]
FRAME = ROOT/'evidence/runtime/window-20261008-084911/frame-0167'
BUTTON = (1620,851,100,36)


@pytest.fixture
def fixture():
    data = json.loads(FRAME.with_suffix('.json').read_text())
    return ([Text(r['text'],tuple(r['box']),r['score']) for r in data['ocr']],
            cv2.imread(str(FRAME.with_suffix('.png'))),GiftCatalog(ROOT/'assets/resource/base'))


def read(fixture):
    records,image,catalog = fixture
    return observe(records,(1920,1080),catalog,image=image,select_box=BUTTON)


def test_real_single_charge_gift_is_unselected_and_has_no_enemy_trial(fixture):
    offers,count = read(fixture)
    assert count == dict(chosen=0,required=1)
    assert offers[0].title == 'Lightning Rod' and offers[0].trial.penalty == 0
    assert offers[0].selection_source == 'single_free_select_button'
    assert rank(offers,Team(2,frozenset({'Charge','Tremor'})),[])[0]['preferred']


@pytest.mark.parametrize('missing',['Lightning Rod','Acquire E.G.O Gift','Select','Refuse Gift'])
def test_missing_single_gift_anchor_stops(fixture,missing):
    records,image,catalog=fixture
    with pytest.raises(ValueError):read(([r for r in records if r.text!=missing],image,catalog))


@pytest.mark.parametrize('added',['Mounting Trials','Enemy Level +2','Cost 10 Modules'])
def test_missing_counter_never_discards_trials_or_payment(fixture,added):
    records,image,catalog=fixture
    with pytest.raises(ValueError):read((records+[Text(added,(800,700,200,30),.99)],image,catalog))


def test_no_image_or_ambiguous_button_stops(fixture):
    records,image,catalog=fixture
    with pytest.raises(ValueError):read((records,None,catalog))
    image[851:887,1620:1720]=40
    with pytest.raises(ValueError,match='ambiguous'):read(fixture)


def test_transition_is_scoped_durable_and_does_not_claim_receipt(fixture,tmp_path):
    offers,count=read(fixture)
    tx=FloorGiftTransaction(tmp_path/'transaction.json')
    tx.prepare('scope',offers,count,'actual-before')
    tx.intent('Lightning Rod',count,'actual-before')
    with pytest.raises(ValueError):tx.observe_pick(offers,count,'unchanged')
    # Retained actual selected frame proves selection, not acquisition.
    selected=cv2.imread(str(ROOT/'evidence/runtime/window-20261008-091114/frame-0002.png'))
    data=json.loads((ROOT/'evidence/runtime/window-20261008-091114/frame-0002.json').read_text())
    records=[Text(r['text'],tuple(r['box']),r['score']) for r in data['ocr']]
    after,count=read((records,selected,fixture[2]))
    tx.observe_pick(after,count,'synthetic-lit')
    tx.commit('synthetic-commit')
    with pytest.raises(ValueError):tx.receipt_intent('Golden Urn','wrong')
    assert not tx.data['completed'] and tx.data['receipts']==[]
    with pytest.raises(ValueError):tx.prepare('scope',after,count,'repeat')


def test_button_and_all_four_outline_segments_must_agree(fixture):
    records,image,catalog=fixture
    image[851:887,1620:1720]=75
    with pytest.raises(ValueError):read(fixture)
    selected=cv2.imread(str(ROOT/'evidence/runtime/window-20261008-091114/frame-0002.png'))
    selected[250:810,760:772]=0
    with pytest.raises(ValueError):read((records,selected,catalog))
