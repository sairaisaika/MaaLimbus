import json
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from maalimbus.gift_vision import GiftCatalog,floor_candidates,recommend
from maalimbus.policies import Team
from maalimbus.vision import Text,classify

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def catalog():
    return GiftCatalog(ROOT/'assets/resource/base')


def words(locale='en'):
    return json.loads((ROOT/f'assets/resource/{locale}/locale.json').read_text(encoding='utf-8'))


def records():
    return [Text('Acquire E.G.O Gift',(180,120,160,25),.99),
            Text('Owned',(110,120,55,25),.99),Text('Bloody Mist',(160,185,180,25),.99),
            Text('Acquire E.G.O Gift',(540,120,160,25),.99),
            Text('Ardent Flower',(530,185,180,25),.99),
            Text('Confirm',(1080,580,100,35),.99)]


def test_catalog_hashes_names_keywords_and_fuzzy_ambiguity(catalog):
    assert len(catalog.entries)==332
    assert catalog.entries['Bloody Mist']['keywords']==['Bleed']
    assert catalog.text_identity('BloodyMist')=='Bloody Mist'
    assert catalog.text_identity('unidentified reward title') is None
    assert catalog.text_identity('A Dream') is None


def test_column_ownership_rank_and_blocked_gift(catalog):
    frame=np.zeros((720,1280,3),np.uint8)
    candidates=floor_candidates(frame,records(),words(),catalog)
    assert [(c.gift.name,c.gift.owned) for c in candidates]==[('Bloody Mist',True),('Ardent Flower',False)]
    target,ranking=recommend(candidates,Team(1,frozenset({'Bleed'})))
    assert target.gift.name=='Ardent Flower' # Unowned beats owned preferred.
    target,_=recommend(candidates,Team(1,frozenset({'Burn'}),block=frozenset({'Ardent Flower'})))
    assert target.gift.name=='Bloody Mist'
    assert recommend(candidates,Team(1,frozenset(),block=frozenset({'Bloody Mist','Ardent Flower'})))==(None,[])


def test_scene_requires_reward_strip_and_confirm_and_paid_veto():
    assert classify(records(),words(),(1280,720))=='FLOOR_GIFTS'
    assert classify(records()[:-1],words(),(1280,720))=='UNKNOWN'
    assert classify(records()+[Text('Purchase Lunacy',(400,300,200,40),.99)],words(),(1280,720))=='RESOURCE_DIALOG'
    jp=records()
    jp[0]=Text('E.G.O ギフト獲得',jp[0].box,.99)
    jp[-1]=Text('確定',jp[-1].box,.99)
    assert classify(jp,words('jp'),(1280,720))=='FLOOR_GIFTS'


def test_conflicting_names_and_duplicate_columns_are_refused(catalog):
    frame=np.zeros((720,1280,3),np.uint8)
    duplicate=records()+[records()[0]]
    assert floor_candidates(frame,duplicate,words(),catalog)==[]
    conflicting=records()+[Text('Homeward',(170,200,170,20),.99)]
    assert [c.gift.name for c in floor_candidates(frame,conflicting,words(),catalog)]==['Ardent Flower']


def test_locale_independent_icon_survives_changed_background(catalog):
    icon=next(icon for name,icon in catalog.icons if name=='Bloody Mist')
    # Public source icon embedded in derived frames; no real gift selection assertion.
    limited=SimpleNamespace(entries=catalog.entries,text_identity=catalog.text_identity,
        icon_identity=lambda crop,width: catalog.icon_identity(crop,width))
    frame=np.full((720,1280,3),(30,50,20),np.uint8)
    frame[280:280+icon.shape[0],220:220+icon.shape[1]]=icon
    no_names=[r for r in records() if r.text not in ('Bloody Mist','Ardent Flower')]
    result=floor_candidates(frame,no_names,words(),limited)
    assert [(c.gift.name,c.evidence) for c in result]==[('Bloody Mist','icon')]
    frame[280:350,220:290]=0
    assert floor_candidates(frame,no_names,words(),catalog)==[]
