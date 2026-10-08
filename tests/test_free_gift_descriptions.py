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
FRAME=ROOT/'evidence/runtime/window-20261008-120756/frame-0005.json'


def fixture():
    data=json.loads(FRAME.read_text())
    return [Text(r['text'],tuple(r['box']),r['score']) for r in data['ocr']],cv2.imread(str(FRAME.with_suffix('.png'))),GiftCatalog(ROOT/'assets/resource/base')


def read(records,image,catalog):
    return observe(records,(1920,1080),catalog,image=image,select_box=(1620,851,100,36))


def test_known_descriptions_are_free_and_healing_is_bounded():
    offers,count=read(*fixture())
    assert count==dict(chosen=0,required=1)
    ranked=rank(offers,Team(2,frozenset({'Charge','Tremor'})),[])
    assert ranked[0]['title']=='First-aid Kit' and ranked[0]['visible_benefit']==25


@pytest.mark.parametrize('text,box', [('Cost 10 Modules',(440,500,200,25)),('Max HP +10%',(440,700,200,25)),('Shop Skill Replacement Cost',(440,700,258,26))])
def test_actual_cost_or_trial_never_inherits_description_exemption(text,box):
    records,image,catalog=fixture()
    with pytest.raises(ValueError):read(records+[Text(text,box,.99)],image,catalog)


def test_missing_description_owner_title_stops():
    records,image,catalog=fixture()
    with pytest.raises(ValueError):read([r for r in records if r.text!='Trial Plan Guide'],image,catalog)


def test_incomplete_healing_has_no_bonus():
    records,image,catalog=fixture()
    offers,_=read([r for r in records if r.text!='activate if the ally is dead)'],image,catalog)
    assert offers[2].visible_benefit==0
