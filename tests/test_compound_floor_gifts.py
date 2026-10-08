import json
from pathlib import Path
import pytest
from maalimbus.floor_gifts import observe, rank
from maalimbus.gift_vision import GiftCatalog
from maalimbus.policies import Team
from maalimbus.vision import Text

ROOT=Path(__file__).resolve().parents[1]
FRAME=ROOT/'evidence/runtime/window-20261008-091754/frame-0178.json'


def fixture():
    data=json.loads(FRAME.read_text())
    return [Text(r['text'],tuple(r['box']),r['score']) for r in data['ocr']],GiftCatalog(ROOT/'assets/resource/base')


def test_real_four_columns_include_wrapped_and_decimal_effects():
    records,catalog=fixture();offers,count=observe(records,(1920,1080),catalog)
    assert count==dict(chosen=0,required=2)
    assert [o.trial.penalty for o in offers]==[155,55,240,202.5]
    assert offers[0].trial.components==(('offense',1),('hp',5))
    assert offers[3].trial.components==(('damage_reduction',7.5),('damage_dealt',7.5))
    ranking=rank(offers,Team(2,frozenset({'Charge','Tremor'})),[])
    assert [r['title'] for r in ranking[:2]]==['Blood, Sweat, and Tears',"Tomorrow's Fortune"]
    assert offers[2].title=='Patrolling Flashlight'


@pytest.mark.parametrize('text',['+5%','Damage Dealt +7.5%','Mounting Trials','0/2'])
def test_partial_trial_or_missing_anchor_refuses(text):
    records,catalog=fixture()
    with pytest.raises(ValueError):observe([r for r in records if r.text!=text],(1920,1080),catalog)


def test_unknown_component_and_wrong_column_never_discarded():
    records,catalog=fixture()
    changed=[Text('Coin Power +7.5%',r.box,r.score) if r.text=='Damage Dealt +7.5%' else r for r in records]
    with pytest.raises(ValueError):observe(changed,(1920,1080),catalog)
    wrong=[Text(r.text,(1068,754,222,36),r.score) if r.text=='Damage Dealt +7.5%' else r for r in records]
    with pytest.raises(ValueError):observe(wrong,(1920,1080),catalog)


def test_fresh_actual_ocr_without_comma_keeps_both_complete_effects():
    data=json.loads((ROOT/'evidence/runtime/window-20261008-093745/frame-0001.json').read_text())
    _,catalog=fixture()
    offers,_=observe([Text(r['text'],tuple(r['box']),r['score']) for r in data['ocr']],data['size'],catalog)
    assert offers[3].trial.components==(('damage_reduction',7.5),('damage_dealt',7.5))
