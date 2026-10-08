import json
from pathlib import Path
import pytest
from maalimbus.floor_gifts import observe,rank
from maalimbus.gift_vision import GiftCatalog
from maalimbus.policies import Team
from maalimbus.vision import Text

ROOT=Path(__file__).resolve().parents[1]
FRAME=ROOT/'evidence/runtime/window-20261008-113601/frame-0136.json'


def fixture():
    data=json.loads(FRAME.read_text())
    return [Text(r['text'],tuple(r['box']),r['score']) for r in data['ocr']],GiftCatalog(ROOT/'assets/resource/base')


def test_complete_fourth_floor_trials_keep_all_three_components():
    records,catalog=fixture();offers,count=observe(records,(1920,1080),catalog)
    assert count==dict(chosen=0,required=2)
    assert offers[0].trial.components==(('clash_power',1),('hp',15))
    assert offers[3].trial.components==(('offense',2),('defense',3),('hp',10))
    ranking=rank(offers,Team(2,frozenset({'Charge','Tremor'})),[])
    assert [r['title'] for r in ranking[:2]]==['Pre-order Discount','Illusory Hunt']
    assert [r['score'] for r in ranking]==[90,280,315,565]


@pytest.mark.parametrize('text',['Coin Power +1, Max HP','Clash Power, Max HP','Clash Power +1.5, Max HP'])
def test_unknown_or_incomplete_power_cannot_be_skipped(text):
    records,catalog=fixture()
    changed=[Text(text,r.box,r.score) if r.text=='Clash Power +1, Max HP' else r for r in records]
    with pytest.raises(ValueError):observe(changed,(1920,1080),catalog)


def test_unknown_third_component_stops():
    records,catalog=fixture()
    changed=[Text('Defense Level +3, Unknown +10',r.box,r.score)
             if r.text=='Defense Level +3, Max HP' else r for r in records]
    with pytest.raises(ValueError):observe(changed,(1920,1080),catalog)

